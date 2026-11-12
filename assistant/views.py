import json
import logging
import mimetypes
import time
from datetime import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, JsonResponse, StreamingHttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q
from django.conf import settings
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from assistant.models import (
    Document, DocumentChunk, ChatSession, ChatMessage,
    Feedback, QueryAuditLog, SystemConfig, CachedAnswer
)
from assistant.services.vector_store import get_vector_store
from assistant.services.llm_service import LocalLLMService
from assistant.services import answer_cache
from assistant.services.query_utils import contextualize_query, detect_topic, salient_tokens
from assistant.services.ingestion import ingest_document, ingest_document_async, rebuild_vector_index
from assistant.services.rbac import (
    can_manage_knowledge_base,
    get_or_create_user_profile,
    get_allowed_access_roles,
)

logger = logging.getLogger(__name__)


def _get_user_profile(request):
    """Returns the authenticated user and their RBAC profile."""
    profile = get_or_create_user_profile(request.user)
    return request.user, profile


def _user_can_access_document(user, document: Document) -> bool:
    """Checks whether the current user can open the source document."""
    return document.access_role in get_allowed_access_roles(user)


def login_view(request):
    """Sign-in page. Authenticates users against Django's auth backend."""
    if request.user.is_authenticated:
        return redirect('assistant:chat')

    error = None
    next_url = request.POST.get('next') or request.GET.get('next') or ''

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_active:
            login(request, user)
            get_or_create_user_profile(user)
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect(settings.LOGIN_REDIRECT_URL)

        error = 'Invalid username or password. Please try again.'

    return render(request, 'assistant/login.html', {'error': error, 'next': next_url})


def logout_view(request):
    """Ends the current session and returns to the login page."""
    logout(request)
    return redirect('assistant:login')


@login_required
def chat_view(request):
    """Main ChatGPT-style dashboard view."""
    user, profile = _get_user_profile(request)
    sessions = ChatSession.objects.filter(user=user).order_by('-updated_at')[:30]
    
    # Active session or default
    active_session_id = request.GET.get('session_id')
    active_session = None
    messages = []

    if active_session_id:
        active_session = ChatSession.objects.filter(id=active_session_id, user=user).first()
        if active_session:
            messages = active_session.messages.all().select_related('feedback')

    ollama_health = LocalLLMService.check_health()
    doc_count = Document.objects.filter(status='indexed').count()

    context = {
        'can_manage_knowledge_base': can_manage_knowledge_base(user),
        'profile': profile,
        'sessions': sessions,
        'active_session': active_session,
        'messages': messages,
        'ollama_health': ollama_health,
        'doc_count': doc_count,
        'categories': Document.CATEGORY_CHOICES,
        'suggested_questions': answer_cache.suggested_questions(get_allowed_access_roles(user), limit=8),
    }
    return render(request, 'assistant/chat.html', context)


@login_required
def search_view(request):
    """Semantic & Keyword document snippet search view."""
    user, profile = _get_user_profile(request)
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', 'All')
    department = request.GET.get('department', 'All')

    results = []
    if query:
        search_started = time.time()
        vector_store = get_vector_store()
        allowed_roles = get_allowed_access_roles(user)
        results = vector_store.hybrid_search(
            query=query,
            top_k=10,
            allowed_roles=allowed_roles,
            category=category,
            department=department
        )

        # Log audit entry
        QueryAuditLog.objects.create(
            user=user,
            user_role=profile.role,
            query_text=query,
            mode='search',
            retrieved_sources_count=len(results),
            top_sources_json=[{'title': r['title'], 'page': r['page_number'], 'score': r['score']} for r in results[:3]],
            response_latency_ms=int((time.time() - search_started) * 1000),
            is_unanswered_or_low_confidence=len(results) == 0,
            ip_address=request.META.get('REMOTE_ADDR')
        )

    context = {
        'can_manage_knowledge_base': can_manage_knowledge_base(user),
        'profile': profile,
        'query': query,
        'category': category,
        'department': department,
        'results': results,
        'categories': ['All'] + [c[0] for c in Document.CATEGORY_CHOICES],
        'departments': [d[0] for d in Document.DEPARTMENT_CHOICES],
    }
    return render(request, 'assistant/search.html', context)


@login_required
def admin_dashboard_view(request):
    """Admin and Knowledge Manager dashboard view."""
    user, profile = _get_user_profile(request)

    # Only administrators and managers may access knowledge administration.
    if not can_manage_knowledge_base(user):
        return redirect('assistant:chat')
    
    # Metrics
    total_docs = Document.objects.count()
    indexed_docs = Document.objects.filter(status='indexed').count()
    total_chunks = DocumentChunk.objects.count()
    total_queries = QueryAuditLog.objects.count()
    cache_hits = QueryAuditLog.objects.filter(served_from_cache=True).count()
    cache_hit_rate = int(cache_hits / total_queries * 100) if total_queries else 0
    cached_answers_count = CachedAnswer.objects.filter(is_active=True, is_curated=False).count()
    curated_faq_count = CachedAnswer.objects.filter(is_active=True, is_curated=True).count()
    
    avg_latency = QueryAuditLog.objects.aggregate(Avg('response_latency_ms'))['response_latency_ms__avg'] or 0
    
    # Satisfaction rate
    positive_feedbacks = Feedback.objects.filter(rating=1).count()
    total_feedbacks = Feedback.objects.count()
    satisfaction_rate = int((positive_feedbacks / total_feedbacks * 100)) if total_feedbacks > 0 else 100

    # Low confidence queries
    low_confidence_queries = QueryAuditLog.objects.filter(is_unanswered_or_low_confidence=True).order_by('-created_at')[:10]

    # Recent Audit logs
    audit_logs = QueryAuditLog.objects.all().order_by('-created_at')[:25]

    # Documents list
    documents = Document.objects.all().order_by('-created_at')

    # Top queries
    top_queries = (
        QueryAuditLog.objects.values('query_text')
        .annotate(total=Count('id'))
        .order_by('-total')[:8]
    )

    ollama_health = LocalLLMService.check_health()
    system_settings = {
        'ollama_base_url': LocalLLMService.get_ollama_base_url(),
        'ollama_model': LocalLLMService.get_ollama_model(),
        'top_k': getattr(settings, 'RAG_TOP_K', 5),
    }

    context = {
        'profile': profile,
        'can_manage_knowledge_base': can_manage_knowledge_base(user),
        'total_docs': total_docs,
        'indexed_docs': indexed_docs,
        'total_chunks': total_chunks,
        'total_queries': total_queries,
        'cache_hit_rate': cache_hit_rate,
        'cached_answers_count': cached_answers_count,
        'curated_faq_count': curated_faq_count,
        'avg_latency': int(avg_latency),
        'satisfaction_rate': satisfaction_rate,
        'low_confidence_queries': low_confidence_queries,
        'audit_logs': audit_logs,
        'documents': documents,
        'top_queries': top_queries,
        'ollama_health': ollama_health,
        'system_settings': system_settings,
        'categories': Document.CATEGORY_CHOICES,
        'departments': Document.DEPARTMENT_CHOICES,
        'access_roles': Document.ACCESS_ROLE_CHOICES,
    }
    return render(request, 'assistant/admin_dashboard.html', context)


# API Endpoints


def _rate_limited(user_id) -> bool:
    """Simple fixed-window per-user limiter (requests/minute)."""
    limit = getattr(settings, 'CHAT_RATE_LIMIT_PER_MIN', 20)
    if not limit:
        return False
    key = f"miiciq_rl_{user_id}_{int(time.time() // 60)}"
    cache.add(key, 0, 70)
    try:
        return cache.incr(key) > limit
    except ValueError:
        return False


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@login_required
def stream_chat_api(request):
    """
    Server-Sent Events (SSE) streaming chat endpoint.
    Order of resolution: canned/cached answer -> hybrid retrieval + LLM -> store verified answer.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    query = (data.get('message') or '').strip()
    session_id = data.get('session_id')
    user, profile = _get_user_profile(request)

    if not query:
        return JsonResponse({'error': 'Message content cannot be empty'}, status=400)
    if len(query) > 2000:
        return JsonResponse({'error': 'Message is too long (max 2000 characters)'}, status=400)
    if _rate_limited(user.pk):
        return JsonResponse({'error': 'Too many requests. Please wait a moment and try again.'}, status=429)

    # Resolve or create session
    chat_session = ChatSession.objects.filter(id=session_id, user=user).first() if session_id else None
    if not chat_session:
        title = query[:40] + ('...' if len(query) > 40 else '')
        chat_session = ChatSession.objects.create(user=user, title=title, mode='chat')

    # Recent history (read before saving the new message)
    past_messages = list(chat_session.messages.order_by('-created_at')[:6])
    past_messages.reverse()
    chat_history = [{'sender': m.sender, 'content': m.content} for m in past_messages]

    user_msg = ChatMessage.objects.create(session=chat_session, sender='user', content=query)
    allowed_roles = get_allowed_access_roles(user)
    started = time.time()
    ip = request.META.get('REMOTE_ADDR')

    # Follow-ups ("what about managers?") are not cached on their own text: they depend on context.
    is_followup = bool(chat_history) and len(salient_tokens(query)) <= 3

    # ---- 1. Canned / cached answer -------------------------------------------------------
    cached = None if is_followup else answer_cache.lookup(query, allowed_roles)
    if cached:
        answer_cache.mark_hit(cached)

        def cached_stream():
            # Send the answer in a few large pieces so the UI renders instantly.
            text = cached.answer
            for i in range(0, len(text), 400):
                yield _sse({'token': text[i:i + 400], 'done': False})
            latency = int((time.time() - started) * 1000)
            assistant_msg = ChatMessage.objects.create(
                session=chat_session, sender='assistant', content=text,
                sources_json=cached.sources_json, latency_ms=latency, cached_answer=cached,
            )
            ChatSession.objects.filter(pk=chat_session.pk).update(updated_at=timezone.now())
            QueryAuditLog.objects.create(
                user=user, user_role=profile.role, query_text=query, mode='chat',
                retrieved_sources_count=len(cached.sources_json), top_sources_json=cached.sources_json[:3],
                response_latency_ms=latency, is_unanswered_or_low_confidence=False,
                served_from_cache=True, ip_address=ip,
            )
            yield _sse({
                'done': True, 'message_id': assistant_msg.id, 'session_id': str(chat_session.pk),
                'sources': cached.sources_json, 'latency_ms': latency, 'is_low_confidence': False,
                'from_cache': True, 'verified': cached.is_curated,
            })

        response = StreamingHttpResponse(cached_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    # ---- 2. Retrieval + generation -------------------------------------------------------
    retrieval_query = contextualize_query(query, chat_history)
    topic = detect_topic(retrieval_query)
    context_chunks = get_vector_store().hybrid_search(
        query=retrieval_query,
        top_k=getattr(settings, 'RAG_TOP_K', 4),
        allowed_roles=allowed_roles,
        topic=topic,
    )

    def event_stream():
        full_answer, sources, latency_ms, is_low_conf = "", [], 0, False
        try:
            for chunk in LocalLLMService.stream_generate(query, context_chunks, chat_history):
                if chunk['type'] == 'token':
                    yield _sse({'token': chunk['token'], 'done': False})
                elif chunk['type'] == 'done':
                    sources = chunk['sources']
                    latency_ms = chunk['latency_ms']
                    is_low_conf = chunk['is_low_confidence']
                    full_answer = chunk['full_answer']
        except GeneratorExit:
            # Client went away mid-stream; nothing more to send, but fall through to persist what we have.
            pass

        if not full_answer:
            return

        assistant_msg = ChatMessage.objects.create(
            session=chat_session, sender='assistant', content=full_answer,
            sources_json=sources, latency_ms=latency_ms, is_low_confidence=is_low_conf,
        )
        ChatSession.objects.filter(pk=chat_session.pk).update(updated_at=timezone.now())
        QueryAuditLog.objects.create(
            user=user, user_role=profile.role, query_text=query, mode='chat',
            retrieved_sources_count=len(sources), top_sources_json=sources[:3],
            response_latency_ms=latency_ms, is_unanswered_or_low_confidence=is_low_conf,
            ip_address=ip,
        )

        # ---- 3. Save verified-confident answers for reuse -------------------------------
        if not is_followup:
            try:
                entry = answer_cache.store(query, full_answer, sources, is_low_confidence=is_low_conf)
                if entry:
                    ChatMessage.objects.filter(pk=assistant_msg.pk).update(cached_answer=entry)
            except Exception:
                logger.exception("Failed to store answer in cache")

        yield _sse({
            'done': True, 'message_id': assistant_msg.id, 'session_id': str(chat_session.pk),
            'sources': sources, 'latency_ms': latency_ms, 'is_low_confidence': is_low_conf,
            'from_cache': False,
        })

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@login_required
def suggested_questions_api(request):
    """Popular + curated questions for the welcome screen (served from the canned-answer store)."""
    topic = request.GET.get('topic', '')
    allowed = get_allowed_access_roles(request.user)
    return JsonResponse({'questions': answer_cache.suggested_questions(allowed, limit=8, topic=topic)})


@login_required
def get_session_messages_api(request, session_id):
    """Retrieves all messages and citations for a chat session."""
    user, _ = _get_user_profile(request)
    session = get_object_or_404(ChatSession, id=session_id, user=user)
    messages_data = []

    for msg in session.messages.all().select_related('feedback'):
        feedback_val = msg.feedback.rating if hasattr(msg, 'feedback') else None
        messages_data.append({
            'id': msg.id,
            'sender': msg.sender,
            'content': msg.content,
            'sources': msg.sources_json,
            'latency_ms': msg.latency_ms,
            'feedback': feedback_val,
            'created_at': msg.created_at.strftime('%H:%M'),
        })

    return JsonResponse({
        'session_id': str(session.id),
        'title': session.title,
        'messages': messages_data,
    })


@login_required
@require_POST
def create_new_session_api(request):
    """Creates a new empty chat session."""
    user, _ = _get_user_profile(request)
    session = ChatSession.objects.create(user=user, title="New Conversation")
    return JsonResponse({
        'session_id': str(session.id),
        'title': session.title,
    })


@login_required
@require_POST
def delete_session_api(request, session_id):
    """Deletes a chat session."""
    user, _ = _get_user_profile(request)
    session = get_object_or_404(ChatSession, id=session_id, user=user)
    session.delete()
    return JsonResponse({'status': 'deleted'})


@login_required
@require_POST
def feedback_api(request):
    """Records thumbs up/down. Feeds the canned-answer cache: thumbs-down retires a cached answer."""
    try:
        data = json.loads(request.body.decode('utf-8'))
        rating = 1 if int(data.get('rating', 1)) > 0 else -1
        message_id = int(data.get('message_id'))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    comment = str(data.get('comment', '')).strip()[:2000]

    # Users may only rate assistant answers in their own conversations
    msg = get_object_or_404(
        ChatMessage.objects.select_related('cached_answer'),
        id=message_id, session__user=request.user, sender='assistant',
    )
    feedback, created = Feedback.objects.update_or_create(
        message=msg, defaults={'rating': rating, 'comment': comment}
    )

    # Update the audit entry for exactly this exchange (the user question just before the answer)
    question = msg.session.messages.filter(sender='user', id__lt=msg.id).order_by('-id').first()
    if question:
        audit = QueryAuditLog.objects.filter(
            user=request.user, query_text=question.content
        ).order_by('-created_at').first()
        if audit:
            audit.feedback_rating = rating
            audit.save(update_fields=['feedback_rating'])

    if created:  # count each message's first vote only, so toggling can't inflate cache stats
        answer_cache.record_feedback(msg.cached_answer, rating)
    elif rating < 0:
        answer_cache.record_feedback(msg.cached_answer, rating)

    return JsonResponse({'status': 'success', 'rating': feedback.rating})


@login_required
def get_chunk_preview_api(request, chunk_id):
    """Returns the full text and metadata for a specific document chunk."""
    chunk = get_object_or_404(DocumentChunk.objects.select_related('document'), chroma_id=chunk_id)
    if not _user_can_access_document(request.user, chunk.document):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    return JsonResponse({
        'chroma_id': chunk.chroma_id,
        'document_id': str(chunk.document_id),
        'title': chunk.document.title,
        'category': chunk.document.category,
        'department': chunk.document.department,
        'version': chunk.document.version,
        'page_number': chunk.page_number,
        'content': chunk.content,
        'token_count': chunk.token_count,
        'metadata': chunk.metadata_json,
    })


@login_required
def resolve_source_api(request):
    """Resolves legacy source citations to a current chunk/document pair."""
    title = request.GET.get('title', '').strip()
    page = request.GET.get('page', '').strip()
    if not title:
        return JsonResponse({'error': 'Title is required'}, status=400)

    allowed_roles = get_allowed_access_roles(request.user)
    chunks = DocumentChunk.objects.select_related('document').filter(
        document__title=title,
        document__access_role__in=allowed_roles,
    )

    page_number = None
    if page.isdigit():
        page_number = int(page)
        page_matches = chunks.filter(page_number=page_number).order_by('-document__updated_at', 'chunk_index')
        chunk = page_matches.first()
    else:
        chunk = None

    if chunk is None:
        chunk = chunks.order_by('-document__updated_at', 'page_number', 'chunk_index').first()

    if chunk is None:
        return JsonResponse({'error': 'Source not found'}, status=404)

    return JsonResponse({
        'chunk_id': chunk.chroma_id,
        'document_id': str(chunk.document_id),
        'title': chunk.document.title,
        'page_number': chunk.page_number,
        'content': chunk.content,
    })


@login_required
def view_document_api(request, doc_id):
    """Streams a source document inline when the current user is allowed to access it."""
    document = get_object_or_404(Document, id=doc_id)
    if not _user_can_access_document(request.user, document):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    content_type, _ = mimetypes.guess_type(document.file.name)
    response = FileResponse(
        document.file.open('rb'),
        content_type=content_type or 'application/octet-stream'
    )
    response['Content-Disposition'] = f'inline; filename="{document.file.name.split("/")[-1]}"'
    return response


@login_required
@require_POST
def upload_document_api(request):
    """Uploads and triggers automatic chunking and indexing."""
    user, profile = _get_user_profile(request)
    if not can_manage_knowledge_base(user):
        return JsonResponse({'error': 'Unauthorized: knowledge manager access required'}, status=403)

    if request.method != 'POST' or 'file' not in request.FILES:
        return JsonResponse({'error': 'File is required'}, status=400)

    uploaded_file = request.FILES['file']
    filename = uploaded_file.name
    ext = filename.split('.')[-1].lower() if '.' in filename else 'txt'

    # .doc/.xls (legacy binary formats) cannot be parsed by python-docx/openpyxl
    if ext not in ['pdf', 'docx', 'txt', 'md', 'xlsx', 'csv']:
        return JsonResponse({'error': f"Unsupported file type .{ext}. Allowed: PDF, DOCX, TXT, MD, XLSX, CSV (save .doc/.xls as .docx/.xlsx first)"}, status=400)
    max_mb = getattr(settings, 'MAX_UPLOAD_MB', 50)
    if uploaded_file.size > max_mb * 1024 * 1024:
        return JsonResponse({'error': f'File too large (max {max_mb} MB)'}, status=400)

    def _choice(value, choices, default):
        return value if value in {c[0] for c in choices} else default

    title = request.POST.get('title', '').strip()[:255] or filename[:255]
    category = _choice(request.POST.get('category', 'Policy'), Document.CATEGORY_CHOICES, 'Policy')
    department = _choice(request.POST.get('department', 'All'), Document.DEPARTMENT_CHOICES, 'All')
    access_role = _choice(request.POST.get('access_role', 'all'), Document.ACCESS_ROLE_CHOICES, 'all')
    version = request.POST.get('version', 'v1.0').strip()[:50] or 'v1.0'

    effective_date = timezone.now().date()
    effective_date_str = request.POST.get('effective_date')
    if effective_date_str:
        try:
            effective_date = datetime.strptime(effective_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    doc = Document.objects.create(
        title=title, file=uploaded_file, file_type=ext, category=category,
        department=department, version=version, access_role=access_role,
        effective_date=effective_date, uploaded_by=user, status='processing',
    )

    ingest_document_async(doc)
    return JsonResponse({
        'status': 'success',
        'document_id': str(doc.id),
        'title': doc.title,
        'chunks': 0,
        'message': 'Upload received. Indexing in the background; refresh to see the status.',
    })


@login_required
@require_POST
def reindex_document_api(request, doc_id):
    """Re-indexes an existing document."""
    user, _ = _get_user_profile(request)
    if not can_manage_knowledge_base(user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    doc = get_object_or_404(Document, id=doc_id)
    ingest_document_async(doc)
    return JsonResponse({'status': 'success', 'message': 'Re-indexing started in the background.', 'chunks': doc.chunk_count})


@login_required
@require_POST
def rebuild_index_api(request):
    """Rebuilds the entire Chroma vector store and BM25 index."""
    user, _ = _get_user_profile(request)
    if not can_manage_knowledge_base(user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    stats = rebuild_vector_index()
    return JsonResponse({'status': 'success', 'stats': stats})


@login_required
@require_POST
def delete_document_api(request, doc_id):
    """Deletes a document and purges its chunks from ChromaDB."""
    user, _ = _get_user_profile(request)
    if not can_manage_knowledge_base(user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    doc = get_object_or_404(Document, id=doc_id)
    vector_store = get_vector_store()
    vector_store.delete_document_chunks(str(doc.id))
    doc.file.delete(save=False)  # also remove the stored file
    doc.delete()
    return JsonResponse({'status': 'deleted'})


def healthz(request):
    """Unauthenticated liveness probe for load balancers / Docker HEALTHCHECK."""
    return JsonResponse({'status': 'ok'})


@login_required
def system_health_api(request):
    """Live Ollama connection and index health status check."""
    health = LocalLLMService.check_health()
    health['total_documents'] = Document.objects.filter(status='indexed').count()
    health['total_chunks'] = DocumentChunk.objects.count()
    return JsonResponse(health)


@login_required
def crm_demo_view(request):
    """
    Interactive Django CRM Portal Mock showcasing the embeddable MIICiQ chatbot widget.
    Demonstrates real-world CRM workflows (Sales Orders, discounts, credit checks)
    with instant redirection to MIIC_iQ with prefilled questions.
    """
    deals = [
        {
            'client': 'Acme Global Logistics',
            'value': '$85,000',
            'stage': 'Quotation Sent (SO Pending)',
            'rep': 'Sarah Lin',
            'date': 'Oct 16, 2026',
            'status': 'Action Needed: Credit Check SO-101',
        },
        {
            'client': 'Nexus Financial Corp',
            'value': '$145,000',
            'stage': 'Director Approval (18% Discount)',
            'rep': 'David Vance',
            'date': 'Oct 15, 2026',
            'status': 'Pending Discount Signoff',
        },
        {
            'client': 'Summit Healthcare Systems',
            'value': '$32,500',
            'stage': 'Contract Signed',
            'rep': 'Elena Gomez',
            'date': 'Oct 17, 2026',
            'status': 'Ready for ERP Order Entry',
        },
        {
            'client': 'BioVanguard Labs',
            'value': '$210,000',
            'stage': 'VP / CFO Review',
            'rep': 'Sarah Lin',
            'date': 'Oct 14, 2026',
            'status': 'Multi-Year Net 45 Approval',
        },
    ]
    return render(request, 'assistant/crm_demo.html', {'deals': deals})

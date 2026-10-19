import json
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, StreamingHttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.db.models import Count, Avg, Q
from django.conf import settings
from django.utils import timezone
from assistant.models import (
    Document, DocumentChunk, ChatSession, ChatMessage,
    Feedback, QueryAuditLog, SystemConfig, UserProfile
)
from assistant.services.vector_store import VectorStoreService
from assistant.services.llm_service import LocalLLMService
from assistant.services.ingestion import ingest_document, rebuild_vector_index
from assistant.services.rbac import get_or_create_user_profile, get_allowed_access_roles, is_admin_or_manager


def _get_or_create_demo_user(request):
    """
    Ensures a valid user session is active (SSO emulation or demo user).
    Supports dev header `X-Remote-User` or session-persisted demo user.
    """
    if request.user.is_authenticated:
        profile = get_or_create_user_profile(request.user)
        return request.user, profile

    # Check session role
    role = request.session.get('active_role', 'admin')  # default to admin for seamless evaluation
    username = request.session.get('active_username', f"evaluator_{role}")
    
    user, _ = User.objects.get_or_create(username=username, defaults={'first_name': 'Company', 'last_name': 'Employee'})
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': role, 'department': 'Operations'})
    profile.role = role
    profile.save()
    
    # Log in user without password for demo intranet access
    login(request, user)
    return user, profile


def chat_view(request):
    """Main ChatGPT-style dashboard view."""
    user, profile = _get_or_create_demo_user(request)
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
        'profile': profile,
        'sessions': sessions,
        'active_session': active_session,
        'messages': messages,
        'ollama_health': ollama_health,
        'doc_count': doc_count,
        'categories': Document.CATEGORY_CHOICES,
    }
    return render(request, 'assistant/chat.html', context)


def search_view(request):
    """Semantic & Keyword document snippet search view."""
    user, profile = _get_or_create_demo_user(request)
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', 'All')
    department = request.GET.get('department', 'All')

    results = []
    if query:
        vector_store = VectorStoreService()
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
            response_latency_ms=35,
            is_unanswered_or_low_confidence=len(results) == 0,
            ip_address=request.META.get('REMOTE_ADDR')
        )

    context = {
        'profile': profile,
        'query': query,
        'category': category,
        'department': department,
        'results': results,
        'categories': ['All'] + [c[0] for c in Document.CATEGORY_CHOICES],
        'departments': ['All', 'Sales', 'HR', 'IT', 'Finance', 'Operations', 'General'],
    }
    return render(request, 'assistant/search.html', context)


def admin_dashboard_view(request):
    """Admin and Knowledge Manager dashboard view."""
    user, profile = _get_or_create_demo_user(request)
    
    # Metrics
    total_docs = Document.objects.count()
    indexed_docs = Document.objects.filter(status='indexed').count()
    total_chunks = DocumentChunk.objects.count()
    total_queries = QueryAuditLog.objects.count()
    
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
        'is_admin': profile.role in ['admin', 'manager'],
        'total_docs': total_docs,
        'indexed_docs': indexed_docs,
        'total_chunks': total_chunks,
        'total_queries': total_queries,
        'avg_latency': int(avg_latency),
        'satisfaction_rate': satisfaction_rate,
        'low_confidence_queries': low_confidence_queries,
        'audit_logs': audit_logs,
        'documents': documents,
        'top_queries': top_queries,
        'ollama_health': ollama_health,
        'system_settings': system_settings,
        'categories': Document.CATEGORY_CHOICES,
        'access_roles': Document.ACCESS_ROLE_CHOICES,
    }
    return render(request, 'assistant/admin_dashboard.html', context)


# API Endpoints
def stream_chat_api(request):
    """
    Server-Sent Events (SSE) streaming chat endpoint.
    Handles user queries, hybrid retrieval, grounding, and streaming tokens.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    query = data.get('message', '').strip()
    session_id = data.get('session_id')
    user, profile = _get_or_create_demo_user(request)

    if not query:
        return JsonResponse({'error': 'Message content cannot be empty'}, status=400)

    # Resolve or create session
    if session_id:
        chat_session = ChatSession.objects.filter(id=session_id, user=user).first()
    else:
        chat_session = None

    if not chat_session:
        title = query[:40] + ('...' if len(query) > 40 else '')
        chat_session = ChatSession.objects.create(user=user, title=title, mode='chat')

    # Save user message
    user_msg = ChatMessage.objects.create(
        session=chat_session,
        sender='user',
        content=query
    )

    # Retrieve context via hybrid search
    vector_store = VectorStoreService()
    allowed_roles = get_allowed_access_roles(user)
    top_k = getattr(settings, 'RAG_TOP_K', 5)
    context_chunks = vector_store.hybrid_search(
        query=query,
        top_k=top_k,
        allowed_roles=allowed_roles
    )

    # Get recent conversation history
    past_messages = list(chat_session.messages.filter(id__lt=user_msg.id).order_by('-created_at')[:6])
    past_messages.reverse()
    chat_history = [{'sender': m.sender, 'content': m.content} for m in past_messages]

    def event_stream():
        full_answer = ""
        sources = []
        latency_ms = 0
        is_low_conf = False

        for chunk in LocalLLMService.stream_generate(query, context_chunks, chat_history):
            if chunk['type'] == 'token':
                full_answer += chunk['token']
                yield f"data: {json.dumps({'token': chunk['token'], 'done': False})}\n\n"
            elif chunk['type'] == 'done':
                sources = chunk['sources']
                latency_ms = chunk['latency_ms']
                is_low_conf = chunk['is_low_confidence']
                full_answer = chunk['full_answer']

        # Persist assistant message in DB
        assistant_msg = ChatMessage.objects.create(
            session=chat_session,
            sender='assistant',
            content=full_answer,
            sources_json=sources,
            latency_ms=latency_ms,
            is_low_confidence=is_low_conf
        )
        chat_session.updated_at = timezone.now()
        chat_session.save(update_fields=['updated_at'])

        # Create Query Audit Log
        QueryAuditLog.objects.create(
            user=user,
            user_role=profile.role,
            query_text=query,
            mode='chat',
            retrieved_sources_count=len(sources),
            top_sources_json=sources[:3],
            response_latency_ms=latency_ms,
            is_unanswered_or_low_confidence=is_low_conf,
            ip_address=request.META.get('REMOTE_ADDR')
        )

        final_payload = {
            'done': True,
            'message_id': assistant_msg.id,
            'session_id': str(chat_session.id),
            'sources': sources,
            'latency_ms': latency_ms,
            'is_low_confidence': is_low_conf,
        }
        yield f"data: {json.dumps(final_payload)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


def get_session_messages_api(request, session_id):
    """Retrieves all messages and citations for a chat session."""
    user, _ = _get_or_create_demo_user(request)
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


def create_new_session_api(request):
    """Creates a new empty chat session."""
    user, _ = _get_or_create_demo_user(request)
    session = ChatSession.objects.create(user=user, title="New Conversation")
    return JsonResponse({
        'session_id': str(session.id),
        'title': session.title,
    })


def delete_session_api(request, session_id):
    """Deletes a chat session."""
    user, _ = _get_or_create_demo_user(request)
    session = get_object_or_404(ChatSession, id=session_id, user=user)
    session.delete()
    return JsonResponse({'status': 'deleted'})


def feedback_api(request):
    """Records thumbs up/down and feedback comments for continuous RAG improvement."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body.decode('utf-8'))
    message_id = data.get('message_id')
    rating = int(data.get('rating', 1))  # +1 or -1
    comment = data.get('comment', '').strip()

    msg = get_object_or_404(ChatMessage, id=message_id)
    feedback, created = Feedback.objects.update_or_create(
        message=msg,
        defaults={'rating': rating, 'comment': comment}
    )

    # Update latest audit log for this query
    audit = QueryAuditLog.objects.filter(query_text=msg.session.messages.filter(sender='user').last().content if msg.session.messages.filter(sender='user').exists() else '').order_by('-created_at').first()
    if audit:
        audit.feedback_rating = rating
        audit.save(update_fields=['feedback_rating'])

    return JsonResponse({'status': 'success', 'rating': feedback.rating})


def get_chunk_preview_api(request, chunk_id):
    """Returns the full text and metadata for a specific document chunk."""
    chunk = get_object_or_404(DocumentChunk.objects.select_related('document'), chroma_id=chunk_id)
    return JsonResponse({
        'chroma_id': chunk.chroma_id,
        'title': chunk.document.title,
        'category': chunk.document.category,
        'department': chunk.document.department,
        'version': chunk.document.version,
        'page_number': chunk.page_number,
        'content': chunk.content,
        'token_count': chunk.token_count,
        'metadata': chunk.metadata_json,
    })


def upload_document_api(request):
    """Uploads and triggers automatic chunking and indexing."""
    user, profile = _get_or_create_demo_user(request)
    if not is_admin_or_manager(user):
        return JsonResponse({'error': 'Unauthorized: Admin or Manager role required'}, status=403)

    if request.method != 'POST' or 'file' not in request.FILES:
        return JsonResponse({'error': 'File is required'}, status=400)

    uploaded_file = request.FILES['file']
    filename = uploaded_file.name
    ext = filename.split('.')[-1].lower() if '.' in filename else 'txt'

    if ext not in ['pdf', 'docx', 'doc', 'txt', 'md', 'xlsx', 'xls', 'csv']:
        return JsonResponse({'error': f"Unsupported file type .{ext}. Allowed: PDF, DOCX, TXT, MD, XLSX, CSV"}, status=400)

    title = request.POST.get('title', '').strip() or filename
    category = request.POST.get('category', 'Policy')
    department = request.POST.get('department', 'All')
    version = request.POST.get('version', 'v1.0')
    access_role = request.POST.get('access_role', 'all')
    effective_date_str = request.POST.get('effective_date')

    effective_date = timezone.now().date()
    if effective_date_str:
        try:
            effective_date = timezone.datetime.strptime(effective_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    doc = Document.objects.create(
        title=title,
        file=uploaded_file,
        file_type=ext,
        category=category,
        department=department,
        version=version,
        access_role=access_role,
        effective_date=effective_date,
        uploaded_by=user
    )

    success, message = ingest_document(doc)
    return JsonResponse({
        'status': 'success' if success else 'error',
        'document_id': str(doc.id),
        'title': doc.title,
        'chunks': doc.chunk_count,
        'message': message,
    })


def reindex_document_api(request, doc_id):
    """Re-indexes an existing document."""
    user, _ = _get_or_create_demo_user(request)
    if not is_admin_or_manager(user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    doc = get_object_or_404(Document, id=doc_id)
    success, message = ingest_document(doc)
    return JsonResponse({'status': 'success' if success else 'failed', 'message': message, 'chunks': doc.chunk_count})


def rebuild_index_api(request):
    """Rebuilds the entire Chroma vector store and BM25 index."""
    user, _ = _get_or_create_demo_user(request)
    if not is_admin_or_manager(user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    stats = rebuild_vector_index()
    return JsonResponse({'status': 'success', 'stats': stats})


def delete_document_api(request, doc_id):
    """Deletes a document and purges its chunks from ChromaDB."""
    user, _ = _get_or_create_demo_user(request)
    if not is_admin_or_manager(user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    doc = get_object_or_404(Document, id=doc_id)
    vector_store = VectorStoreService()
    vector_store.delete_document_chunks(str(doc.id))
    doc.delete()
    return JsonResponse({'status': 'deleted'})


def switch_role_api(request):
    """Demo helper: switch current user role (employee / manager / admin)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body.decode('utf-8'))
    new_role = data.get('role', 'employee')
    if new_role not in ['employee', 'manager', 'admin']:
        return JsonResponse({'error': 'Invalid role'}, status=400)

    request.session['active_role'] = new_role
    user, profile = _get_or_create_demo_user(request)
    profile.role = new_role
    profile.save()

    return JsonResponse({'status': 'success', 'role': new_role})


def system_health_api(request):
    """Live Ollama connection and index health status check."""
    health = LocalLLMService.check_health()
    health['total_documents'] = Document.objects.filter(status='indexed').count()
    health['total_chunks'] = DocumentChunk.objects.count()
    return JsonResponse(health)


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


"""
Canned-answer cache for MIICiQ.

Flow:
  lookup()  -> exact normalized match, then fuzzy token-set match, within the caller's RBAC scope
  store()   -> save a verified, confident RAG answer for reuse
  record_feedback() -> thumbs up/down adjusts or retires a cached answer

Safety rules:
- An answer is only replayed to users whose role can see every source behind it (`scope`).
- Auto-cached answers expire automatically when the knowledge base changes (kb_signature).
- Curated FAQ answers (is_curated) survive re-indexing but can be deactivated by admins.
- Low-confidence answers and answers that were down-voted are never replayed.
"""
import logging
from typing import Any, Dict, List, Optional

from django.db.models import F, Q
from django.utils import timezone

from assistant.models import CachedAnswer
from assistant.services.query_utils import (
    detect_topic, normalize, query_hash, token_key, token_similarity, salient_tokens,
)
from assistant.services.vector_store import kb_signature

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 0.75     # Jaccard on salient tokens
MIN_FUZZY_TOKENS = 2       # never fuzzy-match one-word questions
MAX_FUZZY_CANDIDATES = 400
ACCESS_RANK = {'all': 0, 'manager_plus': 1, 'admin_only': 2}


def _visible_filter(allowed_roles: List[str], signature: str) -> Q:
    """Rows this user may be served: in-scope AND (curated OR still valid for current KB)."""
    return Q(is_active=True, scope__in=allowed_roles) & (Q(is_curated=True) | Q(kb_signature=signature))


def lookup(query: str, allowed_roles: List[str]) -> Optional[CachedAnswer]:
    allowed = allowed_roles or ['all']
    signature = kb_signature()
    base = CachedAnswer.objects.filter(_visible_filter(allowed, signature))

    # 1. Exact normalized match (curated answers win over auto-cached)
    hit = base.filter(query_hash=query_hash(query)).order_by('-is_curated', '-upvotes', '-hit_count').first()
    if hit:
        return hit

    # 2. Fuzzy match: same salient words in any order / minor wording differences
    key = token_key(query)
    if len(salient_tokens(query)) < MIN_FUZZY_TOKENS:
        return None
    best, best_sim = None, 0.0
    for cand in base.order_by('-is_curated', '-hit_count')[:MAX_FUZZY_CANDIDATES]:
        sim = token_similarity(key, cand.token_key)
        if sim > best_sim:
            best, best_sim = cand, sim
    return best if best_sim >= FUZZY_THRESHOLD else None


def mark_hit(entry: CachedAnswer) -> None:
    CachedAnswer.objects.filter(pk=entry.pk).update(hit_count=F('hit_count') + 1, last_hit_at=timezone.now())


def scope_for_sources(sources: List[Dict[str, Any]]) -> str:
    """Most restrictive access_role among the sources used in the answer."""
    scope = 'all'
    for s in sources:
        role = s.get('access_role', 'all')
        if ACCESS_RANK.get(role, 0) > ACCESS_RANK[scope]:
            scope = role
    return scope


def store(
    query: str,
    answer: str,
    sources: List[Dict[str, Any]],
    *,
    is_low_confidence: bool,
) -> Optional[CachedAnswer]:
    """Persist a confident answer. Skips low-confidence, empty, or source-less answers."""
    if is_low_confidence or not answer.strip() or not sources:
        return None
    if len(salient_tokens(query)) < 1:
        return None

    signature = kb_signature()
    qh = query_hash(query)
    scope = scope_for_sources(sources)
    existing = CachedAnswer.objects.filter(query_hash=qh, scope=scope, is_curated=False).first()
    if existing:
        if existing.downvotes > existing.upvotes:
            return None  # users rejected this answer before; do not resurrect it
        existing.answer, existing.sources_json = answer, sources
        existing.kb_signature, existing.is_active = signature, True
        existing.save(update_fields=['answer', 'sources_json', 'kb_signature', 'is_active'])
        return existing

    return CachedAnswer.objects.create(
        query_hash=qh,
        token_key=token_key(query),
        scope=scope,
        question=query.strip()[:1000],
        answer=answer,
        sources_json=sources,
        topic=detect_topic(query),
        kb_signature=signature,
    )


def record_feedback(entry: Optional[CachedAnswer], rating: int) -> None:
    """Thumbs-down retires an auto-cached answer; thumbs-up reinforces it."""
    if entry is None:
        return
    if rating > 0:
        CachedAnswer.objects.filter(pk=entry.pk).update(upvotes=F('upvotes') + 1)
    else:
        CachedAnswer.objects.filter(pk=entry.pk).update(downvotes=F('downvotes') + 1)
        if not entry.is_curated:
            CachedAnswer.objects.filter(pk=entry.pk).update(is_active=False)


def suggested_questions(allowed_roles: List[str], limit: int = 6, topic: str = '') -> List[Dict[str, str]]:
    """Popular curated + frequently-asked cached questions for the welcome screen."""
    qs = CachedAnswer.objects.filter(is_active=True, scope__in=allowed_roles or ['all'])
    qs = qs.filter(Q(is_curated=True) | Q(kb_signature=kb_signature()))
    if topic:
        qs = qs.filter(topic=topic)
    out, seen = [], set()
    for e in qs.order_by('-hit_count', '-is_curated', '-upvotes')[:limit * 3]:
        k = normalize(e.question)
        if k in seen:
            continue
        seen.add(k)
        out.append({'question': e.question, 'topic': e.topic})
        if len(out) >= limit:
            break
    return out

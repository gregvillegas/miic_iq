import os
import math
import hashlib
import re
import logging
import threading
from typing import List, Dict, Any, Optional
import numpy as np
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from django.conf import settings
from rank_bm25 import BM25Okapi
from assistant.services.query_utils import (
    expand_query, detect_topic, TOPIC_TO_CATEGORIES, STOPWORDS,
)

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r'\b[a-zA-Z0-9_\-]{2,}\b')


def _clean_tokens(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


def kb_signature() -> str:
    """Cheap fingerprint of the indexed knowledge base (shared across worker processes)."""
    from django.db.models import Count, Max
    from assistant.models import Document, DocumentChunk
    c = DocumentChunk.objects.aggregate(n=Count('id'), mx=Max('id'))
    d = Document.objects.aggregate(mx=Max('updated_at'))
    stamp = d['mx'].timestamp() if d['mx'] else 0
    return f"{c['n']}-{c['mx']}-{stamp:.3f}"


_BM25_STATE: Dict[str, Any] = {'sig': None, 'bm25': None, 'rows': []}
_BM25_LOCK = threading.Lock()


def _get_bm25_index() -> Dict[str, Any]:
    """Returns the in-memory BM25 index, rebuilding only when the KB signature changes."""
    sig = kb_signature()
    if _BM25_STATE['sig'] == sig:
        return _BM25_STATE
    with _BM25_LOCK:
        if _BM25_STATE['sig'] == sig:
            return _BM25_STATE
        from assistant.models import DocumentChunk
        qs = DocumentChunk.objects.filter(document__status='indexed').values_list(
            'chroma_id', 'content', 'page_number', 'document_id', 'document__title',
            'document__category', 'document__department', 'document__version', 'document__access_role',
        )
        rows = [{
            'chroma_id': r[0], 'content': r[1], 'page_number': r[2], 'document_id': str(r[3]),
            'title': r[4], 'category': r[5], 'department': r[6], 'version': r[7], 'access_role': r[8],
        } for r in qs]
        corpus = [_clean_tokens(r['content']) for r in rows]
        _BM25_STATE.update(
            sig=sig, rows=rows,
            bm25=BM25Okapi(corpus) if corpus and any(corpus) else None,
        )
        return _BM25_STATE


_STORE: Optional['VectorStoreService'] = None
_STORE_LOCK = threading.Lock()


def get_vector_store() -> 'VectorStoreService':
    """Process-wide shared store (avoids re-opening the Chroma client on every request)."""
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                _STORE = VectorStoreService()
    return _STORE


class LocalSemanticEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    High-performance, 100% offline deterministic semantic embedding function.
    Projects text into a 384-dimensional unit vector using n-gram hashing and
    term-frequency normalization. Ensures zero external network requests,
    zero external weight downloads, and deterministic cosine similarities.
    If Ollama embedding is available, it can optionally be leveraged.
    """
    def __init__(self, dim: int = 384):
        self.dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            embeddings.append(self._embed_text(text))
        return embeddings

    def _embed_text(self, text: str) -> List[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return vec.tolist()

        # Word unigrams and bigrams
        for i, word in enumerate(words):
            # Primary word hash
            h1 = int(hashlib.md5(word.encode('utf-8')).hexdigest()[:8], 16) % self.dim
            # Secondary word hash for sign
            sign = 1.0 if (int(hashlib.sha1(word.encode('utf-8')).hexdigest()[:4], 16) % 2 == 0) else -1.0
            weight = 1.0 / (1.0 + math.log1p(len(word)))
            vec[h1] += sign * weight

            # Bigram if available
            if i < len(words) - 1:
                bg = f"{word}_{words[i+1]}"
                h2 = int(hashlib.md5(bg.encode('utf-8')).hexdigest()[:8], 16) % self.dim
                vec[h2] += sign * 0.75

        # Subword character n-grams for policy codes like SO-101, HR-202
        for token in text.split():
            clean_token = token.strip(".,;:()[]{}").lower()
            if len(clean_token) >= 3 and any(c.isdigit() for c in clean_token):
                h_code = int(hashlib.md5(clean_token.encode('utf-8')).hexdigest()[:8], 16) % self.dim
                vec[h_code] += 2.0  # boost policy codes and IDs

        # L2 Normalize
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec.tolist()


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """Neural embeddings from a local Ollama model (e.g. nomic-embed-text). Raises if Ollama is unreachable."""

    def __init__(self, base_url: str, model: str, batch_size: int = 16):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.batch_size = batch_size

    def __call__(self, input: Documents) -> Embeddings:
        import requests
        out: List[List[float]] = []
        texts = list(input)
        for i in range(0, len(texts), self.batch_size):
            batch = [t[:6000] for t in texts[i:i + self.batch_size]]
            resp = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": batch, "keep_alive": getattr(settings, 'OLLAMA_KEEP_ALIVE', '30m')},
                timeout=(3, 120),
            )
            resp.raise_for_status()
            out.extend(resp.json()['embeddings'])
        return out


class VectorStoreService:
    """
    Manages local ChromaDB vector store collection and hybrid BM25 search.
    """
    # One collection per embedding backend: vectors from different models are not comparable.
    COLLECTION_NAME = "miiciq_knowledge_base"

    def __init__(self):
        storage_path = str(settings.CHROMA_PERSIST_DIR)
        os.makedirs(storage_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=storage_path)
        backend = getattr(settings, 'RAG_EMBEDDING_BACKEND', 'hash')
        if backend == 'ollama':
            from assistant.services.llm_service import LocalLLMService
            model = getattr(settings, 'OLLAMA_EMBED_MODEL', 'nomic-embed-text')
            self.embedding_fn = OllamaEmbeddingFunction(LocalLLMService.get_ollama_base_url(), model)
            self.collection_name = f"{self.COLLECTION_NAME}_ollama_{re.sub(r'[^a-zA-Z0-9]+', '_', model)}"[:60]
        else:
            self.embedding_fn = LocalSemanticEmbeddingFunction(dim=384)
            self.collection_name = self.COLLECTION_NAME
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn,
            metadata={"description": "MIICiQ internal documents vector store"}
        )

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Adds parsed chunks to ChromaDB.
        Each chunk dict has: chroma_id, content, metadata
        """
        if not chunks:
            return

        ids = [c['chroma_id'] for c in chunks]
        documents = [c['content'] for c in chunks]
        metadatas = []
        for c in chunks:
            # Chroma metadata values must be primitive types (str, int, float, bool)
            meta = {}
            for k, v in c.get('metadata', {}).items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v
                else:
                    meta[k] = str(v)
            metadatas.append(meta)

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

    def delete_document_chunks(self, document_id: str):
        """
        Removes all chunks associated with a document_id.
        """
        try:
            self.collection.delete(
                where={"document_id": str(document_id)}
            )
        except Exception:
            logger.exception("Failed to delete chunks for document %s", document_id)

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        allowed_roles: Optional[List[str]] = None,
        category: Optional[str] = None,
        department: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval:
        1. Dense vector query (Chroma) with RBAC/category/department filters pushed down
        2. BM25 keyword scoring over a cached in-memory index
        3. Weighted score blending + topic boost
        `allowed_roles` holds Document.access_role values; None defaults to public ('all') only.
        """
        allowed = list(allowed_roles) if allowed_roles else ['all']
        retrieval_query = expand_query(query)
        boost_categories = TOPIC_TO_CATEGORIES.get(topic or detect_topic(query), set())

        # 1. Dense query with filters applied inside Chroma (RBAC is enforced here, not after)
        conds: List[Dict[str, Any]] = [{"access_role": {"$in": allowed}}]
        if category and category != 'All':
            conds.append({"category": category})
        if department and department != 'All':
            conds.append({"department": department})
        chroma_where = conds[0] if len(conds) == 1 else {"$and": conds}

        fetch_k = max(top_k * 3, 15)
        try:
            total = self.collection.count()
            dense_results = self.collection.query(
                query_texts=[retrieval_query],
                n_results=min(fetch_k, max(1, total)),
                where=chroma_where,
            ) if total else None
        except Exception:
            logger.exception("Dense query failed")
            dense_results = None

        candidates: Dict[str, Dict[str, Any]] = {}
        if dense_results and dense_results.get('ids') and dense_results['ids'][0]:
            ids = dense_results['ids'][0]
            docs = dense_results['documents'][0]
            metas = dense_results['metadatas'][0]
            dists = dense_results.get('distances', [[]])[0]
            for rank, (cid, doc, meta) in enumerate(zip(ids, docs, metas)):
                dist = dists[rank] if rank < len(dists) else 1.0
                candidates[cid] = {
                    'content': doc,
                    'metadata': meta or {},
                    'dense_score': max(0.0, 1.0 - (dist / 2.0)),
                    'bm25_score': 0.0,
                }

        # 2. BM25 over the cached index (rebuilt only when the knowledge base changes)
        index = _get_bm25_index()
        if index['bm25'] is not None:
            q_tokens = _clean_tokens(retrieval_query)
            if q_tokens:
                scores = index['bm25'].get_scores(q_tokens)
                max_score = float(scores.max()) if len(scores) else 0.0
                if max_score > 0:
                    rows = index['rows']
                    for i in np.argsort(scores)[::-1][:max(top_k * 4, 20)]:
                        if scores[i] <= 0:
                            break
                        r = rows[i]
                        if r['access_role'] not in allowed:
                            continue
                        if category and category != 'All' and r['category'] != category:
                            continue
                        if department and department != 'All' and r['department'] != department:
                            continue
                        norm = float(scores[i]) / max_score
                        cand = candidates.get(r['chroma_id'])
                        if cand:
                            cand['bm25_score'] = norm
                        else:
                            candidates[r['chroma_id']] = {
                                'content': r['content'],
                                'metadata': {
                                    'document_id': r['document_id'], 'title': r['title'],
                                    'category': r['category'], 'department': r['department'],
                                    'version': r['version'], 'page_number': r['page_number'],
                                    'access_role': r['access_role'],
                                },
                                'dense_score': 0.05,
                                'bm25_score': norm,
                            }

        # 3. Blend scores
        q_lower = query.lower()
        results = []
        for cid, item in candidates.items():
            meta = item['metadata']
            if meta.get('access_role', 'all') not in allowed:  # defence in depth
                continue
            d, b = item['dense_score'], item['bm25_score']
            if b == 0 and d < 0.52:
                combined = max(0.05, d * 0.3)  # no keyword overlap + weak semantics = out of domain
            else:
                combined = 0.6 * d + 0.4 * b
            if q_lower in item['content'].lower():
                combined += 0.15
            if boost_categories and meta.get('category') in boost_categories and combined > 0.2:
                combined += 0.08
            results.append({
                'chroma_id': cid,
                'document_id': meta.get('document_id'),
                'content': item['content'],
                'metadata': meta,
                'score': round(float(min(1.0, combined)), 4),
                'dense_score': round(float(d), 4),
                'bm25_score': round(float(b), 4),
                'page_number': int(meta.get('page_number', 1)),
                'title': meta.get('title', 'Company Document'),
                'category': meta.get('category', 'Policy'),
                'department': meta.get('department', 'General'),
                'version': meta.get('version', 'v1.0'),
                'access_role': meta.get('access_role', 'all'),
            })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def reset_collection(self):
        """Drops and recreates collection for full index rebuild."""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            logger.info("Collection %s did not exist; creating", self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn
        )

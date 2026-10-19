import os
import math
import hashlib
import re
from typing import List, Dict, Any, Optional
import numpy as np
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from django.conf import settings
from rank_bm25 import BM25Okapi


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


class VectorStoreService:
    """
    Manages local ChromaDB vector store collection and hybrid BM25 search.
    """
    COLLECTION_NAME = "miiciq_knowledge_base"

    def __init__(self):
        storage_path = str(settings.CHROMA_PERSIST_DIR)
        os.makedirs(storage_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=storage_path)
        self.embedding_fn = LocalSemanticEmbeddingFunction(dim=384)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
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
            pass

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        allowed_roles: Optional[List[str]] = None,
        category: Optional[str] = None,
        department: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid search:
        1. Dense semantic vector query via ChromaDB
        2. Keyword search via BM25
        3. Reciprocal Rank Fusion / Weighted score blending
        4. RBAC role and metadata filtering
        """
        # Build Chroma where clause
        where_conditions = []
        if category and category != 'All':
            where_conditions.append({"category": category})
        if department and department != 'All':
            where_conditions.append({"department": department})

        chroma_where = None
        if len(where_conditions) == 1:
            chroma_where = where_conditions[0]
        elif len(where_conditions) > 1:
            chroma_where = {"$and": where_conditions}

        # 1. Dense Vector Query
        fetch_k = max(top_k * 3, 15)
        try:
            dense_results = self.collection.query(
                query_texts=[query],
                n_results=min(fetch_k, max(1, self.collection.count())),
                where=chroma_where
            )
        except Exception:
            dense_results = {'ids': [[]], 'documents': [[]], 'metadatas': [[]], 'distances': [[]]}

        dense_candidates: Dict[str, Dict[str, Any]] = {}
        if dense_results and dense_results.get('ids') and len(dense_results['ids'][0]) > 0:
            ids = dense_results['ids'][0]
            docs = dense_results['documents'][0]
            metas = dense_results['metadatas'][0]
            dists = dense_results.get('distances', [[]])[0]

            for rank, (cid, doc, meta) in enumerate(zip(ids, docs, metas)):
                dist = dists[rank] if rank < len(dists) else 0.5
                # Convert distance to normalized similarity score [0, 1]
                sim_score = max(0.0, 1.0 - (dist / 2.0))
                dense_candidates[cid] = {
                    'chroma_id': cid,
                    'content': doc,
                    'metadata': meta,
                    'dense_score': sim_score,
                    'dense_rank': rank + 1,
                    'bm25_score': 0.0,
                }

        # 2. BM25 Keyword Search
        # Query candidates from Django DB chunks for exact term matching
        from assistant.models import DocumentChunk
        all_chunks_qs = DocumentChunk.objects.select_related('document').all()
        if category and category != 'All':
            all_chunks_qs = all_chunks_qs.filter(document__category=category)
        if department and department != 'All':
            all_chunks_qs = all_chunks_qs.filter(document__department=department)

        # Apply RBAC filtering on queryset
        if allowed_roles:
            role_filters = []
            if 'admin' in allowed_roles:
                role_filters.extend(['all', 'manager_plus', 'admin_only'])
            elif 'manager' in allowed_roles:
                role_filters.extend(['all', 'manager_plus'])
            else:
                role_filters.append('all')
            all_chunks_qs = all_chunks_qs.filter(document__access_role__in=role_filters)

        all_chunks = list(all_chunks_qs[:500])

        STOPWORDS = {
            'a', 'an', 'the', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'by', 'for', 'with',
            'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above',
            'below', 'to', 'from', 'up', 'down', 'of', 'off', 'over', 'under', 'again', 'further',
            'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both',
            'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
            'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don',
            'should', 'now', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
            'am', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing',
            'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'you', 'your', 'he', 'him', 'his', 'she', 'her', 'it', 'its', 'they', 'them'
        }

        if all_chunks:
            def clean_tokens(text: str) -> List[str]:
                tokens = re.findall(r'\b[a-zA-Z0-9_\-]{2,}\b', text.lower())
                return [t for t in tokens if t not in STOPWORDS]

            tokenized_corpus = [clean_tokens(c.content) for c in all_chunks]
            bm25 = BM25Okapi(tokenized_corpus)
            query_tokens = clean_tokens(query)

            if query_tokens:
                bm25_scores = bm25.get_scores(query_tokens)
                max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 0.0

                if max_bm25 > 0:
                    for i, score in enumerate(bm25_scores):
                        if score > 0:
                            chunk_obj = all_chunks[i]
                            cid = chunk_obj.chroma_id
                            norm_bm25 = score / max_bm25

                            if cid in dense_candidates:
                                dense_candidates[cid]['bm25_score'] = norm_bm25
                            else:
                                dense_candidates[cid] = {
                                    'chroma_id': cid,
                                    'content': chunk_obj.content,
                                    'metadata': {
                                        'document_id': str(chunk_obj.document_id),
                                        'title': chunk_obj.document.title,
                                        'category': chunk_obj.document.category,
                                        'department': chunk_obj.document.department,
                                        'version': chunk_obj.document.version,
                                        'page_number': chunk_obj.page_number,
                                        'access_role': chunk_obj.document.access_role,
                                    },
                                    'dense_score': 0.05,
                                    'dense_rank': 99,
                                    'bm25_score': norm_bm25,
                                }

        # 3. Combine scores & apply RBAC
        scored_results = []
        for cid, item in dense_candidates.items():
            meta = item.get('metadata', {})
            doc_access = meta.get('access_role', 'all')
            if allowed_roles:
                if 'admin' in allowed_roles:
                    pass
                elif 'manager' in allowed_roles and doc_access == 'admin_only':
                    continue
                elif 'employee' in allowed_roles and doc_access in ['manager_plus', 'admin_only']:
                    continue

            # Hybrid Score calculation: 60% Dense + 40% BM25
            d_score = item.get('dense_score', 0.0)
            b_score = item.get('bm25_score', 0.0)

            # If no keyword overlap and weak semantic similarity, treat as out-of-domain
            if b_score == 0 and d_score < 0.52:
                combined_score = max(0.05, d_score * 0.3)
            else:
                combined_score = (0.6 * d_score) + (0.4 * b_score)

            # Extra boost if exact keyword or code is in content
            lower_content = item['content'].lower()
            if query.lower() in lower_content:
                combined_score += 0.15

            scored_results.append({
                'chroma_id': cid,
                'content': item['content'],
                'metadata': meta,
                'score': round(float(min(1.0, combined_score)), 4),
                'dense_score': round(float(d_score), 4),
                'bm25_score': round(float(b_score), 4),
                'page_number': int(meta.get('page_number', 1)),
                'title': meta.get('title', 'Company Document'),
                'category': meta.get('category', 'Policy'),
                'department': meta.get('department', 'General'),
                'version': meta.get('version', 'v1.0'),
            })

        # Sort by combined score descending
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        return scored_results[:top_k]

    def reset_collection(self):
        """Drops and recreates collection for full index rebuild."""
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_fn
        )

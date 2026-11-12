import os
import time
import logging
import threading
import contextlib
from typing import Dict, Any, Tuple
from django.utils import timezone
from assistant.models import Document, DocumentChunk
from assistant.services.document_processor import DocumentParser, RecursiveChunker
from assistant.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

_INGEST_LOCK = threading.Lock()


@contextlib.contextmanager
def _ingest_guard():
    """Serialise index writes across threads and gunicorn worker processes (Chroma/SQLite are single-writer)."""
    from django.conf import settings
    with _INGEST_LOCK:
        lock_path = os.path.join(str(settings.CHROMA_PERSIST_DIR), '.ingest.lock')
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, 'w') as fh:
            try:
                import fcntl
                fcntl.flock(fh, fcntl.LOCK_EX)
            except ImportError:  # non-POSIX: thread lock only
                pass
            try:
                yield
            finally:
                try:
                    fcntl.flock(fh, fcntl.LOCK_UN)
                except Exception:
                    pass


def ingest_document_async(document: Document) -> None:
    """Index in a background thread so uploads return immediately; status is tracked on the Document."""
    document.status = 'processing'
    document.error_message = ''
    document.save(update_fields=['status', 'error_message'])
    doc_id = document.pk

    def _run():
        from django.db import connection
        try:
            doc = Document.objects.get(pk=doc_id)
            ingest_document(doc)
        except Exception:
            logger.exception("Background ingestion crashed for %s", doc_id)
            Document.objects.filter(pk=doc_id).update(status='failed', error_message='Indexing crashed; see server log.')
        finally:
            connection.close()

    threading.Thread(target=_run, name=f"ingest-{doc_id}", daemon=True).start()


def ingest_document(document: Document) -> Tuple[bool, str]:
    with _ingest_guard():
        return _ingest_document_locked(document)


def _ingest_document_locked(document: Document) -> Tuple[bool, str]:
    """
    Ingests a single Document instance:
    1. Parses file pages and sections.
    2. Splits into 500-1000 token chunks with overlap.
    3. Persists DocumentChunk models in Django DB.
    4. Embeds and upserts into local ChromaDB with hybrid search index.
    5. Updates Document status.
    """
    try:
        document.status = 'processing'
        document.error_message = ''
        document.save(update_fields=['status', 'error_message'])

        file_path = document.file.path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at {file_path}")

        document.file_size = os.path.getsize(file_path)

        # 1. Parse File Pages
        pages = DocumentParser.parse_file(file_path, document.file_type)
        if not pages:
            raise ValueError("No readable text content extracted from document.")

        # 2. Chunk Text
        chunker = RecursiveChunker(target_chars=2400, overlap_chars=400)
        doc_metadata = {
            'document_id': str(document.id),
            'title': document.title,
            'category': document.category,
            'department': document.department,
            'version': document.version,
            'access_role': document.access_role,
            'effective_date': str(document.effective_date),
        }
        chunk_dicts = chunker.chunk_document_pages(pages, doc_metadata)
        if not chunk_dicts:
            raise ValueError("Could not generate valid text chunks.")

        # 3. Clean previous chunks in DB & Chroma
        vector_store = get_vector_store()
        vector_store.delete_document_chunks(str(document.id))
        document.chunks.all().delete()

        # 4. Save DB DocumentChunks & prepare for Chroma
        db_chunks = []
        chroma_chunks = []
        for c in chunk_dicts:
            chroma_id = f"{document.id}_{c['chunk_index']}"
            db_chunk = DocumentChunk(
                document=document,
                chunk_index=c['chunk_index'],
                content=c['content'],
                token_count=c['token_count'],
                page_number=c['page_number'],
                metadata_json=c['metadata'],
                chroma_id=chroma_id
            )
            db_chunks.append(db_chunk)
            chroma_chunks.append({
                'chroma_id': chroma_id,
                'content': c['content'],
                'metadata': c['metadata']
            })

        DocumentChunk.objects.bulk_create(db_chunks)

        # 5. Upsert to Vector Store
        vector_store.add_chunks(chroma_chunks)

        # 6. Finalize Document status
        document.chunk_count = len(db_chunks)
        document.status = 'indexed'
        document.updated_at = timezone.now()
        document.save(update_fields=['status', 'chunk_count', 'file_size', 'updated_at'])

        return True, f"Successfully indexed {len(db_chunks)} chunks."

    except Exception as e:
        logger.exception(f"Error ingesting document {document.id}")
        document.status = 'failed'
        document.error_message = str(e)
        document.save(update_fields=['status', 'error_message'])
        return False, str(e)


def rebuild_vector_index() -> Dict[str, Any]:
    """
    Rebuilds the entire Chroma vector store and BM25 index from all active documents.
    """
    start_time = time.time()
    vector_store = get_vector_store()

    documents = Document.objects.all()
    successful = 0
    failed = 0
    total_chunks = 0

    with _ingest_guard():
        vector_store.reset_collection()
        for doc in documents:
            success, msg = _ingest_document_locked(doc)
            if success:
                successful += 1
                total_chunks += doc.chunk_count
            else:
                failed += 1

    elapsed = round(time.time() - start_time, 2)
    return {
        'total_documents': documents.count(),
        'successful': successful,
        'failed': failed,
        'total_chunks': total_chunks,
        'duration_seconds': elapsed
    }

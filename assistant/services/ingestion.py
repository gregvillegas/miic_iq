import os
import time
import logging
from typing import Dict, Any, Tuple
from django.utils import timezone
from assistant.models import Document, DocumentChunk
from assistant.services.document_processor import DocumentParser, RecursiveChunker
from assistant.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)


def ingest_document(document: Document) -> Tuple[bool, str]:
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
        vector_store = VectorStoreService()
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
    vector_store = VectorStoreService()
    vector_store.reset_collection()

    documents = Document.objects.all()
    successful = 0
    failed = 0
    total_chunks = 0

    for doc in documents:
        success, msg = ingest_document(doc)
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

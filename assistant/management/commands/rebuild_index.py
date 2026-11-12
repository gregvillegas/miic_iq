from django.core.management.base import BaseCommand
from django.conf import settings
from assistant.services.ingestion import rebuild_vector_index


class Command(BaseCommand):
    help = "Rebuild the vector index (required after changing RAG_EMBEDDING_BACKEND or OLLAMA_EMBED_MODEL)."

    def handle(self, *args, **options):
        self.stdout.write(f"Embedding backend: {getattr(settings, 'RAG_EMBEDDING_BACKEND', 'hash')}")
        stats = rebuild_vector_index()
        self.stdout.write(self.style.SUCCESS(str(stats)))
        if stats['failed']:
            self.stdout.write(self.style.WARNING("Some documents failed. If using the ollama backend, check that the embedding model is pulled."))

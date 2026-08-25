from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from knowledge.models import KnowledgeEntry
from rag.semantic_search import COLLECTION_NAME, MODEL_NAME, get_embedding_model


class Command(BaseCommand):
    help = "Index active legal knowledge entries in the local ChromaDB collection."

    batch_size = 64

    def handle(self, *args, **options):
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(settings.BASE_DIR / "chroma_db"))
            collection_names = {
                collection.name for collection in client.list_collections()
            }
            if COLLECTION_NAME in collection_names:
                client.delete_collection(name=COLLECTION_NAME)
            collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            model = get_embedding_model()
        except Exception as exc:
            raise CommandError(f"Could not initialize ChromaDB or {MODEL_NAME}: {exc}") from exc

        indexed = 0
        skipped = 0
        entries = KnowledgeEntry.objects.filter(is_active=True).select_related("category")

        batch = []
        for entry in entries.iterator(chunk_size=self.batch_size):
            text = self._embedding_text(entry)
            if not text:
                skipped += 1
                continue
            batch.append((entry, text))
            if len(batch) == self.batch_size:
                indexed += self._index_batch(collection, model, batch)
                batch = []

        if batch:
            indexed += self._index_batch(collection, model, batch)

        self.stdout.write(
            self.style.SUCCESS(f"Indexed {indexed} knowledge entries; skipped {skipped}.")
        )

    @staticmethod
    def _embedding_text(entry):
        parts = (
            entry.document_title,
            entry.article_number,
            entry.title,
            entry.chapter,
            entry.section,
            entry.content,
        )
        return "\n".join(part.strip() for part in parts if part and part.strip())

    @staticmethod
    def _metadata(entry):
        return {
            "knowledge_entry_id": entry.id,
            "document_title": entry.document_title,
            "article_number": entry.article_number,
            "category": entry.category.name,
            "page_start": entry.page_start if entry.page_start is not None else "",
            "page_end": entry.page_end if entry.page_end is not None else "",
        }

    def _index_batch(self, collection, model, batch):
        texts = [text for _, text in batch]
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()
        ids = [f"knowledge-entry-{entry.id}" for entry, _ in batch]
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=[self._metadata(entry) for entry, _ in batch],
        )

        for (entry, _), embedding_id in zip(batch, ids):
            entry.embedding_id = embedding_id
        KnowledgeEntry.objects.bulk_update(
            [entry for entry, _ in batch],
            ["embedding_id"],
        )
        return len(batch)

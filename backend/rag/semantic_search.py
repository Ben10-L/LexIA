from functools import lru_cache

from django.conf import settings

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "lexia_legal_knowledge"
CHROMA_PATH = settings.BASE_DIR / "chroma_db"


@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def get_collection():
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_collection(name=COLLECTION_NAME)


def search_knowledge_semantic(question, limit=3):
    """Return KnowledgeEntry objects in ChromaDB similarity order."""
    try:
        collection = get_collection()
        if collection.count() == 0:
            return []

        embedding = get_embedding_model().encode(
            [question],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        results = collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=limit,
            include=["metadatas"],
        )
        metadatas = results.get("metadatas") or []
        if not metadatas:
            return []

        entry_ids = [
            metadata.get("knowledge_entry_id")
            for metadata in metadatas[0]
            if metadata.get("knowledge_entry_id") is not None
        ]
        if not entry_ids:
            return []

        from knowledge.models import KnowledgeEntry

        entries_by_id = KnowledgeEntry.objects.filter(
            id__in=entry_ids,
            is_active=True,
        ).select_related("category").in_bulk()
        return [entries_by_id[entry_id] for entry_id in entry_ids if entry_id in entries_by_id]
    except Exception:
        return []

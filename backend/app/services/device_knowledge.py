import os

from app.core.logger import get_logger


logger = get_logger(__name__)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

CHROMA_PATH = os.path.join(
    BASE_DIR,
    "data",
    "chroma_db"
)

COLLECTION_NAME = "device_catalog"

MODEL_NAME = "all-MiniLM-L6-v2"


# ============================================================
# LAZY-LOADED SINGLETONS
# ============================================================

_embedding_model = None
_collection = None


def get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        logger.info("Loading RAG embedding model...")

        # Imported lazily so the app can boot on deployments
        # that do not install the sentence-transformers stack
        # (e.g. Vercel function size limits).
        try:
            from sentence_transformers import (
                SentenceTransformer,
            )
        except ImportError as exc:
            raise RuntimeError(
                "RAG embedding model is not installed "
                "in this deployment."
            ) from exc

        _embedding_model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded.")

    return _embedding_model


def get_collection():
    global _collection

    if _collection is None:
        logger.info("Connecting to ChromaDB...")

        # Imported lazily so the app can boot on deployments
        # that do not install chromadb.
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "ChromaDB is not installed in this deployment."
            ) from exc

        client = chromadb.PersistentClient(
            path=CHROMA_PATH
        )
        _collection = client.get_collection(
            name=COLLECTION_NAME
        )
        logger.info(
            "ChromaDB connected: %d records",
            _collection.count()
        )

    return _collection


# ============================================================
# SEARCH
# ============================================================

def search_devices(
    query: str,
    top_k: int = 5
):
    """
    Semantic search over the device knowledge base.
    """

    query = query.strip()

    if not query:
        return []

    model = get_embedding_model()
    collection = get_collection()

    query_embedding = model.encode(
        [query],
        normalize_embeddings=True
    ).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    output = []

    for i, document in enumerate(documents):

        metadata = (
            metadatas[i]
            if i < len(metadatas)
            else {}
        )

        distance = (
            distances[i]
            if i < len(distances)
            else None
        )

        output.append({
            "document": document,
            "metadata": metadata,
            "distance": distance
        })

    return output

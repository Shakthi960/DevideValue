import os

import chromadb
from sentence_transformers import SentenceTransformer

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
        _embedding_model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded.")

    return _embedding_model


def get_collection():
    global _collection

    if _collection is None:
        logger.info("Connecting to ChromaDB...")
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

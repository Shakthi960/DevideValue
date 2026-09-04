import os
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSV_PATH = os.path.join(
    BASE_DIR,
    "data",
    "device_catalog_clean.csv"
)

CHROMA_PATH = os.path.join(
    BASE_DIR,
    "data",
    "chroma_db"
)

COLLECTION_NAME = "device_catalog"

MODEL_NAME = "all-MiniLM-L6-v2"


# ============================================================
# LOAD DATASET
# ============================================================

print("=" * 60)
print("DEVICE KNOWLEDGE BASE BUILD")
print("=" * 60)

print("\nLoading device catalog...")

df = pd.read_csv(CSV_PATH)

print(f"Rows found: {len(df)}")

required_columns = [
    "brand",
    "model",
    "ram",
    "storage",
    "variant_name"
]

missing = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing:
    raise ValueError(
        f"Missing required columns: {missing}"
    )


# ============================================================
# CLEAN DATA
# ============================================================

df = df.fillna("")

print("Dataset validated.")


# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================

print("\nLoading embedding model...")
print(f"Model: {MODEL_NAME}")

embedding_model = SentenceTransformer(MODEL_NAME)

print("Embedding model loaded.")


# ============================================================
# CREATE CHROMADB
# ============================================================

print("\nInitializing ChromaDB...")

os.makedirs(CHROMA_PATH, exist_ok=True)

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

# Delete old collection if it exists
try:
    client.delete_collection(COLLECTION_NAME)
    print("Existing collection removed.")
except Exception:
    pass

collection = client.create_collection(
    name=COLLECTION_NAME,
    metadata={
        "description": "Smartphone device catalog knowledge base"
    }
)


# ============================================================
# CREATE DOCUMENTS
# ============================================================

print("\nCreating knowledge documents...")

documents = []
metadatas = []
ids = []

for index, row in df.iterrows():

    brand = str(row["brand"]).strip()
    model = str(row["model"]).strip()
    ram = str(row["ram"]).strip()
    storage = str(row["storage"]).strip()
    variant = str(row["variant_name"]).strip()

    document = f"""
Smartphone: {brand} {model}

Brand: {brand}
Model: {model}
RAM: {ram} GB
Storage: {storage} GB
Variant: {variant}

This device is listed in the Device Valuation Platform
smartphone catalog.
""".strip()

    documents.append(document)

    metadatas.append({
        "brand": brand,
        "model": model,
        "ram": ram,
        "storage": storage,
        "variant_name": variant
    })

    ids.append(f"device_{index}")


print(f"Documents created: {len(documents)}")


# ============================================================
# CREATE EMBEDDINGS
# ============================================================

print("\nGenerating embeddings...")

embeddings = embedding_model.encode(
    documents,
    show_progress_bar=True,
    normalize_embeddings=True
)

print("Embeddings generated.")


# ============================================================
# STORE IN CHROMADB
# ============================================================

print("\nStoring documents in ChromaDB...")

collection.add(
    ids=ids,
    documents=documents,
    metadatas=metadatas,
    embeddings=embeddings.tolist()
)

print(f"Stored records: {collection.count()}")


# ============================================================
# TEST SEARCH
# ============================================================

print("\nTesting semantic search...")

test_query = "Vivo phone with 8GB RAM and 256GB storage"

query_embedding = embedding_model.encode(
    [test_query],
    normalize_embeddings=True
)

results = collection.query(
    query_embeddings=query_embedding.tolist(),
    n_results=5
)


print("\nQuery:")
print(test_query)

print("\nTop results:")

for i, document in enumerate(results["documents"][0], start=1):

    metadata = results["metadatas"][0][i - 1]

    print(
        f"\n{i}. "
        f"{metadata['brand']} "
        f"{metadata['model']} "
        f"- {metadata['variant_name']}"
    )


# ============================================================
# COMPLETE
# ============================================================

print("\n" + "=" * 60)
print("KNOWLEDGE BASE BUILD COMPLETE")
print("=" * 60)

print(f"Collection : {COLLECTION_NAME}")
print(f"Records    : {collection.count()}")
print(f"Database   : {CHROMA_PATH}")
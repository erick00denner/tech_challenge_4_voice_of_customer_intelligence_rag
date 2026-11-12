"""Index prepared Olist reviews in a persistent ChromaDB collection."""

import argparse
import time

import chromadb
import pandas as pd
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from src.config import CHROMA_PATH, COLLECTION_NAME, MODEL_NAME, ROOT_DIR


DATA_PATH = ROOT_DIR / "data/processed/olist_reviews_clean.csv"
BATCH_SIZE = 128
TEST_QUERY = "produto não chegou"


def load_reviews() -> pd.DataFrame:
    """Load prepared reviews and validate document identifiers."""
    reviews = pd.read_csv(DATA_PATH, keep_default_na=False)

    if reviews["review_id"].duplicated().any():
        raise ValueError("Duplicate review IDs found.")

    return reviews


def build_metadata(row: dict) -> dict[str, str | int]:
    """Build Chroma-compatible metadata for a review."""
    return {
        "order_ids": str(row["order_ids"]),
        "review_score": int(row["review_score"]),
        "review_creation_date": str(row["review_creation_date"]),
        "n_chars": int(row["n_chars"]),
        "dedup_key": str(row["dedup_key"]),
    }


def get_collection(client: chromadb.ClientAPI, reset: bool):
    """Create a collection and prevent embedding model mismatches."""
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except chromadb.errors.NotFoundError:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
        metadata={"embedding_model": MODEL_NAME},
    )

    if collection.metadata.get("embedding_model") != MODEL_NAME:
        raise ValueError(
            "Embedding model mismatch. Rebuild the index with --reset."
        )

    return collection


def index_reviews(reviews: pd.DataFrame, reset: bool) -> None:
    """Generate embeddings and persist reviews in ChromaDB."""
    started = time.perf_counter()

    model = SentenceTransformer(MODEL_NAME)
    print(f"Model: {MODEL_NAME} | device: {model.device}")

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = get_collection(client, reset)

    for start in tqdm(range(0, len(reviews), BATCH_SIZE), desc="Indexing"):
        records = reviews.iloc[start:start + BATCH_SIZE].to_dict("records")
        documents = [row["document"] for row in records]

        embeddings = model.encode(
            documents,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        collection.upsert(
            ids=[row["review_id"] for row in records],
            documents=documents,
            embeddings=embeddings.tolist(),
            metadatas=[build_metadata(row) for row in records],
        )

    elapsed = time.perf_counter() - started
    validate_index(collection, model, expected=len(reviews))
    print(f"Elapsed: {elapsed:.1f}s")


def validate_index(collection, model, expected: int) -> None:
    """Validate index integrity, distance metric and semantic retrieval."""
    count = collection.count()

    if count != expected:
        raise RuntimeError(
            f"Expected {expected:,} documents, found {count:,}."
        )

    space = collection.configuration["hnsw"]["space"]

    if space != "cosine":
        raise RuntimeError(
            f"Expected cosine distance, found {space!r}."
        )

    query_embedding = model.encode(
        [TEST_QUERY],
        normalize_embeddings=True,
    ).tolist()

    result = collection.query(
        query_embeddings=query_embedding,
        n_results=3,
        include=["documents", "distances", "metadatas"],
    )

    print(f"Collection documents: {count:,}")
    print(f"Distance metric: {space}")
    print(f"\nTest query: {TEST_QUERY!r}")

    for document, distance, metadata in zip(
        result["documents"][0],
        result["distances"][0],
        result["metadatas"][0],
    ):
        similarity = 1 - distance

        print(
            f"  similarity={similarity:.3f} | "
            f"score={metadata['review_score']} | "
            f"{document}"
        )


def main() -> None:
    """Load prepared data and create the persistent vector index."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing collection before indexing.",
    )
    args = parser.parse_args()

    index_reviews(load_reviews(), reset=args.reset)


if __name__ == "__main__":
    main()
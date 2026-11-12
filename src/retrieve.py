
"""Retrieve semantically relevant Olist reviews from ChromaDB."""

import argparse
from collections import Counter

from src.config import CHROMA_PATH, COLLECTION_NAME, MODEL_NAME


DEFAULT_RETRIEVAL_TOP_K = 10
CANDIDATE_MULTIPLIER = 5
MAX_CANDIDATES = 200


def normalize_query(query: str) -> str:
    """Normalize query whitespace without changing its meaning."""
    return " ".join(query.split())


def deduplicate_results(results: dict, top_k: int) -> list[dict]:
    """Select unique reviews and count occurrences among candidates."""
    metadatas = results["metadatas"][0]
    key_counts = Counter(
        metadata["dedup_key"] for metadata in metadatas
    )

    selected = []
    seen_keys = set()

    for review_id, document, distance, metadata in zip(
        results["ids"][0],
        results["documents"][0],
        results["distances"][0],
        metadatas,
    ):
        key = metadata["dedup_key"]

        if key in seen_keys:
            continue

        seen_keys.add(key)

        selected.append({
            "review_id": review_id,
            "order_ids": metadata.get("order_ids", ""),
            "document": document,
            "similarity": 1 - distance,
            "review_score": metadata["review_score"],
            "review_creation_date": metadata["review_creation_date"],
            "n_chars": metadata["n_chars"],
            "candidate_occurrences": key_counts[key],
        })

        if len(selected) >= top_k:
            break

    return selected


def retrieve_reviews(
    query: str,
    collection,
    model,
    top_k: int = DEFAULT_RETRIEVAL_TOP_K,
) -> dict:
    """Expand vector search until enough distinct reviews are found."""
    processed_query = normalize_query(query)

    if not processed_query:
        raise ValueError("Query cannot be empty.")

    if top_k < 1:
        raise ValueError("top_k must be greater than zero.")

    total_documents = collection.count()

    if total_documents == 0:
        raise ValueError("The ChromaDB collection is empty.")

    query_embedding = model.encode(
        [processed_query],
        normalize_embeddings=True,
    ).tolist()

    candidate_limit = min(total_documents, MAX_CANDIDATES)

    candidate_count = min(
        top_k * CANDIDATE_MULTIPLIER,
        candidate_limit,
    )

    while True:
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=candidate_count,
            include=["documents", "distances", "metadatas"],
        )

        reviews = deduplicate_results(results, top_k)

        if len(reviews) >= top_k or candidate_count >= candidate_limit:
            break

        candidate_count = min(
            candidate_count * 2,
            candidate_limit,
        )

    return {
        "query": processed_query,
        "reviews": reviews,
        "candidates_examined": len(results["ids"][0]),
        "candidate_limit_reached": candidate_count >= candidate_limit,
        "retrieval_incomplete": len(reviews) < top_k,
    }


def main() -> None:
    """Run semantic retrieval from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Question or topic to search.")
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_RETRIEVAL_TOP_K,
        help="Maximum number of distinct reviews to return.",
    )
    args = parser.parse_args()

    import chromadb
    from sentence_transformers import SentenceTransformer

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_collection(COLLECTION_NAME)
    model = SentenceTransformer(MODEL_NAME)

    result = retrieve_reviews(
        query=args.query,
        collection=collection,
        model=model,
        top_k=args.top_k,
    )

    print(f"\nQuery: {result['query']}")
    print(f"Candidates examined: {result['candidates_examined']}")
    print(f"Distinct reviews: {len(result['reviews'])}")
    print(f"Candidate limit reached: {result['candidate_limit_reached']}")
    print(f"Retrieval incomplete: {result['retrieval_incomplete']}")

    for index, review in enumerate(result["reviews"], start=1):
        print(
            f"{index}. similarity={review['similarity']:.3f} | "
            f"score={review['review_score']} | "
            f"candidate_occurrences={review['candidate_occurrences']} | "
            f"review_id={review['review_id']} | "
            f"order_ids={review['order_ids']}"
        )
        print(f"   {review['document']}\n")


if __name__ == "__main__":
    main()

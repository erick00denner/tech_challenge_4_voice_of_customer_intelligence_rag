
"""Unit tests for semantic review retrieval."""

from unittest.mock import Mock

import pytest

from src.retrieve import (
    deduplicate_results,
    normalize_query,
    retrieve_reviews,
)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("produto não chegou", "produto não chegou"),
        ("  produto   não chegou  ", "produto não chegou"),
        ("atraso\nna\tentrega", "atraso na entrega"),
        ("", ""),
        ("   \n\t  ", ""),
    ],
)
def test_normalize_query(query: str, expected: str) -> None:
    """Verify query whitespace normalization."""
    assert normalize_query(query) == expected


@pytest.fixture
def sample_results() -> dict:
    """Create Chroma-like results with repeated review texts."""
    return {
        "ids": [["review_1", "review_2", "review_3", "review_4"]],
        "documents": [[
            "Produto não chegou",
            "O produto não chegou",
            "Produto não chegou!",
            "Entrega atrasada",
        ]],
        "distances": [[0.05, 0.10, 0.15, 0.20]],
        "metadatas": [[
            {
                "dedup_key": "produto nao chegou",
                "order_ids": "order_1,order_2",
                "review_score": 1,
                "review_creation_date": "2018-01-01",
                "n_chars": 18,
            },
            {
                "dedup_key": "o produto nao chegou",
                "order_ids": "order_3",
                "review_score": 1,
                "review_creation_date": "2018-01-02",
                "n_chars": 19,
            },
            {
                "dedup_key": "produto nao chegou",
                "order_ids": "order_4",
                "review_score": 1,
                "review_creation_date": "2018-01-03",
                "n_chars": 19,
            },
            {
                "dedup_key": "entrega atrasada",
                "order_ids": "order_5",
                "review_score": 2,
                "review_creation_date": "2018-01-04",
                "n_chars": 16,
            },
        ]],
    }


def test_deduplicate_results(sample_results: dict) -> None:
    """Verify repeated deduplication keys are removed."""
    reviews = deduplicate_results(sample_results, top_k=10)

    assert len(reviews) == 3
    assert [review["review_id"] for review in reviews] == [
        "review_1",
        "review_2",
        "review_4",
    ]


def test_retrieval_order(sample_results: dict) -> None:
    """Verify selected reviews preserve similarity ranking."""
    reviews = deduplicate_results(sample_results, top_k=10)

    assert [review["similarity"] for review in reviews] == pytest.approx(
        [0.95, 0.90, 0.80]
    )


def test_top_k_limit(sample_results: dict) -> None:
    """Verify retrieval respects the requested result limit."""
    reviews = deduplicate_results(sample_results, top_k=2)

    assert len(reviews) == 2
    assert [review["review_id"] for review in reviews] == [
        "review_1",
        "review_2",
    ]


def test_fewer_unique_reviews_than_top_k(sample_results: dict) -> None:
    """Verify retrieval returns available unique reviews only."""
    reviews = deduplicate_results(sample_results, top_k=10)

    assert len(reviews) == 3


def test_candidate_occurrences(sample_results: dict) -> None:
    """Count repeated text keys among retrieved candidates."""
    reviews = deduplicate_results(sample_results, top_k=10)

    assert reviews[0]["candidate_occurrences"] == 2
    assert reviews[1]["candidate_occurrences"] == 1
    assert reviews[2]["candidate_occurrences"] == 1


def test_order_ids_preserved(sample_results: dict) -> None:
    """Preserve associated order IDs in retrieved evidence."""
    reviews = deduplicate_results(sample_results, top_k=10)

    assert reviews[0]["order_ids"] == "order_1,order_2"
    assert reviews[1]["order_ids"] == "order_3"


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_empty_query(query: str) -> None:
    """Verify empty queries are rejected before vector search."""
    collection = Mock()
    model = Mock()

    with pytest.raises(ValueError, match="Query cannot be empty"):
        retrieve_reviews(query, collection, model)

    model.encode.assert_not_called()
    collection.query.assert_not_called()


@pytest.mark.parametrize("top_k", [0, -1, -10])
def test_invalid_top_k(top_k: int) -> None:
    """Verify nonpositive result limits are rejected."""
    collection = Mock()
    model = Mock()

    with pytest.raises(ValueError, match="top_k must be greater than zero"):
        retrieve_reviews("produto não chegou", collection, model, top_k=top_k)

    model.encode.assert_not_called()
    collection.query.assert_not_called()


def test_empty_collection() -> None:
    """Reject retrieval against an empty vector collection."""
    collection = Mock()
    collection.count.return_value = 0
    model = Mock()

    with pytest.raises(ValueError, match="collection is empty"):
        retrieve_reviews("produto não chegou", collection, model)

    model.encode.assert_not_called()
    collection.query.assert_not_called()


def test_retrieve_reviews_with_mocks(sample_results: dict) -> None:
    """Verify vector search, metadata and deduplication together."""
    collection = Mock()
    collection.count.return_value = 4
    collection.query.return_value = sample_results

    model = Mock()
    model.encode.return_value.tolist.return_value = [[0.1, 0.2, 0.3]]

    result = retrieve_reviews(
        "  produto   não chegou  ",
        collection,
        model,
        top_k=3,
    )

    model.encode.assert_called_once_with(
        ["produto não chegou"],
        normalize_embeddings=True,
    )

    collection.query.assert_called_once_with(
        query_embeddings=[[0.1, 0.2, 0.3]],
        n_results=4,
        include=["documents", "distances", "metadatas"],
    )

    reviews = result["reviews"]

    assert result["query"] == "produto não chegou"
    assert result["candidates_examined"] == 4
    assert len(reviews) == 3
    assert reviews[0]["review_id"] == "review_1"
    assert reviews[0]["similarity"] == pytest.approx(0.95)
    assert reviews[0]["candidate_occurrences"] == 2
    assert reviews[0]["order_ids"] == "order_1,order_2"
    assert result["candidate_limit_reached"] is True
    assert result["retrieval_incomplete"] is False


def test_adaptive_candidate_expansion() -> None:
    """Increase candidate count when initial results lack diversity."""
    collection = Mock()
    collection.count.return_value = 100

    def make_results(count: int) -> dict:
        """Generate ranked candidates with controlled text diversity."""
        keys = (
            ["repeated"] * 15
            + [f"unique_{index}" for index in range(15, count)]
        )

        return {
            "ids": [[f"review_{index}" for index in range(count)]],
            "documents": [[f"Document {index}" for index in range(count)]],
            "distances": [[index / 100 for index in range(count)]],
            "metadatas": [[
                {
                    "dedup_key": key,
                    "order_ids": f"order_{index}",
                    "review_score": 1,
                    "review_creation_date": "2018-01-01",
                    "n_chars": 20,
                }
                for index, key in enumerate(keys)
            ]],
        }

    collection.query.side_effect = [
        make_results(15),
        make_results(30),
    ]

    model = Mock()
    model.encode.return_value.tolist.return_value = [[0.1, 0.2]]

    result = retrieve_reviews(
        "produto não chegou",
        collection,
        model,
        top_k=3,
    )

    assert len(result["reviews"]) == 3
    assert result["candidates_examined"] == 30
    assert collection.query.call_count == 2
    assert result["candidate_limit_reached"] is False
    assert result["retrieval_incomplete"] is False

    assert [
        call.kwargs["n_results"]
        for call in collection.query.call_args_list
    ] == [15, 30]

    model.encode.assert_called_once()


def test_candidate_limit_reached() -> None:
    """Return available unique reviews when the candidate cap is reached."""
    collection = Mock()
    collection.count.return_value = 300

    def make_results(count: int) -> dict:
        """Generate candidates sharing the same deduplication key."""
        return {
            "ids": [[f"review_{index}" for index in range(count)]],
            "documents": [["Produto não chegou"] * count],
            "distances": [[0.05] * count],
            "metadatas": [[
                {
                    "dedup_key": "produto nao chegou",
                    "order_ids": f"order_{index}",
                    "review_score": 1,
                    "review_creation_date": "2018-01-01",
                    "n_chars": 18,
                }
                for index in range(count)
            ]],
        }

    collection.query.side_effect = [
        make_results(50),
        make_results(100),
        make_results(200),
    ]

    model = Mock()
    model.encode.return_value.tolist.return_value = [[0.1, 0.2]]

    result = retrieve_reviews(
        "produto não chegou",
        collection,
        model,
        top_k=10,
    )

    assert len(result["reviews"]) == 1
    assert result["candidates_examined"] == 200
    assert result["reviews"][0]["candidate_occurrences"] == 200
    assert result["candidate_limit_reached"] is True
    assert result["retrieval_incomplete"] is True

    assert [
        call.kwargs["n_results"]
        for call in collection.query.call_args_list
    ] == [50, 100, 200]

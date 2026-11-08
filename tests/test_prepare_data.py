
"""Unit tests for Olist review data preparation."""

import pandas as pd
import pytest

from src.prepare_data import (
    build_document,
    consolidate_reviews,
    create_dedup_key,
    has_letters,
)


@pytest.mark.parametrize(
    ("title", "comment", "expected"),
    [
        ("Muito bom", "Muito bom, recomendo", "Muito bom, recomendo"),
        ("Muito bom", "Muito bom", "Muito bom"),
        ("3", "Produto excelente", "Produto excelente"),
        ("Bom", "Bombom delicioso", "Bom Bombom delicioso"),
        ("Entrega", "Produto danificado", "Entrega Produto danificado"),
        (
            "Ótimo Produto!",
            "Ótimo produto, chegou rápido",
            "Ótimo produto, chegou rápido",
        ),
        ("Muito bom.", "Muito bom, recomendo", "Muito bom, recomendo"),
        ("3", "", ""),
        ("Entrega rápida", "", "Entrega rápida"),
    ],
)
def test_build_document(title: str, comment: str, expected: str) -> None:
    """Verify title and comment combination rules."""
    row = pd.Series({
        "review_comment_title": title,
        "review_comment_message": comment,
    })

    assert build_document(row) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Muito bom!", "muito bom"),
        ("MUITO BOM", "muito bom"),
        ("Ótimo produto.", "otimo produto"),
        ("Entrega\nrápida", "entrega rapida"),
        ("Péssimo!!!", "pessimo"),
    ],
)
def test_create_dedup_key(text: str, expected: str) -> None:
    """Verify normalization of retrieval deduplication keys."""
    assert create_dedup_key(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ótimo", True),
        ("A", True),
        ("123", False),
        ("!!!", False),
        ("", False),
    ],
)
def test_has_letters(text: str, expected: bool) -> None:
    """Verify Unicode-aware detection of alphabetic characters."""
    assert has_letters(text) is expected


def test_consolidate_reviews() -> None:
    """Verify repeated review IDs preserve all associated orders."""
    reviews = pd.DataFrame({
        "review_id": ["review_1", "review_1", "review_2"],
        "order_id": ["order_2", "order_1", "order_3"],
        "review_score": [5, 5, 3],
    })

    result = consolidate_reviews(reviews)

    assert len(result) == 2
    assert result["review_id"].is_unique

    orders = result.set_index("review_id")["order_ids"]

    assert orders["review_1"] == "order_1,order_2"
    assert orders["review_2"] == "order_3"

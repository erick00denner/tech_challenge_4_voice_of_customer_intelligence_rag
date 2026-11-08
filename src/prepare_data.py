
"""Prepare Olist customer reviews for RAG indexing."""

from pathlib import Path
import re
import unicodedata

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT_DIR / "data/raw/olist_order_reviews_dataset.csv"
OUTPUT_PATH = ROOT_DIR / "data/processed/olist_reviews_clean.csv"


def normalize_text(value: object) -> str:
    """Normalize whitespace while preserving the original text."""
    if pd.isna(value):
        return ""

    return " ".join(str(value).split())


def build_document(row: pd.Series) -> str:
    """Combine meaningful titles and comments without repeated prefixes."""
    title = normalize_text(row["review_comment_title"])
    comment = normalize_text(row["review_comment_message"])

    if not has_letters(title):
        return comment

    if not comment:
        return title

    title_prefix = title.rstrip(".,!?;: ").casefold()
    comment_key = comment.casefold()

    if comment_key == title_prefix:
        return comment

    if any(
        comment_key.startswith(title_prefix + separator)
        for separator in (" ", ",", ".", "!", "?", ":", ";")
    ):
        return comment

    return f"{title} {comment}"



def create_dedup_key(text: str) -> str:
    """Create an accent-insensitive key for retrieval deduplication."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(
        char for char in normalized
        if not unicodedata.combining(char)
    )
    without_punctuation = re.sub(
        r"[^\w\s]", " ", without_accents
    )

    return " ".join(without_punctuation.split())


def has_letters(text: str) -> bool:
    """Check whether the document contains at least one Unicode letter."""
    return any(char.isalpha() for char in text)


def consolidate_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """Merge repeated review IDs while preserving associated order IDs."""
    orders = (
        df.groupby("review_id")["order_id"]
        .agg(lambda values: ",".join(sorted(set(values))))
        .rename("order_ids")
    )

    unique_reviews = df.drop_duplicates("review_id").copy()

    return unique_reviews.merge(
        orders, on="review_id", how="left", validate="one_to_one"
    )


def prepare_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """Build and validate the dataset used for RAG indexing."""
    reviews = df.copy()

    reviews["document"] = reviews.apply(build_document, axis=1)
    reviews = reviews[reviews["document"].ne("")].copy()

    print(f"Eligible rows: {len(reviews):,}")

    reviews = consolidate_reviews(reviews)
    print(f"Unique reviews: {len(reviews):,}")

    without_letters = ~reviews["document"].map(has_letters)
    print(f"Documents without letters: {without_letters.sum():,}")

    reviews = reviews.loc[~without_letters].copy()

    reviews["n_chars"] = reviews["document"].str.len()
    reviews["dedup_key"] = reviews["document"].map(create_dedup_key)

    columns = [
        "review_id",
        "order_ids",
        "review_score",
        "review_creation_date",
        "n_chars",
        "dedup_key",
        "document",
    ]

    result = reviews[columns].reset_index(drop=True)

    assert result["review_id"].is_unique
    assert result["document"].str.len().gt(0).all()
    assert result["document"].map(has_letters).all()

    return result


def main() -> None:
    """Load raw reviews and export the prepared RAG dataset."""
    reviews = pd.read_csv(INPUT_PATH)
    prepared = prepare_reviews(reviews)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(OUTPUT_PATH, index=False)

    print(f"Final documents: {len(prepared):,}")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

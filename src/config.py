"""Shared paths and names for the index, retrieval and generation stages."""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CHROMA_PATH = ROOT_DIR / "data/chroma"

COLLECTION_NAME = "olist_reviews"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

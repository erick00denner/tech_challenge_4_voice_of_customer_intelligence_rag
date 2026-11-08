"""Download the Olist customer reviews dataset from Kaggle."""

from pathlib import Path
import shutil

import kagglehub


DATASET = "olistbr/brazilian-ecommerce"
FILENAME = "olist_order_reviews_dataset.csv"
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def download_dataset() -> Path:
    """Download the Olist dataset and return its local directory."""
    return Path(kagglehub.dataset_download(DATASET))


def copy_reviews(source_dir: Path) -> Path:
    """Copy the reviews CSV to the project's raw data directory."""
    source = source_dir / FILENAME
    destination = DATA_DIR / FILENAME

    if not source.is_file():
        raise FileNotFoundError(f"File not found: {source}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

    return destination


def main() -> None:
    """Download the dataset and copy the reviews CSV."""
    source_dir = download_dataset()
    destination = copy_reviews(source_dir)

    print(f"Dataset saved to: {destination}")


if __name__ == "__main__":
    main()

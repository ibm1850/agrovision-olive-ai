from __future__ import annotations

import argparse
from pathlib import Path

try:
    from kaggle.api.kaggle_api_extended import KaggleApi
except ImportError as exc:
    raise SystemExit(
        "The `kaggle` package is required. Install it with `pip install kaggle`."
    ) from exc

DEFAULT_DATASETS = [
    "vipoooool/new-plant-diseases-dataset",
    "fpeccia/olives-dataset",
]


def download_dataset(api: KaggleApi, slug: str, output_root: Path) -> None:
    target_dir = output_root / slug.replace("/", "_")
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {slug} -> {target_dir}")
    api.dataset_download_files(slug, path=target_dir, unzip=True, quiet=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download plant/olive datasets from Kaggle.")
    parser.add_argument(
        "--dataset",
        action="append",
        dest="datasets",
        help="Kaggle dataset slug (e.g. username/dataset-name). Use multiple --dataset entries.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Output directory for downloaded datasets.",
    )
    args = parser.parse_args()

    datasets = args.datasets if args.datasets else DEFAULT_DATASETS
    output_root = args.output
    output_root.mkdir(parents=True, exist_ok=True)

    api = KaggleApi()
    api.authenticate()

    for slug in datasets:
        try:
            download_dataset(api, slug, output_root)
        except Exception as exc:
            print(f"[WARN] Failed to download {slug}: {exc}")

    print("Dataset download process completed.")


if __name__ == "__main__":
    main()


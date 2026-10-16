"""Download the Olist dataset from Kaggle into data/raw/."""

import shutil
from pathlib import Path

import kagglehub

from common.config import load_config


def main() -> None:
    cfg = load_config()
    src = Path(kagglehub.dataset_download(cfg.data.kaggle_dataset))
    cfg.data.raw_dir.mkdir(parents=True, exist_ok=True)
    for csv in sorted(src.glob("*.csv")):
        shutil.copy2(csv, cfg.data.raw_dir / csv.name)
        print(f"{csv.name:50s} {csv.stat().st_size / 1e6:8.1f} MB")
    print(f"-> {cfg.data.raw_dir}")


if __name__ == "__main__":
    main()

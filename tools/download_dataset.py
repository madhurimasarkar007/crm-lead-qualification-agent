"""
Download the UCI Bank Marketing dataset to .tmp/bank-full.csv.
Idempotent: skips download if the file already exists with the correct row count.
"""

import os
import sys
import zipfile
import requests
from pathlib import Path

DATASET_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/00222/bank.zip"
EXPECTED_ROWS = 45211
EXPECTED_COLUMNS = [
    "age", "job", "marital", "education", "default", "balance",
    "housing", "loan", "contact", "day", "month", "duration",
    "campaign", "pdays", "previous", "poutcome", "y",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
ZIP_PATH = TMP_DIR / "bank.zip"
CSV_PATH = TMP_DIR / "bank-full.csv"


def check_existing():
    if not CSV_PATH.exists():
        return False
    try:
        import pandas as pd
        df = pd.read_csv(CSV_PATH, sep=";", nrows=5)
        missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
        if missing:
            print(f"Existing file missing columns: {missing}. Re-downloading.")
            return False
        # Count rows without loading full file into memory
        with open(CSV_PATH) as f:
            row_count = sum(1 for _ in f) - 1  # subtract header
        if row_count == EXPECTED_ROWS:
            print(f"Dataset already present: {CSV_PATH} ({row_count:,} rows). Skipping download.")
            return True
        print(f"Row count mismatch ({row_count} vs {EXPECTED_ROWS}). Re-downloading.")
        return False
    except Exception as e:
        print(f"Could not verify existing file ({e}). Re-downloading.")
        return False


def download():
    TMP_DIR.mkdir(exist_ok=True)
    print(f"Downloading dataset from UCI...")
    try:
        response = requests.get(DATASET_URL, stream=True, timeout=60)
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0
        with open(ZIP_PATH, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
        print(f"Downloaded {downloaded / 1024:.1f} KB -> {ZIP_PATH}")
    except requests.RequestException as e:
        print(f"ERROR: Download failed: {e}", file=sys.stderr)
        sys.exit(1)


def unzip():
    print(f"Unzipping {ZIP_PATH}...")
    try:
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            zf.extractall(TMP_DIR)
        print(f"Extracted to {TMP_DIR}/")
    except zipfile.BadZipFile as e:
        print(f"ERROR: Bad zip file: {e}", file=sys.stderr)
        sys.exit(1)

    if not CSV_PATH.exists():
        print(f"ERROR: Expected {CSV_PATH} after unzip but not found.", file=sys.stderr)
        print(f"Files in .tmp/: {list(TMP_DIR.iterdir())}", file=sys.stderr)
        sys.exit(1)


def verify():
    import pandas as pd
    try:
        df = pd.read_csv(CSV_PATH, sep=";")
    except Exception as e:
        print(f"ERROR: Could not read CSV: {e}", file=sys.stderr)
        sys.exit(1)

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        print(f"ERROR: Missing expected columns: {missing}", file=sys.stderr)
        sys.exit(1)

    if len(df) != EXPECTED_ROWS:
        print(f"WARNING: Expected {EXPECTED_ROWS} rows, got {len(df)}.")
    else:
        print(f"Verified: {len(df):,} rows, {len(df.columns)} columns.")

    print(f"Columns: {list(df.columns)}")
    print(f"Dataset ready at: {CSV_PATH}")


def main():
    if check_existing():
        sys.exit(0)
    download()
    unzip()
    verify()
    print("\nDone.")


if __name__ == "__main__":
    main()

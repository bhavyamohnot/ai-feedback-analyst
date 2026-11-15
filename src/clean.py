"""Step 2 - Clean: keep reviews with enough signal to analyse.

    python src/clean.py

Rules (each one is printed with how many rows it removed):
  1. drop exact duplicate texts per app (copy-paste spam)
  2. drop reviews under 5 words ("good", "nice app") - no theme to extract
  3. drop mostly non-English text (< 80% ASCII characters)
Output: data/clean_reviews.csv
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
MIN_WORDS = 5
MIN_ASCII = 0.8


def ascii_share(text: str) -> float:
    return sum(c.isascii() for c in text) / max(len(text), 1)


def main():
    df = pd.read_csv(DATA / "raw_reviews.csv").fillna({"text": "", "app_version": ""})
    df["text"] = df["text"].str.strip()
    print(f"start: {len(df)}")

    steps = [
        ("duplicate text", lambda d: ~d.duplicated(["app", "text"])),
        (f"under {MIN_WORDS} words", lambda d: d["text"].str.split().str.len() >= MIN_WORDS),
        ("non-English", lambda d: d["text"].map(ascii_share) >= MIN_ASCII),
    ]
    for label, keep in steps:
        before = len(df)
        df = df[keep(df)]
        print(f"  - {label}: removed {before - len(df)}")

    df = df.assign(words=df["text"].str.split().str.len()).sort_values(["app", "date"])
    df.to_csv(DATA / "clean_reviews.csv", index=False, encoding="utf-8")
    print(f"kept: {len(df)}  ->  {df.groupby('app').size().to_dict()}")


if __name__ == "__main__":
    main()

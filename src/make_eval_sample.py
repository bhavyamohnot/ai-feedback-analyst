"""Pick the 100 reviews you will hand-label as the answer key (the "gold set").

    python src/make_eval_sample.py

- 60 Notion + 40 Evernote, matching each app's share of the clean data (2,441 vs 1,667).
- Random within each app, so the set looks like the real data (not just the angry reviews).
- Leaves out the 145 reviews used to design the themes: testing on reviews you studied
  would make the AI look better than it really is (that's called "leakage").
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"


def taxonomy_sample(df: pd.DataFrame) -> pd.DataFrame:
    """Re-create the exact sample read while drafting the themes."""
    d = df[df.words >= 10]
    return pd.concat([
        d[(d.app == "Notion") & (d.rating <= 2)].sample(45, random_state=1),
        d[(d.app == "Notion") & (d.rating == 3)].sample(15, random_state=1),
        d[(d.app == "Notion") & (d.rating >= 4)].sample(25, random_state=1),
        d[(d.app == "Evernote") & (d.rating <= 2)].sample(45, random_state=1),
        d[(d.app == "Evernote") & (d.rating >= 3)].sample(15, random_state=1),
    ])


def main():
    df = pd.read_csv(DATA / "clean_reviews.csv")
    pool = df[~df.review_id.isin(taxonomy_sample(df).review_id)]
    sample = pd.concat([
        pool[pool.app == "Notion"].sample(60, random_state=42),
        pool[pool.app == "Evernote"].sample(40, random_state=42),
    ]).sample(frac=1, random_state=7)  # shuffle so apps are mixed while labelling
    sample.to_csv(DATA / "eval_sample.csv", index=False, encoding="utf-8")
    print(f"saved {len(sample)} reviews -> data/eval_sample.csv")
    print("stars:", sample.rating.value_counts().sort_index().to_dict())


if __name__ == "__main__":
    main()

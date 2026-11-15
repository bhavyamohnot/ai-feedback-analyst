"""Step 1 - Collect: pull Play Store reviews for each app and save them raw.

    python src/collect.py

Output: data/raw_reviews.csv (one row per review, untouched text).
"""
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from google_play_scraper import Sort, reviews

APPS = {"notion.id": "Notion", "com.evernote": "Evernote"}
MONTHS_BACK = 12
MAX_PER_APP = 6000
OUT = Path(__file__).resolve().parent.parent / "data" / "raw_reviews.csv"


def pull(app_id: str, since: datetime) -> list[dict]:
    """Page through newest reviews until we pass the cutoff date or hit the cap."""
    rows, token = [], None
    while len(rows) < MAX_PER_APP:
        batch, token = reviews(app_id, lang="en", country="in", sort=Sort.NEWEST,
                               count=200, continuation_token=token)
        if not batch:
            break
        rows += [r for r in batch if r["at"] >= since]
        if batch[-1]["at"] < since or token is None:
            break
    return rows


def main():
    since = datetime.now() - timedelta(days=30 * MONTHS_BACK)
    frames = []
    for app_id, name in APPS.items():
        rows = pull(app_id, since)
        df = pd.DataFrame([{
            "review_id": r["reviewId"],
            "app": name,
            "date": r["at"].date().isoformat(),
            "rating": r["score"],
            "text": r["content"] or "",
            "thumbs_up": r["thumbsUpCount"],
            "app_version": r.get("reviewCreatedVersion") or "",
            "company_replied": bool(r.get("replyContent")),
        } for r in rows])
        print(f"{name}: {len(df)} reviews from {df['date'].min()} to {df['date'].max()}")
        frames.append(df)
    out = pd.concat(frames).drop_duplicates("review_id")
    OUT.parent.mkdir(exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"saved {len(out)} rows -> {OUT}")


if __name__ == "__main__":
    main()

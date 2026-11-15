"""Step 7 - Weekly update + digest data (run by the n8n workflow every Monday, or by hand).

    python src/weekly.py            # fetch new reviews -> clean -> tag -> analyse -> compare weeks
    python src/weekly.py --no-fetch # just recompute the comparison on the data we already have

Prints one JSON object (and saves it to data/digest/) with, per app:
  - reviews this week vs. the average week of the previous 4 weeks
  - complaint topics this week, and SPIKES: a topic whose complaint share is 1.5x+ its 4-week average
    (with at least 5 complaints, so 1 -> 2 complaints doesn't count as a spike)
  - most-liked new complaints (quotes) and newly named competitors
n8n turns this JSON into a written digest with an LLM and sends it.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "src"))
MODEL = "gemini-3.5-flash-lite"
SPIKE_RATIO, SPIKE_MIN = 1.5, 5


def run(script, *args):
    """Run one pipeline step; its log goes to stderr so stdout stays pure JSON for n8n."""
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "src" / script), *args],
                       capture_output=True, text=True, encoding="utf-8")
    print(r.stdout[-1500:], r.stderr[-1500:], sep="\n", file=sys.stderr)
    if r.returncode:
        raise RuntimeError(f"{script} failed")


def fetch_new():
    """Pull reviews newer than the latest one we have and append them to raw_reviews.csv."""
    from google_play_scraper import Sort, reviews
    from collect import APPS
    raw = pd.read_csv(DATA / "raw_reviews.csv")
    added = 0
    for app_id, name in APPS.items():
        since = pd.to_datetime(raw[raw.app == name].date).max().to_pydatetime() - timedelta(days=1)
        rows, token = [], None
        while True:
            batch, token = reviews(app_id, lang="en", country="in", sort=Sort.NEWEST, count=200,
                                   continuation_token=token)
            rows += [r for r in batch if r["at"] >= since]
            if not batch or batch[-1]["at"] < since or token is None:
                break
        new = pd.DataFrame([{"review_id": r["reviewId"], "app": name, "date": r["at"].date().isoformat(),
                             "rating": r["score"], "text": r["content"] or "", "thumbs_up": r["thumbsUpCount"],
                             "app_version": r.get("reviewCreatedVersion") or "",
                             "company_replied": bool(r.get("replyContent"))} for r in rows])
        new = new[~new.review_id.isin(raw.review_id)] if len(new) else new
        added += len(new)
        raw = pd.concat([raw, new])
    raw.to_csv(DATA / "raw_reviews.csv", index=False, encoding="utf-8")
    return added


def update_index():
    """Embed only reviews that aren't in the search index yet (local model, free)."""
    import numpy as np
    import rag
    clean = pd.read_csv(DATA / "clean_reviews.csv")
    ids = pd.read_csv(rag.RAG / "ids.csv")
    new = clean[~clean.review_id.isin(ids.review_id)]
    if new.empty:
        return 0
    vecs = rag.embed([f"{a} review ({r} stars): {t}" for a, r, t in zip(new.app, new.rating, new.text)], "passage")
    old = np.load(rag.RAG / "embeddings.npy")
    np.save(rag.RAG / "embeddings.npy", np.vstack([old, vecs.astype(np.float16)]))
    pd.concat([ids, new[["review_id"]]]).to_csv(rag.RAG / "ids.csv", index=False)
    return len(new)


def compare_weeks():
    from analyze import load
    reviews, points = load(MODEL)
    end = reviews.date.max().normalize() + timedelta(days=1)
    week_start, base_start = end - timedelta(days=7), end - timedelta(days=35)
    neg = points[(points.type == "negative") & ~points.topic.isin(["overall", "other"])]
    out = {"generated": datetime.now().isoformat(timespec="minutes"),
           "week": f"{week_start:%d %b} - {end - timedelta(days=1):%d %b %Y}", "apps": {}}
    for app in sorted(reviews.app.unique()):
        R = reviews[reviews.app == app]
        wk, base = R[R.date >= week_start], R[(R.date >= base_start) & (R.date < week_start)]
        N = neg[neg.app == app]
        n_wk = N[N.review_id.isin(wk.review_id)].groupby("topic").size()
        n_base = N[N.review_id.isin(base.review_id)].groupby("topic").size()
        topics = []
        for t in sorted(set(n_wk.index) | set(n_base.index)):
            share_wk = n_wk.get(t, 0) / max(len(wk), 1)
            share_base = n_base.get(t, 0) / max(len(base), 1)
            topics.append({"topic": t, "complaints_this_week": int(n_wk.get(t, 0)),
                           "share_this_week": round(share_wk, 3), "share_prev_4_weeks": round(share_base, 3),
                           "spike": bool(n_wk.get(t, 0) >= SPIKE_MIN and share_wk >= SPIKE_RATIO * max(share_base, 0.01))})
        topics.sort(key=lambda x: -x["complaints_this_week"])
        q = N[N.review_id.isin(wk.review_id)].sort_values(["thumbs_up", "sev_w"], ascending=False).head(5)
        sw = wk[wk.switching_to.fillna("").str.strip() != ""].switching_to.value_counts().head(5)
        out["apps"][app] = {
            "reviews_this_week": len(wk), "avg_reviews_per_week_prev_4": round(len(base) / 4, 1),
            "avg_stars_this_week": round(wk.rating.mean(), 2) if len(wk) else None,
            "avg_stars_prev_4_weeks": round(base.rating.mean(), 2) if len(base) else None,
            "leaving_this_week": int(wk.churn_signal.sum()),
            "spikes": [t["topic"] for t in topics if t["spike"]],
            "top_complaints": topics[:6],
            "top_quotes": [{"topic": x.topic, "quote": x.quote, "stars": int(x.rating), "likes": int(x.thumbs_up)}
                           for x in q.itertuples()],
            "switching_to": sw.to_dict(),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args()
    steps = {}
    if not args.no_fetch:
        steps["new_raw_reviews"] = fetch_new()
        run("clean.py")
        run("tag.py", "--set", "all", "--model", MODEL)
        run("analyze.py")
        steps["newly_indexed"] = update_index()
    digest = compare_weeks() | {"pipeline": steps}
    (DATA / "digest").mkdir(exist_ok=True)
    (DATA / "digest" / f"digest_{datetime.now():%Y-%m-%d}.json").write_text(json.dumps(digest, indent=2), encoding="utf-8")
    print(json.dumps(digest, ensure_ascii=False))


if __name__ == "__main__":
    main()

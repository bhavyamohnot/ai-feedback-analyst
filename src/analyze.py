"""Step 5 - Analyse: turn 4,108 tagged reviews into answers a product team can act on.

    python src/analyze.py                         # uses the Flash-Lite tags
    python src/analyze.py --model gemini-3.8-flash

Outputs (data/analysis/):
  topic_map.csv      every app x topic: how many reviews praise it, complain about it, ask for something
  fix_first.csv      complaints ranked by impact score (volume x severity), with churn share and top quotes
  requests.csv       what users ask for, by topic, with example quotes
  switching.csv      which competitors users say they are moving to
  monthly.csv        complaints per topic per month (to spot when a problem started)

Counting rule: a review counts once per topic+type, even if it mentions it twice.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "analysis"
SEV_WEIGHT = {"low": 1, "medium": 2, "high": 3}  # how much a complaint hurts the user


def load(model):
    reviews = pd.read_csv(DATA / "clean_reviews.csv", parse_dates=["date"])
    tags = [json.loads(x) for x in (DATA / f"tags_all_{model.replace('/', '_')}.jsonl").open(encoding="utf-8")]
    review_tags = pd.DataFrame([{k: v for k, v in t.items() if k != "points"} for t in tags])
    reviews = reviews.merge(review_tags, on="review_id", how="inner")
    points = pd.DataFrame([{"review_id": t["review_id"], **p} for t in tags for p in t["points"]])
    points = points.merge(reviews[["review_id", "app", "date", "rating", "thumbs_up", "churn_signal", "text"]],
                          on="review_id")
    # one row per review x topic x type (dedupe repeats), keeping the most severe version
    points["sev_w"] = points.severity.map(SEV_WEIGHT).fillna(0)
    points = points.sort_values("sev_w", ascending=False).drop_duplicates(["review_id", "topic", "type"])
    return reviews, points


def topic_map(reviews, points):
    n = reviews.groupby("app").size()
    t = points.pivot_table(index=["app", "topic"], columns="type", values="review_id", aggfunc="count", fill_value=0)
    t = t.reindex(columns=["positive", "negative", "neutral", "request"], fill_value=0).reset_index()
    t["reviews_in_app"] = t.app.map(n)
    t["mention_pct"] = (t[["positive", "negative", "neutral", "request"]].sum(axis=1) / t.reviews_in_app).round(3)
    # net sentiment: +100 = everyone who has an opinion on this topic loves it, -100 = everyone hates it
    opin = t.positive + t.negative
    t["net_sentiment"] = ((t.positive - t.negative) / opin.where(opin > 0) * 100).round(0)
    return t.sort_values(["app", "negative"], ascending=[True, False])


def top_quotes(df, k=3):
    best = df.sort_values(["thumbs_up", "sev_w"], ascending=False).head(k)
    return " | ".join(f'"{q}" ({int(u)} likes)' for q, u in zip(best.quote, best.thumbs_up))


def fix_first(reviews, points):
    n = reviews.groupby("app").size()
    neg = points[(points.type == "negative") & (~points.topic.isin(["overall", "other"]))]
    rows = []
    for (app, topic), g in neg.groupby(["app", "topic"]):
        rows.append({
            "app": app, "topic": topic,
            "complaints": len(g),
            "pct_of_reviews": round(len(g) / n[app], 3),
            "high_severity_pct": round((g.severity == "high").mean(), 2),
            # impact = how many complain x how badly it hurts (low 1, medium 2, high 3)
            "impact_score": int(g.sev_w.sum()),
            "churn_pct": round(g.churn_signal.mean(), 2),  # of these complainers, how many say they're leaving
            "avg_stars": round(g.rating.mean(), 2),
            "likes_on_reviews": int(g.thumbs_up.sum()),  # other users agreeing
            "top_quotes": top_quotes(g),
        })
    f = pd.DataFrame(rows).sort_values(["app", "impact_score"], ascending=[True, False])
    f.insert(2, "rank", f.groupby("app").impact_score.rank(ascending=False, method="first").astype(int))
    return f


def requests(points):
    r = points[points.type == "request"]
    return (r.groupby(["app", "topic"])
             .apply(lambda g: pd.Series({"requests": len(g), "examples": top_quotes(g, 4)}), include_groups=False)
             .reset_index().sort_values(["app", "requests"], ascending=[True, False]))


SWITCH_NAMES = {"onenote": "OneNote", "microsoft onenote": "OneNote", "google keep": "Google Keep", "keep": "Google Keep",
                "obsidian": "Obsidian", "notion": "Notion", "joplin": "Joplin", "samsung notes": "Samsung Notes",
                "apple notes": "Apple Notes", "evernote": "Evernote", "anytype": "Anytype", "upnote": "UpNote",
                "simplenote": "Simplenote", "google docs": "Google Docs", "standard notes": "Standard Notes",
                "zoho notebook": "Zoho Notebook", "craft": "Craft", "coda": "Coda", "clickup": "ClickUp",
                "todoist": "Todoist", "trello": "Trello", "affine": "AFFiNE", "logseq": "Logseq"}


VAGUE = {"another app", "alternative", "alternatives", "google", "other apps", "another", "other", "competitor",
          "a different app", "other app", "something else", "competitors", "free app", "elsewhere", "browser", "browser version", "web version", "website",
          "another application"}  # no app actually named


def switching(reviews):
    s = reviews[reviews.switching_to.fillna("").str.strip() != ""].copy()
    s["to"] = s.switching_to.str.strip().str.lower()
    s = s[~s.to.isin(VAGUE)]
    s["to"] = s.to.map(lambda x: SWITCH_NAMES.get(x, x.title()))
    return s.groupby(["app", "to"]).size().rename("reviews").reset_index().sort_values(
        ["app", "reviews"], ascending=[True, False])


def monthly(points):
    neg = points[points.type == "negative"].copy()
    neg["month"] = neg.date.dt.to_period("M").astype(str)
    return neg.pivot_table(index=["app", "month"], columns="topic", values="review_id", aggfunc="count",
                           fill_value=0).reset_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.5-flash-lite")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    reviews, points = load(args.model)

    tm, ff, rq, sw, mo = topic_map(reviews, points), fix_first(reviews, points), requests(points), \
        switching(reviews), monthly(points)
    for name, df in [("topic_map", tm), ("fix_first", ff), ("requests", rq), ("switching", sw), ("monthly", mo)]:
        df.to_csv(OUT / f"{name}.csv", index=False)

    pd.set_option("display.width", 200, "display.max_colwidth", 90)
    for app, g in reviews.groupby("app"):
        print(f"\n=== {app}: {len(g):,} reviews | avg {g.rating.mean():.2f} stars | "
              f"saying they're leaving: {g.churn_signal.mean():.0%}")
        print("overall sentiment:", (g.overall_sentiment.value_counts(normalize=True).round(2) * 100)
              .astype(int).astype(str).add("%").to_dict())
        print("\nHow users feel about each topic (reviews):")
        print(tm[tm.app == app][["topic", "positive", "negative", "request", "mention_pct", "net_sentiment"]]
              .to_string(index=False))
        print("\nFix first (impact = complaints x severity):")
        print(ff[ff.app == app].head(6)[["rank", "topic", "complaints", "pct_of_reviews", "high_severity_pct",
                                         "impact_score", "churn_pct", "avg_stars"]].to_string(index=False))
        print("\nTop requests:")
        print(rq[rq.app == app].head(5)[["topic", "requests", "examples"]].to_string(index=False))
        print("\nSwitching to:", dict(zip(*sw[sw.app == app].head(8)[["to", "reviews"]].T.values)))
    print(f"\nCSVs written to {OUT}")


if __name__ == "__main__":
    main()

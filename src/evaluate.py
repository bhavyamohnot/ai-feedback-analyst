"""Step 4 - Evaluate: how often does each AI model agree with the human answer key?

    python src/evaluate.py                                  # compare every model that tagged the eval set
    python src/evaluate.py --model gemini-3.8-flash --show 20   # one model + its disagreements

Metrics (all on the 100 hand-labelled reviews):
- Theme hit rate: the human's main theme is one of the AI's 1-2 themes.
- Theme exact: the AI's FIRST theme equals the human's main theme (stricter).
- Sentiment accuracy.
- Churn precision: when the AI says "leaving", how often is that true?
- Churn recall: of the people really leaving, how many did the AI catch?
With --model it also prints every disagreement, so you can see WHY it was wrong (error analysis).
"""
import argparse
import json
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"


def score(safe_name: str) -> tuple[dict, pd.DataFrame]:
    gold = pd.read_csv(DATA / "gold_labels.csv").fillna({"theme_2": ""})
    lines = (DATA / f"tags_eval_{safe_name}.jsonl").read_text(encoding="utf-8").splitlines()
    pred = pd.DataFrame([json.loads(x) for x in lines]).drop_duplicates("review_id", keep="last")
    text = pd.read_csv(DATA / "eval_sample.csv")[["review_id", "app", "rating", "text"]]
    df = gold.merge(pred, on="review_id", how="inner").merge(text, on="review_id")

    df["theme_hit"] = df.apply(lambda r: r.theme_1 in r.themes, axis=1)
    df["theme_exact"] = df.apply(lambda r: len(r.themes) > 0 and r.themes[0] == r.theme_1, axis=1)
    df["sent_ok"] = df.sentiment_x == df.sentiment_y
    gold_churn, ai_churn = df.churn_signal_x.astype(bool), df.churn_signal_y.astype(bool)
    tp = (gold_churn & ai_churn).sum()
    metrics = {
        "model": safe_name.replace("openai_", "openai/"),
        "n": len(df),
        "theme_hit": df.theme_hit.mean(),
        "theme_exact": df.theme_exact.mean(),
        "sentiment": df.sent_ok.mean(),
        "churn_precision": tp / ai_churn.sum() if ai_churn.sum() else float("nan"),
        "churn_recall": tp / gold_churn.sum() if gold_churn.sum() else float("nan"),
    }
    (DATA / f"eval_{safe_name}.json").write_text(json.dumps(metrics, indent=2, default=float))
    return metrics, df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="all")
    ap.add_argument("--show", type=int, default=15, help="how many disagreements to print")
    args = ap.parse_args()

    if not (DATA / "gold_labels.csv").exists():
        raise SystemExit("No hand labels yet - finish labelling in the app first (data/gold_labels.csv).")

    if args.model == "all":
        names = sorted(p.stem.removeprefix("tags_eval_") for p in DATA.glob("tags_eval_*.jsonl"))
        table = pd.DataFrame([score(n)[0] for n in names]).sort_values("theme_hit", ascending=False)
        pct = ["theme_hit", "theme_exact", "sentiment", "churn_precision", "churn_recall"]
        print(table.to_string(index=False, formatters={c: "{:.0%}".format for c in pct}))
        return

    m, df = score(args.model.replace("/", "_"))
    print(f"\n{m['model']}: {m['n']} reviews compared")
    for k in ["theme_hit", "theme_exact", "sentiment", "churn_precision", "churn_recall"]:
        print(f"  {k:16} {m[k]:6.1%}")
    bad = df[~df.theme_hit | ~df.sent_ok]
    print(f"\nDisagreements ({len(bad)}), first {args.show}:")
    for r in bad.head(args.show).itertuples():
        print(f"- [{r.app} {r.rating}*] {r.text[:140]}")
        print(f"    you: {r.theme_1}/{r.sentiment_x}   AI: {'+'.join(r.themes)}/{r.sentiment_y}")


if __name__ == "__main__":
    main()

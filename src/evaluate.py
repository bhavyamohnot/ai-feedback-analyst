"""Step 4 - Evaluate: how often does the AI agree with the human answer key?

    python src/evaluate.py --model claude-haiku-5-5

Metrics (all on the 100 hand-labelled reviews):
- Theme hit rate: the human's main theme is one of the AI's 1-2 themes.
- Theme exact: the AI's FIRST theme equals the human's main theme (stricter).
- Sentiment accuracy.
- Churn precision: when the AI says "leaving", how often is that true?
- Churn recall: of the people really leaving, how many did the AI catch?
It also prints every disagreement, so you can see WHY it was wrong (error analysis).
"""
import argparse
import json
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--show", type=int, default=15, help="how many disagreements to print")
    args = ap.parse_args()

    gold = pd.read_csv(DATA / "gold_labels.csv").fillna({"theme_2": ""})
    lines = (DATA / f"tags_eval_{args.model}.jsonl").read_text(encoding="utf-8").splitlines()
    pred = pd.DataFrame([json.loads(x) for x in lines]).drop_duplicates("review_id", keep="last")
    text = pd.read_csv(DATA / "eval_sample.csv")[["review_id", "app", "rating", "text"]]
    df = gold.merge(pred, on="review_id", how="inner").merge(text, on="review_id")

    df["theme_hit"] = df.apply(lambda r: r.theme_1 in r.themes, axis=1)
    df["theme_exact"] = df.apply(lambda r: r.themes[0] == r.theme_1, axis=1)
    df["sent_ok"] = df.sentiment_x == df.sentiment_y
    gold_churn, ai_churn = df.churn_signal_x.astype(bool), df.churn_signal_y.astype(bool)
    tp = (gold_churn & ai_churn).sum()
    precision = tp / ai_churn.sum() if ai_churn.sum() else float("nan")
    recall = tp / gold_churn.sum() if gold_churn.sum() else float("nan")

    print(f"\n{args.model}: {len(df)} reviews compared")
    print(f"  theme hit rate   {df.theme_hit.mean():6.1%}")
    print(f"  theme exact      {df.theme_exact.mean():6.1%}")
    print(f"  sentiment        {df.sent_ok.mean():6.1%}")
    print(f"  churn precision  {precision:6.1%}   ({ai_churn.sum()} flagged by AI)")
    print(f"  churn recall     {recall:6.1%}   ({gold_churn.sum()} truly leaving)")

    bad = df[~df.theme_hit | ~df.sent_ok]
    print(f"\nDisagreements ({len(bad)}), first {args.show}:")
    for r in bad.head(args.show).itertuples():
        print(f"- [{r.app} {r.rating}*] {r.text[:140]}")
        print(f"    you: {r.theme_1}/{r.sentiment_x}   AI: {'+'.join(r.themes)}/{r.sentiment_y}")

    summary = {"model": args.model, "n": len(df), "theme_hit": df.theme_hit.mean(), "theme_exact": df.theme_exact.mean(),
               "sentiment": df.sent_ok.mean(), "churn_precision": precision, "churn_recall": recall}
    (DATA / f"eval_{args.model}.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

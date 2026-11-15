"""Step 4 - Evaluate: how well does each AI model match the human answer key?

    python src/evaluate.py                                    # compare every model that tagged the eval set
    python src/evaluate.py --model gemini-3.8-flash --show 15  # one model: per-topic scores + disagreements

Each review has a LIST of points (topic + type), so we compare lists:
- Topic recall:     of the topics YOU tagged, how many did the AI also find?   (did it miss things?)
- Topic precision:  of the topics the AI tagged, how many did you also tag?    (did it invent things?)
- Topic F1:         one number combining recall and precision (their harmonic mean).
- Pair recall / precision / F1: the same, but topic AND type must both match (e.g. performance + negative).
- Overall sentiment accuracy, churn precision and churn recall.
Counting rule: within one review, each topic (and each topic+type pair) counts once.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"


def read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def prf(tp, n_pred, n_gold):
    p = tp / n_pred if n_pred else float("nan")
    r = tp / n_gold if n_gold else float("nan")
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def score(safe_name):
    gold = {g["review_id"]: g for g in read_jsonl(DATA / "gold_labels.jsonl")}
    pred = {p["review_id"]: p for p in read_jsonl(DATA / f"tags_eval_{safe_name}.jsonl")}
    ids = [i for i in gold if i in pred]

    c = Counter()
    per_topic = Counter()
    rows = []
    for i in ids:
        g, p = gold[i], pred[i]
        gt, pt = {x["topic"] for x in g["points"]}, {x["topic"] for x in p["points"]}
        gp = {(x["topic"], x["type"]) for x in g["points"]}
        pp = {(x["topic"], x["type"]) for x in p["points"]}
        c["t_tp"] += len(gt & pt); c["t_pred"] += len(pt); c["t_gold"] += len(gt)
        c["p_tp"] += len(gp & pp); c["p_pred"] += len(pp); c["p_gold"] += len(gp)
        c["overall_ok"] += g["overall_sentiment"] == p["overall_sentiment"]
        gc, pc = bool(g["churn_signal"]), bool(p["churn_signal"])
        c["churn_tp"] += gc and pc; c["churn_pred"] += pc; c["churn_gold"] += gc
        for t in gt:
            per_topic[(t, "gold")] += 1
            per_topic[(t, "hit")] += t in pt
        for t in pt:
            per_topic[(t, "pred")] += 1
        rows.append({"review_id": i, "missed": sorted(gp - pp), "extra": sorted(pp - gp),
                     "overall_you": g["overall_sentiment"], "overall_ai": p["overall_sentiment"],
                     "quotes": {(x["topic"], x["type"]): x["quote"] for x in p["points"]}})

    tp_, tr, tf = prf(c["t_tp"], c["t_pred"], c["t_gold"])
    pp_, pr, pf = prf(c["p_tp"], c["p_pred"], c["p_gold"])
    cp, cr, _ = prf(c["churn_tp"], c["churn_pred"], c["churn_gold"])
    metrics = {"model": safe_name.replace("openai_", "openai/"), "n": len(ids),
               "topic_recall": tr, "topic_precision": tp_, "topic_f1": tf,
               "pair_recall": pr, "pair_precision": pp_, "pair_f1": pf,
               "overall_acc": c["overall_ok"] / len(ids) if ids else float("nan"),
               "churn_precision": cp, "churn_recall": cr,
               "points_per_review_ai": c["p_pred"] / len(ids) if ids else 0,
               "points_per_review_you": c["p_gold"] / len(ids) if ids else 0}
    (DATA / f"eval_{safe_name}.json").write_text(json.dumps(metrics, indent=2, default=float))
    return metrics, rows, per_topic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="all")
    ap.add_argument("--show", type=int, default=15, help="how many disagreements to print")
    args = ap.parse_args()

    if not (DATA / "gold_labels.jsonl").exists():
        raise SystemExit("No hand labels yet - finish labelling in the app first (data/gold_labels.jsonl).")

    pct = ["topic_recall", "topic_precision", "topic_f1", "pair_recall", "pair_precision", "pair_f1",
           "overall_acc", "churn_precision", "churn_recall"]
    if args.model == "all":
        names = sorted(p.stem.removeprefix("tags_eval_") for p in DATA.glob("tags_eval_*.jsonl"))
        table = pd.DataFrame([score(n)[0] for n in names]).sort_values("pair_f1", ascending=False)
        fmt = {c: "{:.0%}".format for c in pct} | {c: "{:.1f}".format for c in ["points_per_review_ai", "points_per_review_you"]}
        print(table.to_string(index=False, formatters=fmt))
        return

    m, rows, per_topic = score(args.model.replace("/", "_"))
    print(f"\n{m['model']}: {m['n']} reviews compared "
          f"(you: {m['points_per_review_you']:.1f} points/review, AI: {m['points_per_review_ai']:.1f})")
    for k in pct:
        print(f"  {k:16} {m[k]:6.1%}")

    print("\nPer topic (topics you used 3+ times):")
    topics = sorted({t for t, kind in per_topic if kind == "gold" and per_topic[(t, 'gold')] >= 3},
                    key=lambda t: -per_topic[(t, "gold")])
    for t in topics:
        g, h, p = per_topic[(t, "gold")], per_topic[(t, "hit")], per_topic[(t, "pred")]
        print(f"  {t:17} you {g:3}  AI {p:3}  recall {h / g:5.0%}  precision {h / p if p else float('nan'):5.0%}")

    text = pd.read_csv(DATA / "eval_sample.csv").set_index("review_id")
    bad = [r for r in rows if r["missed"] or r["extra"] or r["overall_you"] != r["overall_ai"]]
    print(f"\nReviews with any disagreement: {len(bad)}; first {args.show}:")
    for r in bad[: args.show]:
        t = text.loc[r["review_id"]]
        print(f"- [{t.app} {t.rating}*] {t.text[:150]}")
        if r["missed"]:
            print(f"    AI missed:  {', '.join(f'{a}/{b}' for a, b in r['missed'])}")
        for pair in r["extra"]:
            print(f"    AI added:   {pair[0]}/{pair[1]}  (quote: \"{r['quotes'].get(pair, '')[:60]}\")")
        if r["overall_you"] != r["overall_ai"]:
            print(f"    overall:    you {r['overall_you']}, AI {r['overall_ai']}")


if __name__ == "__main__":
    main()

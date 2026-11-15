"""Hand-labelling tool: you label the 100 eval reviews; these become the answer key for the AI.

    streamlit run src/label_app.py --server.headless true

For each review: add one row per point (topic + type), flip "leaving" if they say so, pick the
overall sentiment, then Save & next. Every save is written to data/gold_labels.jsonl straight away,
so you can stop and come back anytime.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import OVERALL, POINT_TYPES, TOPICS  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
GOLD = DATA / "gold_labels.jsonl"
TYPE_LABELS = {"👍 positive": "positive", "👎 negative": "negative", "➖ neutral": "neutral", "💡 request": "request"}


def load_gold():
    if not GOLD.exists():
        return []
    return [json.loads(x) for x in GOLD.read_text(encoding="utf-8").splitlines() if x.strip()]


def save_gold(rows):
    GOLD.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


st.set_page_config(page_title="Label reviews", layout="centered")
sample = pd.read_csv(DATA / "eval_sample.csv")
gold = load_gold()
done_ids = {g["review_id"] for g in gold}
todo = sample[~sample.review_id.isin(done_ids)]

done = len(sample) - len(todo)
st.progress(done / len(sample), text=f"{done} of {len(sample)} labelled")

with st.sidebar:
    if gold and st.button("↩ Undo last saved review"):
        save_gold(gold[:-1])
        st.rerun()
    st.subheader("Topics")
    for k, v in TOPICS.items():
        st.markdown(f"**{k}**: {v}")
    st.subheader("Point types")
    for k, v in POINT_TYPES.items():
        st.markdown(f"**{k}**: {v}")
    st.subheader("Overall sentiment")
    for k, v in OVERALL.items():
        st.markdown(f"**{k}**: {v}")
    st.caption("Text and stars disagree? Trust the text.")

if todo.empty:
    st.success("All 100 done! Tell Claude you're finished.")
    st.stop()

r = todo.iloc[0]
rid = r.review_id
n_key = f"n_{rid}"
st.session_state.setdefault(n_key, 1)

st.caption(f"{r.app} · {'★' * int(r.rating)}{'☆' * (5 - int(r.rating))}")
st.markdown(f"> {r.text}")

st.markdown("**Points in this review** (one row per thing they talk about)")
for i in range(st.session_state[n_key]):
    c1, c2 = st.columns([2, 3])
    c1.selectbox(f"Topic {i + 1}", list(TOPICS), index=None, placeholder="Choose topic",
                 key=f"t_{rid}_{i}", label_visibility="collapsed")
    c2.radio(f"Type {i + 1}", list(TYPE_LABELS), index=None, horizontal=True,
             key=f"y_{rid}_{i}", label_visibility="collapsed")

b1, b2, _ = st.columns([1.3, 1.3, 2])
if b1.button("➕ Add another point"):
    st.session_state[n_key] += 1
    st.rerun()
if st.session_state[n_key] > 1 and b2.button("➖ Remove last point"):
    st.session_state[n_key] -= 1
    st.rerun()

st.divider()
leaving = st.toggle("They say they're leaving / uninstalled / switching", key=f"c_{rid}")
overall = st.radio("Overall sentiment (whole comment + stars)", list(OVERALL), index=None,
                   horizontal=True, key=f"o_{rid}")

if st.button("Save & next", type="primary"):
    points = []
    for i in range(st.session_state[n_key]):
        topic, label = st.session_state.get(f"t_{rid}_{i}"), st.session_state.get(f"y_{rid}_{i}")
        if topic is None or label is None:
            st.error(f"Point {i + 1}: pick both a topic and a type (or remove the empty row).")
            st.stop()
        point = {"topic": topic, "type": TYPE_LABELS[label]}
        if point not in points:  # same topic + same type twice counts once
            points.append(point)
    if overall is None:
        st.error("Pick the overall sentiment.")
        st.stop()
    save_gold(gold + [{"review_id": rid, "points": points, "churn_signal": leaving, "overall_sentiment": overall}])
    st.rerun()

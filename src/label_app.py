"""Hand-labelling tool: you label the 100 eval reviews; these become the answer key for the AI.

    streamlit run src/label_app.py

Labels are saved after every review to data/gold_labels.csv, so you can stop and come back anytime.
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import SENTIMENTS, THEMES  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
GOLD = DATA / "gold_labels.csv"
COLS = ["review_id", "theme_1", "theme_2", "sentiment", "churn_signal"]

st.set_page_config(page_title="Label reviews", layout="centered")
sample = pd.read_csv(DATA / "eval_sample.csv")
gold = pd.read_csv(GOLD) if GOLD.exists() else pd.DataFrame(columns=COLS)
todo = sample[~sample.review_id.isin(gold.review_id)]

done = len(sample) - len(todo)
st.progress(done / len(sample), text=f"{done} of {len(sample)} labelled")

with st.sidebar:
    st.subheader("Theme guide")
    for k, v in THEMES.items():
        st.markdown(f"**{k}**: {v}")
    if len(gold) and st.button("Undo last label"):
        gold.iloc[:-1].to_csv(GOLD, index=False)
        st.rerun()

if todo.empty:
    st.success("All 100 done! Close this tab and tell Claude you're finished.")
    st.stop()

r = todo.iloc[0]
st.caption(f"{r.app} · {'★' * int(r.rating)}{'☆' * (5 - int(r.rating))}")
st.markdown(f"> {r.text}")

with st.form(key=f"f_{r.review_id}", clear_on_submit=True):
    t1 = st.radio("Main theme", list(THEMES), index=None, horizontal=True)
    t2 = st.selectbox("Second theme (optional)", ["(none)"] + list(THEMES))
    sent = st.radio("Sentiment", SENTIMENTS, index=None, horizontal=True)
    churn = st.toggle("Says they're leaving / uninstalled / switching")
    if st.form_submit_button("Save & next", type="primary"):
        if t1 is None or sent is None:
            st.error("Pick a main theme and a sentiment.")
        else:
            row = pd.DataFrame([[r.review_id, t1, "" if t2 == "(none)" else t2, sent, churn]], columns=COLS)
            pd.concat([gold, row]).to_csv(GOLD, index=False, encoding="utf-8")
            st.rerun()

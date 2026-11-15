"""AI Feedback Analyst - public dashboard.

    streamlit run app.py

Reads only files already in the repo (tags + analysis CSVs), so it needs no API key and costs nothing.
The "Ask the reviews" tab is the only part that calls an AI model (see src/rag.py).
"""
import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from analyze import load  # noqa: E402

DATA, AN = ROOT / "data", ROOT / "data" / "analysis"
MODEL = "gemini-3.5-flash-lite"

# reference palette (validated): apps = categorical slots 1-2; praise/complaint = diverging blue <-> red
APP_COLORS = {"Notion": "#2a78d6", "Evernote": "#eb6834"}
POS, NEG = "#2a78d6", "#e34948"
LABEL = {
    "core_features": "Features", "performance": "Speed & crashes", "editing": "Editing & typing",
    "usability_design": "Ease of use & design", "ai": "AI features", "pricing_plans": "Pricing & plans",
    "ads_prompts": "Ads & upgrade pop-ups", "billing": "Billing & refunds", "sync_login": "Sync & login",
    "data_safety": "Data loss & export", "support": "Customer support", "overall": "General opinion",
    "other": "Other",
}

st.set_page_config(page_title="AI Feedback Analyst", page_icon="📊", layout="wide")


@st.cache_data
def get_data():
    reviews, points = load(MODEL)
    return (reviews, points, pd.read_csv(AN / "topic_map.csv"), pd.read_csv(AN / "fix_first.csv"),
            pd.read_csv(AN / "requests.csv"), pd.read_csv(AN / "switching.csv"))


reviews, points, topic_map, fix_first, requests_df, switching = get_data()
for df in (topic_map, fix_first, requests_df):
    df["Topic"] = df.topic.map(LABEL)
points["Topic"] = points.topic.map(LABEL)

# ----------------------------------------------------------------- header
st.title("AI Feedback Analyst")
st.markdown(
    f"**{len(reviews):,} Google Play reviews** of **Notion** and its competitor **Evernote** "
    f"({reviews.date.min():%b %Y} – {reviews.date.max():%b %Y}), read by an LLM that splits each review into "
    "points (topic + praise/complaint/request + the exact quote), then ranked into what to fix first. "
    "Built for ₹0 on free AI tiers; accuracy checked against 100 hand-labelled reviews."
)

app = st.segmented_control("App", ["Notion", "Evernote"], default="Notion", label_visibility="collapsed") or "Notion"
R, P = reviews[reviews.app == app], points[points.app == app]

tabs = st.tabs(["Overview", "What users love & hate", "Fix first", "Requests & switching", "Trends",
                "Ask the reviews", "Explore quotes", "How it was built"])


def ax(title=None, **kw):
    """Recessive axis: muted ticks and titles. Category labels pass labelColor=None to keep the theme's text ink."""
    style = {"grid": False, "domainColor": "#c3c2b7", "tickColor": "#c3c2b7", "labelColor": "#898781",
             "titleColor": "#898781", "tickCount": 6, "labelOverlap": True} | kw
    return alt.Axis(title=title, **{k: v for k, v in style.items() if v is not None})


# ----------------------------------------------------------------- overview
with tabs[0]:
    c = st.columns(4)
    c[0].metric("Reviews analysed", f"{len(R):,}")
    c[1].metric("Average stars", f"{R.rating.mean():.2f} ★")
    c[2].metric("Positive overall", f"{(R.overall_sentiment == 'positive').mean():.0%}")
    c[3].metric("Say they're leaving", f"{R.churn_signal.mean():.0%}")

    top = fix_first[fix_first.app == app].iloc[0]
    other = "Evernote" if app == "Notion" else "Notion"
    O = reviews[reviews.app == other]
    st.subheader("In one line")
    if app == "Notion":
        mob = R.text.str.contains(r"mobile|android|phone", case=False)
        st.markdown(
            f"Users like Notion as a whole (general opinion **{(R.overall_sentiment == 'positive').mean():.0%} positive**), "
            f"but the **mobile app** drags it down: **{top.Topic.lower()}** is the #1 complaint "
            f"({int(top.complaints)} reviews, {top.high_severity_pct:.0%} high severity), and reviews that mention "
            f"mobile average **{R[mob].rating.mean():.2f}★ vs {R[~mob].rating.mean():.2f}★** for the rest.")
    else:
        st.markdown(
            f"Evernote users are leaving over **money and nagging**: pricing and ads/upgrade pop-ups each appear in "
            f"over a third of reviews, and **{R.churn_signal.mean():.0%}** of reviewers say they're leaving "
            f"(Notion: {O.churn_signal.mean():.0%}).")

    st.subheader("Overall sentiment, both apps")
    s = (reviews.groupby("app").overall_sentiment.value_counts(normalize=True).rename("share").reset_index())
    order = ["positive", "mixed", "neutral", "negative"]
    s["Sentiment"] = s.overall_sentiment.str.capitalize()
    chart = alt.Chart(s).mark_bar().encode(
        x=alt.X("share:Q", stack="normalize", axis=ax(None, format="%")),
        y=alt.Y("app:N", axis=ax(None, labelColor=None), sort=["Notion", "Evernote"]),
        color=alt.Color("Sentiment:N", sort=[o.capitalize() for o in order],
                        scale=alt.Scale(domain=["Positive", "Mixed", "Neutral", "Negative"],
                                        range=[POS, "#9ec5f4", "#d6d5cf", NEG]),
                        legend=alt.Legend(orient="top", title=None)),
        order=alt.Order("sort_key:Q"),
        tooltip=["app", "Sentiment", alt.Tooltip("share:Q", format=".0%")],
    ).transform_calculate(sort_key=f"indexof({[o.capitalize() for o in order]}, datum.Sentiment)").properties(
        height=alt.Step(40))
    st.altair_chart(chart, width="stretch")

# ----------------------------------------------------------------- love & hate
with tabs[1]:
    st.markdown("Each bar counts **reviews**: praise to the right, complaints to the left. "
                "General opinions ('great app') are left out here so specific topics are readable.")
    t = topic_map[(topic_map.app == app) & ~topic_map.topic.isin(["overall", "other"])].copy()
    t["total"] = t.positive + t.negative
    long = pd.concat([t.assign(kind="Praise", value=t.positive), t.assign(kind="Complaints", value=-t.negative)])
    sort = t.sort_values("total", ascending=False).Topic.tolist()
    base = alt.Chart(long).encode(
        y=alt.Y("Topic:N", sort=sort, axis=ax(None, labelColor=None, labelLimit=200)),
        x=alt.X("value:Q", axis=ax("← complaints   |   praise →", labelExpr="abs(datum.value)")),
        color=alt.Color("kind:N", scale=alt.Scale(domain=["Praise", "Complaints"], range=[POS, NEG]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["Topic", alt.Tooltip("positive:Q", title="praise"), alt.Tooltip("negative:Q", title="complaints"),
                 alt.Tooltip("net_sentiment:Q", title="net sentiment (-100..+100)")],
    )
    bars = (base.transform_filter("datum.value < 0").mark_bar(cornerRadiusTopLeft=4, cornerRadiusBottomLeft=4)
            + base.transform_filter("datum.value >= 0").mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4))
    st.altair_chart(bars.properties(height=alt.Step(30)), width="stretch")

    st.subheader("Notion vs Evernote, topic by topic")
    st.caption("Net sentiment = (praise − complaints) ÷ (praise + complaints). +100 = everyone who mentions it is happy. "
               "Only topics with 20+ opinions per app.")
    tm = topic_map[~topic_map.topic.isin(["other"])].copy()
    tm["opinions"] = tm.positive + tm.negative
    keep = tm[tm.opinions >= 20].groupby("topic").app.nunique()
    tm = tm[tm.topic.isin(keep[keep == 2].index)]
    dots = alt.Chart(tm).mark_circle(size=140, opacity=1, stroke="white", strokeWidth=2).encode(
        x=alt.X("net_sentiment:Q", scale=alt.Scale(domain=[-100, 100]), axis=ax("net sentiment")),
        y=alt.Y("Topic:N", sort=alt.EncodingSortField("net_sentiment", op="max", order="descending"),
                axis=ax(None, labelColor=None, labelLimit=200)),
        color=alt.Color("app:N", scale=alt.Scale(domain=list(APP_COLORS), range=list(APP_COLORS.values())),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["app", "Topic", "net_sentiment", "positive", "negative"],
    )
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#c3c2b7").encode(x="x:Q")
    st.altair_chart((zero + dots).properties(height=40 * tm.topic.nunique()), width="stretch")

# ----------------------------------------------------------------- fix first
with tabs[2]:
    st.markdown("**Impact score** = every complaint weighted by how much it hurts (low 1, medium 2, high 3). "
                "100 'a bit slow' complaints matter less than 100 'I lost my notes'.")
    f = fix_first[fix_first.app == app].head(8)
    chart = alt.Chart(f).mark_bar(color=NEG, cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
        x=alt.X("impact_score:Q", axis=ax("impact score")),
        y=alt.Y("Topic:N", sort="-x", axis=ax(None, labelColor=None, labelLimit=200)),
        tooltip=["Topic", "complaints", alt.Tooltip("pct_of_reviews:Q", format=".0%", title="% of reviews"),
                 alt.Tooltip("high_severity_pct:Q", format=".0%", title="high severity"),
                 alt.Tooltip("churn_pct:Q", format=".0%", title="say they're leaving"), "avg_stars"],
    ).properties(height=alt.Step(30))
    st.altair_chart(chart, width="stretch")
    pc = ["pct_of_reviews", "high_severity_pct", "churn_pct"]
    st.dataframe(
        f[["rank", "Topic", "complaints", *pc, "avg_stars", "likes_on_reviews"]].assign(**{c: f[c] * 100 for c in pc}),
        hide_index=True, width="stretch",
        column_config={"pct_of_reviews": st.column_config.NumberColumn("% of reviews", format="%.0f%%"),
                       "high_severity_pct": st.column_config.NumberColumn("high severity", format="%.0f%%"),
                       "churn_pct": st.column_config.NumberColumn("say they're leaving", format="%.0f%%"),
                       "avg_stars": st.column_config.NumberColumn("avg ★", format="%.2f"),
                       "likes_on_reviews": st.column_config.NumberColumn("'helpful' likes")})
    st.subheader("What users actually say (most-liked first)")
    for row in f.head(4).itertuples():
        with st.expander(f"#{row.rank} {row.Topic}: {row.complaints} complaints"):
            q = P[(P.topic == row.topic) & (P.type == "negative")].sort_values("thumbs_up", ascending=False).head(6)
            for x in q.itertuples():
                st.markdown(f"> {x.quote}  \n<small>{int(x.rating)}★ · {int(x.thumbs_up)} people found this helpful · "
                            f"{x.date:%b %Y}</small>", unsafe_allow_html=True)

# ----------------------------------------------------------------- requests & switching
with tabs[3]:
    left, right = st.columns(2)
    with left:
        st.subheader("What users ask for")
        r = requests_df[requests_df.app == app].head(6)
        st.altair_chart(alt.Chart(r).mark_bar(color=APP_COLORS[app], cornerRadiusTopRight=4,
                                              cornerRadiusBottomRight=4).encode(
            x=alt.X("requests:Q", axis=ax("requests")),
            y=alt.Y("Topic:N", sort="-x", axis=ax(None, labelColor=None, labelLimit=200)),
            tooltip=["Topic", "requests"]).properties(height=alt.Step(30)), width="stretch")
        q = P[P.type == "request"].sort_values("thumbs_up", ascending=False).head(8)
        for x in q.itertuples():
            st.markdown(f"💡 **{x.Topic}:** “{x.quote}” <small>({int(x.thumbs_up)} likes)</small>", unsafe_allow_html=True)
    with right:
        st.subheader("Where leaving users say they're going")
        sw = switching[switching.app == app].head(8)
        st.altair_chart(alt.Chart(sw).mark_bar(color=APP_COLORS[app], cornerRadiusTopRight=4,
                                               cornerRadiusBottomRight=4).encode(
            x=alt.X("reviews:Q", axis=ax("reviews naming it")),
            y=alt.Y("to:N", sort="-x", axis=ax(None, labelColor=None)),
            tooltip=[alt.Tooltip("to:N", title="switching to"), "reviews"]).properties(height=alt.Step(30)),
            width="stretch")
        st.caption(f"{int(R.churn_signal.sum())} {app} reviewers say they're leaving; "
                   f"{int(sw.reviews.sum())} of them name where they're going.")

# ----------------------------------------------------------------- trends
with tabs[4]:
    topics = [t for t in LABEL if t not in ("overall", "other")]
    pick = st.selectbox("Complaint topic", topics, format_func=LABEL.get,
                        index=topics.index("ads_prompts" if app == "Evernote" else "performance"))
    neg = points[(points.type == "negative") & (points.topic == pick)].copy()
    neg["month"] = neg.date.dt.to_period("M").dt.to_timestamp()
    rv = reviews.assign(month=reviews.date.dt.to_period("M").dt.to_timestamp())
    m = rv.groupby(["app", "month"]).size().rename("reviews").to_frame().join(
        neg.groupby(["app", "month"]).size().rename("complaints")).fillna(0).reset_index()
    m["share"] = m.complaints / m.reviews
    hover = alt.selection_point(fields=["month"], nearest=True, on="pointerover", empty=False)
    base = alt.Chart(m).encode(
        x=alt.X("yearmonth(month):T", axis=ax(None, format="%b %y")),
        y=alt.Y("share:Q", axis=ax("% of that month's reviews", format="%")),
        color=alt.Color("app:N", scale=alt.Scale(domain=list(APP_COLORS), range=list(APP_COLORS.values())),
                        legend=alt.Legend(orient="top", title=None)))
    lines = base.mark_line(strokeWidth=2)
    pts = base.mark_circle(size=70).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=["app", alt.Tooltip("yearmonth(month):T", format="%B %Y"), alt.Tooltip("share:Q", format=".0%"),
                 alt.Tooltip("complaints:Q", format=".0f"), "reviews"]).add_params(hover)
    rule = alt.Chart(m).mark_rule(color="#c3c2b7").encode(x="yearmonth(month):T").transform_filter(hover)
    st.altair_chart((lines + pts + rule).properties(height=340), width="stretch")
    st.caption("First and last months are partial (the data covers 12 months up to the collection date). "
               "Spikes usually point to a release, a price change or an ads rollout.")

# ----------------------------------------------------------------- RAG
with tabs[5]:
    try:
        from rag_ui import render  # noqa: E402
        render(app)
    except ImportError:
        st.info("Coming soon: ask a question in plain English and get an answer backed by cited reviews.")

# ----------------------------------------------------------------- explore
with tabs[6]:
    a, b, c = st.columns(3)
    tp = a.selectbox("Topic", ["(all)"] + list(LABEL), format_func=lambda x: LABEL.get(x, x))
    ty = b.selectbox("Type", ["(all)", "negative", "positive", "request", "neutral"])
    word = c.text_input("Contains word")
    q = P
    if tp != "(all)":
        q = q[q.topic == tp]
    if ty != "(all)":
        q = q[q.type == ty]
    if word:
        q = q[q.text.str.contains(word, case=False, regex=False)]
    st.caption(f"{len(q):,} points")
    st.dataframe(q.sort_values("thumbs_up", ascending=False)[["Topic", "type", "severity", "quote", "rating",
                                                             "thumbs_up", "date", "text"]].head(500),
                 hide_index=True, width="stretch",
                 column_config={"rating": "★", "thumbs_up": "likes", "text": "full review",
                                "date": st.column_config.DateColumn(format="MMM YYYY")})

# ----------------------------------------------------------------- how it was built
with tabs[7]:
    st.markdown("""
**Pipeline:** collect (Google Play, 12 months) → clean → AI tagging → evaluation vs. hand labels → ranking → Q&A (RAG) → weekly digest (n8n)

| Step | What happened |
|---|---|
| Collect | 5,495 reviews scraped from the public Play Store pages |
| Clean | duplicates, reviews under 5 words and non-English removed → **4,108** |
| Topic list | 13 neutral topics designed by reading 145 reviews (affinity mapping) |
| AI tagging | each review split into points: exact quote → topic → praise / complaint / neutral / request → severity; plus overall sentiment and "is this user leaving?" |
| Evaluation | 100 reviews hand-labelled (kept separate from the 145) and 4 free models compared |
| Cost | **$0**: Gemini and Groq free tiers |
""")
    rows = []
    for p in sorted(DATA.glob("eval_*.json")):
        m = json.loads(p.read_text())
        rows.append({"Model": m["model"], "Topic F1": m["topic_f1"], "Topic + type F1": m["pair_f1"],
                     "Overall sentiment acc.": m["overall_acc"], "Churn recall": m["churn_recall"],
                     "Churn precision": m["churn_precision"]})
    ev = pd.DataFrame(rows).sort_values("Topic + type F1", ascending=False)
    ev[ev.columns[1:]] = ev[ev.columns[1:]] * 100
    pct = {k: st.column_config.NumberColumn(k, format="%.0f%%") for k in ev.columns[1:]}
    st.subheader("How accurate is the AI? (vs. 100 hand-labelled reviews)")
    st.dataframe(ev, hide_index=True, width="stretch", column_config=pct)
    st.markdown(
        "Full run used **Gemini 3.5 Flash-Lite**: 1 point behind the best model on F1, the same 100% churn recall, "
        "and ~10x faster. The top model was overloaded (HTTP 503) on the day. Error analysis showed half of all "
        "disagreements came from one blurry topic boundary (general praise vs. 'features'), so the definition was fixed.")

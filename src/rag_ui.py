"""The 'Ask the reviews' tab of the dashboard (Streamlit UI on top of src/rag.py)."""
import os

import streamlit as st

import rag

EXAMPLES = {
    "Notion": ["Why do people dislike Notion AI?", "What exactly is slow on the Notion mobile app?",
               "What do users love most about Notion?", "Which desktop features do mobile users miss?"],
    "Evernote": ["Why are Evernote users leaving?", "What do users say about the new pricing?",
                 "Where are Evernote users moving to and why?", "Is anything about Evernote still praised?"],
}
MAX_QUESTIONS = 8  # per visitor session, to protect the free-tier quota on the public demo


def api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        rag.load_dotenv(rag.ROOT / ".env")
        return os.environ.get("GEMINI_API_KEY")


@st.cache_resource
def index():
    return rag.Index()


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def cached_answer(question, scope):
    out = rag.answer(question, None if scope == "Both apps" else scope, index(), rag.client(api_key()))
    return out["answer"], out["sources"], out["model"]


def render(app):
    st.markdown("Ask a question in plain English. The AI finds the most relevant reviews by **meaning** "
                "(not keywords), answers using only those reviews, and cites them as [n] so you can check every claim.")
    if not (rag.RAG / "embeddings.npy").exists():
        st.info("The review index hasn't been built yet (run `python src/rag.py build`).")
        return
    if not api_key():
        st.info("Add GEMINI_API_KEY to the app's secrets to enable questions.")
        return

    scope = st.radio("Search in", [app, "Both apps"], horizontal=True, key="rag_scope")
    cols = st.columns(len(EXAMPLES[app]))
    for col, ex in zip(cols, EXAMPLES[app]):
        if col.button(ex, key=f"ex_{ex}", width="stretch"):
            st.session_state.rag_q = ex
    q = st.text_input("Your question", key="rag_q", placeholder="e.g. What do students say about Notion?")
    if not q:
        return
    used = st.session_state.setdefault("rag_used", set())
    if (q, scope) not in used and len(used) >= MAX_QUESTIONS:
        st.warning("Question limit reached for this session (the demo runs on a free AI tier).")
        return
    with st.spinner("Searching 4,108 reviews and writing an answer..."):
        try:
            text, sources, model = cached_answer(q.strip(), scope)
        except Exception as e:
            st.error(f"The free AI tier is busy right now ({type(e).__name__}). Please try again in a minute.")
            return
    used.add((q, scope))
    st.markdown(text)
    st.caption(f"Answered by {model} from the {rag.TOP_K} most relevant reviews + topic counts for all reviews.")
    with st.expander(f"Sources cited ({len(sources)})", expanded=True):
        for r in sources.itertuples():
            st.markdown(f"**[{r.n}]** {r.app} · {int(r.rating)}★ · {r.date:%b %Y}  \n> {r.text}")

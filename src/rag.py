"""Step 6 - Ask the reviews (RAG: retrieval-augmented generation).

    python src/rag.py build                                    # one-off: embed all 4,108 reviews (free tier)
    python src/rag.py ask "Why do people dislike Notion AI?" --app Notion

How it works:
1. EMBED: every review is turned into a vector (384 numbers that capture its meaning) with
   BGE-small, a free open-source embedding model that runs on this computer (no API, no quota).
   Saved to data/rag/ so this happens once, not per question. (Gemini's embedding API was tried
   first, but its free tier allows only 1,000 texts a day.)
2. RETRIEVE: the question is embedded the same way; the reviews whose vectors point in the most
   similar direction (cosine similarity) are the most relevant, even if they share no words
   ("laggy" finds "takes forever to load").
3. GENERATE: an LLM writes the answer using ONLY those reviews plus the pre-computed topic counts,
   and cites every claim as [n] so a reader can check the source.
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAG = DATA / "rag"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"  # 384 dimensions, ~70 MB, runs on CPU
ANSWER_MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]  # fallback if the first is overloaded
TOP_K = 25


def client(api_key=None):
    from google import genai
    load_dotenv(ROOT / ".env")
    return genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])


_embedder = None


def embed(texts, kind):
    """kind='passage' for reviews, 'query' for questions (BGE adds a search instruction to queries)."""
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(EMBED_MODEL)
    fn = _embedder.query_embed if kind == "query" else _embedder.passage_embed
    v = np.array(list(fn(texts)), dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)  # unit length, so dot product = cosine similarity


def build():
    df = pd.read_csv(DATA / "clean_reviews.csv")
    RAG.mkdir(exist_ok=True)
    texts = [f"{a} review ({r} stars): {t}" for a, r, t in zip(df.app, df.rating, df.text)]
    t = time.time()
    vecs = embed(texts, "passage")
    print(f"embedded {len(texts)} reviews in {time.time() - t:.0f}s")
    np.save(RAG / "embeddings.npy", vecs.astype(np.float16))  # float16 halves the file size
    df[["review_id"]].to_csv(RAG / "ids.csv", index=False)
    print(f"saved {RAG / 'embeddings.npy'}")


class Index:
    """The 'vector database': for 4,108 reviews, a NumPy matrix is all we need (a search takes ~1 ms)."""

    def __init__(self):
        self.vecs = np.load(RAG / "embeddings.npy").astype(np.float32)
        ids = pd.read_csv(RAG / "ids.csv").review_id
        reviews = pd.read_csv(DATA / "clean_reviews.csv", parse_dates=["date"]).set_index("review_id")
        self.reviews = reviews.loc[ids].reset_index()
        self.stats = pd.read_csv(DATA / "analysis" / "topic_map.csv")

    def search(self, qvec, app=None, k=TOP_K):
        scores = self.vecs @ qvec
        if app:
            scores = np.where(self.reviews.app.values == app, scores, -1)
        top = np.argsort(-scores)[:k]
        return self.reviews.iloc[top].assign(similarity=scores[top])


SYSTEM = """You answer a product manager's questions about app-store reviews of Notion and Evernote.
Use ONLY the numbered reviews and the topic statistics provided. Rules:
- Cite every claim with the review numbers it comes from, like [3] or [3, 7].
- Lead with the direct answer in 1-2 sentences, then 3-5 short bullet points with the main reasons.
- For "how many / how common" questions, use the topic statistics (they cover all reviews);
  the numbered reviews are only a sample of the most relevant ones, so never count them as if they were all reviews.
- If the reviews don't answer the question, say so plainly. Never invent facts, numbers or quotes.
- Plain, simple English. Under 200 words."""


def stats_text(stats, app):
    s = stats if not app else stats[stats.app == app]
    rows = [f"{r.app} | {r.topic}: {r.positive} praise, {r.negative} complaints, {r.request} requests "
            f"(of {r.reviews_in_app} reviews)" for r in s.itertuples() if r.topic != "other"]
    return "\n".join(rows)


def answer(question, app=None, index=None, c=None):
    c, index = c or client(), index or Index()
    hits = index.search(embed([question], "query")[0], app)
    context = "\n".join(f"[{i + 1}] {r.app}, {r.rating} stars, {r.date:%b %Y}: {r.text}"
                        for i, r in enumerate(hits.itertuples()))
    prompt = (f"Question: {question}\n\nTopic statistics (all {len(index.reviews):,} reviews):\n"
              f"{stats_text(index.stats, app)}\n\nMost relevant reviews:\n{context}")
    from google.genai import types
    last = None
    for model in ANSWER_MODELS:
        try:
            r = c.models.generate_content(model=model, contents=prompt, config=types.GenerateContentConfig(
                system_instruction=SYSTEM, temperature=0.2))
            text = r.text
            cited = sorted({int(n) for grp in re.findall(r"\[([\d,\s]+)\]", text) for n in grp.split(",") if n.strip()})
            sources = hits.iloc[[n - 1 for n in cited if 0 < n <= len(hits)]].assign(n=[n for n in cited if 0 < n <= len(hits)])
            return {"answer": text, "sources": sources, "model": model, "retrieved": hits}
        except Exception as e:  # e.g. 503 high demand -> try the next model
            last = e
    raise last


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    a = sub.add_parser("ask")
    a.add_argument("question")
    a.add_argument("--app", choices=["Notion", "Evernote"])
    args = ap.parse_args()
    if args.cmd == "build":
        return build()
    out = answer(args.question, args.app)
    print(out["answer"], f"\n\n(model: {out['model']})\nSources:")
    for r in out["sources"].itertuples():
        print(f"  [{r.n}] {r.app} {r.rating}* {r.date:%b %Y}: {r.text[:140]}")


if __name__ == "__main__":
    sys.exit(main())

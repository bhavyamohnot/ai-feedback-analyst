# AI Feedback Analyst

Turns thousands of messy app-store reviews into a ranked list of what to fix, answers questions about
them with sources, and sends a weekly digest automatically.

**Live dashboard:** https://ai-feedback-analyst.streamlit.app/ (8 tabs, incl. "Ask the reviews" RAG Q&A)

Demo case: **Notion** (SaaS workspace) vs. its competitor **Evernote**, 12 months of Google Play reviews.

## Pipeline

```
collect -> clean -> tag with LLM -> evaluate vs. hand labels -> rank themes -> Q&A (RAG) -> weekly digest (n8n)
```

| Step | File | Status |
|---|---|---|
| 1. Collect 12 months of reviews | `src/collect.py` | done (5,495 reviews) |
| 2. Clean (dupes, <5 words, non-English) | `src/clean.py` | done (4,108 kept; weekly runs add new ones) |
| 3a. Topic list v2 (13 neutral topics; aspect-based sentiment) | `src/taxonomy.py` | done |
| 3b. Split each review into points (quote + topic + type), overall sentiment, churn (Gemini + Groq free tiers) | `src/tag.py` | done: all 4,108 tagged (Gemini 3.5 Flash-Lite, $0) |
| 4a. Hand-label 100 reviews (gold set) | `src/make_eval_sample.py`, `src/label_app.py` | done |
| 4b. Eval: 4 models vs. hand labels (topic/pair F1, sentiment, churn) | `src/evaluate.py` | done |
| 5. Topic map, fix-first ranking (volume x severity), requests, switching, monthly trends | `src/analyze.py` | done |
| 6. Dashboard (8 tabs, light/dark) | `app.py` | done |
| 7. Ask questions in plain English (RAG: local BGE-small embeddings + Gemini, cited answers) | `src/rag.py`, `src/rag_ui.py` | done |
| 8. PRD for the top problem found | [`docs/PRD_Notion_Android_Performance.md`](docs/PRD_Notion_Android_Performance.md) | done |
| 9. Weekly update + spike detection | `src/weekly.py` | done |
| 10. n8n: AI agent over the reviews (tools via `src/api.py`) + weekly digest workflow | `n8n/` | done ([sample digest](docs/sample_weekly_digest.md)) |

## Key findings

- **Evernote** (1.53★, 34% of reviewers say they're leaving): pricing and ads/upgrade pop-ups each appear in over
  a third of reviews, with ad spikes in Feb and Sep 2026. Leavers name OneNote, Obsidian and UpNote.
- **Notion** (3.56★, 54% positive): users like the app overall (net +89), but **speed and crashes** are the #1 problem
  (17% of reviews, 53% high severity, in every app version), and reviews that mention mobile average 2.65★ vs 3.72★.

## Run

```
pip install -r requirements.txt
streamlit run app.py                 # dashboard (no API key needed except for "Ask the reviews")
python src/rag.py ask "Why do people dislike Notion AI?" --app Notion
python src/weekly.py                 # fetch new reviews, tag, analyse, compare with previous 4 weeks
```
n8n (self-hosted, free; needs Node 24 and `npm install n8n`, see `n8n/start_n8n.ps1`):
```
powershell -ExecutionPolicy Bypass -File n8n\start_n8n.ps1   # review API + n8n on http://localhost:5678
```
Import `n8n/ask_the_reviews_agent.json` and `n8n/weekly_digest.json`, add a "Google Gemini (PaLM) API" credential, done.
- **Ask the reviews (AI agent):** chat -> Gemini agent with memory -> tools `search_reviews` / `get_topic_stats` (HTTP to `src/api.py`).
- **Weekly review digest:** every Monday 9am -> `weekly.py` -> spike detection (1.5x the 4-week share, at least 5 complaints) -> Gemini writes the digest -> `data/digest/latest.md`.

Full pipeline from scratch: `collect.py -> clean.py -> tag.py --set all --model gemini-3.5-flash-lite -> analyze.py -> rag.py build`.
API keys go in `.env` (`GEMINI_API_KEY`, optional `GROQ_API_KEY`); never committed.

Concepts used in this project are explained in [docs/LEARNING_NOTES.md](docs/LEARNING_NOTES.md).

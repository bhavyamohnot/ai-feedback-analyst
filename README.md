# AI Feedback Analyst

Turns thousands of messy app-store reviews into a ranked list of what to fix, answers questions about
them with sources, and sends a weekly digest automatically.

Demo case: **Notion** (SaaS workspace) vs. its competitor **Evernote**, 12 months of Google Play reviews.

## Pipeline

```
collect -> clean -> tag with LLM -> evaluate vs. hand labels -> rank themes -> Q&A (RAG) -> weekly digest (n8n)
```

| Step | File | Status |
|---|---|---|
| 1. Collect 12 months of reviews | `src/collect.py` | done (5,495 reviews) |
| 2. Clean (dupes, <5 words, non-English) | `src/clean.py` | done (4,108 kept) |
| 3a. Topic list v2 (13 neutral topics; aspect-based sentiment) | `src/taxonomy.py` | done |
| 3b. Split each review into points (quote + topic + type), overall sentiment, churn (Gemini + Groq free tiers) | `src/tag.py` | done: all 4,108 tagged (Gemini 3.5 Flash-Lite, $0) |
| 4a. Hand-label 100 reviews (gold set) | `src/make_eval_sample.py`, `src/label_app.py` | done |
| 4b. Eval: 4 models vs. hand labels (topic/pair F1, sentiment, churn) | `src/evaluate.py` | done |
| 5. Topic map, fix-first ranking (volume x severity), requests, switching, monthly trends | `src/analyze.py` | done |
| 6. Ask questions in plain English (RAG, with citations) | - | |
| 7. Weekly digest automation (n8n) | - | |
| 8. PRD for the top problem found | - | |

## Run

```
pip install -r requirements.txt
python src/collect.py
python src/clean.py
```

Concepts used in this project are explained in [docs/LEARNING_NOTES.md](docs/LEARNING_NOTES.md).

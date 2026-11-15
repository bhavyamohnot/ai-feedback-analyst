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
| 3. Discover themes + tag each review with an LLM | - | next |
| 4. Eval: compare LLM tags to hand labels | - | |
| 5. Rank themes by volume x severity, with example quotes | - | |
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

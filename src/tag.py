"""Step 3 - Tag: an LLM reads each review and returns themes, sentiment, severity and churn signals.

    python src/tag.py --set eval --model claude-haiku-5-5     # the 100 hand-labelled reviews
    python src/tag.py --set all  --model claude-haiku-5-5     # all 4,108 clean reviews

Reviews are sent 20 per request. The answer comes back as structured JSON (validated by Pydantic),
so the code never has to parse free text. Results are appended to data/tags_<set>_<model>.jsonl,
which makes the run resumable: re-running skips reviews that are already tagged.
Needs ANTHROPIC_API_KEY in the project's .env file.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

import anthropic
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import SENTIMENTS, SEVERITY, THEMES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BATCH = 20
# USD per million tokens (input, output) - from Anthropic's published price list
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00), "claude-opus-5-5": (4.00, 20.00)}

Theme = Literal[tuple(THEMES)]


class ReviewTag(BaseModel):
    id: int
    themes: list[Theme]  # 1-2 themes, most important first
    sentiment: Literal[tuple(SENTIMENTS)]
    severity: Literal[tuple(SEVERITY)]
    churn_signal: bool  # says they are leaving, uninstalled, or switching
    switching_to: str  # competitor named as the replacement, or "" if none
    summary: str  # the core point in under 12 words


class TagBatch(BaseModel):
    tags: list[ReviewTag]


SYSTEM = f"""You tag app-store reviews of note-taking apps for a product team.

For every review, return:
- themes: 1 or 2 themes from the list below, most important first. Use "other" only if nothing fits.
- sentiment: one of {SENTIMENTS}. "mixed" = clear praise and a clear complaint together.
- severity: how much the issue hurts the user.
- churn_signal: true only if the user says they are leaving, have uninstalled, cancelled, or are switching.
- switching_to: the competitor they name as their replacement (e.g. "Notion", "Google Keep"), else "".
- summary: the core point in under 12 words, in plain English.

Themes:
{chr(10).join(f'- {k}: {v}' for k, v in THEMES.items())}

Severity:
{chr(10).join(f'- {k}: {v}' for k, v in SEVERITY.items())}

Judge from the review text; the star rating is context, not the answer. Return one tag per review id."""


def load_set(name: str) -> pd.DataFrame:
    path = DATA / ("eval_sample.csv" if name == "eval" else "clean_reviews.csv")
    df = pd.read_csv(path)
    return df.reset_index(drop=True).assign(row_id=lambda d: d.index)


def tag_batch(client, model: str, rows: pd.DataFrame):
    body = "\n".join(
        f'<review id="{r.row_id}" app="{r.app}" stars="{r.rating}">{r.text}</review>' for r in rows.itertuples()
    )
    resp = client.messages.parse(
        model=model,
        max_tokens=8000,
        system=SYSTEM,
        output_config={"effort": "low"},  # simple classification: low effort keeps cost down
        output_format=TagBatch,
        messages=[{"role": "user", "content": f"Tag these {len(rows)} reviews.\n\n{body}"}],
    )
    if resp.stop_reason != "end_turn" or resp.parsed_output is None:
        raise RuntimeError(f"stop_reason={resp.stop_reason}")
    wanted = set(rows.row_id)
    tags = [t for t in resp.parsed_output.tags if t.id in wanted]
    return tags, resp.usage.input_tokens, resp.usage.output_tokens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["eval", "all"], default="eval")
    ap.add_argument("--model", default="claude-opus-5-5", choices=list(PRICES))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic(max_retries=4)
    df = load_set(args.set)
    out = DATA / f"tags_{args.set}_{args.model}.jsonl"
    done = set()
    if out.exists():
        done = {json.loads(line)["review_id"] for line in out.read_text(encoding="utf-8").splitlines()}
    todo = df[~df.review_id.isin(done)]
    chunks = [todo.iloc[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    print(f"{args.model}: {len(todo)} reviews to tag in {len(chunks)} requests ({len(done)} already done)")

    tok_in = tok_out = tagged = 0
    with ThreadPoolExecutor(args.workers) as pool, out.open("a", encoding="utf-8") as f:
        futures = {pool.submit(tag_batch, client, args.model, c): c for c in chunks}
        for fut in as_completed(futures):
            rows = futures[fut].set_index("row_id")
            try:
                tags, i, o = fut.result()
            except Exception as e:  # one failed request shouldn't kill the run; re-run picks it up
                print(f"  request failed ({type(e).__name__}: {e}); will retry on next run")
                continue
            tok_in, tok_out = tok_in + i, tok_out + o
            for t in tags:
                rec = {"review_id": rows.loc[t.id, "review_id"], **t.model_dump(exclude={"id"})}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            tagged += len(tags)
            print(f"  tagged {tagged}/{len(todo)}", end="\r")

    p_in, p_out = PRICES[args.model]
    cost = tok_in / 1e6 * p_in + tok_out / 1e6 * p_out
    print(f"\ndone: {tagged} tagged | tokens in {tok_in:,} out {tok_out:,} | cost ${cost:.3f}"
          + (f" (${cost / tagged * 1000:.2f} per 1,000 reviews)" if tagged else ""))


if __name__ == "__main__":
    main()

"""Step 3 - Tag: an LLM reads each review and returns themes, sentiment, severity and churn signals.

    python src/tag.py --set eval --model gemini-2.5-flash     # the 100 hand-labelled reviews
    python src/tag.py --set all  --model gemini-2.5-flash     # all 4,108 clean reviews

Works with Google Gemini (free tier), Groq (free tier, open models such as openai/gpt-oss-120b)
and Anthropic Claude (paid); the provider is picked from the model name. Reviews are sent 20 per request. The answer comes back as structured JSON validated by
Pydantic, so the code never parses free text. Results are appended to data/tags_<set>_<model>.jsonl,
which makes the run resumable: re-running skips reviews already tagged (useful when a free-tier
daily limit stops a run halfway).
Keys live in the project's .env file: GEMINI_API_KEY, GROQ_API_KEY (or ANTHROPIC_API_KEY for Claude).
"""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import SENTIMENTS, SEVERITY, THEMES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BATCH = 20
# USD per million tokens (input, output). Gemini free tier = $0.
PAID_PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00), "claude-opus-5-5": (4.00, 20.00)}

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


# ----------------------------- providers -------------------------------------
class Gemini:
    def __init__(self, model):
        from google import genai
        self.genai, self.model = genai, model
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def call(self, prompt):
        from google.genai import types
        resp = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                response_schema=TagBatch,
                # sorting reviews is a simple task: little thinking = faster and uses less free quota
                thinking_config=types.ThinkingConfig(thinking_level="LOW") if self.model.startswith("gemini-3") else None,
            ),
        )
        u = resp.usage_metadata
        out_tokens = (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
        return resp.parsed, u.prompt_token_count or 0, out_tokens

    def wait_seconds(self, err):
        """Free tier speed limit (HTTP 429): return how long to wait, or None if it's another error."""
        if getattr(err, "code", None) != 429:
            return None
        m = re.search(r"retry in ([\d.]+)s|retryDelay['\"]?:\s*['\"]?(\d+)", str(err))
        return float(next(g for g in m.groups() if g)) + 2 if m else 30


class Claude:
    def __init__(self, model):
        import anthropic
        self.model, self.client = model, anthropic.Anthropic(max_retries=4)

    def call(self, prompt):
        resp = self.client.messages.parse(
            model=self.model, max_tokens=8000, system=SYSTEM, output_config={"effort": "low"},
            output_format=TagBatch, messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason != "end_turn":
            raise RuntimeError(f"stop_reason={resp.stop_reason}")
        return resp.parsed_output, resp.usage.input_tokens, resp.usage.output_tokens

    def wait_seconds(self, err):
        return None  # the Anthropic SDK already retries rate limits itself


def strict_schema(model_cls):
    """Pydantic schema -> plain JSON schema with references inlined and no extra fields allowed
    (the strict format Groq's structured outputs expect)."""
    schema = model_cls.model_json_schema()
    defs = schema.pop("$defs", {})

    def fix(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return fix(defs[node["$ref"].split("/")[-1]])
            node = {k: fix(v) for k, v in node.items() if k != "title"}
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            return node
        if isinstance(node, list):
            return [fix(x) for x in node]
        return node

    return fix(schema)


class Groq:
    """Groq runs open models (e.g. OpenAI's gpt-oss, Alibaba's Qwen) fast, with a free tier."""

    def __init__(self, model):
        import groq
        self.groq, self.model = groq, model
        self.client = groq.Groq(api_key=os.environ["GROQ_API_KEY"], max_retries=0)
        self.schema = strict_schema(TagBatch)

    def call(self, prompt):
        extra = {"reasoning_effort": "low"} if "gpt-oss" in self.model else {}
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": "tag_batch", "strict": True, "schema": self.schema}},
            **extra,
        )
        parsed = TagBatch.model_validate_json(resp.choices[0].message.content)
        return parsed, resp.usage.prompt_tokens, resp.usage.completion_tokens

    def wait_seconds(self, err):
        if not isinstance(err, self.groq.RateLimitError):
            return None
        retry = err.response.headers.get("retry-after") if err.response is not None else None
        return float(retry) + 1 if retry else 20


def make_provider(model):
    if model.startswith("claude"):
        return Claude(model)
    if model.startswith("gemini") or model.startswith("gemma"):
        return Gemini(model)
    return Groq(model)  # e.g. openai/gpt-oss-120b, qwen/qwen3.8-27b


# ----------------------------- tagging ---------------------------------------
def load_set(name):
    path = DATA / ("eval_sample.csv" if name == "eval" else "clean_reviews.csv")
    return pd.read_csv(path).reset_index(drop=True).assign(row_id=lambda d: d.index)


def tag_batch(provider, rows, max_waits=6):
    body = "\n".join(
        f'<review id="{r.row_id}" app="{r.app}" stars="{r.rating}">{r.text}</review>' for r in rows.itertuples()
    )
    prompt = f"Tag these {len(rows)} reviews.\n\n{body}"
    for _ in range(max_waits):
        try:
            parsed, tin, tout = provider.call(prompt)
            break
        except Exception as e:
            wait = provider.wait_seconds(e)
            if wait is None:
                raise
            print(f"  free-tier limit hit, waiting {wait:.0f}s...")
            time.sleep(wait)
    else:
        raise RuntimeError("still rate-limited (daily cap?) - re-run later to continue")
    if parsed is None:
        raise RuntimeError("model returned no parsable JSON")
    wanted = set(rows.row_id)
    return [t for t in parsed.tags if t.id in wanted], tin, tout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["eval", "all"], default="eval")
    ap.add_argument("--model", required=True, help="e.g. gemini-2.5-flash or claude-haiku-5-5")
    ap.add_argument("--workers", type=int, default=1, help="parallel requests (keep 1 on free tiers)")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    provider = make_provider(args.model)
    df = load_set(args.set)
    out = DATA / f"tags_{args.set}_{args.model.replace('/', '_')}.jsonl"
    done = set()
    if out.exists():
        done = {json.loads(line)["review_id"] for line in out.read_text(encoding="utf-8").splitlines()}
    todo = df[~df.review_id.isin(done)]
    chunks = [todo.iloc[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    print(f"{args.model}: {len(todo)} reviews to tag in {len(chunks)} requests ({len(done)} already done)")

    tok_in = tok_out = tagged = failed = 0
    with ThreadPoolExecutor(args.workers) as pool, out.open("a", encoding="utf-8") as f:
        futures = {pool.submit(tag_batch, provider, c): c for c in chunks}
        for fut in as_completed(futures):
            rows = futures[fut].set_index("row_id")
            try:
                tags, i, o = fut.result()
            except Exception as e:  # one failed request shouldn't kill the run; re-run picks it up
                failed += 1
                print(f"  request failed ({type(e).__name__}: {str(e)[:200]})")
                continue
            tok_in, tok_out = tok_in + i, tok_out + o
            for t in tags:
                rec = {"review_id": rows.loc[t.id, "review_id"], **t.model_dump(exclude={"id"})}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            tagged += len(tags)
            print(f"  tagged {tagged}/{len(todo)}")

    p_in, p_out = PAID_PRICES.get(args.model, (0, 0))
    cost = tok_in / 1e6 * p_in + tok_out / 1e6 * p_out
    print(f"done: {tagged} tagged, {failed} failed requests | tokens in {tok_in:,} out {tok_out:,} | "
          + (f"cost ${cost:.3f}" if cost else "cost $0 (free tier)"))
    if failed or tagged < len(todo):
        print("some reviews are not tagged yet - just run the same command again to finish them")


if __name__ == "__main__":
    main()

"""Step 3 - Tag: an LLM splits each review into points (topic + type + evidence quote), then gives the
review an overall sentiment, churn signal and summary (aspect-based sentiment analysis).

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
from taxonomy import OVERALL, POINT_TYPES, SEVERITY, TOPICS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BATCH = 20
# USD per million tokens (input, output). Gemini free tier = $0.
PAID_PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00), "claude-opus-5-5": (4.00, 20.00)}

class Point(BaseModel):
    # field order matters: the model writes the evidence BEFORE deciding topic and type
    quote: str  # exact words from the review this point is based on
    topic: Literal[tuple(TOPICS)]
    type: Literal[tuple(POINT_TYPES)]
    severity: Literal[tuple(SEVERITY)]  # "none" unless type is negative


class ReviewTag(BaseModel):
    id: int
    points: list[Point]  # as many as the review contains
    churn_signal: bool  # says they are leaving, uninstalled, cancelled or switching
    switching_to: str  # competitor named as the replacement, or "" if none
    overall_sentiment: Literal[tuple(OVERALL)]  # judged last, from the whole text + stars
    summary: str  # the core point in under 15 words


class TagBatch(BaseModel):
    tags: list[ReviewTag]


def _bullets(d):
    return "\n".join(f"- {k}: {v}" for k, v in d.items())


SYSTEM = f"""You analyse app-store reviews of note-taking apps for a product team, using aspect-based
sentiment analysis: every review is split into separate points, and each point gets a topic and a type.

Work through each review in this order:
1. Read the whole review. Note the app and the star rating, but the TEXT decides; stars are only context.
2. Split the review into its separate points: every distinct opinion, complaint, request, question or
   statement about the app. There is no limit; a review may have one point or many.
3. For each point, in this order:
   a. quote: copy the exact words it is based on (short, up to about 12 words).
   b. topic: the one topic it is about (list below). Prefer a specific topic; use "overall" only when
      the point names nothing specific, and "other" only for spam, off-topic or unclear text.
   c. type: positive, negative, neutral or request.
   d. severity: for negative points, how much it hurts the user; for every other type use "none".
   If the same topic comes up twice with the same type, keep only one point for it.
4. churn_signal: true only if the user says they are leaving, have uninstalled, cancelled, deleted their
   account or are switching. switching_to: the replacement app they name, else "".
5. overall_sentiment: judge the review as a whole from the text AND the stars (rules below).
6. summary: the core message in under 15 words, plain English.

Topics:
{_bullets(TOPICS)}

Point types:
{_bullets(POINT_TYPES)}

Severity (negative points only):
{_bullets(SEVERITY)}

Overall sentiment:
{_bullets(OVERALL)}
If the text and the stars disagree (e.g. 5 stars but only complaints), trust the text.

Tricky cases:
- Sarcasm ("great, another update that breaks everything") is negative.
- Past praise with a present complaint ("used to be the best app, now it sucks") is a negative point
  about the present; do not tag the past praise as positive.
- A question ("how do I export my notes?") is a neutral point on its topic.
- Resellers, adverts or spam inside a review ("Notion AI plan available cheap") are topic "other".
- A request to bring back an old feature is type "request" on that feature's topic.

Return one tag per review id."""


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
        """Return how long to wait before retrying, or None if retrying won't help.
        429 = free-tier speed limit; 503 = Google's servers are busy (temporary)."""
        code = getattr(err, "code", None)
        if code == 503:
            return 30
        if code != 429:
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
            max_completion_tokens=16000,  # 20 reviews x several points with quotes is a long answer
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
            print(f"  free tier busy or limited, waiting {wait:.0f}s...")
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

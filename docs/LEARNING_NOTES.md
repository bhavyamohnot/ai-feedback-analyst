# Learning Notes: AI Feedback Analyst

Short notes on every concept used in this project. Read one section at a time.
Each ends with **Say it in an interview**, a one-line version you can use out loud.

---

## 1. The product problem: "Voice of the Customer"

Companies get thousands of reviews, support tickets and survey answers. Nobody reads them all, so
decisions get made on the loudest complaint or the CEO's gut feeling.

**Analogy:** 4,000 people each shout one sentence at you in a stadium. You can't listen to all of
them, but you want to know the 5 things most of them are shouting about.

This project's job: read everything, group it into themes, rank the themes, and show real quotes as proof.

**Say it in an interview:** "I built a tool that turns thousands of reviews into a ranked list of what
to fix, with real quotes as evidence."

---

## 2. Data pipeline

A pipeline is a chain of small steps where each step's output is the next step's input:
`collect -> clean -> tag -> evaluate -> rank -> answer questions -> send digest`.

**Analogy:** a kitchen. Buy vegetables (collect), wash and chop them (clean), cook (tag with AI),
taste before serving (evaluate), plate (dashboard and digest).

Why split it into steps? If something breaks, you only fix and re-run that one step.

**Say it in an interview:** "I split it into separate steps so each one can be checked and re-run on its own."

---

## 3. Scraping vs. an API

- **API:** the company gives you an official door to ask for data (e.g. "give me 200 reviews").
- **Scraping:** reading the public web page the way a browser does and pulling the data out.

We used `google-play-scraper`, a free library that reads the public Play Store review pages.
Play Store reviews are public, so this is fine. Sites like LinkedIn forbid scraping in their terms,
which is one reason we didn't pick the job-hunt project.

**Pagination:** the Play Store hands out reviews 200 at a time, with a "bookmark" (continuation token)
to ask for the next 200. `collect.py` keeps asking until the reviews are older than 12 months.

---

## 4. Data cleaning

Raw data is always messy. We removed 3 kinds of rows, and the script prints how many each rule removed:

| Rule | Removed | Why |
|---|---|---|
| Exact duplicate text | 396 | Copy-paste or spam reviews would double-count a complaint |
| Under 5 words | 960 | "good app" has no theme to extract |
| Mostly non-English | 31 | The AI and our checks are set up for English |

5,495 -> **4,108** reviews kept.

**Why print the counts?** So anyone can check the cleaning didn't throw away something important.
That's called making your work **auditable**.

**Say it in an interview:** "I cleaned 5,495 reviews down to 4,108 and logged what each rule removed,
so the analysis could be checked."

---

## 5. First look at the data (before any AI)

| | Notion | Evernote |
|---|---|---|
| Reviews in last 12 months (raw) | 3,626 | 1,869 |
| Average rating, last 12 months | 3.85 | **1.63** |
| 1-star share | 16% | **74%** |
| Company replied to reviews | 0.1% | 1.3% |

Evernote's all-time Play Store rating is 3.54, but the last 12 months average 1.63. Something
recently made its users very unhappy. That's a **hypothesis**, and the AI tagging step will tell us what.

**PM lesson:** always look at the simple numbers first. They tell you which questions to ask the AI.

---

## 6. Building the theme list (taxonomy)

Before any AI tagging, we read 145 reviews (both apps, every star rating) and grouped similar
complaints together. This is **affinity mapping**, the same thing PMs do with sticky notes after user interviews.
Result: 13 themes in `src/taxonomy.py`, e.g. `performance`, `pricing_free_plan`, `ads_upsell`, `billing_trust`.

**Why not let the AI invent themes for every review?** You'd get "slow app", "laggy", "performance issues"
as three different themes and couldn't count anything. A **fixed list** makes the results countable and
comparable over time.

**Design rules we followed:**
- Each theme should be clearly different (we split `ads_upsell` from `pricing_free_plan`, because
  "too many pop-ups" and "too expensive" need different fixes).
- Always have an `other` bucket, and watch its size. If it gets big, a theme is missing.

**Say it in an interview:** "I built the theme list by affinity-mapping a sample of reviews first,
so the AI was tagging against categories that reflect real user language."

---

## 7. LLM API and structured output

**LLM API:** instead of typing into ChatGPT, your code sends text to the model over the internet and
gets the answer back. You pay per **token** (about ¾ of a word), with separate prices for input
(what you send) and output (what it writes).

**Structured output:** we don't ask "what do you think of this review?" (free text, impossible to count).
We give the model a strict form to fill in:

```
themes: [performance]    sentiment: negative    severity: high
churn_signal: true       switching_to: "Google Keep"    summary: "App crashes after every update"
```

The API **guarantees** the answer matches this form (we define it with Pydantic in `src/tag.py`),
so the code never breaks on a weird answer.

**Analogy:** asking 100 people "how was your trip?" vs. handing them a form with checkboxes. Only the
form gives you numbers.

**Cost tricks used:** 20 reviews per request (the instructions are sent once, not 20 times), and
`effort: low` because sorting reviews is a simple task that doesn't need deep thinking.

---

## 8. Evals: the most important AI concept for a PM

An **eval** checks how often the AI is right, against answers a human agreed on.

1. You hand-label 100 reviews. That's the **gold set** (answer key).
2. The AI labels the same 100.
3. We compare and get a score.

**Leakage:** the 100 test reviews **don't include** the 145 we read to design the themes.
Testing on reviews you studied is like an exam with questions you've already seen. The score looks
great but means nothing.

**Metrics we use:**

| Metric | Plain meaning |
|---|---|
| Theme hit rate | Your main theme is one of the AI's 1–2 themes |
| Sentiment accuracy | Same positive/mixed/negative as you |
| **Precision** (churn) | When the AI says "this user is leaving", how often is it true? |
| **Recall** (churn) | Of all users who really are leaving, how many did the AI catch? |

**Precision vs. recall analogy:** a fishing net. Recall = how many of the fish in the lake you caught.
Precision = how much of what's in your net is actually fish, not boots.

**Error analysis:** `evaluate.py` prints every disagreement. Reading *why* the AI was wrong
(vague review? bad theme definition?) tells you what to fix. Sometimes the fix is in the theme list, not the AI.

**Say it in an interview:** "Before trusting the AI on 4,000 reviews, I hand-labelled 100 and measured
agreement, then read every disagreement to improve the prompt."

---

## 9. Building it for ₹0: free tiers

This project runs entirely free on Google's **Gemini API free tier**. A free tier means you pay
with **limits** instead of money: a cap on requests per minute and per day.

How the code copes with limits:
- **Batching:** 20 reviews per request, so 4,108 reviews take only ~206 requests.
- **Auto-wait:** if Google says "too many requests" (error code **429**), the tagger waits and retries.
- **Resumable runs:** results are saved after every request. If the daily cap stops a run, the same
  command continues where it stopped the next day.

**API key safety:** the key lives in `.env`, which `.gitignore` blocks from GitHub. A leaked key
lets strangers use your quota.

**Free-tier catch:** Google may use what you send to improve its models. That's fine for public
Play Store reviews, but never send private customer data on a free tier.

---

## 10. "Thinking" models: more thinking isn't always better

Newer models "think" (write hidden reasoning) before answering. Test on 20 reviews:

| Gemini 3.8 Flash | Time for 20 reviews |
|---|---|
| Default thinking | ~115 s for just 5 reviews |
| `thinking_level = LOW` | **46 s** for 20 |

Sorting a review into a theme is easy, so deep thinking only wastes time and quota.
**PM lesson:** match the model's effort to the task's difficulty.

---

## 11. Choosing a model with evidence (quality vs. speed)

Two free models both returned the right format:

| Model | Size | Time for 20 reviews |
|---|---|---|
| Gemini 3.5 Flash-Lite | small, fast | ~5 s |
| Gemini 3.8 Flash | bigger, smarter | ~46 s |

Plan: run **both** on your 100 hand-labelled reviews, compare accuracy, then pick. If the small model
scores about the same, it's ~9x faster, so the full run takes ~17 minutes instead of ~2.5 hours.
That's a real PM decision: **is the extra quality worth the extra time and quota?**

---

## 12. Open vs. closed models, and one tagger for many providers

| | Closed model | Open-weight model |
|---|---|---|
| Example here | Google **Gemini** | OpenAI **gpt-oss**, Alibaba **Qwen** |
| Can you download it? | No, only use it through Google's API | Yes, anyone can download and run it |
| Why companies care | Usually the strongest, easy to start | Privacy (runs on your own servers), no lock-in, cheaper at scale |

**Groq** is a company that runs open models on very fast chips. It has a free tier, so we use it to
try open models without owning a powerful computer.

**One tagger, many providers:** `tag.py` picks the provider from the model name
(`gemini-...` → Google, `openai/...` → Groq, `claude-...` → Anthropic). The prompt, theme list and
output form stay identical, so the comparison is fair. This is called being **model-agnostic**:
if one provider gets expensive or shuts down a free tier, you switch with one word.

**Structured output isn't equally reliable everywhere** (from our test runs):

| Model | Valid JSON? | Time for 20 reviews |
|---|---|---|
| Gemini 3.5 Flash-Lite | ✅ every time | ~5 s |
| Gemini 3.8 Flash | ✅ every time | ~46 s |
| gpt-oss-120b (Groq) | ✅ every time | ~5 s |
| gpt-oss-20b (Groq) | ⚠️ 1 bad answer in 6 requests (re-run fixed it) | ~2 s |
| Qwen 3.8 (Groq) | ❌ broken JSON, dropped | – |

**PM lesson:** reliability is a product requirement, not just accuracy. A model that's right 95% of
the time but breaks the format 1 in 6 times needs retry logic, or it'll crash the pipeline.

**Say it in an interview:** "I made the pipeline model-agnostic and benchmarked four free models from
two providers on the same labelled set, comparing accuracy, speed and format reliability."

---

## Coming next

- **Embeddings and RAG:** letting the AI answer questions using *our* reviews, with sources
- **n8n:** drag-and-drop automation that runs the pipeline every week
- **Prioritisation:** turning tags into a ranked "what to fix first" list

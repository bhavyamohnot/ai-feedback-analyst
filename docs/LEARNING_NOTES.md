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

## 6. Building the topic list (taxonomy)

Before any AI tagging, we read 145 reviews (both apps, every star rating) and grouped similar
comments together. This is **affinity mapping**, the same thing PMs do with sticky notes after user interviews.
Result: 13 topics in `src/taxonomy.py`, e.g. `performance`, `ai`, `pricing_plans`, `ads_prompts`, `billing`.

**Why not let the AI invent topics for every review?** You'd get "slow app", "laggy", "performance issues"
as three different topics and couldn't count anything. A **fixed list** makes the results countable and
comparable over time.

**Design rules we followed:**
- Each topic should be clearly different (we split `ads_prompts` from `pricing_plans`, because
  "too many pop-ups" and "too expensive" need different fixes).
- Topic names are **neutral**: `performance` covers "so fast!" and "crashes constantly".
- `overall` holds general opinions that name nothing specific ("great app", "worst app ever").
- Always have an `other` bucket, and watch its size. If it gets big, a topic is missing.

### Version 1 → version 2 (a real design decision)

**v1** had a `praise` theme next to problem themes, plus one sentiment per review. Bhavya spotted the flaw:
if all praise goes into one bucket, sentiment tells you nothing new (praise is always positive), and
"AI is amazing" and "AI is forced on me" end up in different buckets, so you can't see how users feel about the AI.

**v2 = aspect-based sentiment analysis**, the standard approach in customer-feedback tools:

1. Split the review into **points** (as many as it has).
2. Each point gets a **topic** (what it's about) and a **type**: 👍 positive / 👎 negative / ➖ neutral / 💡 request.
3. The whole review gets an **overall sentiment** (positive / mixed / negative / neutral) from the text **and** the stars.
4. Plus: are they leaving, and to which competitor?

**Analogy:** a restaurant review says "Food was great, service was slow." v2 records
**food = 👍** and **service = 👎**, instead of throwing the whole review into a "praise" or "complaint" folder.

Why "request" is a point type, not a topic: "please bring back the old editor" is *about* `editing`.
Tagging it `editing` + 💡 tells the team which area people want improved.

**Say it in an interview:** "My first design had a praise bucket, which made sentiment redundant. I switched
to aspect-based sentiment, so every topic has its own positive/negative split. That turned the output into a
strengths-vs-weaknesses map per app instead of a complaint counter."

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

**Metrics we use** (each review has a *list* of points, so we compare lists):

| Metric | Plain meaning |
|---|---|
| **Topic recall** | Of the topics *you* tagged, how many did the AI also find? (did it miss things?) |
| **Topic precision** | Of the topics the *AI* tagged, how many did you also tag? (did it invent things?) |
| **F1** | One number combining recall and precision. Used to rank models |
| Pair recall / precision / F1 | The same, but topic **and** type must match (e.g. performance + 👎) |
| Overall sentiment accuracy | Same overall sentiment as you |
| Churn precision / recall | Same idea for "is this user leaving?" |

**Precision vs. recall analogy:** a fishing net. Recall = how many of the fish in the lake you caught.
Precision = how much of what's in your net is actually fish, not boots.

**Why F1 and not just the average?** A model that tags every topic on every review gets 100% recall
but terrible precision. F1 punishes being lopsided, so it only scores high when both are good.

**Counting rule:** within one review, each topic counts once, even if it's mentioned twice.

**Evidence quotes:** the AI must copy the exact words behind each point *before* choosing the topic,
like "show your working" in maths. It makes fewer mistakes, and anyone can check *why* it tagged something.

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

## 13. Eval results, and why the fix was in the spec, not the AI

Bhavya hand-labelled 100 reviews. The 4 models scored against those labels:

| Model | Topic + type F1 | Overall sentiment right | Churn recall |
|---|---|---|---|
| Gemini 3.8 Flash | **65%** | **85%** | **100%** |
| gpt-oss-120b | 65% | 79% | 87% |
| **Gemini 3.5 Flash-Lite** (used for the full run) | 64% | 84% | **100%** |
| gpt-oss-20b | 58% | 84% | 73% |

**First choice: Flash.** It tied for the best F1, was best on overall sentiment, and never missed a user
who said they were leaving. Churn is the signal a product team cares about most.

**What actually happened:** when the full run started, Google's servers returned **error 503
("model experiencing high demand")** for Flash again and again. After about 15 minutes, 0 reviews were tagged.
Flash-Lite was answering fine, so we switched. That's a sensible trade: **only 1 point lower on F1,
also 100% churn recall**, and about 10x faster. What we give up: Flash-Lite finds fewer points
(65% topic recall vs 81%), so the counts are conservative. It rarely invents a point, but it misses some.

**PM lesson:** availability is part of model choice. The "best" model is no use if it can't
answer when you need it. That's why the tagger is model-agnostic: switching took one word.

**Error analysis:** reading the disagreements showed that **about half of all errors in every model**
came from one blurry boundary. Bhavya tagged "best app for note making" as `overall`, but the AI
chose `core_features`, because the old definition said "notes, organising". The rule was unclear,
not the model. Fix: `overall` now covers verdicts on the whole app and its main job, and
`core_features` needs a named feature (databases, templates, search...).

Strong topics even before the fix: ads_prompts (100% recall, 96% precision), pricing (94% recall), ai (91%).

**Caveat (be honest about it):** the definitions changed after the eval, so the 65% is the score
*before* the fix. We didn't re-score, to avoid tuning on the same test set.

**Say it in an interview:** "I benchmarked 4 models on 100 hand-labelled reviews. Error analysis showed
half the disagreements came from one ambiguous category boundary, so I fixed the spec rather than
swapping models. When the top model was overloaded on launch day, I switched to the runner-up, 1 point behind
on F1 with the same 100% churn recall. That swap took one word because the pipeline is model-agnostic."

---

## 14. From tags to decisions: the analysis (`src/analyze.py`)

The tagger gives ~5,500 points. `analyze.py` turns them into 4 product answers:

| Question | How it's measured |
|---|---|
| What do users love or hate? | **Net sentiment** per topic = (positive − negative) ÷ (positive + negative), from −100 to +100 |
| What should we fix first? | **Impact score** = each complaint weighted by severity (low 1, medium 2, high 3), added up |
| What do users want? | Count of 💡 request points per topic, with the most-liked quotes |
| Who are we losing users to? | Competitors named in `switching_to` (vague answers like "another app" removed) |

**Why impact score, not just a count?** 100 "it's a bit slow" complaints hurt less than 100 "I lost all my notes".
Weighting by severity is a simple form of the **RICE / impact** thinking PMs use to prioritise.

**Likes as evidence:** quotes are sorted by the review's Play Store "helpful" likes, because
other users clicking "helpful" means more people agree with it.

**Trends over time:** counting complaints per month shows *when* a problem started, which usually points
to *why* (a release, a price change, an ads rollout).

**Say it in an interview:** "I ranked problems by volume × severity, backed each with the most-upvoted quotes,
and used monthly trends to tie spikes to likely causes."

---

## 15. The dashboard (`app.py`, Streamlit)

**Streamlit** turns a Python script into a web page: every `st.metric`, `st.altair_chart`,
`st.tabs` line becomes a piece of the page. No HTML or JavaScript needed.

Design choices (each one is a rule from data-viz practice):
- **Color has a job.** Blue = praise, red = complaints everywhere; Notion = blue and Evernote = orange
  only on charts that compare the two apps. Buttons use violet so red always means "complaint".
- **The butterfly chart** (complaints left, praise right) shows each topic's love/hate split at a glance.
- **One number per tile** on the overview ("3.56★", "4% say they're leaving") - the headline before the detail.
- **Evidence next to every claim:** the "Fix first" tab shows the most-liked real quotes under each problem.
- **Light and dark mode**, both checked with screenshots.

**Why it needs no API key:** the dashboard only *reads* files the pipeline already produced. Only the
"Ask the reviews" tab calls an AI model. So the live demo is free and can't break when an AI provider is busy.

---

## 16. RAG: letting the AI answer from *our* reviews (`src/rag.py`)

**Problem:** ask ChatGPT "why do Notion users hate the AI?" and it guesses from its training data.
**RAG (retrieval-augmented generation)** = find the relevant reviews first, then make the AI answer *only* from them.

**Analogy:** an open-book exam. The AI isn't trusted to remember; it must look things up and cite the page.

Three steps:
1. **Embeddings.** Each review becomes a list of 384 numbers (a *vector*) that captures its meaning.
   Reviews with similar meaning get similar vectors, so "takes forever to open" sits near "so slow to load"
   even though they share no words. That's **semantic search**, vs. keyword search.
2. **Retrieve.** The question becomes a vector too; we take the 25 reviews pointing in the most similar
   direction (**cosine similarity**). With 4,108 reviews a NumPy matrix is enough; at millions you'd use a
   **vector database** (Pinecone, pgvector, Qdrant).
3. **Generate with citations.** Gemini gets the question + the 25 reviews + topic counts for *all* reviews,
   with rules: cite every claim as [n], use the counts for "how many" questions, and say so if the reviews don't answer it.
   Citations make answers **checkable**, the main defence against **hallucination** (the AI making things up).

**A real constraint we hit:** Google's free embedding API allows only **1,000 texts a day**, and we had 4,108.
Fix: **BGE-small**, a free open-source embedding model that runs on the laptop (2.5 minutes, no quota).
Same idea as section 12: don't get locked in to one provider.

**Hybrid answer:** retrieved quotes say *why*; pre-computed counts say *how many*. RAG alone can't count,
because it only sees 25 reviews.

**Say it in an interview:** "I built a RAG Q&A over 4,108 reviews: local open-source embeddings for semantic
search, an LLM that answers only from retrieved reviews, and a citation on every claim so a PM can verify it."

---

## 17. Writing the PRD from data (`docs/PRD_Notion_Android_Performance.md`)

The pipeline picked the problem: **performance** was #1 by impact score. The PRD then answers:
- **Is it real?** 416 reviews, 53% high severity, 2.29★, leaving at about 2x the normal rate, 1,468 "helpful" likes.
- **What exactly?** Sub-problems: slow open (37%), lag, long pages, crashes.
- **One bad release or long-running?** It shows up in all 35 app versions, so it's long-running. That changes the
  solution: a performance budget in CI, not a rollback.
- **How will we know it worked?** North star = the share of reviews complaining about performance (17% → <10%),
  re-measured weekly by the n8n digest. Guardrails = desktop doesn't get worse, no new upgrade nagging (the Evernote lesson).
- **Honesty:** the PRD states what reviews can't tell you (device mix, real load times) and marks those
  metrics *needs internal data*.

**Say it in an interview:** "The data chose the problem; the PRD turned it into scoped requirements, a
measurable north star, and guardrails borrowed from what was driving the competitor's users away."

---

## 18. n8n: the same AI, as a visual workflow (`n8n/`)

**n8n** is a drag-and-drop automation tool: boxes (**nodes**) joined by arrows. Each node does one job and passes
its output (JSON **items**) to the next. We self-host it on the laptop (free), started by `n8n/start_n8n.ps1`.

**Workflow 1: Ask the reviews (an AI agent).**
`Chat -> AI Agent`, with three things plugged into the agent:
- a **chat model** (Gemini Flash-Lite), the brain;
- **memory** (last 6 messages), so "and for Evernote?" works as a follow-up;
- two **tools**, which are plain HTTP calls to our own `src/api.py`: `search_reviews` (semantic search) and `get_topic_stats` (counts).

Difference from the Python RAG (section 16): Python **always** retrieves, then answers (a fixed **chain**).
The **agent** *decides* which tool to call, how many times and with what words (for example, search Notion,
then Evernote, then compare). The tool inputs are filled in by the model through `$fromAI('query', ...)`.
That's more flexible, but slower and less predictable. Rule of thumb: **chain when the steps are known, agent when they aren't.**

**Workflow 2: Weekly digest.** `Schedule (Mon 9am) -> Execute Command (weekly.py) -> Code -> LLM chain (Gemini) -> Code -> file`.
- **Schedule trigger:** cron-like timing. Here the workflow is the *orchestrator* and Python does the heavy lifting.
- **Code node:** small JavaScript glue (parse the JSON, build the prompt, build a markdown table).
- **Spike rule (in weekly.py):** a topic is a spike if its share of this week's reviews is at least **1.5x** the previous 4-week
  average **and** it has at least **5 complaints**, so 1 -> 2 complaints isn't an alarm.
- Numbers come from code; the LLM only **writes** them up. **LLMs explain numbers; they shouldn't compute them.**

**Real-world gotchas we hit (good interview stories):**
- n8n needs Node 24; Node 26 was too new for one native part, so we used a portable Node 24.
- n8n 2.x **disables Execute Command by default** (it can run anything on the machine). We turned it on
  deliberately (`NODES_EXCLUDE=[]`), limited file nodes to `data/digest/` (`N8N_RESTRICT_FILE_ACCESS_TO`),
  and made n8n listen on this laptop only (`N8N_LISTEN_ADDRESS=127.0.0.1`). This is **least privilege**.
- API keys live in n8n's encrypted **credentials** store, never inside the workflow JSON, so the JSON is safe to put on GitHub.

**Say it in an interview:** "I automated the weekly voice-of-customer loop in n8n: a scheduled workflow refreshes
the data, detects complaint spikes against a 4-week baseline, and has an LLM write the digest. A second workflow
is a tool-using AI agent that answers PM questions with cited reviews."

---

## Coming next

- **Deploy:** putting the dashboard online (Streamlit Community Cloud)
- **Resume bullets:** only real numbers from these runs

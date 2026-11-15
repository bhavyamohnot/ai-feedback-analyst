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

## Coming next

- **LLM API:** how a program talks to an AI model
- **Theme discovery:** letting the AI suggest categories, then a human fixing them
- **Structured output:** making the AI answer in a fixed format a program can read
- **Evals:** measuring how often the AI is right
- **Embeddings and RAG:** letting the AI answer questions using *our* reviews, with sources
- **n8n:** drag-and-drop automation that runs the pipeline every week

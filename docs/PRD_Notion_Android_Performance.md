# PRD: Make Notion on Android feel instant

**Author:** Bhavya Mohnot · **Status:** Proposal (portfolio case study) · **Date:** Nov 2026
**Evidence base:** 2,441 Notion Google Play reviews (Nov 2025 – Nov 2026), AI-tagged and ranked with the
[AI Feedback Analyst](../README.md). Competitor baseline: 1,667 Evernote reviews from the same period.

> Notion is an independent case study built only from public reviews. No internal Notion data was used;
> every number below comes from the public reviews and can be reproduced by running the pipeline.

---

## 1. TL;DR

Android users like **what** Notion does (general opinion: **+89** net sentiment) but hate **how it feels**
on their phone. Speed and crashes are the **#1 complaint by impact**: 416 reviews (17%), more than half rated
high severity, average **2.29★**, and those users say they're leaving at **about 2x the normal rate**.
The problem has shown up in every app version for 12 months, so it won't fix itself with one patch.

**Proposal:** a 2-quarter "Android feels instant" programme: (1) open to a usable page fast, including
offline, (2) make long pages and databases scroll smoothly, (3) cut crashes, (4) add quick capture
(widget) so the most common mobile job doesn't need the full app. Success = performance complaints
fall from **17% to under 10%** of reviews and the Play rating rises from **3.56 to 3.9+**.

---

## 2. Problem and evidence

### 2.1 What users say

| Signal (Notion, 12 months) | Value |
|---|---|
| Reviews with a performance complaint | **416 of 2,441 (17%)**, the #1 topic by impact score (1,010; next is ease of use at 556) |
| Rated high severity ("blocks use, drives me away") | **53%** (219 reviews) |
| Average stars of these reviewers | **2.29★** vs 3.56★ for all Notion reviews |
| Say they're leaving | **8.7%** vs 4.5% across all Notion reviewers |
| "Helpful" likes from other users on these reviews | **1,468** (people agreeing) |
| Reviews that mention mobile/phone/tablet | 362; average **2.65★ vs 3.72★** for the rest |
| Notion replies to Play Store reviews | **0.04%** (1 reply in 2,441 reviews) |

### 2.2 What exactly is slow (keyword split of the 416 complaints; a review can match several)

| Sub-problem | Reviews | Example (most-liked) |
|---|---|---|
| Slow to load or open | 155 (37%) | "Android app is horrible. There's a big delay in everything" (29 likes) |
| General lag | 78 (19%) | "navigating very difficult and laggy" (22 likes) |
| Long pages, databases, scrolling | 62 (15%) | "pages become unscrollable" (41 likes) |
| Crashes or closes | 56 (13%) | "app crashes immediately" (25 likes) |
| Freezes or hangs | 35 (8%) | "only load half the content" (23 likes) |
| Typing lag | 20 (5%) | n/a |
| Battery, heat, memory | 17 (4%) | n/a |
| Tablet layout bugs | n/a | "Tablet version extremely bugged out" (54 likes, the most-liked complaint) |

### 2.3 It's chronic, not one bad release

- Across **35 app versions** with 25+ reviews each (v0.6.3424 → v0.6.4288), the share of reviews
  complaining about performance ranged from **4% to 29%** and never reached zero.
- It peaked at **23% in Mar and May 2026**, when Notion's monthly rating also hit its low (**3.22★ in April**).
  It eased to 12–13% from Jun to Oct, then rose again to 21% in early Nov 2026.
- **Implication:** this is about the architecture and the budget for speed, not a regression to roll back.

### 2.4 Users want the desktop experience on their phone

- 222 feature requests in total. **50 explicitly ask for desktop/mobile parity**, e.g. "Please add this feature
  to mobile!" (24 likes), "I just wish mobile had better widgets" (13), "bring back the home button on mobile" (10).

### 2.5 Competitor lesson (Evernote)

Evernote's last 12 months averaged **1.53★**, and **34%** of reviewers say they're leaving, driven by pricing
(36% of reviews) and ads/upgrade pop-ups (36%; two spikes, Feb and Sep 2026). Its leaving users name
**OneNote, Obsidian and UpNote**; Notion's name **Obsidian** most (7 of 46 named). **Lesson for this PRD:** the speed fixes
must ship free for everyone. Charging for a usable app, or adding upgrade prompts, is exactly what's
driving Evernote's users away.

---

## 3. Users and jobs to be done

| Segment | Job on Android | Pain today |
|---|---|---|
| **Capturers** (students, professionals on the go) | "Jot this down in 5 seconds before I forget" | Cold start + page load is slower than the thought |
| **Checkers** | "Look up my task list / class notes / meeting doc" | Long pages and databases load half, freeze or won't scroll |
| **Desktop-first power users** | "Do on my phone what I set up on my laptop" | Missing or hidden features, so they open the laptop or give up |
| **Tablet users** | "Use Notion as my main notebook" | Layout bugs (most-liked complaint) |

Primary persona for v1: **the Capturer/Checker on a mid-range Android phone**. India is the review
source, and mid-range devices are the majority there.

---

## 4. Goals and non-goals

**Goals**
1. Open the app to a usable page fast, even on mid-range phones and bad networks.
2. Long pages and databases scroll smoothly and never "load half".
3. Crashes become rare.
4. The most common mobile job (quick capture) takes 1 tap.

**Non-goals (this cycle)**
- Full desktop parity (we fix the top parity requests only).
- A separate "Notion Lite" app. It was considered (see §7) and rejected for now.
- AI feature changes. AI is the #4 complaint and needs its own PRD: users are split (106 praise vs
  167 complaints), and its complainers say they're leaving at 17%.
- Monetisation changes: none, per the Evernote lesson.

---

## 5. Success metrics

| Type | Metric | Baseline | Target (2 quarters after launch) |
|---|---|---|---|
| **North star** | Share of Play reviews with a performance complaint (measured by this pipeline) | 17% | **< 10%** |
| Outcome | Play Store average rating (12-month, Android) | 3.56★ | **3.9★+** |
| Outcome | Leaving rate among reviewers | 4.5% | ≤ 3.5% |
| Product (internal, proposed) | Cold start → first page usable, p75, mid-range device | *needs internal data* | < 2 s |
| Product (internal, proposed) | Crash-free sessions (Android vitals) | *needs internal data* | ≥ 99.5% |
| Product (internal, proposed) | Quick-capture widget weekly users | 0 | 10% of Android WAU |
| **Guardrail** | Desktop / iOS performance and complaint share | current | no worse |
| **Guardrail** | Pricing + ads complaint share | 2.3% + 0.4% | no increase |

*Why a review-based north star:* it's public and comparable with competitors, and the pipeline re-measures it
every week (the n8n digest), so a regression shows up in days, not quarters.

---

## 6. Requirements

| Priority | Requirement | Addresses |
|---|---|---|
| **P0** | **Fast open:** show the last-opened page from a local cache immediately, then refresh in the background; skeleton UI instead of a blank screen | Slow to load (37%) |
| **P0** | **Offline read** of recently opened pages (last 50) | Load failures on bad networks |
| **P0** | **Virtualised rendering** for long pages and databases: render only what's on screen; load blocks as you scroll | Scrolling / "only half loads" (15%), freezes |
| **P0** | **Crash fixes from Android vitals top-10 clusters** + automatic crash-to-ticket pipeline | Crashes (13%) |
| **P0** | **Performance budget in CI** on a reference mid-range device: a release is blocked if cold start or scroll jank gets worse | Chronic problem across 35 versions |
| **P1** | **Quick-capture home-screen widget** (new note / add to a chosen database) | Capturer job; "better widgets" requests |
| **P1** | **Tablet layout fixes** (top-liked complaint) | Tablet bugs |
| **P1** | Top-5 parity gaps from the request list (e.g. the `/` command behaviour, the home button) | 50 parity requests |
| **P2** | "Lightweight mode" setting: turns off heavy embeds and animations on low-RAM devices | Lag, battery, heat |
| **P2** | **Reply to reviews** that mention performance after each fix ships ("fixed in v__") | 0.04% reply rate; win back churners |

---

## 7. Options considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| A. Rewrite the Android editor natively | Biggest long-term gain | 3+ quarters, high risk, freezes feature work | Not now |
| **B. Incremental: cache-first open, virtualised lists, crash clusters, CI budget** | Ships in weeks, measurable each release | Doesn't fix everything | **Chosen** |
| C. Separate "Notion Lite" app | Fast for capture | Two apps to maintain; splits ratings; confuses users | Rejected; P2 "lightweight mode" covers the need |

---

## 8. Rollout and experiment plan

1. **Weeks 0–2:** set up device benchmarks (cold start, scroll jank, crash-free sessions) and the CI budget.
2. **Weeks 2–8:** ship P0 behind feature flags; staged rollout 5% → 25% → 100% on Play.
   A/B test cache-first open vs control, with D7 retention and sessions per user as success metrics.
3. **Weeks 8–14:** P1 (widget, tablet, parity). Reply to performance reviews when fixes land.
4. **Every week:** the review pipeline re-scores new reviews; the n8n digest flags any rise in
   performance complaints, with quotes.

---

## 9. Risks and open questions

| Risk / question | Mitigation |
|---|---|
| Cached content may be stale or conflict with edits | Show "updating…"; edits always go through the existing sync path |
| Review data is biased (unhappy users write more; Play Store only; India store; English only) | Use reviews to decide *what* to fix; use internal telemetry to measure *how much* it improved |
| AI tagging isn't perfect (63.9% topic+type F1 vs. hand labels; it misses more than it invents) | Counts are conservative; every number has quotes behind it; key numbers double-checked with keyword search |
| Which device tiers matter most? | Needs Play Console device breakdown (internal) |
| Is iOS affected too? | Run the same pipeline on App Store reviews |

---

## Appendix: method

Pipeline: collect 12 months of Google Play reviews (5,495) → clean (4,108) → LLM splits each review into
points (exact quote → topic → praise/complaint/neutral/request → severity) + overall sentiment + churn
signal → checked against 100 hand-labelled reviews (4 models compared) → ranked by impact
(complaints × severity) → RAG Q&A for follow-up questions → weekly n8n digest. Total AI cost: **$0** (free tiers).
Sub-problem counts in §2.2 use keyword matching on the AI-tagged performance complaints.

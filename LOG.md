# Build Log

A record of what was planned and what changed, kept per the course artifact requirement.
Newest entries at the top. Entries are appended, never rewritten - the same rule the research
record follows.

**This file is the technical record** - what each change does, why, and what it measured.
For the collaboration record - what I asked for session by session, what I decided, and what
I abandoned - see [`notes/LOG.md`](notes/LOG.md).

---

## 2026-10-25 (later) — Deleted the server the website needed

**Decision: the site is static, published to GitHub Pages, and the schedule never calls a model.**

### Why the API stopped being on the critical path

The website called a FastAPI server. That meant something to host, pay for and keep awake, and
a site that broke whenever it wasn't. The research record changes a few times a month — a live
API was the wrong shape for data that moves that slowly.

`scripts/export_site_data.py` now writes the same JSON to `web/public/data/`, and the pages read
it with `fs` at build time. `next build` emits 35 static pages: 20 companies, 8 digests, 7 index
pages. No server at request time, hosted free, cannot fail at 3am.

**The export does not reimplement the API** — it imports `api.main` and calls the same functions
the endpoints call. Had it duplicated that logic, the site and the API could disagree about
whether a metric was available, which is the one thing this project cannot afford. Self-test 64
now fails if the export does not cover every company the API serves.

The honest cost of going static is that the figures are frozen. That is printed in the footer of
every page — **"Data as of YYYY-MM-DD — a static snapshot, not live market data"** — because a
reader who assumed these were live prices would be wrong about the fastest-moving number on the
page. It was always half-true anyway: the fundamentals come from quarterly filings.

### What runs on a timer, and what does not

| Workflow | Trigger | Does |
|---|---|---|
| `publish.yml` | push to `master` | rebuild + republish. Never fetches, never calls a model. |
| `refresh.yml` | Sat 06:20 UTC | prices, macro, prediction tracking, screen → commit → republish. |

**The schedule deliberately stops short of the model.** `claude -p` authenticates with a Claude
Code login that exists on a laptop, not on a GitHub runner; running judgments in CI would need
an Anthropic API key that bills per call and is a separate product. So the deterministic half
keeps itself current for nothing, and the judgement half stays human-initiated.

That split is not a workaround. It is the same boundary the artifact draws everywhere else in
this system: **the machine does what can be checked, and a person decides what cannot.** A
weekly cron writing investment judgements with nobody reading them would be the wrong thing to
build even if it were free.

### Scope note

`refresh.yml` commits to the research record from CI. It touches `data/`, `memory/` and the
exported JSON — never `predictions.csv`, which stays append-only and session-written.

---

## 2026-10-25 — Built: the model is now inside the system, and measured against me

Part A of `docs/BUILD_PLAN.md` is done. `invest/judge.py` is the only module in the project that
calls a model, and `scripts/score_stock.py --judge` wires it into the real scoring path. The
boundary is written up in `CLAUDE.md` under *The model in the loop*.

### What the model does

It receives a finished evidence pack — figures the Python has already extracted from SEC XBRL
facts and labelled — and returns five integers with a written argument for each: business
quality, competitive advantage, catalysts, risk/reward, management. **It never touches a number.**
It does not fetch data, pick a tag, compute a ratio, or decide what a company is worth.

Its answer is then thrown away unless it passes seven checks (`validate()`). The one that earns
its keep is **check5_groundedness**: every figure appearing in the model's written reasoning must
also appear in the evidence pack it was given. `scripts/selftest.py` tests it offline — a verdict
citing a 28.4% margin that is nowhere in the evidence is rejected.

### The backtest: 13 companies, model vs. the judgments I wrote by hand

The 14 hand-written judgments in `research/judgments/` were the control group. The model scored
the same companies from the same evidence; its output went to `_backtest/` and the originals were
restored afterwards.

```
mean difference         -2.77 points   (model scores lower)
mean ABSOLUTE difference 3.38 points   (out of 50)
model scored lower in    10 of 13

PER PILLAR (positive = model scores HIGHER than me)
  business_quality      /15   +0.38
  competitive_advantage /10   +0.31
  catalysts             /10   -2.77   <-- the whole gap
  risk_reward           /10   +0.08
  management            /5    -0.77
```

**The finding is sharper than "the model agrees with me."** On four of five pillars the model and
I are within half a point — business quality, moat, and risk/reward are effectively
indistinguishable. The entire systematic disagreement is **one pillar**, and it is not a model
defect: it is an **evidence defect**. Catalysts are dated, forward-looking events, and the
evidence pack is built from SEC filings. The filings do not contain them. The model scored 2–3 of
10 across almost every company and said so plainly — EXEL's verdict reads *"The evidence contains
no dated catalyst with a clear mechanism... Two 8-Ks were filed, but their contents are not in
the evidence, so they count as neither positive nor negative."*

That is the correct behaviour. When I wrote these by hand I had read the news; the model has only
the pack. **It scored low rather than inventing a catalyst, which is exactly what the design
asked for.** The gap measures what I failed to put in the evidence pack, not what the model
failed to reason about. Fixing it means adding an evidence source (8-K contents, earnings dates),
not tuning the prompt.

My -0.77 on management is the same shape: the pack has buybacks and share counts but no record of
guidance versus delivery, so the model scored the half it could see and said the other half was
unverifiable.

### A defect in my own instrumentation

The first backtest reported `rejection rate: 0, no validation failures recorded`. That was wrong.
Two of thirteen companies show `attempts: 2` in their accepted verdicts — they were rejected once
and accepted on retry. `judge()` only persisted a rejection record when *every* attempt failed, so
a verdict that was rejected and then recovered left nothing on disk.

An instrument that reads 0% when the true figure is 13% is worse than no instrument, and this is
the third time this project has caught itself scoring something without checking the line beside
it. Fixed in `_record_rejections()`, which now always persists rejected attempts, tagged
`recovered_on_retry` or `abandoned`, and the accepted verdict carries
`checks_failed_before_acceptance`.

**Corrected figures:**

```
model calls made    15
calls rejected       2   (13.3% of calls)
recovered on retry   2   (rejected once, valid next attempt)
abandoned entirely   0   (none fell back to the PARTIAL score)
```

So the validators do fire, on roughly one call in seven, and the retry absorbs them.

**And then the corrected counter was wrong too.** The fix read every file in `_backtest/` to
count calls, which includes files left by *earlier* runs — so a 9-call determinism run reported
21 calls. Now tallied in-process, scoped to the invocation. Two successive attempts to measure
the same thing, both wrong in the same direction: **the easy way to count was to read what was
lying around on disk, and what was lying around was not what I had just done.**

### Determinism — the same evidence, three times

```
ADBE   spread 1 point      EOG   spread 0 points      BKNG   spread 1 point
mean total spread : 0.7 points      max : 1 point   (out of 50)
```

The question in `docs/MODEL_IN_THE_LOOP.md` was whether judgment scores swing enough that they
should be reported as a range rather than a point estimate. **They do not.** A one-point spread
on a 50-point scale is well inside the rounding the score band already applies, so a single run
is a fair representation. EOG came back identical all three times.

This also re-measures the catalysts gap on a different sample: **-3.00 per company across these
three**, against -2.77 across all thirteen. The finding reproduces.

### Cost and latency, measured

13 companies, 15 model calls, **969 seconds** — about 75s per company wall-clock, almost all of it
model latency. One call per company per evidence state; verdicts are cached on a SHA-256 hash of
the evidence pack, so re-scoring an unchanged company costs nothing. Reached via `claude -p`
(Claude Code, headless), invoked as an argument list with the prompt on stdin — never `shell=True`.
The Claude API is a separate paid product and this system does not call it.

### Part B — the frontend

`api/main.py` (FastAPI, 9 endpoints) and `web/` (Next.js 16, React 19, MUI v9) are built and
running. The API's core invariant: a null metric is returned as `null` **plus an entry in
`_unavailable` giving the reason**, so "we could not measure this" survives JSON serialisation
instead of flattening into zero.

Verified end to end against live data: all 7 routes return 200, AAPL's stale goodwill renders as
a hoverable *not available* carrying "last reported 2017-09-30, 2919 days behind", INTU's page
renders 73.4 and labels the judgment pillars *scored by model · 7 validation checks passed*, and
every financial row names the form and XBRL tag it came from.

### The bug the frontend exposed

Generating model judgments for two companies that had never had one surfaced a defect that had
been latent in the API since it was written. The API reported PAYX at **67.8**; the script that
had just computed the same score printed **67.4**.

The API builds a total by adding the data pillars from `data/fundamentals/TICKER_analysis.json`
to the judgment pillars from `research/judgments/TICKER.json`. Those files are written by
different processes at different times, and `score_stock.py` only persists its score when passed
`--save`. So the API was adding **today's judgment to a data score saved on 2026-09-11**, at
September prices, and serving the sum as one current number.

This is the project's oldest failure mode wearing a new hat. The pipeline already refuses to read
an abandoned XBRL tag's last value as current; here the stale figure was not a component but
*half the score*, and the addition erased both timestamps on the way through.

Fixed in three places, because one would not have held:

- `/companies/{ticker}/thesis` returns `dataScoredAt` and `judgmentAt`, and `freshnessWarning`
  past a 14-day gap.
- The stock page renders that warning as a top-level error **above** the score, not a footnote
  beneath it, and prints both dates under the gauge.
- `selftest.py` check 63 walks every company and fails if any has halves more than 14 days apart
  without a flag.

Two build findings worth keeping:

- **MUI v9 removed `gap` and `flexWrap` as Stack props.** They belong in `sx` now.
- **A Server Component cannot pass `component={Link}` into an MUI component.** React refuses to
  serialise a function across that boundary and `next build` fails on `/_not-found`. Solved with
  one `"use client"` link primitive (`components/nav/AppLink.tsx`) so every page stays a Server
  Component and the API base URL never reaches the browser bundle.

`scripts/selftest.py` is now **62 checks, 0 failures**, including five that exercise the API and
three that exercise the validators offline with no model call.

---

## 2026-10-24 — Planned: move the model inside the system

**Context.** The artifact requires that a model do real work inside the system *every time it
runs*. Audit result: **it currently does not.**

```
$ grep -rln "anthropic|claude|openai|llm" invest/ scripts/ --include=*.py
  NONE
```

All 14 files in `research/judgments/` were written by Claude **in a chat session** and saved by
hand. The running system is deterministic Python. The model has been operating the system from
outside rather than being a component of it.

**Plan.** Move the judgment work inside, at the seam the architecture already defines.
`docs/SCORING.md` has said since 2026-09-03 that 50 of the 100 scoring points "require judgment
a program does not have." That boundary already has an evidence pack on one side
(`scoring.judgment_evidence()`), a schema on the other (`research/judgments/*.json`), and a
validator (`scoring.load_judgment()`).

**Shape chosen:** `claude -p` headless, invoked by Python via subprocess.
**Why:** covered by Claude Code access rather than billing per API call. `claude` CLI v2.1.309
confirmed on PATH. Rejected the direct API (costs money, buys nothing here) and an MCP server
(inverts control — Claude would drive the pipeline rather than the pipeline calling Claude).

**The split:** code fetches, computes and validates; the model returns five integers and five
justifications; code checks the result against seven rules before it may contribute to a score.

**Design doc:** `docs/MODEL_IN_THE_LOOP.md`.

**Not yet built.** This entry records the plan. Implementation and its results — including the
backtest against the 14 existing hand-written judgments — will be logged as they happen,
whatever the numbers say.

---

## 2026-10-24 — Planned: frontend and platform roadmap

**Asked for:** a plan to improve the platform, and a frontend spec to hand to Claude Code.

**Finding that reshaped both:** INVEST has no HTTP surface at all. It is a CLI writing JSON,
CSV and Markdown to disk. A Next.js frontend cannot call a Python CLI, so an API layer is a
hard prerequisite rather than a nice-to-have.

**Decided:** FastAPI over the existing `invest/` package, chosen over Flask specifically because
its automatic OpenAPI schema lets the frontend *generate* its TypeScript types. The TCSS 460
project hit type drift from hand-reconciling against a spec; generating removes that failure
mode.

**Frontend stack** deliberately mirrors `TCSS_460/Frontend/group-project-frontend-public-group-2`
(Next.js App Router, TypeScript, MUI v9, NextAuth v5, Server Actions, `ActionResult<T>`) because
those conventions are proven and already documented. Added Recharts and TanStack Table; dropped
Tailwind, which that project installed and never used.

**Explicitly not doing:** modifying the TCSS 460 repository. It is graded coursework. The
frontend is a new application that borrows its conventions.

**Docs:** `docs/PLATFORM_ROADMAP.md`, `docs/FRONTEND_SPEC.md`.

---

## Earlier history

Before this log existed, the project's record was kept in:

- `memory/research_state.md` — session-by-session state, newest first
- `memory/lessons_learned.md` — 40 generalizable rules, append-only
- `memory/rejected_stocks.md` — 15 rejections with re-review dates
- `memory/predictions.csv` — 11 predictions, never edited
- Git history — one commit per session with a full description

Those remain the primary record for research decisions. This file covers build and design
decisions about the system itself.

# Session log — Artifact 3

What I asked for, what we decided, and what got dropped. Kept per the artifact requirement
that the repository record what was planned and what changed along the way.

This is the *collaboration* record — the prompts and the decisions behind them. The root
[`LOG.md`](../LOG.md) is the *technical* record: what each change does and why, with the
measured results. Where they overlap, the root file has the detail.

Newest last, so it reads in order.

---

## 2026-10-24 — Planning, before writing any code

**What I asked for**

1. To open my TCSS 460 group frontend project, plan how to improve the investment platform,
   and write a structure and tech stack for a frontend I could hand to Claude Code.
2. Partway through I pasted my course's artifact instructions: build something where **a model
   does some of the work every time it runs**; keep the model's part **small and clear so that
   when something goes wrong you can tell whether it was the model or your code**; write down
   in CLAUDE.md or a README exactly what the model is responsible for and what the surrounding
   code checks; keep a log; and check what it costs, because Claude Code access does not cover
   the Claude API.
3. "Reexplain to me in simpler terms, what exactly are the course instructions I pasted asking,
   api?? and reexplain to me as a learning SWE student on how we can integrate this into our
   system."
4. "So what is the plan to build the model into my system and also build a frontend that has
   clear visuals?"

**The finding that set the whole direction.** Before planning anything, we audited whether the
system already used a model. It did not:

```
$ grep -rln "anthropic|claude|openai|llm" invest/ scripts/ --include=*.py
  NONE
```

All 14 judgment files in `research/judgments/` had been written by Claude **in a chat** and
saved by hand. The running system was deterministic Python. The model was operating the system
from the outside, which is precisely what the artifact says not to do.

**Decided.** Split the 100-point score along a line that already existed in the rubric:

- ~50 points are arithmetic over SEC filings (growth, valuation, financial strength, cash flow)
- ~50 points are judgement (business quality, moat, catalysts, risk/reward, management)

The model goes in the second half **and nowhere else.** That boundary is what makes a wrong
score attributable: if the measured half is wrong it is a code bug with a failing line, and if
the judged half is wrong it is an argument I can read and disagree with.

**What I abandoned here**

- **Modifying the TCSS 460 group repo.** It is graded coursework. The new frontend borrows its
  conventions (App Router, MUI, Server Actions) but lives in this repo.
- **Tailwind.** The group project installed it and never used it. Dropped from the stack.
- **Calling the Anthropic API directly.** `claude -p` runs under Claude Code, which I already
  pay for; the API bills per call and is a separate product.

**Produced:** `docs/PLATFORM_ROADMAP.md`, `docs/FRONTEND_SPEC.md`, `docs/MODEL_IN_THE_LOOP.md`,
`LOG.md` — commit `d8252f6`.

---

## 2026-10-25 — Sequencing the build

**Decided.** Part A (the model) before Part B (the frontend), so the frontend would have real
model output to display rather than placeholder data.

I also pre-committed, in writing, to recording whatever the backtest said:

> **Record whatever the numbers say.** A finding that the model disagrees with the human is a
> *better* artifact result than one that says it agrees.

That mattered later. **Produced:** `docs/BUILD_PLAN.md` — commit `0e26f3e`.

---

## 2026-10-25 — "work on Part A and Part B go!"

**What I asked for.** Build both halves.

**Part A — `invest/judge.py`.** The only module in the project that calls a model. It receives
an evidence pack the Python has already built and returns five pillar scores with a written
argument each. It never fetches data, never picks an XBRL tag, never computes a ratio.

Its answer is discarded unless it passes seven checks. The one that earns its keep is
**groundedness**: every figure in the model's reasoning must appear in the evidence it was
given.

**Decided during the build**

- **Reject an out-of-range score, never clamp it.** Clamping would silently convert a model
  that misunderstood the scale into a plausible-looking answer.
- **Keep rejections on disk.** A record of what the model got wrong is the evidence for whether
  this design works at all.
- **Human override runs one way only.** An explicit `--judgment` file beats the model; the
  model can never overwrite a person.
- **Failure degrades, never fabricates.** When validation fails, `judge()` returns `None` and
  the score falls back to the PARTIAL path the system has always had.
- **Enriched the evidence pack after the first live run.** INTU first scored 24/50 and the model
  explained the gap itself — *"The evidence has no share price, market value, valuation
  multiple, or bear/base/bull cases."* Adding valuation, a reverse DCF, recent filings and
  share-count change took it to 28/50. The model was right about what it had been given.

**Part B — `api/main.py` and `web/`.** FastAPI with 9 endpoints, Next.js 16 with MUI v9. The
core invariant: a metric that could not be measured is returned as `null` **plus a reason**, so
"we could not measure this" survives JSON serialisation instead of flattening into zero.

**What I abandoned here**

- **NextAuth / login.** Specced in `FRONTEND_SPEC.md`, not built. Nothing on the site is
  private, so an auth layer would have been weight with no job.
- **`gap` and `flexWrap` as Stack props.** MUI v9 removed them; they live in `sx` now.
- **`component={Link}` from Server Components.** React will not serialise a function across
  that boundary and `next build` fails on it. Replaced with one `"use client"` link primitive
  so every page stays a Server Component.
- **Colouring the score.** Deliberately not a traffic light. A 79 is not "green", it is 79, and
  colour is reserved for realised outcomes measured against something.

**Produced:** commit `8dd7730`.

---

## 2026-10-25 — Measuring the model against myself

**What I asked for.** This was the part of the plan I most wanted an answer to: run the model
against the 14 judgments I had written by hand and report the numbers.

**Agreement.** Mean absolute deviation **3.38 points out of 50**. But the per-pillar split was
the real result:

| Pillar | Model minus me |
|---|---|
| business_quality | +0.38 |
| competitive_advantage | +0.31 |
| **catalysts** | **−2.77** |
| risk_reward | +0.08 |
| management | −0.77 |

Four of five pillars agree to within half a point. The entire gap is one pillar — and it is an
**evidence defect, not a model defect.** Catalysts are dated future events; the evidence pack is
built from SEC filings, which do not contain them. The model scored 2–3 of 10 almost everywhere
and said why rather than inventing one.

**The uncomfortable half of that finding is about my own work.** Every catalyst score I wrote by
hand drew on news I had read and never recorded. Those scores are not reproducible from anything
in this repository.

**Determinism.** Same evidence, three runs: mean spread **0.7 points of 50**, max 1. EOG came
back identical all three times. So a single run is a fair representation, and scores do not need
to be reported as ranges.

**What I abandoned here — two claims of my own**

- **"0% rejection rate."** False. Two verdicts carried `attempts: 2` — rejected once, accepted
  on retry — but rejections were only written to disk when *every* attempt failed. True rate: 2
  of 15 calls.
- **The first fix for it.** It counted files in `_backtest/`, which includes earlier runs, and
  reported 21 calls for a 9-call run. Both wrong versions shared a cause: the cheap way to count
  was to read what was lying around on disk, and what was lying around was not what had just
  happened. Now tallied in-process.
- **Restoring the control group through `json.dumps`.** It dropped the trailing newline on all
  14 files. Restores raw bytes now — a control group that drifts, even cosmetically, stops being
  evidence the comparison was fair.

**Produced:** commit `81e6dbd`.

---

## 2026-10-25 — "stop the servers… do i have to keep prompting for the system to update?"

**What I asked for.** Stop the running servers; explain whether I have to keep prompting for the
system and the website to update; give me commands to run it locally; and explain how to get
**both servers deployed on GitHub**.

**The honest answer to the last part was no.** GitHub Pages serves static files only — it cannot
run a Python server, and the Next.js pages were all rendering per-request. Three real options
were laid out; I picked:

- **Deployment: static site on GitHub Pages.**
- **Automation: the free half only.**

**What that changed**

- **ABANDONED: the live API as the website's data source.** `scripts/export_site_data.py` now
  writes the same JSON to disk and the pages read it at build time. The API survives as a local
  tool and as the *source* of the export — the script imports `api.main` and calls the same
  functions the endpoints call, so the site cannot disagree with the API about whether a metric
  is available.
- **ABANDONED: `force-dynamic` rendering.** `next build` now emits 35 static pages.
- **ABANDONED: Vercel + Render**, and **keeping it local only** — the two options I did not pick.
- **ABANDONED: running the model on a schedule.** `claude -p` authenticates with a Claude Code
  login that lives on my laptop, not on a GitHub runner. Judgments in CI would need a paid API
  key. So the deterministic half refreshes itself weekly for free, and the judgement half stays
  human-initiated. **That is the same boundary as everywhere else in this system: the machine
  does what can be checked, a person decides what cannot.**
- **ADDED: a "Data as of" line in the footer of every page.** Going static freezes the figures,
  and a reader assuming live prices would be wrong about the fastest-moving number on the page.

**A bug the frontend exposed.** The API reported PAYX at 67.8 while the script that had just
computed it printed 67.4 — it was adding today's model judgment to a data score saved
2026-09-11 and serving the sum as one current number. Same failure as reading a stale XBRL tag
as current, except the stale figure was half the score. Now flagged by `freshnessWarning` and
guarded by a self-test.

**Produced:** commit `bc613df`.

---

## 2026-10-26 — Getting it live

**What I asked for.** "Has all been pushed to github and what are the next steps I need to take
to deploy my frontend?" — then, after setting it up: "What should I do if I already did deploy
from a branch and now I want to follow your instructions?"

**Decided.** Switch Pages source from *Deploy from a branch* to *GitHub Actions*.

**ABANDONED: deploy-from-a-branch.** It runs Jekyll over the repository and serves the markdown
it finds — it has no idea how to build a Next.js project, so the published site was my README
rendered as a web page. No cleanup was needed; there was no `gh-pages` branch, and switching the
source is a single dropdown.

---

## Still open

Recorded here so they are not quietly forgotten:

- **Catalysts have no evidence source.** The backtest proved this is the one pillar the model
  cannot score, because the pack is built from filings and catalysts are news. The fix is a new
  evidence source (8-K contents, scheduled earnings dates) — **not a looser prompt.**
- **My hand-written catalyst scores are unreproducible.** They used news that was never recorded.
- **`SEC_CONTACT_EMAIL` repository secret** is not set yet. It does not block the site; the
  weekly refresh fails with a clear message until it exists.

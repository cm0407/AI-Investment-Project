# Build Log

A record of what was planned and what changed, kept per the course artifact requirement.
Newest entries at the top. Entries are appended, never rewritten - the same rule the research
record follows.

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

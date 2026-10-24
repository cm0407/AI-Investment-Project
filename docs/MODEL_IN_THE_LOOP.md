# The Model Inside INVEST

**Design for the course artifact: a model doing real work every time the system runs.**
Written 2026-10-24.

---

## The honest starting point

**INVEST currently contains no model at all.**

```
$ grep -rln "anthropic\|claude\|openai\|llm" invest/ scripts/ --include=*.py
  NONE
```

Every one of the 14 files in `research/judgments/` was written by Claude **in a chat session**
and saved by hand. The system itself is deterministic Python: it downloads filings, computes
ratios, applies thresholds, and writes files. When `scripts/score_stock.py` runs today, no
model runs with it.

That means the artifact requirement — *a model does real work inside it every time it runs* —
is **not currently met**. The model has been standing outside the system, operating it.

This document is the design for moving that work inside.

---

## Where the model belongs (LO 11)

The architecture already identifies the seam, and it was drawn for a human analyst. From
`docs/SCORING.md`:

> Only four of those nine pillars can be scored honestly by a script:
> growth (15) · valuation (15) · financial strength (10) · free cash flow (10) = 50 pts
>
> The other five require judgment a program does not have. Whether a moat is durable, whether
> a catalyst is real or wishful, whether management allocates capital well — these are
> readings, not calculations.

That is the seam. Not a guess about where AI might help — a boundary the system already
enforces, with a schema, a validator and an evidence pack on either side of it.

| | Does the work | Why |
|---|---|---|
| **Deterministic code** | Fetch filings, select XBRL tags, compute 72 metrics, detect stale/split/fallback data, score 4 pillars on fixed thresholds, run the reverse DCF | Arithmetic and rules. A model would be slower, costlier and less reliable at this, and could not be audited. |
| **Model** | Read an evidence pack; return 5 integer scores and 5 written justifications for business quality, moat, catalysts, risk/reward, management | Requires reading industry context and weighing qualitative evidence. No threshold expresses "is this moat durable?" |
| **Deterministic code again** | Validate the model's JSON, clamp points to caps, check groundedness, assemble the final 0–100 score, apply the band | The model's output is *input to be checked*, never trusted directly. |

**The model's job is deliberately narrow: five integers and five paragraphs.** It does not
choose stocks, fetch data, compute metrics, set targets or decide BUY/WATCH/AVOID. That
narrowness is the point — when a score looks wrong, the cause is attributable.

---

## Which shape, and what it costs (LO 13)

The course text distinguishes shapes that run on Claude Code access from those that bill
separately.

| Option | Cost | Verdict |
|---|---|---|
| **`claude -p` headless, invoked by Python** | Covered by Claude Code access | **Chosen** |
| Anthropic API with a key | Bills per call | Rejected — would need permission, and buys nothing here |
| MCP server exposing INVEST to Claude | Covered | Useful later, but inverts control: Claude drives, not the pipeline |
| Claude Code skill/hook | Covered | Helps *my* workflow, not the system's runtime |

`claude` CLI v2.1.309 is installed and on PATH.

**Latency and reliability trade-offs, stated honestly:**

- A headless call adds roughly 10–30s per company. Scoring 16 candidates goes from seconds to
  minutes. **Mitigation:** judgments are cached to `research/judgments/{TICKER}.json` keyed by
  the evidence hash — the model re-runs only when the underlying evidence changes, not on
  every invocation of the script.
- The model is non-deterministic. Two runs on identical evidence can differ by a point or two.
  **This is acceptable for judgment and unacceptable for arithmetic**, which is exactly why the
  split falls where it does. Every judgment is stored with its justification so a later reader
  can see what reasoning produced the number.
- The call can fail (timeout, malformed JSON). **Mitigation:** on failure the system falls back
  to its existing behaviour — report a PARTIAL score and label it `INCOMPLETE`. That path
  already exists and is already tested. A model outage degrades the system; it does not break
  it.

**Security:** the evidence pack contains only public SEC data and computed ratios. No
credentials, no personal financial information from `notes/my_investing_preferences.md`, and
nothing from `.env`. The prompt is assembled from a template — filing text is passed as data,
never concatenated into instructions.

---

## The implementation

```
invest/
  judge.py          ← new: the ONLY module that calls a model
scripts/
  score_stock.py    ← gains --judge to invoke it
```

### `invest/judge.py`

```python
def build_evidence(metrics, fund, insider) -> dict
    # reuses scoring.judgment_evidence() - already exists, already structured

def call_model(evidence: dict, ticker: str, timeout: int = 120) -> str
    # subprocess: claude -p --output-format json
    # stdin: rendered prompt template
    # NO shell=True; argument list only

def validate(raw: str, evidence: dict) -> tuple[dict | None, list[str]]
    # every check below must pass or the judgment is rejected

def judge(ticker, metrics, fund, insider, refresh=False) -> dict | None
    # cache -> call -> validate -> persist, with fallback to None
```

### What the surrounding code checks

This list is the heart of the artifact. The model is not trusted; it is **checked**:

1. **Parses as JSON.** Reject otherwise.
2. **Exactly the five required pillars**, no more, no fewer.
3. **`points` is an integer within the pillar's cap** (15 / 10 / 10 / 10 / 5). A 12 for a
   10-point pillar is rejected, not clamped silently.
4. **`justification` is present and ≥ 120 characters.** A bare number with no argument is
   exactly what `docs/SCORING.md` already forbids.
5. **Groundedness.** Every numeric figure appearing in a justification must also appear in the
   evidence pack supplied to the model. A justification citing "ROIC of 28%" when the evidence
   pack says 16.2% is a hallucination, and the judgment is rejected. *This is the single most
   important check — it catches the model inventing data, which is the exact failure mode this
   project's rules forbid.*
6. **No forbidden language.** The project bans implying certainty; "guaranteed", "will
   definitely", "risk-free" cause rejection.
7. **Sector sanity.** If the company is flagged `banking/credit`, a justification leaning on
   free cash flow is rejected — those metrics are already declared meaningless for banks.

On any failure: log the reason, retry once, then fall back to an unscored (PARTIAL) result.
**A rejected judgment is recorded, not discarded** — `research/judgments/_rejected/` keeps
them, because a log of what the model got wrong is the evidence for whether this design works.

### Attribution, which is the whole point

When a final score looks wrong, exactly one of three things happened, and they are
distinguishable:

| Symptom | Cause | Where to look |
|---|---|---|
| Metrics are wrong | Code defect | `data/fundamentals/{T}_analysis.json` — tags and accession numbers |
| Metrics right, judgment unreasonable | Model | `research/judgments/{T}.json` — the written justification |
| Both right, total wrong | Scoring assembly | `invest/scoring.py` |

That separation is only possible because the model's surface is five integers.

---

## What this does NOT do

Stated so the boundary stays honest:

- **The model does not pick stocks.** Screening is deterministic and market-wide.
- **The model does not set price targets or probabilities.** Those remain analyst inputs;
  automating them would hide the calibration this project exists to measure.
- **The model does not write the digest.** Tempting, but the digest states conclusions to a
  beginner, and a generated one would be harder to hold to account. *Reconsider only after the
  judgment loop has a track record.*
- **The model never touches `predictions.csv`.** Append-only, human-authored. A model editing
  the record it is being judged against would destroy the point.

---

## How we will know whether it worked

Not "does it run" — **does it produce judgments a human would endorse?**

1. **Backtest against the existing 14 hand-written judgments.** They were produced by Claude in
   conversation with full context. Running `judge.py` on the same evidence and comparing scores
   gives a direct measure of agreement. Per-pillar deviation is the metric; large systematic
   gaps (e.g. the model consistently scoring moats higher) are findings worth recording.
2. **Rejection rate.** What fraction fail validation, and which check fires most? A high
   groundedness-rejection rate would be the most interesting possible result.
3. **Determinism spread.** Run the same evidence five times; report the range. If judgment
   scores swing six points, the output needs to be reported as a range, not a point estimate.

All three go in `LOG.md` with the numbers, including unflattering ones.

---

## Build order

| Step | |
|---|---|
| 1 | `invest/judge.py` — prompt template, subprocess call, cache keyed by evidence hash |
| 2 | The seven validation checks + `_rejected/` logging |
| 3 | `--judge` flag on `score_stock.py`; fallback to PARTIAL on any failure |
| 4 | Backtest against the 14 existing judgments; record agreement in `LOG.md` |
| 5 | Determinism spread; decide whether to report a range |
| 6 | Document the split in `CLAUDE.md` — what the model owns, what the code checks |
| 7 | Expose `judgmentSource: "model" \| "analyst"` through the API so the **frontend can show which judgments a model wrote** |

Step 7 matters for the frontend spec: a user should be able to see that a moat score came from
a model rather than a person, and read the justification that produced it. That is the same
honesty principle the rest of the UI is built on.

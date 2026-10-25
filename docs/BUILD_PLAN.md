# Build Plan — Model Inside, Frontend On Top

**The sequencing document.** `MODEL_IN_THE_LOOP.md` says *what* the model does,
`FRONTEND_SPEC.md` says *what* the UI is. This says **in what order to build them, and what
you can demo at the end of each step.**

Two workstreams. The model work is small and is the graded artifact. The frontend is the big
one. They only converge at the API.

```
Week 1   A1 judge.py ──► A2 validate ──► A3 backtest        ← the artifact, done
                                              │
Week 2                    B1 FastAPI ◄────────┘
                               │
Week 3+                        └──► B2 design system ──► B3 pages
```

---

# Workstream A — Put the model inside (the artifact)

## A1. `invest/judge.py` — make the call

**Goal:** Python runs Claude and gets five scores back.

```python
def build_evidence(metrics, fund, insider) -> dict   # reuse scoring.judgment_evidence()
def render_prompt(evidence, ticker) -> str           # template + facts, never f-string the data in
def call_model(prompt, timeout=120) -> str           # subprocess ["claude","-p","--output-format","json"]
def judge(ticker, ...) -> dict | None                # cache → call → validate → persist
```

Two things to get right from the start:

- **No `shell=True`.** Pass an argument list. The evidence goes in on **stdin**, not
  interpolated into a command string.
- **Cache on a hash of the evidence**, not the ticker. Same facts → same cached judgment, no
  second call. Re-runs become free, and that is what makes the latency acceptable.

**Demo:** `python -c "from invest.judge import judge; print(judge('INTU', ...))"` prints five
scores and five justifications.

## A2. `validate()` — the part that is actually the engineering

The model is an untrusted external service. Seven checks, each returning a named failure:

| # | Check | Rejects |
|---|---|---|
| 1 | Parses as JSON | garbled output |
| 2 | Exactly 5 pillars | missing/extra keys |
| 3 | `points` is an int within the cap (15/10/10/10/5) | a 12 on a 10-point pillar |
| 4 | `justification` ≥ 120 chars | a bare number with no argument |
| 5 | **Groundedness — every figure cited exists in the evidence** | **invented numbers** |
| 6 | No certainty language ("guaranteed", "will definitely") | project rule violations |
| 7 | Sector sanity — no FCF reasoning for a bank | metrics already declared meaningless |

Check 5 is the one that matters. If the model writes *"ROIC of 28% shows a strong moat"* and
the evidence says **16.2%**, it hallucinated. Reject, log to `research/judgments/_rejected/`,
retry once, then fall back to the existing PARTIAL path.

**Demo:** feed it deliberately broken JSON and watch each check fire by name.

## A3. Backtest against the 14 hand-written judgments

You already have a free test set: 14 judgment files written by Claude **in conversation**.
Re-run `judge.py` on the same evidence and compare.

Report three numbers in `LOG.md`:

1. **Agreement** — mean absolute deviation per pillar. Is the model within a point or two, or
   systematically kinder on moats?
2. **Rejection rate** — what fraction fail validation, and which check fires most?
3. **Determinism** — same evidence five times. If scores swing six points, report a range, not
   a single number.

**Record whatever the numbers say.** A finding that the model disagrees with the human is a
*better* artifact result than one that says it agrees — it is a real measurement either way.

**Demo:** a table of 14 companies, human score vs model score, with the gaps.

## A4. Wire it up and document the split

`--judge` flag on `score_stock.py`. A `CLAUDE.md` section stating plainly what the model owns
(five integers, five paragraphs) and what the code checks (the seven rules).

**At this point the artifact is complete.** A model does real work every time the scorer runs
with `--judge`, its part is small and clear, and `LOG.md` has the plan and the results.

---

# Workstream B — The frontend

## B1. FastAPI — give the data an HTTP surface

Six read endpoints over data the pipeline already wrote. **No recomputation on request** —
screening hits the SEC and takes seconds.

```
GET /companies/{ticker}        metrics + caveats + provenance
GET /companies/{ticker}/thesis score, scenarios, judgments (with source: model|analyst)
GET /screens/latest            screen rows
GET /predictions               predictions + latest review + benchmark
GET /digests, /digests/{date}  markdown archive
GET /macro                     FRED series
```

**The one invariant that cannot break:** a missing metric serialises as `null` **plus a
reason**, never as `0`.

```json
{ "roic_pct": null,
  "_unavailable": { "roic_pct": "invested capital not computable - equity is negative" } }
```

Then `npx openapi-typescript http://localhost:8000/openapi.json -o src/types/generated.ts`
and the frontend's types are **generated, never hand-written.**

**Demo:** `curl localhost:8000/companies/INTU | jq` returns the real analysis.

## B2. The design system — build the visuals before the pages

This is the step people skip, and it is why dashboards end up inconsistent. Build and
eyeball every visual component in isolation first, on a `/styleguide` page (exactly as your
TCSS 460 project did).

### The six visuals that carry this product

**1. Reverse-DCF bar — the single most important visual you will build**

Two bars. A beginner understands it in one second.

```
What the price demands    ████████████████████████  22.4%
What the company delivers ██████████                 9.2%
                          └─ the market is asking for 2.4× reality
```

Green when delivered > demanded, red when not. This one chart is the whole investment case
for most of your holdings.

**2. Score gauge with coverage — never one without the other**

```
INTU   79.4 / 100          ●●●●●●●●●●●●●●●○  15/16 measured
       ▓▓▓▓▓▓▓▓░░░░░░░░    WORTH MONITORING

JPM    20.5 / 30 available ●●●●●○○○○○○○○○○○   5/16 measured
       ▓▓▓▓▓▓▓░░░          2 pillars unscorable — banking
```

The dots are the honesty. A 93% on 6 dots must *look* weaker than an 81% on 15 dots.

**3. Scenario range, sized to volatility**

```
   bear          base            bull
   −33% ◄────────┤ +15% ├────────► +50%
   ├──────────── 1σ = 42% ────────────┤   ⚠ range narrower than a normal year
```

Showing the 1-sigma band *behind* the bars makes "my bear case is an ordinary year" visible
instead of something you have to be told.

**4. Financial trends with visible gaps**

Five-year revenue / operating income / net income. **Where data is missing, break the line** —
never interpolate. A gap is information.

**5. Pick vs benchmark**

Each prediction against the S&P over its *own* window, plus the summary strip:

```
mean +9.5%  │  ex-largest +5.4%  │  median +12.2%  │  S&P −0.2%
```

Three numbers, always together. One takeover once made the book look 3 points ahead when it
was 1.6 behind.

**6. The unavailable chip**

```
ROIC   ⌐ Not available ⌐     ← dotted underline, hover for the reason
```

Never blank, never `—`, never `0`. Blank cells read as zero, and that is the one misreading to
design out.

### Visual rules

- **IBM Plex Mono with tabular figures for every number.** Columns must align; proportional
  digits make tables unreadable.
- **Colour means outcome, not quality.** Green/red only for realised performance vs benchmark.
  Scores get a neutral ramp — a 79 is not "good", it is 79.
- Recharts, no gradients, no 3D, axes always labelled with units.
- Light default, dark via toggle, both through MUI `colorSchemes`.

**Demo:** `/styleguide` showing all six components with real INTU, JPM and PTC data, in both
themes.

## B3. Pages, hardest first

| Order | Page | Why this order |
|---|---|---|
| 1 | `/stock/[ticker]` | Hardest. Uses every component. Build it first to prove the contracts. |
| 2 | `/predictions` | The differentiator — track record, calibration, what held and what broke |
| 3 | `/screen` | TanStack Table; thinly-measured rows in a **separate section**, never interleaved |
| 4 | `/` dashboard | Easy once the parts exist |
| 5 | `/macro`, `/digests`, `/preferences` | Straightforward |

**Why hardest-first:** if the company page works, every contract and component is proven. If
you start with the dashboard you will build four tiles and discover the data shape is wrong.

---

# What to do first

**Start with A1–A3.** It is roughly a day's work, it is the graded artifact, and it produces a
measurable result (14 human judgments vs 14 model judgments) that is worth writing about
regardless of which way it comes out.

The frontend can begin in parallel at B2 against mock fixtures — the design system does not
need the API to exist.

| Risk | Mitigation |
|---|---|
| Model output is unreliable | Validation + fallback to PARTIAL already designed; rejection rate is itself a result |
| API work balloons | Six read-only endpoints, no recomputation, no writes in v1 |
| Frontend scope balloons | One page done properly beats five half-built; `/stock/[ticker]` is the demo |
| Latency makes screening painful | Cache on evidence hash; `--judge` is opt-in, never on the 184-name screen |

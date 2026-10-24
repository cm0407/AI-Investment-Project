# INVEST — Platform Roadmap

**Written 2026-10-24.** Where the system is strong, where it is genuinely weak, and what to
build next — ordered by what unlocks the most.

This is a planning document, not a commitment. Items are justified from the project's own
record (`memory/lessons_learned.md`, `memory/research_state.md`), not from general advice.

---

## Where the system actually stands

**What works, and is worth protecting:**

| | Evidence |
|---|---|
| Market-wide screening | 4,354 SEC filers via the bulk XBRL frames API, ~12 requests |
| Refuses to invent data | `DATA UNAVAILABLE OR UNVERIFIED`, never `0` |
| Full provenance | Every figure carries its XBRL tag, form, accession number, filing date |
| Append-only record | 11 predictions, never edited; 15 rejections with re-review dates |
| Self-correcting | 40 lessons, several of which found real defects before they reached a recommendation |
| Honest scoring | Refuses to complete a score without analyst judgment; 54 self-tests |

**Defects this system caught in its own output** — the reason the honesty layer earns its
keep: Air Lease's 329% net margin (wrong revenue tag), HEICO's 11-year-old share count making
a 61× stock look like 11×, Netflix excluded for "856% dilution" that was a 10-for-1 split,
Harmony ranked #1 of 4,354 while its profit fell 13%, Freshworks ranked #1 on a one-off tax
gain.

**What is genuinely weak** — carried in `research_state.md`:

1. **No API.** Blocking for any frontend. The system is file-based.
2. **Financial sector analysis.** No net interest margin, ROTCE or FFO. Banks, insurers and
   REITs are correctly refused rather than mis-scored — but that means they are never
   analysed at all. Kinsale, Progressive, Blackstone and Tradeweb were all excluded on these
   grounds, not judged.
3. **Organic vs acquired growth is undetectable** from frames data. Paychex passed a screen on
   revenue growth that was ~20% the Paycor acquisition.
4. **M&A optionality unmodelled.** The catalysts pillar scored PTC 5/10 for having no dated
   event, three weeks before a 59% takeover.
5. **Portfolio construction is advisory only.** Position sizing, sector caps and correlation
   are flagged in prose; nothing computes them.
6. **No scheduling.** Every run is manual.
7. **Scoring thresholds are unvalidated.** Every band in `docs/ASSUMPTIONS.md` is my choice,
   never tested against outcomes.

---

## Priority 0 — Put a model inside the system

**Added 2026-10-24.** An audit found INVEST contains no model call anywhere. Every judgment in
`research/judgments/` was written by Claude in a chat session and saved by hand — the model has
been operating the system from outside rather than running inside it.

The fix uses a seam the architecture already defines: the 50 of 100 scoring points that
`docs/SCORING.md` has always said "require judgment a program does not have." A `claude -p`
headless call supplies five integers and five justifications; seven deterministic checks —
including a **groundedness test that rejects any justification citing a figure absent from the
evidence pack** — decide whether that output may contribute to a score.

Full design, cost and latency analysis, and the attribution model: **`docs/MODEL_IN_THE_LOOP.md`**.

This is Priority 0 rather than 1 because it is the course artifact's defining requirement, and
because it changes what the API in Priority 1 must expose: every judgment needs a
`judgmentSource: "model" | "analyst"` field so the frontend can show which scores a model wrote.

---

## Priority 1 — The API layer (blocks the frontend)

**Build `api/` as a FastAPI service over the existing `invest/` package.** Not a rewrite —
a thin HTTP surface over functions that already work.

Why FastAPI specifically: automatic OpenAPI schema generation, which means the frontend's
TypeScript types can be *generated* rather than hand-written and drifting. The TCSS 460 project
learned this the hard way — `src/types/media.ts` had to be manually "reconciled against Group
1's authoritative OpenAPI spec."

```
api/
  main.py              FastAPI app, CORS, error envelope
  routers/
    universe.py        GET  /screens, /screens/{id}
    companies.py       GET  /companies/{ticker}, /companies/{ticker}/thesis
    predictions.py     GET  /predictions, /predictions/review, /predictions/benchmark
    digests.py         GET  /digests, /digests/{date}
    macro.py           GET  /macro
  schemas.py           Pydantic models -> OpenAPI -> TS types
  deps.py              auth, rate limiting
```

**Hard rule: the API is read-mostly and never recomputes on request.** Screening a company
takes seconds and hits the SEC. The API serves what the pipeline already wrote to `data/` and
`memory/`. A POST that triggers a re-screen should enqueue a job and return immediately.

**The error envelope must preserve the honesty layer.** A missing metric is not an error — it
is `null` plus a reason. Do not let JSON serialization collapse "not measured" into "zero";
that is the single most important invariant in the entire system.

```json
{
  "roic_pct": null,
  "_unavailable": {
    "roic_pct": "invested capital not computable - equity is negative (buybacks exceed retained earnings)"
  }
}
```

---

## Priority 2 — Make the honesty layer machine-readable

Today the caveats live in prose inside markdown theses. For a UI to *show* them, they must be
structured. This is the work that makes the frontend worth building rather than being another
stock screener.

Promote these from prose to fields on every company response:

| Field | Already computed in | Why the UI needs it |
|---|---|---|
| `data_coverage` (n of 16) | `scoring.py` | "scored on 6 of 16" must sit next to any score |
| `_sector` unreliable metrics | `metrics.py` | Grey out ratios that are meaningless for banks |
| `_fallback_tags_used` | `metrics.py` | "operating income came from a pre-tax tag" |
| `_stale_inputs_excluded` | `metrics.py` | JPMorgan's 2018 cash balance |
| `_composites_suppressed` | `metrics.py` | Why total debt is blank |
| `_growth_base_warning` | `metrics.py` | EOG's 15.5% CAGR masking a 4.2% decline |
| `_per_share_split_warning` | `metrics.py` | BKNG's pre-split EPS |
| `_share_count_warning` | `metrics.py` | HEICO's 2015 share count |
| `range_check` | `valuation.py` | Bear/bull sized against actual volatility |

All nine already exist. None is currently exposed in a form a UI can render.

---

## Priority 3 — Close the two real analytical gaps

**3a. Financial-sector metrics.** Currently banks and insurers are excluded, which means a
whole sector goes unexamined. Add:

- Banks: net interest margin, efficiency ratio, ROTCE, CET1, provision coverage
- Insurers: combined ratio, float growth, reserve development, book value per share growth
- REITs: FFO, AFFO, net asset value, occupancy

These are computable from XBRL tags the system already downloads. The work is a
`invest/sector_metrics.py` with per-sector metric sets, and scoring pillars that select the
right set by SIC code rather than suppressing.

**3b. M&A optionality in the catalysts pillar.** From the PTC lesson: a hard-to-replace asset
trading below its reverse-DCF implied growth *is* a catalyst. Add a computed
`takeover_attractiveness` signal — market cap under ~$30B, high switching costs (proxied by
gross margin stability and recurring revenue), reverse-DCF gap — and let it contribute to the
bull case rather than scoring zero.

---

## Priority 4 — Portfolio construction that computes

The preferences file sets max 20% per position, max 40% per sector, 8–10 positions. Nothing
enforces these; the digest reminds the user in prose. Build `invest/portfolio.py`:

- Position sizing by conviction score and volatility (a 48%-volatility stock and a
  28%-volatility stock should not get the same weight at the same score)
- Sector concentration against the user's caps
- **Correlation clustering** — the system has already flagged twice that ADBE/INTU/NICE are one
  bet, and EXEL/NBIX another. Computing this from return correlations rather than noticing it
  by eye is a genuine improvement.
- Portfolio-level drawdown estimate against the stated −45% tolerance

---

## Priority 5 — Scheduling and delivery

`scripts/send_digest.py` works. What is missing is unattended operation:

- A scheduled weekly run: refresh macro, re-screen, review predictions, email the digest
- Alert triggers between runs: a position breaching the stop-loss level, a thesis-breaking
  metric crossing its stated threshold, an upcoming dated catalyst (Exelixis' 3 December FDA
  date should surface without being remembered)

---

## Priority 6 — Validate the thresholds

Every number in `docs/ASSUMPTIONS.md` is an analyst choice that has never been tested: the
2.0× debt/equity limit, the 10% dilution limit, the 10-point revenue-vs-profit gap, every
scoring band. Two of them (debt/equity, dilution) once did nearly all the filtering in a
screen.

The honest way to validate: backtest the *composite score* against forward returns across the
universe. Does a 77 actually outperform a 68? If not, the scoring is decoration. This is the
most intellectually valuable item on the list and the least urgent — it needs the prediction
record to mature first, and the record is currently 44 days old against 12-month horizons.

---

## Sequencing

```
Phase 0 (the course artifact)     Model-in-the-loop for judgment pillars
Phase 1 (unlocks the frontend)    API layer + structured honesty fields
Phase 2 (makes it worth using)    Sector metrics, M&A signal, portfolio construction
Phase 3 (makes it autonomous)     Scheduling, alerts
Phase 4 (makes it credible)       Threshold backtesting, once predictions mature
```

Phase 1 is the only one the frontend strictly requires.

---

## What NOT to build

- **Real-time prices / streaming quotes.** The horizons here are 12–18 months. Intraday data
  would add cost and noise and change nothing.
- **A trading integration.** This system produces research, not orders. The gap between the
  two is where a beginner gets hurt, and it should stay wide.
- **Social or sharing features.** The calibration record is only honest because nobody is
  performing for an audience.
- **More data sources before the free ones are exhausted.** SEC EDGAR, FRED and Yahoo cover
  everything the current process actually uses.

# Lessons Learned

**Rules of this file**
- **Append only.** Never edit or soften a past lesson to make earlier thinking look better.
- Each lesson must be *generalizable* — a rule that changes future behavior, not a one-off story.
- Prefer lessons drawn from resolved predictions and observed errors over lessons drawn from
  reading. Mark the difference.
- Format each entry:

```
### YYYY-MM-DD — <short rule title>
**Trigger:** what happened that taught this.
**Rule:** the generalizable behavior change, stated as an instruction to future-me.
**Evidence:** ticker(s), dates, prices, filing references.
**Confidence:** low / medium / high — and why.
```

---

## Process lessons recorded at build time (not yet earned from real outcomes)

These are starting priors from the project rules, written down so that later, real, evidence-based
lessons can be compared against them. They are labelled clearly because **no prediction has been
made or resolved yet** — nothing here has been paid for with a real mistake.

### 2026-09-03 — Financial-sector filings break naive fundamental math
**Trigger:** Build-time pipeline test on JPM.
**Rule:** Banks and insurers do not report `GrossProfit` or conventional capital expenditure in
XBRL. Any screen that ranks on gross margin or free-cash-flow margin will silently mis-rank them.
Either exclude financials from those specific ranking factors or score them on a
sector-appropriate basis (net interest margin, efficiency ratio, ROTCE). Never let a missing tag
become a zero.
**Evidence:** SEC XBRL companyfacts for CIK 0000019617 (JPMorgan Chase) — see the build-test output.
**Confidence:** high (structural fact about the data, not a market opinion).

### 2026-09-03 — Vendor "forward" numbers are opinions wearing a number's clothing
**Trigger:** Design decision while wiring yfinance.
**Rule:** Forward P/E, target prices, and next-year EPS pulled from a vendor are consensus
*estimates*. Tag them `basis=vendor_estimate` and never let one enter an intrinsic-value
calculation as though it were reported fact. A DCF built on someone else's forecast is that
person's opinion with extra arithmetic.
**Evidence:** CLAUDE.md data rules; yfinance `.info` field provenance.
**Confidence:** high.

### 2026-09-03 — A hand-picked universe pre-decides the answer
**Trigger:** Needing a workable screening universe at build time.
**Rule:** A curated ticker list is a convenience, not a market scan. Any "best idea found" that
comes out of a curated list must state the universe it was drawn from and the bias that universe
carries. Broad claims require the broad universe.
**Evidence:** `data/universe/starter_universe.csv` (120 names, chosen for name-recognition and
sector spread).
**Confidence:** high.

---

## Outcome-based lessons (earned from real predictions)

*None yet. The first entry here should appear only after a prediction in `predictions.csv` has
run far enough to be judged.*

---

## Lessons earned during the build (real defects found in real data)

Unlike the priors above, these were discovered by running the pipeline against live SEC
filings and watching it produce wrong answers. Each one is a rule because each one already
bit.

### 2026-09-03 — An XBRL tag can exist and still be a decade out of date
**Trigger:** The first working screen reported Caterpillar's P/E as unavailable and
JPMorgan's ROIC as 68%. Both traced to the same root cause: the code picked the first
candidate US-GAAP tag that had *any* data, without checking whether that data was current.
Caterpillar stopped filing `NetIncomeLoss` after **2010** and reports `ProfitLoss` now;
Johnson & Johnson stopped filing `OperatingIncomeLoss` after **2014**; JPMorgan stopped
filing `LongTermDebt` after **2013** and `CashAndCashEquivalentsAtCarryingValue` after
**2018**.
**Rule:** When several tags can express one concept, choose by CURRENCY FIRST and priority
second. Independently, flag any concept whose latest value is more than ~400 days behind
the newest fiscal period and refuse to use it. "The latest value of this tag" is not the
same as "the latest value of this concept", and confusing the two silently returns
fifteen-year-old numbers labelled as this year's.
**Evidence:** CIK 0000018230 (CAT), 0000200406 (JNJ), 0000019617 (JPM). Fixed in
`invest/sec_edgar.py:extract_facts`.
**Confidence:** high — reproducible, structural, and verified fixed by `selftest.py`.

### 2026-09-03 — A sum built from a known-missing part is worse than no answer
**Trigger:** After the staleness fix, JPMorgan's ROIC was still 68%. Long-term debt had
been correctly *excluded* as stale, but `total_debt` was then computed as the sum of what
remained — dropping several hundred billion dollars of debt while still subtracting $343B
of cash. Invested capital came out at $84B instead of something several times larger, and
the resulting ROIC looked like a spectacular business rather than a broken calculation.
**Rule:** When a composite is assembled from components (total debt, total cash,
enterprise value), and any component is KNOWN to exist but be unavailable, the composite
must be `None`. Only sum when the absent parts are genuinely absent. A partial sum is not
a conservative estimate — it is a confident wrong number, and it looks entirely plausible.
**Evidence:** `invest/metrics.py:_composite`. Verified by `selftest.py`
("bank's suppressed composites flagged").
**Confidence:** high.

### 2026-09-03 — Fallback tags change what a metric MEANS, not just where it came from
**Trigger:** Johnson & Johnson's operating margin printed as 34.6%. Its true operating
margin is materially lower — the figure came from a fallback to a pre-tax income tag,
which includes non-operating income.
**Rule:** A fallback tag is not a neutral substitution. Record every one in
`_fallback_tags_used`, carry it into screen output, and never compare a fallback-derived
margin across companies without saying so. The arithmetic being right does not make the
label right.
**Confidence:** high — but note the deeper point: the system currently keeps the fallback
because a roughly-right margin beats no margin for triage. That trade-off is only
acceptable *because* the substitution is disclosed. If it were hidden it would be a lie.

### 2026-09-03 — Zero and unknown must never be the same value
**Trigger:** Designing the screener. A bank with no `GrossProfit` tag would score 0% gross
margin and rank below a genuinely unprofitable company.
**Rule:** `None` means "not measured"; `0` means "measured and it was zero". Never let a
missing input default to zero anywhere in a scoring path. Where every component of a
pillar is unavailable, reduce the *available* points rather than scoring the pillar zero —
JPMorgan is scored out of 30, not marked down to 20.5/50.
**Confidence:** high.

### 2026-09-05 — A tighter stop-loss buys noise, not protection
**Trigger:** Backtesting the user's proposed −20% stop before adopting it
(`scripts/analyze_stop_loss.py`, 45,431 simulated 12-month entries, 181 stocks, 6 years).
**Rule:** When evaluating any stop-loss level, do not look only at the average return cost.
Compare the *hit rate* (positions the stop genuinely saved from a worse outcome) against
the *false-alarm rate* (positions that recovered after being sold). Across −20% to −35%,
the hit rate was almost flat at 35.7–37.3% while the false-alarm rate fell from 23.8% to
7.9%. Tightening a stop therefore adds ejections without adding protection. Also check
whether position sizing already caps the tail the stop is meant to cap — with a 20% max
position, the worst observed −71.5% outcome costs 14.3% of the sleeve, already inside a
45% tolerance.
**Evidence:** research/notes/2026-09-05_stop_loss_backtest.md
**Confidence:** medium. The direction of the effect is clear and mechanical, but the
universe carries severe survivorship bias that flatters holding, the sample covers a mostly
rising market, and overlapping windows are not independent.

### 2026-09-05 — Past return is a bar the company must now clear, not a signal
**Trigger:** Testing the user's stated intent to prioritise "the ones with the best
returns" (`scripts/analyze_return_chasing.py`, 72,635 observations, 181 stocks, 10 years).
**Rule:** Never rank candidates by trailing return. In this sample the best-performing
quintile returned +16.7% over the following year against +17.9% for random selection, and
carried the HIGHEST rate of losing money (35.7%) of any quintile — with the loss rate
rising monotonically as past performance rose. Survivorship bias flatters that bucket, so
the true result is worse. When a screen surfaces a big recent winner, treat the run-up as
having raised the bar (check the reverse DCF's implied growth against delivered growth),
not as evidence of quality.
**Counter-caution:** the same test showed past LOSERS returning +29.5%. That figure is a
survivorship artifact — bankrupt companies are absent from the universe — and must never
be used to justify buying beaten-down stocks.
**Evidence:** research/notes/2026-09-05_return_chasing.md
**Confidence:** medium-high for the "winners do not persist" half; the mechanism (a higher
price is a higher bar) is sound independent of this sample. Low for anything about losers.

### 2026-09-09 — A ticker can point at a company with no history
**Trigger:** XOM was excluded from a screen for having "0 annual filing periods." Exxon
plainly files annual reports.
**Rule:** After a holding-company reorganization the SEC reassigns the ticker to a NEW CIK
with no filing history, while decades of financials remain under the predecessor entity —
which typically loses its ticker and so disappears from `company_tickers.json` entirely.
Whenever a large, actively-filing company shows fewer than two annual periods, suspect a
reorganization before concluding it is a recent IPO. The recovery route is the SEC's full
`cik-lookup-data.txt` index (which includes ticker-less entities), matching on normalized
name plus identical SIC code, then requiring the candidate to actually carry annual
history. Never match on name alone.
**Evidence:** XOM -> CIK 0002115436 "ExxonMobil Holdings Corp" (registered 2026, no annual
periods) while CIK 0000034088 "EXXON MOBIL CORP" holds 17 annual periods including FY2025
revenue of $332.2B.
**Caution:** recovered history is only comparable if the reorganization was a pure holding-
company restructure. If assets were spun off or acquired in the transition, the predecessor's
numbers do not describe the entity you would be buying.
**Confidence:** high — mechanical, verified end to end.

### 2026-09-09 — Test that the program parses, not just that the library works
**Trigger:** `scripts/score_stock.py` shipped with a syntax error and the 51-check
self-test passed anyway, because nothing in it imported that script.
**Rule:** A self-test that only exercises library internals will certify a completely
broken command-line tool as healthy. Compile every module in the project as an explicit
check. Cheap, and it catches the entire class of "the CLI is broken but the tests are green."
**Confidence:** high.

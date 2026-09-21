# Research State

**What this file is:** the running "where am I?" note for the INVEST system. Read it at the
start of every session; update it before the session ends. Append new entries at the top of
the Session Log. Never delete or rewrite older entries.

---

## Current status

- **System status:** Operational. 54 self-tests passing. Fourth research session 2026-09-20.
- **Recommendations:** 0 BUY. 9 WATCH (BKNG, ADBE, INTU, APH, PTC, EXEL, RMD, NBIX, NICE),
  2 AVOID (EOG, ULTA). 11 further candidates rejected across sessions.
- **Open predictions:** 11. Marked to market 2026-09-20: **average -1.3% vs S&P 500 +0.0%,
  so trailing the index by 1.3 points; 3 of 10 beat it.** Oldest is 11 days old against
  12-18 month horizons - NOT a track record and the tool now says so.
- **Stocks rejected (`rejected_stocks.md`):** 12
- **Theses written:** 11

### CONCENTRATION RISK - now material
ADBE (9 Sep), INTU (11 Sep) and NICE (20 Sep) all rest on the SAME one-sentence bet: "the
market over-punishes incumbent software over AI fear." Three positions, one wager. Separately,
EXEL and NBIX are both patent-dependent pharma, and BKNG and APH are both economically
sensitive. Flagged in the 2026-09-20 digest with an explicit instruction not to hold all three
software names.

### Unresolved items carried forward
1. **No diversified core.** Raised in SIX consecutive sessions without a response.
2. **Stop-loss contradiction.** -25% stop fires before the -30% the user said they would hold.
3. **Analyst-chosen thresholds unconfirmed:** 2.0x debt/equity, 10% dilution, 10-point
   revenue-vs-profit gap, 400-day staleness windows. All mine.
4. **Financial-sector analysis remains weak** - no NIM, ROTCE or FFO.
5. **Organic vs acquired growth undetectable from XBRL frames** - must be checked by hand.

## Superseded status (2026-09-18 session)

- **System status:** Operational. 54 self-tests passing. Third research session completed
  2026-09-18, including the first review of past predictions.
- **Recommendations to date:** 0 BUY. 8 WATCH (BKNG, ADBE, INTU, APH, PTC, EXEL, RMD, NBIX),
  2 AVOID (EOG, ULTA). Six further candidates rejected 2026-09-18.
- **Open predictions:** 10. **All marked to market 2026-09-18; average move -0.01%.**
  NO outcome is judgeable - only 1.6-2.5% of the stated horizons has elapsed.
- **Stocks rejected (`rejected_stocks.md`):** 8
- **Theses written:** 10
- **Email delivery:** built (`scripts/send_digest.py`). Requires the user to add a Gmail App
  Password to `.env`; not yet configured at the time of writing.

### Unresolved items carried forward
1. **No diversified core.** Raised in FIVE consecutive sessions without a response. Printed on
   every screen run and in every digest.
2. **Stop-loss contradiction.** -25% stop fires before the -30% drawdown the user said they
   would hold through.
3. **Analyst-chosen thresholds unconfirmed:** 2.0x debt/equity, 10% dilution, and now the
   10-point revenue-vs-profit gap added this session. All mine, not the user's.
4. **Financial-sector analysis remains weak** - no net interest margin, ROTCE or FFO.
5. **Organic vs acquired growth is undetectable from XBRL frames.** Paychex passed the screen
   on revenue growth that was ~20% acquisition. Must be checked by hand per candidate.
6. **Pharma concentration forming.** EXEL (11 Sep) and NBIX (18 Sep) are both
   patent-dependent drug companies. Flagged in the NBIX thesis and the digest.

## Superseded status (2026-09-14 session)

- **System status:** Operational. 52 self-tests passing. Second full research session
  completed 2026-09-14 (analysis dated 2026-09-11).
- **Investment recommendations issued to date:** 0 BUY. 7 WATCH (BKNG, ADBE, INTU, APH, PTC,
  EXEL, RMD), 2 AVOID (EOG, ULTA).
- **Open predictions in `predictions.csv`:** 9
- **Stocks rejected (`rejected_stocks.md`):** 2 (EOG, ULTA)
- **Theses written (`research/theses/`):** 9
- **User preferences:** COMPLETE as of 2026-09-05. Recommendations gate open.
- **Universe:** NOW MARKET-WIDE. `scripts/broad_screen.py` scans every SEC filer via the bulk
  XBRL frames API (4,354 revenue filers in CY2025) rather than the 184-name curated list. The
  selection-bias limitation recorded on 2026-09-03 is resolved for stage-1 screening.

### Unresolved items carried forward
1. **No diversified core.** Sleeve is 30-50% of investable money with no index-fund base.
   Raised in four consecutive sessions; the user has not responded. Printed as a warning on
   every screen run and in every digest.
2. **Stop-loss contradiction.** -25% stop fires before the -30% drawdown the user said they
   would hold through. One answer must change.
3. **Analyst-chosen thresholds still unconfirmed:** 2.0x debt/equity and 10% dilution. Both
   were materially repaired this session (see below) but the levels themselves remain my
   choice, not the user's instruction.
4. **Financial-sector analysis remains weak** - no net interest margin, ROTCE or FFO. Banks,
   insurers and REITs land in the "thinly measured" bucket by design. This session excluded
   Kinsale, Palomar, Blackstone, Tradeweb, Hamilton Lane and others on those grounds, so
   genuinely good financial companies are going unexamined rather than being judged badly.
5. **Correlation risk in my own conclusions.** INTU, ADBE and arguably PTC are the same
   underlying bet - that the market over-punishes incumbent software over AI fear. If that
   call is wrong it is wrong across several positions at once. Flagged in the digest.

## Superseded status (2026-09-09 session)

- **System status:** Operational. 52 self-tests passing. First full research session completed
  2026-09-09.
- **Investment recommendations issued to date:** 0 BUY. 2 WATCH (BKNG, ADBE), 2 AVOID (EOG, ULTA).
- **Open predictions in `predictions.csv`:** 4 (all logged 2026-09-09)
- **Stocks rejected (`rejected_stocks.md`):** 2 (EOG, ULTA)
- **Theses written (`research/theses/`):** 4 (ADBE, BKNG, EOG, ULTA)
- **User preferences:** COMPLETE as of 2026-09-05. Recommendations gate is open.
- **Remote:** https://github.com/cm0407/AI-Investment-Project (public; private financial files
  gitignored)

### Unresolved items carried forward
1. **No diversified core.** Sleeve is 30-50% of investable money with no index-fund base.
   Flagged three times; the user has not yet responded. Every screen prints this warning.
2. **Stop-loss contradiction.** -25% stop fires before the -30% drawdown the user said they
   would hold through. One answer must change.
3. **Analyst-chosen thresholds need confirming:** 2.0x debt/equity (excluded 48 companies) and
   10% dilution (excluded 35). Together they did nearly all the filtering.
4. **Financial-sector analysis remains weak** — no net interest margin, ROTCE or FFO. Banks,
   insurers and REITs land in the "thinly measured" bucket by design.

## Superseded status (2026-09-03 build session)

- **System status:** Built and self-tested (2026-09-03). No investment research has been done yet.
- **Investment recommendations issued to date:** 0
- **Open predictions in `predictions.csv`:** 0
- **Stocks rejected so far (`rejected_stocks.md`):** 0
- **User preferences captured (`notes/my_investing_preferences.md`):** ❌ NOT YET FILLED IN by the
  user. Per CLAUDE.md, no stock may be recommended until this file is completed.

## Universe currently in use

`data/universe/starter_universe.csv` — a 120-name cross-sector bootstrap list.
**Known limitation:** it is a hand-picked list, so it carries selection bias toward
well-known, liquid U.S. companies. It is a starting point, not a broad market scan.
Run `python scripts/build_universe.py --full` to build the ~10,000-name SEC-registered
universe when a genuinely broad screen is wanted.

## Open questions / next actions

1. User must complete `notes/my_investing_preferences.md` (risk tolerance, horizon, avoid-list,
   position sizing limits). Blocking for any recommendation.
2. Decide whether to run screens on the starter universe or build the full SEC universe.
3. No macro regime assessment has been recorded yet — run `python scripts/fetch_fred.py` and
   write an interpretation into `research/notes/`.

## Known data gaps and caveats currently live

- Forward-looking figures (forward P/E, analyst estimates, next-year EPS) come from **yfinance /
  Yahoo, a third-party vendor**, not from filings. They are labelled `basis=vendor_estimate`
  everywhere and must never be presented as fact.
- SEC XBRL data for financial companies (banks, insurers) legitimately lacks `GrossProfit` and
  capital-expenditure tags. The metrics engine reports these as
  `DATA UNAVAILABLE OR UNVERIFIED` rather than substituting zero.
- No paid data source is in use. There is no access to consensus estimates, ownership
  13F history, or short interest beyond what is free and public.

---

## Session log (newest first — append, never overwrite)

### 2026-09-20 - Fourth session: a share-count bug that would have misled the user

**Did NOT re-run the identical screen.** The prompt was the same as 2026-09-18, but CY2025
frames are annual and cannot change until FY2026 filings land - re-running would have returned
the identical 216 survivors. Instead mined the ~156 survivors never examined, deliberately
weighted toward sectors outside the existing pharma/software concentration.

**THE FINDING: HEICO ranked #1 at 91.2% on a P/E of 11.6. It is actually 60.8.**
HEICO's dei cover-page share count reads 26.9M **as of 2015-12-15** - eleven years stale -
against a true diluted count of 141M. Market cap was understated 5.2x ($8.0B vs $42.0B).
The direction matters: too few shares means too small a market cap means the stock looks CHEAP,
so the bug actively promotes its victims to the top of a value screen.

**The compounding failure:** the `_per_share_split_warning` built on 2026-09-09 FIRED correctly
on HEICO - and the screener used the poisoned market cap anyway, because the warning was
advisory rather than blocking. Second occurrence of this shape (18 Sep: a lesson written in
prose but never encoded). Fix: share-count age validation in `metrics.compute()` substitutes
the diluted weighted-average count when the cover page is >400 days stale, or suppresses market
cap entirely. Age - not ratio - is what distinguishes this from a legitimate split: BKNG's
cover page is 23x its pre-split WA and is CURRENT, so its market cap is right.

**Benchmarking added.** The review showed picks down 1.3% with no way to judge that. Added
`track_predictions.py benchmark`: each pick vs SPY over its OWN window (different start dates
would otherwise misattribute market moves). Result: -1.3% vs +0.0%, 3 of 10 beating. The
command refuses to call it a track record while the oldest prediction is under six months.

**Outcome: ONE new idea.** NICE 71.4 (WATCH) - 10.4x earnings, 11.0% FCF yield, reverse DCF
implies -8.9% FCF growth against +8.9% delivered. Presented WITH an explicit warning that it
is the third instance of the ADBE/INTU bet and arguably the weakest: the only one to have
already cut margin guidance (31% -> 25-26%) and the only one facing both Microsoft and
Salesforce in its core market. Rejected HEI (60.8x after correction), CHKP (5.7% growth,
nothing to buy), MPWR/ADSK/HWM (96x/40x/61x).

Deliverables: `reports/daily/digest_2026-09-20.md`, 5 rejections, 3 lessons, metrics fix,
benchmark command. Digest emailed.

### 2026-09-18 - Third research session + FIRST prediction review

**Prediction review (CLAUDE.md learning loop).** All 9 open predictions marked to market and
appended to `prediction_reviews.csv`. `predictions.csv` was NOT modified. Average move -0.01%;
range -5.4% (BKNG) to +4.4% (PTC). **No outcome judged, and none could honestly be** - 7-9 days
against 12-18 month horizons is 1.6-2.5% elapsed. Recorded the elapsed-percentage explicitly so
that a future reader cannot mistake a mark-to-market for a verdict.

**New research.** Rather than re-running an identical screen four days after the last one - the
CY2025 fundamentals had not changed - I examined the candidates deep-dived on 11 September but
never presented. That surfaced the session's most important finding.

**The screen's top two rankings were both wrong.** Harmony Biosciences ranked #1 of 4,354
companies at 95.9% with revenue up 98% over three years while net income FELL 13%; Doximity
ranked #2 with operating and net income both down in the latest year. The stage-1 composite
weighted revenue growth at 30% and never tested whether profit followed. Added the profit-pace
test to `broad_screen.py` (excludes when revenue CAGR exceeds net income CAGR by >10 points);
23 companies dropped out. **The lesson had already been written on 2026-09-09 after Ulta and
was not encoded in code** - recorded as a lesson in its own right.

**Phase 5 disproof earned its keep twice more:**
- *United Therapeutics* would have been the top idea on filings alone (all three lines rising,
  46.9% operating margin, 16.0x earnings). Current-year data shows nebulized Tyvaso revenue
  down 18% YoY in Q2 2026 as Liquidia's Yutrepia takes share. Same structure as EOG: cheap
  multiple, deteriorating core. Rejected.
- *Paychex* passed on revenue growth that was ~20% the Paycor acquisition; organic growth is
  4-5%. Rejected.
- *Ubiquiti* rejected purely on the reverse DCF: price implies 29.5% FCF growth against 8.9%
  delivered, despite a 116% ROIC.

**Outcome: ONE new idea.** NBIX 71.8 (WATCH). Netflix scored 69.7 and Qualys 68.6 - both inside
the speculative band, both rejected rather than promoted. Netflix missed the threshold by 0.3
points; moving a single judgment score would have produced a fuller-looking list. Recorded as a
lesson.

**Also corrected a reporting error of my own:** on 14 September I told the user INTU had "already
run" +8.4% and that only ~6% of upside remained. By 18 September it was back at $313.13,
essentially the original entry price. Re-framing a 12-month thesis on a four-day move was wrong
and is now a recorded lesson.

Deliverables: `reports/daily/digest_2026-09-18.md`, `research/theses/NBIX.md`, 6 rejections,
5 lessons, screen fix.

### 2026-09-14 - Second full research session (analysis dated 2026-09-11)

**Universe upgraded from curated to market-wide.** Built `scripts/broad_screen.py` on the SEC
bulk XBRL frames API - one request returns a concept for every filer, so a genuinely
unbiased first pass costs ~12 requests instead of ~10,000 downloads. Scanned 4,354 companies
reporting CY2025 revenue -> 2,222 above the $300M floor -> 239 passing quality and growth ->
39 through the user's preference rules -> 16 into deep research -> 5 presented.

**Growth window deliberately set to CY2022-CY2025**, applying the 2026-09-09 lesson: six-year
windows start in 2020 and measure pandemic recovery rather than growth.

**Four defects found and fixed, all by inspecting output rather than trusting it:**
1. *Revenue tag priority was wrong for lessors and financials.* Preferring
   `RevenueFromContractWithCustomerExcludingAssessedTax` over `Revenues` understated Air
   Lease's revenue ninefold ($0.33B vs $3.02B), producing a 329% net margin and a 452% FCF
   margin that still ranked 20th. Now takes the larger value - a component cannot exceed the
   total - plus sanity guards rejecting margins above 100%.
2. *Stock splits were being read as massive dilution.* The filter excluded Netflix for
   "share count grew 856.4%", KLA 749.0%, ServiceNow 416.9%, US Lime 409.5% - all four are net
   BUYERS of their own stock. Netflix went 451M -> 4,495M diluted shares on a 10-for-1 split.
   `_share_change_ex_splits()` now compounds only year-on-year ratios inside 0.67x-1.5x.
   Netflix reads -4.0% and KLA -12.6% after the fix; genuine dilution survives untouched.
3. *Debt-free companies were being excluded for "cannot check leverage".* 23 of 39 candidates
   failed this way, including Manhattan Associates, whose liabilities are 0.00x assets. The
   leverage test now falls back to liabilities/assets when no debt tag exists, rather than
   fabricating a zero or excluding the safest companies.
4. *Score bands had a gap.* A score of 79.4 matched neither the 70-79 nor the 80-89 band and
   reported "OUT OF RANGE". `band_for_score()` now matches on the lower bound only.

**Outcome: no BUY.** INTU 79.4, APH 77.3, PTC 76.9, EXEL 76.7, RMD 74.6 - all WATCH. Intuit
landed 0.6 points below the STRONG threshold; I scored its catalysts 6/10, identical to
Adobe's, because in both cases the re-rating catalyst has no date. Moving one judgment point
would have produced a BUY and would have been inflation dressed as judgment.

**Prices moved between analysis (2026-09-10) and publication (2026-09-14):** INTU +8.4%,
PTC +6.2%. The logged predictions keep their analysis-date entry prices - that is the
permanent record - but the digest shows remaining upside at current prices, which is
materially lower for the top idea.

Deliverables: `reports/daily/digest_2026-09-14.md`, 5 theses, 5 judgment files,
`research/notes/2026-09-11_macro_backdrop.md`, 2 lessons.

### 2026-09-09 - First full research session (Phases 1-5)
- Built `invest/preferences.py`: the user's avoid-list and limits are now ENFORCED by the
  screener, fail-closed, with unenforceable rules declared rather than faked.
- Found and fixed four defects by inspecting output rather than trusting it:
  (a) XOM resolved to a new holding-company CIK with no history while $332B of revenue sat
      under the predecessor - added `find_predecessor()` via the SEC's full CIK index;
  (b) `score_stock.py` shipped a syntax error that 51 self-tests missed - selftest now
      compiles all 24 modules;
  (c) insurers were scored on free-cash-flow metrics already declared meaningless for them -
      suppressed the whole FCF family; PGR fell 48.3/50 -> 37.4/40;
  (d) ranking by raw points buried financials, then ranking by percentage promoted them for
      being thinly measured - screens now split well-measured from thin (>=10 of 16 components).
- Screened 184 names -> 102 passed the user's rules -> top 4 taken through Phases 2-5.
- **Caught a base-year distortion that would have driven a wrong conclusion.** EOG ranked #2
  on a 15.5% revenue CAGR while revenue had fallen three consecutive years; the window started
  at the 2020 oil crash. Added `revenue_cagr_3y_pct` and `_growth_base_warning`.
- Added split detection: BKNG's cover-page share count is 23.0x its diluted weighted-average
  count, so filed EPS of $165.57 is on a pre-split base and cannot be compared with a $180 price.
- **Outcome: no BUY.** BKNG 77.8 (WATCH), ADBE 72.7 (WATCH), EOG 67.6 (AVOID), ULTA 66.2
  (AVOID). Four predictions logged, two rejections recorded, four theses written.
- Deliverables: `reports/INVEST_Research_Report_2026-09-09.docx`,
  `reports/daily/digest_2026-09-09.md`.

### 2026-09-04 - Repository prepared for public publication
- Moved the SEC contact address out of the source code into a gitignored `.env` file.
  `invest/config.py` now ships a placeholder default and reads `SEC_CONTACT_EMAIL` at
  import time; `selftest.py` fails if the placeholder is still in use.
- Redacted the address from the four other files that carried it, including the line
  above in this file. **This was a privacy redaction, not a revision of any research
  conclusion** - no figure, prediction, score or judgement was altered.
- Untracked `notes/my_investing_preferences.md` and `portfolio/investment_log.csv` and
  committed `.example` templates in their place, so real holdings and risk tolerance
  cannot reach a public repository.
- `memory/predictions.csv` remains tracked on purpose: it is the calibration record and
  CLAUDE.md requires it to be tamper-evident.
- Remote added: https://github.com/cm0407/AI-Investment-Project
- No research conducted. No recommendations issued.

### 2026-09-03 — System build session
- Inspected folder: only `CLAUDE.md` and `notes/GLOSSARY.md` existed.
- Built the full folder structure, memory files, the `invest/` Python package (8 modules),
  9 `scripts/` CLIs, `requirements.txt`, `README.md`, and `docs/` (DATA_SOURCES,
  ASSUMPTIONS, SCORING).
- Data sources wired and verified live: SEC EDGAR (`data.sec.gov`, User-Agent
  `INVEST-Research/1.0 (<SEC_CONTACT_EMAIL>)`, rate-limited to 5 req/s against their
  10 req/s ceiling), yfinance (prices), FRED (macro, works with no API key).
- `scripts/selftest.py`: **49 checks passed, 0 failed** on the 5-company test
  (AAPL/tech, JNJ/health care, JPM/financials, PG/staples, CAT/industrials).
- Form 4 insider parsing verified: 12/12 recent CAT filings parsed, correctly separating
  option exercises (code M) and tax withholding (code F) from real open-market sales (S).

**Three real data defects were found and fixed during the build** — see
`lessons_learned.md` for the full write-ups. Summary:
  1. Tag selection took the first tag with *any* data, returning Caterpillar's 2010 net
     income and JPMorgan's 2013 long-term debt as current figures. Now selects by
     currency first, priority second, plus an independent staleness flag.
  2. Composites (total debt) summed the remaining parts after a stale component was
     dropped, producing a 68% ROIC for JPMorgan. Composites with a known-missing part now
     return unavailable.
  3. Fallback tags silently changed metric meaning (JNJ's "operating margin" is derived
     from a pre-tax income tag and is overstated). Now disclosed everywhere it appears.

- **No investment analysis, screening conclusions, or recommendations were produced.**
  The user explicitly asked for none at this stage. The 5-company run was a data-pipeline
  test; the composite scores it printed are triage numbers out of 50, not CLAUDE.md scores.

**Known weaknesses carried forward (do not forget these):**
  - Financial-sector coverage is *defensive only*: the system correctly refuses to apply
    operating-company ratios to banks, but does not yet compute the right ones
    (net interest margin, efficiency ratio, ROTCE, and FFO/AFFO for REITs).
  - No institutional-ownership tracking, though CLAUDE.md lists it as a Phase 1 input.
  - Scoring thresholds are sector-blind, so cross-sector composite comparisons are weak.

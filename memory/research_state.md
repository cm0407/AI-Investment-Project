# Research State

**What this file is:** the running "where am I?" note for the INVEST system. Read it at the
start of every session; update it before the session ends. Append new entries at the top of
the Session Log. Never delete or rewrite older entries.

---

## Current status

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

# How Scoring Works

The CLAUDE.md rubric, and why the script only fills in half of it.

---

## The rubric

| Pillar | Points | Who scores it |
|---|---|---|
| Business quality | 15 | **Analyst** |
| Growth | 15 | Script |
| Valuation | 15 | Script |
| Financial strength | 10 | Script |
| Free cash flow | 10 | Script |
| Competitive advantage | 10 | **Analyst** |
| Catalysts | 10 | **Analyst** |
| Risk / reward | 10 | **Analyst** |
| Management & capital allocation | 5 | **Analyst** |
| **Total** | **100** | 50 / 50 |

### Verdict bands

| Score | Band |
|---|---|
| 90–100 | Exceptional |
| 80–89 | Strong |
| 70–79 | Worth monitoring |
| 60–69 | Speculative / incomplete |
| below 60 | **Reject** |

CLAUDE.md: *"Never inflate a score to force a stock into a higher tier."*

---

## Why the script stops at 50 points

A program can measure whether free cash flow grew. It cannot tell you whether the moat
that produced it will still be there in five years.

If `score_stock.py` printed *"Competitive advantage: 7/10"*, that 7 would be fabricated —
there is no calculation behind it, only the appearance of one. And a fabricated 7 does
real damage: it flows into a total, the total lands in a band, the band becomes a
recommendation, and by then nobody can see that the foundation was invented.

So the script:

1. Scores the four pillars it can defend, from SEC-filed figures
2. Assembles an **evidence pack** for the five it cannot
3. Labels the result `INCOMPLETE — DO NOT COMPARE TO THE 0-100 BANDS`
4. Refuses to produce a verdict band until the judgment pillars are recorded

```
PARTIAL SCORE: 26.7 of 50.0 points available from filings. The 5 judgment
pillar(s) business_quality, competitive_advantage, catalysts, risk_reward,
management (worth 50 points) have NOT been scored - a script cannot judge a
moat or a catalyst. Score them by hand from the evidence pack and pass them
back with --judgment. Until then this number is not a CLAUDE.md score and
must not be presented as one.
```

---

## Recording the judgment pillars

Create a JSON file — by convention `research/judgments/TICKER.json`:

```json
{
  "business_quality": {
    "points": 12,
    "justification": "Gross margin 46% and operating margin 32%, both stable across six years. ROIC is very high but flattered by the cash-excluding convention (see ASSUMPTIONS.md). Read the FY2025 10-K segment detail: hardware is still ~75% of revenue, so this is not yet a services business."
  },
  "competitive_advantage": {
    "points": 8,
    "justification": "Switching costs and ecosystem lock-in are real and visible in retention. Deducted 2 points because regulatory pressure on App Store economics directly targets the highest-margin part of the moat."
  },
  "catalysts": {
    "points": 5,
    "justification": "Q1 earnings 2026-01-29 is dated and specific. The rest of the bull case rests on an upgrade cycle with no announced date, which is a hope, not a catalyst."
  },
  "risk_reward": {
    "points": 6,
    "justification": "Base case +18%, bear case -25% at roughly 30% probability. Positive but not compelling; the asymmetry is thin."
  },
  "management": {
    "points": 4,
    "justification": "Consistent large buybacks and a shrinking share count. Deducted 1 point: buyback pace did not slow when the multiple expanded, which is price-insensitive capital allocation."
  }
}
```

Then:

```bash
python scripts/score_stock.py AAPL --judgment research/judgments/AAPL.json
```

Now the total is complete and the verdict band applies.

**Rules for judgment scores**

1. **Every pillar needs a written justification.** A number with no argument is a guess.
   The field is recorded as `NO JUSTIFICATION RECORDED` if you omit it, which should be
   read as a red flag.
2. **Cite what you read.** "Per the FY2025 10-K risk factors" beats "seems durable".
3. **Score before you know the answer, not after.** Reverse-engineering a score to justify
   a stock you already like is the single easiest way to make this entire system useless.
4. Points are clamped to each pillar's maximum, so a typo cannot inflate a total.

---

## How the four automated pillars work

Each pillar averages several components; each component maps a metric onto 0–1 through
threshold bands, then the average is multiplied by the pillar's point weight.

| Pillar | Components |
|---|---|
| Growth | revenue CAGR · net income CAGR · FCF CAGR · latest-year revenue growth |
| Valuation | P/E · P/FCF · EV/EBITDA · FCF yield · PEG |
| Financial strength | debt/equity · current ratio · interest coverage · net debt/EBITDA |
| Free cash flow | FCF margin · OCF÷net income · FCF positive |

Exact thresholds: [ASSUMPTIONS.md §5](ASSUMPTIONS.md).

### Missing components are visible, not hidden

A pillar is averaged over the components that **have data**, and every pillar reports
`components_scored / components_total`. A valuation score built on 2 of 5 inputs is not
the same evidence as one built on 5 of 5 — check the ratio before trusting a rank.

If **no** component can be scored, the pillar returns `None` and appears under
`unscorable_data_pillars`, reducing the available points rather than scoring zero. This
distinction is the whole design: **zero means "measured and bad", `None` means "not
measured".** Conflating them is how a bank ends up looking like a failing company.

### Sector suppression in practice

```
JPM partial: 20.5 / 30.0 (of 50 possible)
  UNSCORABLE: financial_strength (not scored: every component is meaningless
              for a banking/credit company - debt_to_equity, current_ratio,
              interest_coverage, net_debt_to_ebitda)
  UNSCORABLE: free_cash_flow (not scored: every component is meaningless for a
              banking/credit company - fcf_margin_pct, ocf_to_net_income, fcf_latest)
```

JPMorgan is scored out of 30 available points, not marked down to 20.5/50. Ranking a bank
against an industrial on leverage ratios would produce a confident, wrong answer.

---

## Reading a composite score from the screener

`screen_stocks.py` reports `composite_score` out of **50**, not 100. It is a
*triage* number: "which of these deserve the hours that Phases 2–5 take?"

It is **not** a recommendation, and it is weak evidence across sectors, because the
thresholds are sector-blind (a 25% FCF margin is ordinary for software and remarkable for
a grocer).

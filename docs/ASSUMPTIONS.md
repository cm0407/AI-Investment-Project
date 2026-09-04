# Assumptions

Every judgment call baked into the code, in one place, so it can be argued with.

An assumption you cannot find is an assumption you cannot challenge. Where a threshold is
a convention rather than a fact, this file says so.

---

## 1. Formula definitions

| Metric | Formula used here | The argument against it |
|---|---|---|
| **Free cash flow** | operating cash flow − \|capital expenditure\| | Ignores acquisitions, which for a serial acquirer are effectively growth capex. Overstates FCF for roll-ups. |
| **EBITDA** | operating income + depreciation & amortisation | EBITDA is *not* a GAAP measure. Every company defines it differently. Treated as a proxy and labelled as one. |
| **Enterprise value** | market cap + total debt − cash & short-term investments | Ignores pensions, leases and minority interests. |
| **Invested capital** | total debt + equity − cash & short-term investments | Excluding cash **flatters cash-rich companies' ROIC**. Apple's ROIC looks enormous partly because of this convention. |
| **NOPAT** | operating income × (1 − effective tax rate) | Effective rate ≠ cash rate ≠ marginal rate. Rejected outright if outside 0–60% as an unusual year. |
| **ROIC** | NOPAT ÷ invested capital | Uses *end-of-period* invested capital, not the average. Overstates when the balance sheet grew during the year. |
| **PEG** | P/E ÷ multi-year net-income CAGR | A backward-looking growth rate applied to a forward-looking multiple. Only computed when growth is positive. |
| **Market cap** | market price × share count from the latest SEC cover page | Uses the `dei:EntityCommonStockSharesOutstanding` tag, which is more current than the annual balance-sheet count. |
| **CAGR** | (last ÷ first)^(1/years) − 1 | **Endpoint-sensitive.** One unusual first or last year distorts it. Undefined when either endpoint is ≤ 0. The year-by-year series is always reported alongside. |
| **Volatility** | stdev(daily returns) × √252 | Assumes 252 trading days and that past volatility predicts future volatility. It does not, reliably. |

---

## 2. Data-selection rules

- **Annual figures only** come from `10-K` / `20-F` / `40-F`. Duration facts are kept only
  when the period spans **300–400 days**, which filters out the quarterly and
  year-to-date stubs that also appear inside a 10-K.
- **Restatements:** the most recently *filed* version of a period wins.
- **Tag choice: currency first, priority second.** Among the candidate tags for a concept,
  any tag reaching within ~400 days of the newest available period is considered current,
  and among those the concept dictionary's priority order decides. *Reason: Caterpillar's
  `NetIncomeLoss` stops in 2010 and Johnson & Johnson's `OperatingIncomeLoss` stops in
  2014 — a naive first-match returns a decade-old number labelled as the latest year.*
- **Staleness flagging:** any concept whose latest value is >400 days behind the newest
  fiscal period is excluded from metrics and reported under `_stale_inputs_excluded`.
- **Composite suppression:** a total built from parts (e.g. total debt = long-term +
  short-term) is set to `None` if any component was excluded as stale. *Reason: summing
  only what remains understates the total. JPMorgan's abandoned `LongTermDebt` tag would
  otherwise drop hundreds of billions of dollars of debt and produce an ROIC near 70% for
  a bank.*
- **Fallback tags are surfaced,** not hidden. When a concept resolves to a non-preferred
  tag the substitution is listed under `_fallback_tags_used`. **This matters:** Johnson &
  Johnson's "operating income" falls back to a pre-tax income tag, which includes
  non-operating items and therefore **overstates its operating margin**. The number is
  arithmetically correct and conceptually loose — check the fallback list before quoting
  a margin.

---

## 3. Sector adjustments

Standard ratios mislead in some industries. Rather than rank a bank against an industrial
on the same yardstick, the affected metrics are computed but marked unreliable, and the
scorer refuses to use them.

| SIC range | Industry | Metrics treated as not meaningful |
|---|---|---|
| 6000–6199 | Banking / credit | debt/equity, current ratio, net debt/EBITDA, cash/debt, ROIC, FCF margin, capex/revenue, interest coverage, OCF/net income, FCF, P/FCF, FCF yield, EV/EBITDA |
| 6200–6299 | Brokerage / exchanges | debt/equity, current ratio, net debt/EBITDA, ROIC, OCF/net income, EV/EBITDA |
| 6300–6499 | Insurance | debt/equity, current ratio, net debt/EBITDA, ROIC, FCF margin, capex/revenue, OCF/net income, EV/EBITDA |
| 6500–6599 | Real estate | debt/equity, net debt/EBITDA, P/E |
| 6798 | REITs | debt/equity, net debt/EBITDA, P/E, FCF margin |
| 4900–4999 | Utilities | debt/equity, net debt/EBITDA, FCF margin, capex/revenue |

**Why:** a bank borrowing 10× its equity is not distressed — borrowing is its raw
material. A REIT's P/E looks terrible because depreciation swamps GAAP earnings. A bank's
operating cash flow swings by hundreds of billions as its loan book moves.

**Consequence:** JPMorgan is scored out of **30 available points instead of 50**, and the
output says so rather than quietly ranking it as though the missing pillars were failures.

**Known gap:** the system does *not* yet compute the sector-appropriate replacements
(net interest margin, efficiency ratio, ROTCE for banks; FFO/AFFO for REITs). Those must
be read out of the filing by hand. Until they are built, financial-sector companies are
under-analysed by this system, and that is a reason for caution, not for confidence.

---

## 4. Valuation assumptions

Configured in [invest/config.py](../invest/config.py) → `DCF_DEFAULTS`:

| Assumption | Default | Justification and objection |
|---|---|---|
| Discount rate | **10%** | Roughly the long-run U.S. equity return. It is a *single* rate applied to every company regardless of risk, which is crude — a speculative small cap deserves a higher one. |
| Terminal growth | **2.5%** | Near long-run nominal GDP. Above ~3% a DCF starts assuming a company eventually becomes the whole economy. |
| Projection window | **10 years** | Long enough to matter, short enough to be arguable. |
| Growth fade | **linear to terminal** | Assumes competition erodes growth. Kinder to cyclicals than reality, harsher on genuine compounders. |
| Margin of safety | **25%** | A convention, not a calculation. |

**The honest caveat:** a DCF is an opinion dressed in arithmetic. Moving the discount rate
by two percentage points can move fair value 40%. That is why `--dcf` always prints a
**sensitivity grid** — the spread across that table is the real uncertainty, and the
single "fair value" number is the least interesting output.

The **reverse DCF** is usually more useful: rather than guessing growth to produce a
target, it asks what growth today's price already assumes, which can be compared against
what the company has actually delivered.

---

## 5. Scoring thresholds

The pillar weights come from CLAUDE.md and are not negotiable here. The **thresholds**
inside each pillar are conventions chosen at build time.

**Growth** (revenue/net income/FCF CAGR): ≥20% → 1.0 · ≥12% → 0.85 · ≥8% → 0.7 ·
≥5% → 0.5 · ≥2% → 0.3 · >0% → 0.15

**Valuation:** P/E ≤10 → 1.0, ≤15 → 0.85, ≤20 → 0.7, ≤25 → 0.55, ≤35 → 0.35, ≤50 → 0.15 ·
P/FCF ≤12 → 1.0 … ≤50 → 0.3 · EV/EBITDA ≤8 → 1.0 … ≤30 → 0.25 · FCF yield ≥8% → 1.0 …
≥1% → 0.25 · PEG ≤0.8 → 1.0 … ≤4.0 → 0.2

**Financial strength:** debt/equity ≤0.3 → 1.0 … ≤3.0 → 0.2 · current ratio ≥2.0 → 1.0 …
≥0.8 → 0.25 · interest coverage ≥15 → 1.0 … ≥1.5 → 0.25 · net debt/EBITDA ≤0 → 1.0 …
≤4.0 → 0.25

**Free cash flow:** FCF margin ≥25% → 1.0 … >0% → 0.15 · OCF/net income ≥1.3 → 1.0 …
≥0.6 → 0.25 · FCF positive at all → 1.0

**Objections you should hold onto:**

1. These bands are **sector-blind**. A 25% FCF margin is unremarkable for software and
   extraordinary for a grocer. Cross-sector comparisons of the composite score are
   therefore weak evidence.
2. A pillar is averaged over **whichever components have data**, so a company with two of
   five valuation inputs is scored on those two. `components_scored/components_total` is
   always reported — check it before trusting a rank.
3. Cheap multiples score well, and stocks are often cheap **because earnings are about to
   fall**. The valuation pillar must never be read alone.

---

## 6. The 50-point limit on automation

**Only 50 of the 100 points can be computed by a script:**

| Machine-scorable (50) | Requires an analyst (50) |
|---|---|
| Growth 15 | Business quality 15 |
| Valuation 15 | Competitive advantage 10 |
| Financial strength 10 | Catalysts 10 |
| Free cash flow 10 | Risk/reward 10 |
| | Management & capital allocation 5 |

Whether a moat is durable, whether a catalyst is real or wishful, whether management tells
the truth — these are readings, not calculations. A script that printed
"Competitive advantage: 7/10" would have **invented that number**, which CLAUDE.md
forbids.

So `score_stock.py` emits a **partial** score plus an evidence pack, and refuses to map it
onto the 0–100 verdict bands until the judgment pillars are recorded with written
justification via `--judgment`. See [SCORING.md](SCORING.md).

---

## 7. Universe assumptions

- The **starter universe** is ~184 hand-picked large, liquid U.S. companies across all 11
  sectors. It is a bootstrap, and it is **biased** — it under-represents small caps,
  recent IPOs and turnarounds, which is exactly where mispricing tends to live. A result
  from it is "the best of these 184 names", never "the best in the market".
- The **full universe** (`build_universe.py --full`) is every SEC-registered ticker, with
  no curation. It also includes trusts, funds and shells that are not operating companies;
  the screener drops anything without usable financial data as it goes.
- **CLAUDE.md asks for broad scans across sectors and market caps.** Only the full universe
  actually satisfies that. Any claim of breadth made off the starter list is overstated.

---

## 8. Things this system cannot do

Stated plainly, because a limitation you have not written down will eventually be
forgotten and then implicitly denied:

- It cannot read a 10-K's narrative. Risk factors, competition, segment commentary and
  management's tone all require a human reader.
- It has **no institutional-ownership tracking**, despite CLAUDE.md listing ownership
  shifts as a screening input.
- Its insider analysis covers only recent non-derivative Form 4 transactions, and it
  cannot tell a routine pre-scheduled 10b5-1 sale from a conviction sale.
- It has no consensus estimates, short interest, credit ratings or options data.
- It cannot judge whether a management team is honest.
- **It cannot tell you what will happen.** Every forward number it produces is a
  projection under assumptions listed on this page, and the probabilities attached to
  scenarios are informed estimates, not measurements.

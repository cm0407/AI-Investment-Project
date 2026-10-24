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

### 2026-09-09 — Suppress a metric family, not one member of it
**Trigger:** The first full screen ranked Progressive (an insurer) #1 at 48.3/50. The
scoring engine suppressed `fcf_margin_pct` for insurers as meaningless, but still scored
them on `fcf_yield_pct` and `pfcf_ratio` — the same free-cash-flow number divided by market
cap instead of revenue.
**Rule:** When a metric is declared not-meaningful for an industry, suppress every metric
derived from the same underlying quantity, not just the one that was noticed. Changing the
denominator does not make an invalid numerator valid. Enumerate the family
(FCF -> fcf_margin, fcf_yield, P/FCF, fcf_cagr, fcf_latest) and suppress it as a set.
**Effect:** PGR fell from 48.3/50 to 37.4/40 with its free-cash-flow pillar correctly
marked unscorable.
**Confidence:** high.

### 2026-09-09 — Ranking on raw points punishes companies for their industry
**Trigger:** After the fix above, insurers could reach at most 40 points and banks 30,
while operating companies could reach 50. Sorting on raw points would bury every financial
company regardless of quality — an artefact of the scoring design, not a judgement about
the business.
**Rule:** When the maximum obtainable score varies between candidates, rank on the share of
AVAILABLE points earned and always display the denominator alongside. Never sort on a raw
total whose ceiling differs across the list.
**Counter-caution:** a percentage flatters companies scored on very few components. Always
show points/available and the count of unscorable pillars so thin coverage stays visible,
and keep repeating that cross-sector comparison is weak evidence because the thresholds
are sector-blind.
**Confidence:** high.

### 2026-09-09 — A percentage hides how much was actually measured
**Trigger:** After switching the screen to rank on share-of-available-points, the top four
results were insurers and a bank. Progressive led at 93.5% — scored on **6 of 16**
components. Adobe's 81.5% was scored on 15 of 16.
**Rule:** A ratio says nothing about the size of its own evidence base. Whenever scores are
built from a variable number of inputs, display the input count and refuse to rank
thinly-measured candidates alongside well-measured ones. A high percentage on few
components means "little was measured and it looked fine", which is not the same claim as
"this is good" and must never be presented as though it were.
**Implementation:** screens now split into a main ranking (>=10 of 16 components scored) and
a separate "thinly measured" list, with coverage shown on every row.
**Confidence:** high. This is a general property of ratios, not a fact about markets.

### 2026-09-09 — Watch which thresholds are the analyst's invention
**Trigger:** Reviewing why 79 of 184 companies were excluded from the first real screen.
**Rule:** When a user says "avoid highly leveraged companies" or "avoid heavy dilution"
without giving a number, the number is the ANALYST's choice and must be labelled as such.
Here a self-chosen 2.0x debt/equity limit excluded 48 companies and a self-chosen 10%
dilution limit excluded 35 — together doing almost all of the filtering. An exclusion rate
that high from an unstated threshold should be surfaced to the user for confirmation, not
buried in a config file.
**Confidence:** high.

### 2026-09-09 — Check the base year before believing any CAGR
**Trigger:** The first full research session. Three of four candidates had multi-year growth
rates that inverted or badly overstated the truth, all for the same reason: the six-year
window began in 2020.
**Rule:** Never quote a multi-year CAGR without computing the recent three-year rate beside
it. A window that starts in a crisis year measures RECOVERY, not growth. The gap is not
subtle: Booking 31.7% vs 16.3%; EOG 15.5% vs **−4.2%**; Ulta 15.0% vs 6.7%. EOG's headline
implied a growing company while revenue had fallen three consecutive years. Adobe was the only
clean series (13.1% vs 10.5%) and that fact alone materially raised my confidence in it.
**Implementation:** `metrics.compute()` now emits `revenue_cagr_3y_pct` and sets
`_growth_base_warning` when the long CAGR exceeds the recent one by 5+ points.
**Confidence:** high. Mechanical and verified on four companies.

### 2026-09-09 — Read the profit line, not the per-share line
**Trigger:** Ulta Beauty guided to 11.9–13.1% EPS growth and had just raised guidance. The
filings showed operating income falling three years running.
**Rule:** When a company runs a large buyback, per-share figures and business performance
decouple. Always compare net income growth against EPS growth. Ulta's net income fell 11%
($1.29B → $1.15B) while diluted EPS held roughly flat ($26.03 → $25.64), the entire difference
coming from a 50M → 45M share-count reduction. A screen or a headline reading only EPS would
have called this a stable grower. Sales rising while operating profit falls is the signature
of promotional pressure and should be treated as a red flag, not a growth story.
**Confidence:** high.

### 2026-09-09 — Honest process can end with no recommendation
**Trigger:** Four candidates taken through all five phases; best score 77.8, none reaching the
80 threshold for STRONG. Two landed in the speculative band and were rejected.
**Rule:** A session that recommends nothing is a completed session, not a failed one. The
pressure to produce a BUY — especially when the user has asked for 20% returns and is waiting
— is exactly the pressure that inflates scores. The correct output was two WATCH and two
AVOID, with the reasons recorded. Resist the urge to promote the best available idea to a
recommendation simply because it is the best available.
**Confidence:** high. This is a process commitment, not an empirical claim.

### 2026-09-11 — A stock split is not dilution, and a filter that confuses them deletes the best companies
**Trigger:** A broad screen excluded Netflix for "share count grew 856.4%", KLA for 749.0%,
ServiceNow for 416.9% and US Lime for 409.5%. All four are net BUYERS of their own stock.
**Rule:** Never compute share-count change by comparing the first and last value of a
weighted-average share series. A stock split multiplies the count without transferring
anything, and reads as catastrophic dilution. Netflix went 451M -> 4,495M diluted shares in
one year on a 10-for-1 split. Walk consecutive years instead and compound only the ratios
inside a plausible band (0.67x-1.5x); anything outside it is a split or reverse split, not
issuance. After the fix Netflix reads -4.0% and KLA -12.6%, while genuine dilution survives
untouched (Globus Medical +35.7%, Elastic +22.9%, InterDigital +11.0%).
**Wider point:** this is the same failure as the BKNG per-share warning added on 2026-09-09.
That fix only compared the cover-page count with the weighted-average count at ONE instant;
it did not protect the time series. When a distortion is found, ask which OTHER calculations
consume the same corrupted input.
**Confidence:** high — mechanical, verified across eight companies.

### 2026-09-11 — "No debt tag" means no debt, not unknown debt
**Trigger:** 23 of 39 stage-2 candidates were excluded for "debt/equity is DATA UNAVAILABLE -
cannot check leverage", including Manhattan Associates, whose total liabilities are 0.00x its
assets. The filter was throwing out the least leveraged companies in the sample.
**Rule:** Fail-closed is right when a missing value could hide a risk. It is wrong when the
absence of the value IS the evidence. A company that files no long-term or short-term debt tag
almost always has no debt, which is the safest case. Do not invent a zero - instead fall back
to a different measure that IS present. Total liabilities over total assets answers "is this
company highly leveraged?" without fabricating a debt figure.
**Generalisable:** before excluding on missing data, ask whether another available field
answers the same underlying question.
**Confidence:** high.

### 2026-09-18 - My screen ranked two profit-stagnating companies #1 and #2
**Trigger:** Reviewing the candidates I had deep-dived but not presented. Harmony Biosciences
topped the entire market-wide screen at 95.9%, and Doximity was second at 93.2%. Harmony's
revenue had risen 98% over three years while net income FELL 13%; Doximity's operating and net
income both declined in the latest year.
**Rule:** Any composite that weights revenue growth must also test whether PROFIT kept pace.
Mine weighted revenue growth at 30% and never checked. Revenue rising while profit stalls is
the signature of discounting, cost inflation, or growth bought through acquisition - never of a
compounding business. A gap of more than ~10 points a year between revenue CAGR and net income
CAGR should exclude, not rank first.
**Implementation:** added the profit-pace test to `scripts/broad_screen.py`; 23 companies
dropped out, Harmony among them.
**The uncomfortable part:** `lessons_learned.md` already contained "Read the profit line, not
the per-share line" from 2026-09-09, written after Ulta. I had written the lesson and then
built a screen that violated it. **A lesson recorded in prose but not encoded in the code is
a lesson that will be forgotten.** Where a rule can be made mechanical, make it mechanical.
**Confidence:** high.

### 2026-09-18 - Annual filings lag reality by up to a year
**Trigger:** United Therapeutics looked like the best idea of the session on the numbers -
revenue, operating income and net income all rising every year, 46.9% operating margin, 16.0x
earnings. Phase 5 disproof found that nebulized Tyvaso revenue fell 18% year over year in Q2
2026 and 20% in the first half, as a competitor's product took share after a May 2025 approval.
**Rule:** SEC annual filings are authoritative about the PAST. A company whose most recent
10-K shows clean compounding can already be in decline by the time you read it. Before
presenting any idea built on annual data, check the most recent quarter and the competitive
news for the CURRENT year. This matters most when the multiple is unusually low: a cheap price
attached to excellent trailing figures usually means the market knows something the annual
filing does not yet show.
**Pattern match:** this is structurally identical to EOG (rejected 2026-09-09) - cheap multiple,
deteriorating core. Two for two now. A low multiple on a high-quality trailing record should
trigger a search for what is breaking, not excitement.
**Confidence:** high.

### 2026-09-18 - Acquired growth is not organic growth, and my screen cannot tell them apart
**Trigger:** Paychex showed revenue rising $4.91B to $6.30B and passed the screen comfortably.
Roughly 20% of that increase was the Paycor acquisition; organic growth is 4-5%, and FY2027
guidance is 5-6%.
**Rule:** Top-line growth from the frames API is TOTAL revenue growth and includes acquisitions.
For any candidate whose growth looks strong, check whether it bought that growth. An acquisition
can be good capital allocation, but it is not evidence of organic demand and must not be scored
as though it were.
**Known limitation, stated rather than fixed:** the XBRL frames data cannot distinguish organic
from acquired revenue. This has to be checked by hand per candidate. I am recording it as an
open gap rather than pretending the screen handles it.
**Confidence:** high.

### 2026-09-18 - I re-anchored a 12-month thesis on four days of price noise
**Trigger:** On 2026-09-14 I told the user Intuit had "already run" +8.4% since analysis and
that "only about 6% of upside remains". Four days later INTU was back at $313.13 - essentially
the $312.77 entry price. The move fully reversed.
**Rule:** A few days of price movement carries no information about a 12-month thesis. Reporting
current prices is correct and necessary; re-framing the ATTRACTIVENESS of an idea around a
four-day move is not. I effectively told the user the best idea of that session had become
mediocre, on the basis of noise. State the current price, and let the thesis stand or fall on
the business.
**Confidence:** high - and this one is about my own behaviour, not about markets.

### 2026-09-18 - A session can produce one idea, and that is a result
**Trigger:** Asked for the strongest 3-5 ideas, the honest output was ONE new name clearing the
70 threshold (NBIX at 71.8). Netflix scored 69.7 and Qualys 68.6 - both inside the speculative
band, both rejected rather than promoted.
**Rule:** When two candidates land within 1.5 points of the threshold, the temptation is to move
a single judgment score and produce a fuller-looking list. Netflix at 69.7 needed 0.3 points.
Resist it. The threshold is only meaningful if it binds when it is inconvenient, and a session
that honestly yields one idea has still told the user something true about the opportunity set.
**Related evidence:** this is consistent with the macro note for this period - high-yield
spreads at 2.71% are historically very tight, meaning little is being offered cheaply anywhere.
A screen finding few bargains in that environment is the screen working, not failing.
**Confidence:** high.

### 2026-09-20 - An eleven-year-old share count made a 61x stock look like an 11x stock
**Trigger:** HEICO ranked #1 in a stage-2 screen at 91.2%, showing a P/E of 11.6 and a 10.7%
free-cash-flow yield on 20.2% revenue growth. Those numbers were impossible for that company.
Its cover-page (dei) share count read **26.9 million as of 2015-12-15** - eleven years stale -
while the diluted weighted-average count was 141 million. Market cap was understated 5.2x
($8.0B instead of $42.0B), turning a ~61x P/E into a fake 11.6x.
**Rule:** Validate the AGE of the share count before pricing anything off it. A stale
cover-page figure is uniquely dangerous because of its DIRECTION: too few shares means too
small a market cap, which makes a stock look CHEAP. The bug therefore promotes its own victims
to the top of a value screen. Where the cover-page count is more than ~400 days behind the
latest fiscal period, substitute the diluted weighted-average count; if that is unavailable,
suppress market cap and every multiple derived from it.
**Age is what separates this from a legitimate split.** Booking Holdings' cover page (751M) is
23x its pre-split weighted average (33M) and is perfectly CURRENT, so its market cap is right.
HEICO's is eleven years old and is not. A ratio test alone cannot tell the two apart; the
period_end date can.
**The deeper failure:** I had ALREADY built a detector for this on 2026-09-09 - the
`_per_share_split_warning`. It fired correctly on HEICO. And the screener used the poisoned
market cap anyway, because the warning was advisory rather than blocking. **A guard that
detects a bad number but does not prevent its use is not a guard.** This is the second time
this exact shape of mistake has appeared (see 2026-09-18, where a lesson written in prose was
never encoded in code). When a defect is detected, ask what still consumes the bad value.
**Confidence:** high - mechanical, verified across HEI, NICE, BKNG and INTU.

### 2026-09-20 - A return means nothing without the market's return beside it
**Trigger:** The prediction review showed picks down 1.3% on average and I had no way to say
whether that was bad. It turns out the S&P 500 was flat over the same windows, so the picks
trailed the index by 1.3 points, with 3 of 10 beating it.
**Rule:** Never report portfolio performance without a benchmark measured over the SAME window.
"Down 1.3%" reads as failure and "up 8%" reads as skill; in both cases the honest question is
what the market did meanwhile. A pick that falls 2% while the index falls 5% is working.
Because predictions are made on different dates, each must be compared from ITS OWN start date
- a single shared window misattributes market moves to stock selection.
**Implementation:** added `track_predictions.py benchmark`, which prints each pick against SPY
over its own window and refuses to call the result a track record while the oldest prediction
is under six months old.
**Confidence:** high. This is measurement methodology, not a market claim.

### 2026-09-20 - Three versions of the same bet is one bet
**Trigger:** NICE cleared the threshold at 71.4 on the argument that the market is
over-punishing an incumbent software company over AI fear. That is the identical argument I
made for Adobe on 2026-09-09 and Intuit on 2026-09-11.
**Rule:** Correlation between ideas is not visible from any single thesis - each one looks
independently reasonable. Before adding a position, state the one-sentence bet behind it and
check whether an existing holding carries the same sentence. Three stocks expressing "the
market is wrong about AI destroying incumbent software" is not diversification across three
companies; it is a single concentrated wager on one macro-technological judgement, and if that
judgement is wrong all three fail together.
**Applied here:** NICE is presented WITH an explicit instruction not to hold all three, and it
is arguably the weakest of the trio - it is the only one that has already cut margin guidance
(31% to 25-26%) and the only one facing both Microsoft and Salesforce in its core market.
**Confidence:** high.

### 2026-10-12 - I called the ceiling and the ceiling was not there: PTC +51% on a takeover
**Trigger:** My first resolved prediction. PTC was logged 2026-09-11 at $128.72 with a $152
target (+18%). On 2026-10-05 Schneider Electric agreed to acquire it for **$205 per share in
cash** (~$23.7B). The stock is at $194.39, up **51%** in 31 days, having blown through my
target by 22%.

**What was RIGHT, and worth keeping:** the business judgement. I identified CAD/PLM switching
costs as punitive ("migrating an engineering record means re-validating decades of product
data"), scored it the best-measured company in the screen at 16/16 components, and the reverse
DCF showed the market demanding 8.6% free-cash-flow growth from a company delivering 32%. Every
one of those readings was correct.

**What was WRONG:** I wrote, explicitly, that the upside was *structurally capped* - "a
business growing ARR at 9% does not re-rate dramatically... reaching +20% needs the multiple to
expand, which I cannot point to a specific reason for." I scored catalysts 5/10 on the grounds
that "a company growing ARR 9% and guiding to 9% is delivering precisely what is already
expected."

**The rule: a high-quality, hard-to-replace asset trading below what its own cash generation
justifies IS a catalyst, because it makes the company an acquisition target.** A strategic buyer
pays for exactly the characteristics I had identified - mission-critical software embedded in
customers' workflows with punitive switching costs. I spotted that the asset was both excellent
and cheap, then failed to consider that somebody else might notice the same thing.

**The deeper error - arguing from my own ignorance.** "I cannot point to a catalyst" is a
statement about the limits of my search. I converted it into "there is no catalyst", which is a
statement about the world. Those are not the same claim, and the gap between them cost 41
percentage points of upside in my stated target. **Never convert an absence of evidence in my
own analysis into an upper bound on an outcome.**

**Framework consequence:** M&A is an entirely unmodelled source of upside here. The catalysts
pillar only credits dated, company-announced events; it assigns zero weight to "this asset is
strategically valuable and mispriced", which is the precondition for a bid. For any candidate
that is (a) sub-$30B, (b) high switching costs, (c) trading below its reverse-DCF implied
growth, takeover optionality is a real part of the return distribution and the bull case should
say so.

**And a practical point for the position:** the thesis is now COMPLETE. At $194.39 against a
$205 cash offer, the remaining 5.2% over roughly nine months to close is a merger-arbitrage
bet on deal completion - a different proposition from the business thesis I underwrote, with
different risks (regulatory review, deal break). Holding it is a new decision, not a
continuation of the old one.
**Confidence:** high. Single observation, but the reasoning error is plainly identifiable
independent of the outcome.

### 2026-10-12 - My apparent outperformance is one takeover bid
**Trigger:** The picks are up 5.2% against the S&P 500's 2.2% - ahead by 3.0 points, 7 of 11
beating the index. That reads as skill.
**Strip out PTC and the picks are up 0.62% against the index's 2.20% - BEHIND by 1.6 points.**
PTC alone contributed +4.6 points of the +5.2% average.
**Rule:** Whenever a performance figure is reported, check whether a single position is
producing it, and say so in the same breath. An average across eleven positions where one moved
51% on a takeover is not a measure of stock selection; it is a measure of one event. Report the
median or the ex-outlier figure alongside the mean, because the mean is the number that
flatters.
**What this means honestly:** on the evidence so far, nine of my eleven theses are doing nothing
in particular and one got lucky with an acquirer. That is the correct reading at 33 days.
**Confidence:** high - arithmetic, not judgement.

### 2026-10-12 - The macro assumption under every valuation moved, and I never checked it
**Trigger:** Reviewing why Booking fell 12%, I found the Federal Reserve had RAISED rates for
the first time in three years. Checking FRED confirmed a broader shift since my 2026-09-11
macro note:

| | 2026-09-11 | 2026-10-12 |
|---|---|---|
| 10-year Treasury | 4.83% | **5.22%** (+39bp) |
| Fed funds | 3.63% | 3.75% (a HIKE) |
| High-yield spread | 2.71% | **3.15%** (+44bp) |
| Consumer sentiment | 55.2 | **51.7** |

**Rule:** Every DCF in this system uses a 10.0% required return, chosen against a 4.83%
risk-free rate - a 5.2-point equity risk premium. Holding that premium constant at today's
5.22% implies **10.4%**, which cuts a DCF-derived fair value by about **5.3%**. None of my
price targets was adjusted. I wrote in the September macro note that "none of these theses need
rates to fall" - which was correct and useful - but I never built the converse check: what
happens if rates RISE. A macro note that records the backdrop without a trigger for the
backdrop changing is a snapshot, not a control.
**Action:** before each review, re-pull the risk-free rate and state what the change implies for
existing targets. Widening credit spreads (+44bp) and falling consumer sentiment (-3.5) both
lean against the economically-sensitive positions specifically - Booking and Amphenol.
**Confidence:** high on the mechanism; the magnitude depends on holding the risk premium
constant, which is itself an assumption.

### 2026-10-12 - I named the right risk and the wrong company
**Trigger:** My Booking thesis listed as a structural threat "Google increasingly inserting
itself between the traveller and the OTA." What actually happened: **Meta** launched its Muse AI
agent and **Expedia** integrated it.
**Rule:** Credit where due - the SHAPE of the risk was correctly identified, and that is the
part that matters for a thesis. But I attached it to a specific named competitor, which made it
easy to monitor the wrong thing. When writing a structural risk, describe the MECHANISM
("anything that intermediates between the customer and the booking platform") rather than the
incumbent most likely to do it. Monitoring "is Google doing this?" would have missed Meta
entirely.
**Confidence:** medium-high. One observation, but the distinction between mechanism and actor
is generally sound.

### 2026-10-23 - My bear and bull cases describe an ordinary year, not an extreme one
**Trigger:** Six of eleven positions are at or within 3% of a TWELVE-MONTH price target after
about 12% of the horizon. Three have already exceeded it (PTC, ULTA, RMD). At the same time
Booking is 41% of the way to its bear case. Both ends of my ranges are being reached far too
fast for the ranges to be right.

**I tested it properly rather than guessing.** Comparing each scenario span against the stock's
own annualised volatility:

| | ann. volatility | my bear-to-bull span |
|---|---|---|
| NICE | 47.9% | −33% to +50% |
| INTU | 42.5% | −28% to +50% |
| APH | 41.0% | −38% to +40% |
| EXEL | 40.3% | −32% to +50% |
| ADBE | 37.8% | −30% to +50% |
| ULTA | 36.9% | −28% to +30% |
| NBIX | 35.1% | −30% to +50% |
| BKNG | 33.3% | −33% to +38% |
| EOG | 29.3% | −32% to +40% |
| RMD | 28.4% | −28% to +31% |

**All 10 of 10 spans are narrower than a two-sigma annual move.** For most, the bear case and
the bull case are each roughly a ONE-sigma event - which is to say, an ordinary year. I have
been labelling the normal range of outcomes "bear" and "bull".

**Rule:** size scenario ranges against the stock's own volatility, not against what feels like a
big number. If a stock has 40% annualised volatility, a ±30% range does not describe the tails -
it describes Tuesday. A bear case should be an outcome that genuinely hurts, which for a
40%-vol stock means something closer to −50%, and the bull case correspondingly wider.

**Why this matters more than it looks:** the probabilities attached to those cases are now also
wrong. If my "bear case" is really a 1-in-3 ordinary outcome rather than a 1-in-10 bad one, then
a stated 30% probability of the bear case is not conservative - it may be optimistic. Narrow
ranges make the whole scenario apparatus look more precise than it is.
**Confidence:** high. Measured across ten positions with a clear mechanism.

### 2026-10-23 - "I cannot forecast this" is not "this will do badly"
**Trigger:** My two AVOID-rated picks are up **+12.95%** on average. My eight WATCH-rated picks
excluding the takeover are up **+3.50%**. The stocks I told the user to skip are beating the
ones I favoured.

**EOG is the clean case, and the error is mine, not the market's.** I rejected it writing: "the
return depends chiefly on the oil price, which I have no framework to forecast." Then I rated it
AVOID. Brent subsequently moved above $100 and EOG is up 12.2%, within 2.4% of my target.

I was **correct** that oil would decide the outcome. I then converted *my own inability to
forecast oil* into *an expectation of a poor outcome*. Those are different claims. The honest
rating for something outside my competence is **no opinion** - decline to cover it - not AVOID.
AVOID is a prediction, and it should only be made when I have positive evidence of a bad
outcome, not an absence of evidence about any outcome.

**ULTA is the instructive counter-case.** It is up 13.7% past my target, but it **has not
reported earnings since** - next results are due around 3 December. The concern that drove the
rejection (operating income falling three straight years while revenue grew, EPS propped up by a
20.5% share-count reduction) is entirely **untested**. The stock re-rated on no new information
about the problem. So the analysis is not shown to be wrong - it is shown to be *slow*, which is
a different thing and must not be confused with it.

**Rule:** separate two questions that I have been answering as one. (1) Is the business
deteriorating? (2) Will the share price fall over my horizon? An AVOID conflates them. Where the
answer to (1) is yes but I have no edge on (2), say exactly that.
**Confidence:** medium-high on the reasoning; low on the performance data itself (n=2, 44 days).

### 2026-10-23 - The outlier discipline earned its keep by reversing the answer twice
**Trigger:** On 2026-10-12 I committed to always reporting performance with the single largest
contributor stripped out. This review is the second application and it has now changed the
conclusion in BOTH directions.

| | all 11 | excluding PTC | median |
|---|---|---|---|
| 2026-10-12 | +5.2% vs +2.2% → **ahead 3.0** | +0.62% vs +2.20% → **BEHIND 1.6** | — |
| 2026-10-23 | +9.5% vs −0.2% → **ahead 9.7** | +5.39% vs −0.2% → **ahead 5.6** | +12.2% |

Last review the headline flattered me and the ex-outlier figure corrected it downward. This
review the ex-outlier figure still shows genuine outperformance, so the headline was not purely
an artefact. **A discipline that only ever moves the answer in the flattering direction is not a
discipline.** This one has moved it both ways, which is evidence it is measuring something.
**Standing rule:** report mean, ex-largest-contributor, and median together. The median
(+12.2%) is the most outlier-resistant of the three and is currently the most favourable, which
is itself worth noticing rather than quietly preferring.
**Confidence:** high - arithmetic.

### 2026-10-23 - Check whether the company has actually reported before reading anything into the price
**Trigger:** Three of my largest movers have not reported earnings since the prediction was
made. ULTA next reports ~3 December. Amphenol reports 28 October - five days from now - so its
−7.7% fall happened entirely BEFORE the test of my thesis. ResMed likewise exceeded its target
with no new results.
**Rule:** before attributing a price move to a thesis being right or wrong, establish whether
any new information about that thesis has actually arrived. A stock that rises 13.7% with no
earnings release has told me nothing about whether its margins are recovering. Attribute moves
to sentiment, rates or sector rotation when that is what they are, and record the thesis as
UNTESTED rather than vindicated or refuted.
**Practical consequence:** Amphenol's Q3 on 28 October is the first genuine test of the "AI capex
digestion" bear case. Analysts already flag that recent strength reflects pulled-forward orders,
which is the mechanism I described. That report matters; the price action before it does not.
**Confidence:** high.

# Does buying last year's winners work? — 2026-09-05

**Question:** the user wrote *"i'm a beginner so the ones that have best returns matter
most."* Is past return a useful way to pick stocks?

**Method:** `scripts/analyze_return_chasing.py`. 184-name starter universe, 10 years of
daily adjusted closes, entries every 5 trading days. Each stock sorted by its previous
12-month return, then measured over the following 12 months. 72,635 observations across
181 stocks.

## Results

| Sorted by past 12m return | Past return | **Next 12m return** | Hit +20% | Lost money |
|---|---|---|---|---|
| worst 20% | −20.8% | **+29.5%** (med +21.5%) | 51.9% | 25.3% |
| below avg | +0.3% | +16.5% (med +12.6%) | 38.4% | 28.8% |
| middle 20% | +13.7% | +13.3% (med +10.4%) | 34.5% | 31.7% |
| above avg | +28.7% | +13.6% (med +11.0%) | 34.9% | 32.1% |
| **BEST 20%** | **+68.2%** | **+16.7%** (med +11.0%) | 39.3% | **35.7%** |

Buying at random from this universe: **+17.9%**.
Edge from chasing the best performers: **−1.17 percentage points versus random.**

## The two findings, ranked by how much I trust them

**1. TRUSTWORTHY — buying past winners did not beat picking at random.**
The best-performing quintile returned +16.7% against +17.9% for random selection, and it
**lost money more often than any other group (35.7%)**. The loss rate rises almost
monotonically with past performance: 25.3% → 28.8% → 31.7% → 32.1% → 35.7%. Survivorship
bias *favours* this bucket (winners survive and stay listed), so the real-world figure is
likely worse, not better.

**2. NOT TRUSTWORTHY — the +29.5% for past losers is largely a survivorship artifact.**
The universe contains only companies still large and listed today. A stock that fell 20%
and then went bankrupt is absent by construction. The "worst 20%" bucket is therefore
pre-selected for having recovered. **This must not be read as "buy the losers."** The
honest statement is that this test cannot measure the loser bucket at all.

## Conclusion

Past return is not a selection criterion. It is a fact about a price change that has
already been paid for by whoever held the stock while it rose — buying afterwards means
paying the higher price without having received the return. What predicts a *future* 20%
is the gap between today's price and the business's prospects, which is what the
reverse DCF in `invest/valuation.py` is built to measure.

Worked example already on file: Apple's price implies ~35.6% annual free-cash-flow growth
for 10 years, against 6.1% actually delivered over the past six. A strong past return has
raised the bar the company must now clear, not lowered it.

## Limits

- Survivorship bias, severe, in both directions described above.
- Overlapping windows are not independent; these are frequencies, not significance tests.
- One market regime, 10 years, mostly rising.
- **This tests NAIVE 12-month return-chasing. It is not a test of systematic momentum**,
  which is a genuine documented factor operating on shorter rebalancing cycles with its
  own risk controls. Momentum being real does not rescue "buy what went up most."

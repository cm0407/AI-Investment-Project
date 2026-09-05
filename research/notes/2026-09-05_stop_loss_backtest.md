# Stop-loss backtest — 2026-09-05

**Question:** does a hard stop-loss protect a 12-month, 8–10 position portfolio, and at
what level?

**Method:** `scripts/analyze_stop_loss.py`. 184-name starter universe, 6 years of daily
adjusted closes, entries simulated every 5 trading days, 12-month forward window.
45,431 simulated entries across 181 stocks (MMC returned no data).

## Results

| Stop level | Fires on | Would have finished positive anyway | Would have hit +20% anyway | Genuinely saved you | Avg cost vs holding |
|---|---|---|---|---|---|
| −20% | **25.6%** | 23.8% | 9.4% | 35.7% | **−2.65%** |
| −25% | 16.8% | 16.7% | 6.4% | 36.4% | −1.65% |
| −30% | 10.7% | 10.6% | 4.6% | 37.3% | −0.98% |
| −35% | 6.6% | 7.9% | 3.8% | 37.0% | −0.61% |

Baseline: holding through every drawdown averaged **+16.84%** per 12-month entry.
Worst single outcome if always holding: **−71.5%**.

## The finding that matters

**The "genuinely saved you" rate barely moves — 35.7% → 37.3% — across every stop level.
The false-alarm rate collapses.** Tightening a stop does not buy more protection; it buys
more noise. At −20% you eject yourself from 0.67 recovering positions for every 1 disaster
avoided. At −30% that ratio falls to 0.28.

At −20%, roughly 1 position in 4 gets stopped out per year. On a 10-position portfolio
that is 2–3 forced exits and re-researches annually, costing ~2.65% of return per position,
to cap a tail the position-sizing rule already limits.

## Interaction with position sizing

With a 20% maximum position, the worst historical outcome (−71.5%) costs 14.3% of the
sleeve. That sits inside the stated 45% drawdown tolerance **without any stop at all**.
Diversification across 8–10 names is already doing most of the risk work a stop would do.

## Limits of this evidence

- **Survivorship bias is severe.** The universe is companies still large and listed today;
  the ones that went to zero are absent. This makes "just hold" look better than it was,
  so the real case for a stop is *stronger* than these numbers show. The pro-holding
  conclusion is an upper bound.
- Overlapping windows are not independent — these are frequencies, not significance tests.
- Assumes a clean fill at the stop price; real gaps fill lower.
- Ignores taxes and commissions, which make stops look better than modelled.
- 6 years covering a mostly rising market. A prolonged bear market would favour stops more.
- Past frequencies are not future probabilities.

## Decision taken

Stop level moved from −20% to **−25%** at the user's instruction (2026-09-05).

**Residual conflict, unresolved:** the preferences file also says the user would *hold*
through a −30% month. A −25% stop fires before −30% is ever reached, so that answer can
never take effect. Either the stop widens past −30%, or that answer changes. Flagged, not
silently reconciled.

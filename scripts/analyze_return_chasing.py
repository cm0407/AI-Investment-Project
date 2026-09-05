"""Does last year's winner become next year's winner? Test it, don't assume it.

USAGE
    python scripts/analyze_return_chasing.py
    python scripts/analyze_return_chasing.py --years 10 --forward 12

THE QUESTION IT ANSWERS
    "I'm a beginner, so I should just buy the stocks with the best returns."
    Is that true? Sort every stock by how it performed over the PREVIOUS 12 months,
    then measure what each group did over the FOLLOWING 12 months.

WHY IT MATTERS
    Picking on past return is selecting on an outcome that has already been paid for by
    whoever owned the stock while it rose. This script measures whether that outcome
    carries forward, using the same price data the rest of the system uses.

HONEST LIMITS
    1. SURVIVORSHIP BIAS, and here it cuts in a specific direction: the universe is
       companies large and listed TODAY, so past winners are over-represented by
       construction. That biases the test IN FAVOUR of return-chasing. If high-trailing
       buckets still fail to outperform, the real-world result is worse than shown.
    2. Overlapping windows are not independent observations.
    3. One market regime. A different decade could look different.
    4. This tests NAIVE return-chasing over a 12-month hold. It is not a test of
       systematic momentum strategies, which rebalance far more often and impose their
       own risk controls. Momentum as a factor is real; this is not that.
"""

from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from invest import config, universe


def main() -> int:
    ap = argparse.ArgumentParser(description="Test whether past returns predict future ones.")
    ap.add_argument("--years", type=int, default=10, help="years of history")
    ap.add_argument("--trailing", type=int, default=12, help="look-back window, months")
    ap.add_argument("--forward", type=int, default=12, help="look-forward window, months")
    ap.add_argument("--step", type=int, default=5, help="trading days between entries")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    import yfinance as yf

    config.ensure_dirs()
    tickers = [r["ticker"] for r in universe.load(limit=args.limit)]
    back = int(args.trailing * 21)
    fwd = int(args.forward * 21)

    print("Do last year's best performers keep winning?")
    print("Universe: " + str(len(tickers)) + " tickers | look-back "
          + str(args.trailing) + "m | look-forward " + str(args.forward) + "m\n")
    print("Downloading price history...")

    data = yf.download(tickers, period=str(args.years) + "y", interval="1d",
                       progress=False, auto_adjust=True, threads=True)
    if data is None or data.empty:
        print("Download failed.")
        return 1
    closes = data["Close"]

    # (trailing_return, forward_return) for every simulated entry
    obs: list[tuple[float, float]] = []
    used = 0
    for tk in tickers:
        try:
            s = closes[tk].dropna()
        except KeyError:
            continue
        if len(s) < back + fwd + 20:
            continue
        used += 1
        v = s.values
        for i in range(back, len(v) - fwd, args.step):
            past = float(v[i - back])
            now = float(v[i])
            future = float(v[i + fwd])
            if past <= 0 or now <= 0:
                continue
            obs.append(((now / past - 1.0) * 100.0, (future / now - 1.0) * 100.0))

    if len(obs) < 100:
        print("Not enough observations.")
        return 1

    obs.sort(key=lambda x: x[0])
    n = len(obs)
    buckets = 5
    size = n // buckets
    labels = ["worst 20%", "below avg", "middle 20%", "above avg", "BEST 20%"]

    print("\n" + "=" * 78)
    print("RESULTS - " + format(n, ",") + " observations across " + str(used) + " stocks")
    print("=" * 78)
    print("\nStocks sorted by their PREVIOUS " + str(args.trailing)
          + "-month return, then measured over the NEXT " + str(args.forward) + " months:\n")
    print("  Group by past perf   Past return    ->   NEXT " + str(args.forward)
          + "m return    Hit +20%   Lost money")
    print("  " + "-" * 74)

    summary = []
    for b in range(buckets):
        lo = b * size
        hi = (b + 1) * size if b < buckets - 1 else n
        chunk = obs[lo:hi]
        past_avg = sum(c[0] for c in chunk) / len(chunk)
        fwd_avg = sum(c[1] for c in chunk) / len(chunk)
        fwd_sorted = sorted(c[1] for c in chunk)
        fwd_med = fwd_sorted[len(fwd_sorted) // 2]
        hit20 = sum(1 for c in chunk if c[1] >= 20.0) / len(chunk) * 100.0
        lost = sum(1 for c in chunk if c[1] < 0.0) / len(chunk) * 100.0
        summary.append((labels[b], past_avg, fwd_avg, fwd_med, hit20, lost))
        print("  " + labels[b].ljust(20) + format(past_avg, "+8.1f") + "%"
              + "        " + format(fwd_avg, "+8.1f") + "%  (med "
              + format(fwd_med, "+.1f") + "%)   "
              + format(hit20, "5.1f") + "%     " + format(lost, "5.1f") + "%")

    best, worst = summary[-1], summary[0]
    print("\n" + "-" * 78)
    print("THE COMPARISON THAT MATTERS")
    print("-" * 78)
    print("  Buying the BEST performers of the last " + str(args.trailing) + " months")
    print("     they had returned : " + format(best[1], "+.1f") + "% on average")
    print("     they then returned: " + format(best[2], "+.1f")
          + "% over the next " + str(args.forward) + " months")
    print("     hit +20%          : " + format(best[4], ".1f") + "% of the time")
    print("     lost money        : " + format(best[5], ".1f") + "% of the time")
    print("\n  Buying the WORST performers of the last " + str(args.trailing) + " months")
    print("     they had returned : " + format(worst[1], "+.1f") + "% on average")
    print("     they then returned: " + format(worst[2], "+.1f")
          + "% over the next " + str(args.forward) + " months")
    print("     hit +20%          : " + format(worst[4], ".1f") + "% of the time")
    print("     lost money        : " + format(worst[5], ".1f") + "% of the time")

    overall = sum(o[1] for o in obs) / n
    print("\n  Buying at random from this universe: " + format(overall, "+.1f") + "%")
    edge = best[2] - overall
    print("\n  Edge from chasing the best performers: " + format(edge, "+.2f")
          + " percentage points versus picking at random.")

    print("\n" + "=" * 78)
    print("LIMITS - read before concluding anything")
    print("=" * 78)
    print("  * SURVIVORSHIP BIAS here favours return-chasing: the universe is companies")
    print("    still large and listed today, so yesterday's winners are over-represented")
    print("    by construction. A weak result here is weaker still in reality.")
    print("  * Overlapping windows; frequencies, not significance tests.")
    print("  * One market regime, " + str(args.years) + " years.")
    print("  * This tests naive 12-month return-chasing, NOT systematic momentum.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

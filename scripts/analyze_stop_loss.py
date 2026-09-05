"""Test a stop-loss rule against real price history before trusting it with money.

USAGE
    python scripts/analyze_stop_loss.py                     # default: -20% stop, 12m hold
    python scripts/analyze_stop_loss.py --stop 25 --hold 12
    python scripts/analyze_stop_loss.py --stop 20 --years 8 --limit 60

THE QUESTION IT ANSWERS
    "If I sell automatically whenever a position falls 20% below what I paid, how often
    does that save me from a real loss, and how often does it eject me from a stock that
    was about to recover?"

METHOD
    For every ticker in the universe, step through history weekly. At each entry date,
    look forward over the holding period and ask:
      - did the price ever touch the stop level?          -> the stop would have fired
      - what was the return if you had simply held?       -> what the stop cost or saved
    Then compare the two strategies across every simulated entry.

HONEST LIMITS - read before believing the output
    1. SURVIVORSHIP BIAS, and it is severe. The starter universe is companies that are
       large and listed TODAY. Firms that collapsed are absent, so the "just hold"
       strategy looks better here than it would have in real life. This biases the
       result AGAINST stop-losses. Treat the pro-holding conclusion as an upper bound.
    2. Overlapping windows are not independent observations, so these are descriptive
       frequencies, not statistical significance.
    3. Assumes a clean fill exactly at the stop price. Real gaps fill lower.
    4. Ignores taxes and trading costs, which make stops look better than modelled.
    5. Past frequencies are not probabilities about the future.
"""

from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from invest import config, universe


def main() -> int:
    ap = argparse.ArgumentParser(description="Backtest a stop-loss rule.")
    ap.add_argument("--stop", type=float, default=20.0, help="stop level, %% below entry")
    ap.add_argument("--hold", type=int, default=12, help="holding period in months")
    ap.add_argument("--years", type=int, default=6, help="years of history to test")
    ap.add_argument("--limit", type=int, default=None, help="only use first N tickers")
    ap.add_argument("--step", type=int, default=5, help="days between simulated entries")
    args = ap.parse_args()

    import pandas as pd
    import yfinance as yf

    config.ensure_dirs()
    tickers = [r["ticker"] for r in universe.load(limit=args.limit)]
    hold_days = int(args.hold * 21)          # ~21 trading days per month
    stop_mult = 1.0 - args.stop / 100.0

    print("Testing a -" + format(args.stop, ".0f") + "% stop-loss over a "
          + str(args.hold) + "-month holding period")
    print("Universe: " + str(len(tickers)) + " tickers, " + str(args.years)
          + " years of daily prices\n")
    print("Downloading price history (one batch request)...")

    data = yf.download(tickers, period=str(args.years) + "y", interval="1d",
                       progress=False, auto_adjust=True, threads=True)
    if data is None or data.empty:
        print("Download failed - no data returned.")
        return 1
    closes = data["Close"]

    stopped_out = 0
    total_entries = 0
    stopped_but_recovered = 0        # stop fired, yet holding would have ended positive
    stopped_and_hit_20 = 0           # stop fired, yet holding would have ended >= +20%
    stopped_saved_you = 0            # stop fired, holding would have ended worse than stop
    held_returns: list[float] = []
    stop_returns: list[float] = []
    stopped_hold_returns: list[float] = []
    tickers_used = 0

    for tk in tickers:
        try:
            series = closes[tk].dropna()
        except KeyError:
            continue
        if len(series) < hold_days + 30:
            continue
        tickers_used += 1
        values = series.values

        for i in range(0, len(values) - hold_days, args.step):
            entry = float(values[i])
            if entry <= 0:
                continue
            window = values[i + 1: i + 1 + hold_days]
            if len(window) < hold_days:
                continue

            final = float(window[-1])
            hold_ret = (final / entry - 1.0) * 100.0
            stop_price = entry * stop_mult
            hit_stop = bool((window <= stop_price).any())

            total_entries += 1
            held_returns.append(hold_ret)
            stop_returns.append(-args.stop if hit_stop else hold_ret)

            if hit_stop:
                stopped_out += 1
                stopped_hold_returns.append(hold_ret)
                if hold_ret > 0:
                    stopped_but_recovered += 1
                if hold_ret >= 20.0:
                    stopped_and_hit_20 += 1
                if hold_ret < -args.stop:
                    stopped_saved_you += 1

    if not total_entries:
        print("No usable windows.")
        return 1

    def pct(n, d):
        return (n / d * 100.0) if d else 0.0

    print("\n" + "=" * 76)
    print("RESULTS - " + format(total_entries, ",") + " simulated entries across "
          + str(tickers_used) + " stocks")
    print("=" * 76)

    print("\nHOW OFTEN THE STOP FIRED")
    print("  entries where the price touched -" + format(args.stop, ".0f") + "% : "
          + format(stopped_out, ",") + "  (" + format(pct(stopped_out, total_entries), ".1f")
          + "% of all entries)")

    print("\nOF THOSE STOPPED-OUT POSITIONS, WHAT WOULD HOLDING HAVE DONE?")
    print("  finished POSITIVE anyway          : " + format(stopped_but_recovered, ",")
          + "  (" + format(pct(stopped_but_recovered, stopped_out), ".1f") + "% of stop-outs)")
    print("  finished at +20% or better        : " + format(stopped_and_hit_20, ",")
          + "  (" + format(pct(stopped_and_hit_20, stopped_out), ".1f") + "% of stop-outs)")
    print("  finished WORSE than the stop      : " + format(stopped_saved_you, ",")
          + "  (" + format(pct(stopped_saved_you, stopped_out), ".1f")
          + "% - these are the cases the stop genuinely saved you from)")
    if stopped_hold_returns:
        avg = sum(stopped_hold_returns) / len(stopped_hold_returns)
        print("  average outcome if held           : " + format(avg, "+.1f") + "%")

    avg_hold = sum(held_returns) / len(held_returns)
    avg_stop = sum(stop_returns) / len(stop_returns)
    print("\nSTRATEGY COMPARISON (average " + str(args.hold) + "-month return per entry)")
    print("  hold through the drawdown         : " + format(avg_hold, "+.2f") + "%")
    print("  sell at -" + format(args.stop, ".0f") + "%, sit in cash        : "
          + format(avg_stop, "+.2f") + "%")
    print("  difference                        : "
          + format(avg_stop - avg_hold, "+.2f") + "% per position")

    worst_held = min(held_returns)
    print("\nWHAT THE STOP PROTECTS AGAINST")
    print("  worst outcome if you always held  : " + format(worst_held, ".1f") + "%")
    print("  worst outcome with the stop       : " + format(-args.stop, ".1f")
          + "% (by construction, ignoring gaps)")

    print("\n" + "=" * 76)
    print("READ THIS BEFORE DRAWING A CONCLUSION")
    print("=" * 76)
    print("  * SURVIVORSHIP BIAS is severe here. This universe is companies still large")
    print("    and listed today; the ones that went to zero are missing. That makes")
    print("    'just hold' look better than it really was. The true case for a stop is")
    print("    stronger than these numbers show.")
    print("  * Overlapping windows are not independent - these are frequencies, not")
    print("    statistical significance.")
    print("  * A real stop fills on a gap down, often below the stop price.")
    print("  * The stop caps your worst case. That is its actual job. Judge it on")
    print("    whether you can survive and stick to the alternative, not only on the")
    print("    average return.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pull market prices and market statistics for one or more tickers.

USAGE
    python scripts/fetch_prices.py AAPL
    python scripts/fetch_prices.py AAPL MSFT JNJ --period 5y
    python scripts/fetch_prices.py AAPL --history        # also save the daily OHLCV CSV

WHAT IT DOES
    Saves data/prices/TICKER_prices.json  (quote + return/volatility stats + provenance)
    Optionally saves data/prices/TICKER_history.csv (raw daily bars)

SOURCE
    Yahoo Finance via the yfinance library. Market prices only - fundamentals come from
    SEC EDGAR (scripts/fetch_sec.py), never from here.
"""

from __future__ import annotations

import argparse
import json

import _bootstrap  # noqa: F401
from invest import config, prices
from invest.http_cache import write_dataset, Provenance


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch market prices via yfinance.")
    ap.add_argument("tickers", nargs="+", help="one or more ticker symbols, e.g. AAPL MSFT")
    ap.add_argument("--period", default="2y",
                    help="history window: 1y, 2y, 5y, 10y, max (default 2y)")
    ap.add_argument("--history", action="store_true",
                    help="also write the full daily OHLCV history to CSV")
    ap.add_argument("--vendor", action="store_true",
                    help="also pull Yahoo's summary fields (sector, multiples, estimates)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    config.ensure_dirs()
    verbose = not args.quiet
    failures = 0

    for ticker in args.tickers:
        tk = ticker.upper()
        print("\n=== " + tk + " ===")
        try:
            q = prices.quote(tk, period=args.period, verbose=verbose)
        except Exception as exc:
            print("  FAILED: " + str(exc))
            failures += 1
            continue

        print("  price            : $" + format(q["price"], ".2f") + "  (" + q["price_date"] + ")")
        for label, key in (("1 month", "1_month_pct"), ("6 months", "6_month_pct"),
                           ("1 year", "1_year_pct")):
            v = q["returns"][key]
            print("  return " + label.ljust(10) + ": "
                  + (config.MISSING if v is None else format(v, "+.1f") + "%"))
        print("  52-week range    : $" + format(q["52w_low"], ".2f")
              + " - $" + format(q["52w_high"], ".2f"))
        vol = q["annualized_volatility_pct"]
        print("  volatility (ann) : " + (config.MISSING if vol is None else format(vol, ".1f") + "%"))

        payload = {"quote": q}
        if args.vendor:
            snap = prices.vendor_snapshot(tk, verbose=verbose)
            payload["vendor_snapshot"] = snap
            sector = snap["vendor_reported"].get("sector")
            print("  sector (vendor)  : " + str(sector or config.MISSING))

        out = config.PRICES_DIR / (tk + "_prices.json")
        write_dataset(
            out, payload,
            Provenance(source="Yahoo Finance via yfinance",
                       source_url="https://finance.yahoo.com/quote/" + tk,
                       retrieved_at_utc=q["_provenance"]["retrieved_at_utc"],
                       basis="market", period=args.period),
            assumptions=[
                "Prices are split- and dividend-adjusted closes.",
                "Volatility uses the standard deviation of daily returns x sqrt(252).",
                "Yahoo is a third-party aggregator; it is authoritative for prices, "
                "not for fundamentals.",
            ],
        )
        print("  saved            : " + str(out.relative_to(config.ROOT)))

        if args.history:
            hist = prices.price_history(tk, period=args.period, verbose=verbose)
            hpath = config.PRICES_DIR / (tk + "_history.csv")
            hist.to_csv(hpath)
            print("  saved            : " + str(hpath.relative_to(config.ROOT))
                  + " (" + str(len(hist)) + " rows)")

    if failures:
        print("\n" + str(failures) + " ticker(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

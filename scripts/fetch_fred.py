"""Pull macroeconomic data from FRED (Federal Reserve Bank of St. Louis).

USAGE
    python scripts/fetch_fred.py                      # the default macro dashboard
    python scripts/fetch_fred.py --series DGS10 UNRATE CPIAUCSL
    python scripts/fetch_fred.py --years 20 --refresh

WHAT IT DOES
    Saves data/macro/fred_dashboard.json plus one CSV per series in data/macro/.

SOURCE
    FRED, published by the St. Louis Fed. No API key needed - the public CSV endpoint is
    used by default. Set the FRED_API_KEY environment variable to use the JSON API
    instead (free key: https://fredaccount.stlouisfed.org/apikeys).

WHY MACRO DATA IS HERE
    It does not pick stocks. It sets the backdrop: the 10-year Treasury yield is the rate
    every valuation is discounted against, and credit spreads show stress before earnings
    do. Its job is to catch a thesis that quietly depends on rates falling.
"""

from __future__ import annotations

import argparse
import csv

import _bootstrap  # noqa: F401
from invest import config, fred
from invest.http_cache import write_dataset, Provenance


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch macro series from FRED.")
    ap.add_argument("--series", nargs="*", default=None,
                    help="FRED series IDs (default: the built-in dashboard)")
    ap.add_argument("--years", type=int, default=10, help="years of history (default 10)")
    ap.add_argument("--refresh", action="store_true", help="bypass the local cache")
    ap.add_argument("--no-csv", action="store_true", help="skip writing per-series CSVs")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    config.ensure_dirs()
    verbose = not args.quiet

    key_state = ("FRED_API_KEY is set - using the JSON API"
                 if config.FRED_API_KEY else
                 "no FRED_API_KEY - using the public CSV endpoint (no key required)")
    print("FRED access: " + key_state)
    print("Pulling " + str(len(args.series or config.FRED_DEFAULT_SERIES)) + " series, "
          + str(args.years) + " years of history\n")

    dash = fred.dashboard(args.series, years_back=args.years, refresh=args.refresh,
                          verbose=verbose)

    print("\n--- latest readings ---")
    for line in fred.summarize(dash):
        print("  " + line)

    if dash["failed"]:
        print("\n--- failed series ---")
        for sid, err in dash["failed"].items():
            print("  " + sid + ": " + err)

    out = config.MACRO_DIR / "fred_dashboard.json"
    write_dataset(
        out, dash,
        Provenance(source="FRED (Federal Reserve Bank of St. Louis)",
                   source_url="https://fred.stlouisfed.org/",
                   retrieved_at_utc=dash["retrieved_at_utc"],
                   basis="official_stat"),
        assumptions=[
            "Series are used as published, with no seasonal or inflation adjustment "
            "applied by us beyond whatever the series itself already carries.",
            "Some series lag: GDP is quarterly, CPI monthly, Treasury yields daily. The "
            "'latest' value is the latest PUBLISHED value, not today's reality.",
            "Revisions happen. A figure pulled today may differ from the same figure "
            "pulled next month.",
        ],
    )
    print("\nsaved: " + str(out.relative_to(config.ROOT)))

    if not args.no_csv:
        for sid, data in dash["series"].items():
            path = config.MACRO_DIR / (sid + ".csv")
            with path.open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["date", "value", "series_id", "source"])
                for o in data["observations"]:
                    w.writerow([o["date"], o["value"], sid, "FRED"])
        print("saved: " + str(len(dash["series"])) + " per-series CSVs in "
              + str(config.MACRO_DIR.relative_to(config.ROOT)))

    return 0 if not dash["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

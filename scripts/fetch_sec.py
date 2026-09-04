"""Pull company fundamentals and filings from SEC EDGAR - the authoritative source.

USAGE
    python scripts/fetch_sec.py AAPL
    python scripts/fetch_sec.py AAPL JNJ JPM --years 8
    python scripts/fetch_sec.py AAPL --insider          # also parse recent Form 4 filings
    python scripts/fetch_sec.py AAPL --refresh          # ignore the cache, pull fresh
    python scripts/fetch_sec.py AAPL --filings          # list recent 10-K / 10-Q / 8-K

WHAT IT DOES
    Saves data/fundamentals/TICKER_sec.json  - every annual figure, with the exact XBRL
    tag, filing form, accession number and filing date behind each one, plus a list of
    concepts that could NOT be found (reported as unavailable, never as zero).

SOURCE
    https://data.sec.gov  - free, no API key, no registration.
    User-Agent is set to your-email@example.com as the SEC requires; requests are rate
    limited to 5/second against their published ceiling of 10/second.
"""

from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from invest import config, sec_edgar as sec
from invest.http_cache import write_dataset, Provenance, FetchError
from invest.metrics import format_metric


def _print_series(label: str, rows: list[dict], unit: str = "usd") -> None:
    if not rows:
        print("  " + label.ljust(22) + ": " + config.MISSING)
        return
    parts = []
    for r in rows[-5:]:
        year = r["period_end"][:4]
        parts.append(year + "=" + format_metric(r["value"], unit))
    print("  " + label.ljust(22) + ": " + "  ".join(parts))


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch SEC EDGAR fundamentals.")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--years", type=int, default=6, help="years of annual history (default 6)")
    ap.add_argument("--insider", action="store_true", help="parse recent Form 4 filings")
    ap.add_argument("--filings", action="store_true", help="print recent filings with URLs")
    ap.add_argument("--refresh", action="store_true", help="bypass the local cache")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    config.ensure_dirs()
    verbose = not args.quiet
    failures = 0

    for ticker in args.tickers:
        tk = ticker.upper()
        print("\n=== " + tk + " ===")
        try:
            fund = sec.fundamentals(tk, years=args.years, refresh=args.refresh, verbose=verbose)
        except FetchError as exc:
            print("  FAILED: " + str(exc))
            failures += 1
            continue

        prof = fund["profile"]
        print("  company   : " + str(fund["company_name"]))
        print("  CIK       : " + fund["cik_padded"])
        print("  industry  : SIC " + str(prof.get("sic")) + " - " + str(prof.get("sic_description")))
        print("  exchange  : " + str(prof.get("exchanges")) + "   FY ends: " + str(prof.get("fiscal_year_end")))
        sh = fund.get("shares_outstanding_latest")
        if sh:
            print("  shares    : " + format_metric(sh["value"], "num", 0)
                  + "  (" + sh["tag"] + ", as of " + sh["period_end"] + ", form " + sh["form"] + ")")
        print()
        a = fund["annual"]
        _print_series("revenue", a.get("revenue", []))
        _print_series("gross profit", a.get("gross_profit", []))
        _print_series("operating income", a.get("operating_income", []))
        _print_series("net income", a.get("net_income", []))
        _print_series("operating cash flow", a.get("operating_cash_flow", []))
        _print_series("capital expenditure", a.get("capex", []))
        _print_series("total equity", a.get("equity", []))
        _print_series("cash", a.get("cash", []))
        _print_series("diluted EPS", a.get("eps_diluted", []), unit="num")

        if fund["concepts_unavailable"]:
            print("\n  NOT FOUND in this company's filings (" + config.MISSING + "):")
            print("    " + ", ".join(fund["concepts_unavailable"]))

        payload = {"fundamentals": fund}

        if args.insider:
            print("\n  --- insider activity (Form 4) ---")
            ins = sec.insider_transactions(fund["cik_padded"], refresh=args.refresh,
                                           verbose=verbose)
            s = ins["summary"]
            print("    filings examined : " + str(ins["filings_examined"])
                  + " (parsed " + str(ins["filings_parsed"]) + ")")
            print("    open-market buys : " + str(s["open_market_buys"])
                  + "  worth " + format_metric(s["buy_value_usd"], "usd"))
            print("    open-market sells: " + str(s["open_market_sells"])
                  + "  worth " + format_metric(s["sell_value_usd"], "usd"))
            print("    net              : " + format_metric(s["net_value_usd"], "usd"))
            print("    window           : " + str(s["earliest_txn"]) + " to " + str(s["latest_txn"]))
            payload["insider_activity"] = ins

        if args.filings:
            print("\n  --- recent filings ---")
            fl = sec.recent_filings(fund["cik_padded"], forms=("10-K", "10-Q", "8-K"),
                                    limit=8, refresh=args.refresh, verbose=verbose)
            for f in fl:
                print("    " + str(f["filingDate"]) + "  " + str(f["form"]).ljust(6)
                      + "  " + str(f["url"]))
            payload["recent_filings"] = fl

        out = config.FUNDAMENTALS_DIR / (tk + "_sec.json")
        write_dataset(
            out, payload,
            Provenance(source="SEC EDGAR XBRL companyfacts",
                       source_url=fund["_source_urls"]["companyfacts"],
                       retrieved_at_utc=fund["_provenance"]["retrieved_at_utc"],
                       basis="actual",
                       notes="As-reported figures from filed 10-K/20-F documents."),
            assumptions=[
                "Annual figures are taken from 10-K/20-F/40-F filings only; duration facts "
                "are kept only when the period spans 300-400 days, which excludes the "
                "quarterly and year-to-date stubs that also appear inside a 10-K.",
                "Where a figure was later restated, the most recently FILED version is "
                "used - the company's latest word on its own past.",
                "Concepts absent from a company's filings are listed under "
                "concepts_unavailable and must never be treated as zero.",
            ],
        )
        print("\n  saved     : " + str(out.relative_to(config.ROOT)))

    if failures:
        print("\n" + str(failures) + " ticker(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

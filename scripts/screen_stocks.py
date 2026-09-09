"""Phase 1 - screen a universe of stocks on SEC-filed fundamentals.

USAGE
    python scripts/screen_stocks.py                          # screen the starter universe
    python scripts/screen_stocks.py --limit 25               # quick run on the first 25
    python scripts/screen_stocks.py --tickers AAPL JNJ JPM   # screen specific names
    python scripts/screen_stocks.py --universe full --limit 500
    python scripts/screen_stocks.py --min-revenue-growth 8 --max-pe 25 --top 20
    python scripts/screen_stocks.py --sector "Health Care"

WHAT IT DOES
    For each ticker: pulls SEC fundamentals + the current market price, computes the metric
    set, applies any filters you passed, ranks on a composite of the data-scorable pillars,
    and writes a timestamped CSV + JSON to data/screens/ and reports/screens/.

WHAT IT DOES NOT DO
    It does not recommend anything. A high rank here means "worth a closer look", and
    Phases 2-5 (fundamentals, valuation, catalysts, and actively trying to break the
    thesis) still have to happen before any BUY/WATCH/AVOID call is made.

RUNTIME
    Each ticker needs one SEC companyfacts download (a few MB) plus a price lookup, rate
    limited to 5 requests/second. Roughly 1-3 seconds per name on a first run, and much
    faster afterwards because everything is cached for 24 hours.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime

import _bootstrap  # noqa: F401
from invest import config, metrics, preferences, prices, scoring, universe
from invest import sec_edgar as sec
from invest.http_cache import write_dataset, Provenance, utcnow_iso, FetchError

RANK_FIELDS = [
    ("composite_score", "Composite of the 4 data-scorable pillars, 0-50 points"),
    ("revenue_cagr_pct", "Multi-year revenue growth"),
    ("fcf_yield_pct", "Free cash flow / market cap"),
    ("roic_pct", "Return on invested capital"),
    ("pe_ratio", "Price / earnings (lower ranks first)"),
]


def screen_one(ticker: str, years: int, refresh: bool, verbose: bool) -> dict:
    """Pull everything needed for one ticker and return a flat row of results."""
    row: dict = {"ticker": ticker.upper(), "status": "ok", "error": None}
    try:
        fund = sec.fundamentals(ticker, years=years, refresh=refresh, verbose=False)
    except FetchError as exc:
        return {**row, "status": "no_sec_data", "error": str(exc)[:200]}
    except Exception as exc:
        return {**row, "status": "sec_error", "error": (type(exc).__name__ + ": " + str(exc))[:200]}

    price = None
    try:
        q = prices.quote(ticker, period="1y", verbose=False)
        price = q["price"]
        row["price_date"] = q["price_date"]
        row["return_1y_pct"] = q["returns"]["1_year_pct"]
        row["return_6m_pct"] = q["returns"]["6_month_pct"]
        row["volatility_pct"] = q["annualized_volatility_pct"]
        row["pct_below_52w_high"] = q["pct_below_52w_high"]
    except Exception as exc:
        row["price_error"] = (type(exc).__name__ + ": " + str(exc))[:120]

    m = metrics.compute(fund, price=price)
    sc = scoring.score_company(m, fund)

    profile = fund.get("profile", {})
    row.update({
        "company_name": fund.get("company_name"),
        "cik": fund.get("cik_padded"),
        "sic": profile.get("sic"),
        "industry": profile.get("sic_description"),
        "price": price,
        "market_cap": m.get("market_cap"),
        "revenue_latest": m.get("revenue_latest"),
        "revenue_period": m.get("revenue_period"),
        "revenue_cagr_pct": m.get("revenue_cagr_pct"),
        "revenue_growth_latest_pct": m.get("revenue_growth_latest_pct"),
        "net_income_cagr_pct": m.get("net_income_cagr_pct"),
        "gross_margin_pct": m.get("gross_margin_pct"),
        "operating_margin_pct": m.get("operating_margin_pct"),
        "net_margin_pct": m.get("net_margin_pct"),
        "fcf_margin_pct": m.get("fcf_margin_pct"),
        "roe_pct": m.get("roe_pct"),
        "roic_pct": m.get("roic_pct"),
        "debt_to_equity": m.get("debt_to_equity"),
        "current_ratio": m.get("current_ratio"),
        "net_debt_to_ebitda": m.get("net_debt_to_ebitda"),
        "ocf_to_net_income": m.get("ocf_to_net_income"),
        "pe_ratio": m.get("pe_ratio"),
        "ps_ratio": m.get("ps_ratio"),
        "pfcf_ratio": m.get("pfcf_ratio"),
        "ev_ebitda": m.get("ev_ebitda"),
        "peg_ratio": m.get("peg_ratio"),
        "fcf_yield_pct": m.get("fcf_yield_pct"),
        "share_count_change_pct": m.get("share_count_change_pct"),
        "composite_score": sc.get("data_points_earned"),
        "composite_max_available": sc.get("data_points_available"),
        "growth_points": sc["data_pillars"]["growth"].get("points"),
        "valuation_points": sc["data_pillars"]["valuation"].get("points"),
        "strength_points": sc["data_pillars"]["financial_strength"].get("points"),
        "fcf_points": sc["data_pillars"]["free_cash_flow"].get("points"),
        "growth_trend": sc["data_pillars"]["growth"].get("trend"),
        "metrics_unavailable_count": len(m.get("_unavailable_metrics", [])),
        "stale_inputs_excluded": len(m.get("_stale_inputs_excluded", [])),
        # Carry the data caveats into the CSV. A margin computed from a fallback tag can
        # mean something slightly different from the same margin at another company, and
        # a rank built across the two is comparing unlike things.
        "fallback_tags_count": len(m.get("_fallback_tags_used", {})),
        "fallback_tags": "; ".join(
            c + "->" + str(e.get("tag_used")) for c, e in
            (m.get("_fallback_tags_used") or {}).items()),
        "composites_suppressed": "; ".join(m.get("_composites_suppressed", [])),
        "sector_special": (m.get("_sector") or {}).get("kind") or "",
        # needed by the preference rules (IPO recency, domicile)
        "annual_periods_available": len(fund.get("annual", {}).get("revenue") or []),
        "state_of_incorporation": profile.get("state_of_incorporation"),
        "reorganization_detected": bool(fund.get("reorganization")),
        "history_from_cik": (fund.get("reorganization") or {}).get("history_cik", ""),
    })
    row["_fund"] = fund
    return row


def passes_filters(row: dict, args) -> tuple[bool, str]:
    """Apply the command-line filters. A missing value never silently passes a filter."""
    checks = [
        ("min_revenue_growth", "revenue_cagr_pct", lambda v, t: v >= t, "revenue CAGR"),
        ("max_pe", "pe_ratio", lambda v, t: v <= t, "P/E"),
        ("min_fcf_yield", "fcf_yield_pct", lambda v, t: v >= t, "FCF yield"),
        ("min_roic", "roic_pct", lambda v, t: v >= t, "ROIC"),
        ("max_debt_to_equity", "debt_to_equity", lambda v, t: v <= t, "debt/equity"),
        ("min_market_cap", "market_cap", lambda v, t: v >= t * 1e9, "market cap"),
        ("min_operating_margin", "operating_margin_pct", lambda v, t: v >= t, "operating margin"),
    ]
    for arg_name, field, test, label in checks:
        threshold = getattr(args, arg_name, None)
        if threshold is None:
            continue
        value = row.get(field)
        if value is None:
            return False, "excluded: " + label + " is " + config.MISSING
        if not test(value, threshold):
            return False, ("excluded: " + label + " = " + format(value, ".2f")
                           + " fails threshold " + str(threshold))
    if args.sector:
        industry = (row.get("industry") or "").lower()
        hint = (row.get("sector_hint") or "").lower()
        if args.sector.lower() not in industry and args.sector.lower() not in hint:
            return False, "excluded: sector filter"

    # The user's own rules, read from notes/my_investing_preferences.md. A rule that
    # cannot be evaluated because data is missing EXCLUDES the company rather than
    # letting it through - a filter that fails open is worse than no filter.
    prefs = getattr(args, "_prefs", None)
    if prefs is not None:
        ok, why = preferences.check(row, prefs, fund=row.get("_fund"))
        if not ok:
            return False, "excluded by your preferences: " + "; ".join(why)
    return True, "passed"


def main() -> int:
    ap = argparse.ArgumentParser(description="Screen stocks on SEC fundamentals.")
    ap.add_argument("--tickers", nargs="*", help="screen these tickers instead of a universe")
    ap.add_argument("--universe", choices=["starter", "full"], default="starter")
    ap.add_argument("--limit", type=int, default=None, help="only screen the first N names")
    ap.add_argument("--years", type=int, default=6, help="years of financial history")
    ap.add_argument("--top", type=int, default=25, help="how many rows to print")
    ap.add_argument("--rank-by", default="composite_score",
                    choices=[f for f, _ in RANK_FIELDS])
    ap.add_argument("--sector", default=None, help="substring match on SIC industry")
    ap.add_argument("--min-revenue-growth", type=float, default=None)
    ap.add_argument("--max-pe", type=float, default=None)
    ap.add_argument("--min-fcf-yield", type=float, default=None)
    ap.add_argument("--min-roic", type=float, default=None)
    ap.add_argument("--max-debt-to-equity", type=float, default=None)
    ap.add_argument("--min-market-cap", type=float, default=None, help="in $ billions")
    ap.add_argument("--min-operating-margin", type=float, default=None)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--ignore-preferences", action="store_true",
                    help="do NOT apply your avoid-list and limits (diagnostic use only)")
    args = ap.parse_args()

    config.ensure_dirs()
    verbose = not args.quiet
    started = time.time()

    args._prefs = None
    if not args.ignore_preferences:
        try:
            args._prefs = preferences.load()
        except FileNotFoundError as exc:
            print("NOTE: " + str(exc).splitlines()[0])
            print("Screening without your personal rules applied.")
            print()
    if args._prefs is not None:
        pr = args._prefs
        print("Applying YOUR rules from notes/my_investing_preferences.md:")
        for line in pr.summary():
            print("  " + line)
        if pr.unenforceable_rules or pr.partial_rules:
            print()
            print("  Rules this screen CANNOT fully enforce - check these by hand:")
            for u in pr.unenforceable_rules:
                print("    [not enforced] " + u.split(" - ")[0])
            for u in pr.partial_rules:
                print("    [weak filter ] " + u.split(" - ")[0])
        for w in pr.warnings:
            print()
            print("  ! " + w)
        print()

    if args.tickers:
        entries = [{"ticker": t.upper(), "sector_hint": ""} for t in args.tickers]
        source_label = "explicit ticker list"
        bias_note = ("The tickers were chosen by hand for this run. Results describe only "
                     "these names.")
    else:
        path = config.STARTER_UNIVERSE if args.universe == "starter" else config.FULL_UNIVERSE
        if not path.exists():
            print("Universe not built. Run: python scripts/build_universe.py"
                  + (" --full" if args.universe == "full" else ""))
            return 1
        entries = universe.load(path, limit=args.limit)
        source_label = args.universe + " universe (" + path.name + ")"
        bias_note = (universe.STARTER_BIAS_WARNING if args.universe == "starter"
                     else "Full SEC registry - no curation bias, but includes trusts, "
                          "funds and shells that are not operating companies.")

    print("Screening " + str(len(entries)) + " tickers from the " + source_label)
    print("Data: SEC EDGAR fundamentals + yfinance prices. Rate limited to 5 req/s.\n")

    rows: list[dict] = []
    excluded: list[dict] = []
    errors: list[dict] = []

    for i, entry in enumerate(entries, 1):
        tk = entry["ticker"]
        if verbose:
            print("  [" + str(i).rjust(len(str(len(entries)))) + "/" + str(len(entries))
                  + "] " + tk.ljust(6), end="", flush=True)
        row = screen_one(tk, args.years, args.refresh, verbose)
        row["sector_hint"] = entry.get("sector_hint", "")

        if row["status"] != "ok":
            errors.append(row)
            if verbose:
                print("  SKIPPED (" + row["status"] + ")")
            continue

        ok, reason = passes_filters(row, args)
        row["filter_result"] = reason
        if ok:
            rows.append(row)
            if verbose:
                cs = row.get("composite_score")
                print("  score " + (format(cs, "5.1f") if cs is not None else "  n/a")
                      + "/" + format(row.get("composite_max_available") or 0, ".0f")
                      + "   " + str(row.get("company_name"))[:38])
        else:
            excluded.append(row)
            if verbose:
                print("  " + reason)

    if not rows:
        print("\nNo stocks passed the filters. Loosen them or widen the universe.")
        if errors:
            print(str(len(errors)) + " ticker(s) had no usable data.")
        return 0

    reverse = args.rank_by != "pe_ratio"  # for P/E, lower is better
    ranked = sorted(
        [r for r in rows if r.get(args.rank_by) is not None],
        key=lambda r: r[args.rank_by], reverse=reverse,
    )
    unranked = [r for r in rows if r.get(args.rank_by) is None]

    # ---- Console table ----------------------------------------------------------------
    print("\n" + "=" * 118)
    print("TOP " + str(min(args.top, len(ranked))) + " BY " + args.rank_by.upper()
          + "   (of " + str(len(rows)) + " that passed filters)")
    print("=" * 118)
    hdr = ("  #  TICKER  " + "COMPANY".ljust(26) + "SCORE  " + "PRICE".rjust(9)
           + "  " + "REV CAGR".rjust(9) + "  " + "OP MGN".rjust(7) + "  "
           + "ROIC".rjust(7) + "  " + "P/E".rjust(7) + "  " + "FCF YLD".rjust(8))
    print(hdr)
    print("-" * 118)

    def fmt(v, spec, width):
        # "n/a" rather than a truncated "DATA UNA" - the legend below spells out that n/a
        # means the figure could not be verified, never that it is zero.
        return ("n/a".rjust(width) if v is None else format(v, spec).rjust(width))

    for i, r in enumerate(ranked[:args.top], 1):
        print("  " + str(i).rjust(2) + "  " + r["ticker"].ljust(7)
              + str(r.get("company_name") or "")[:25].ljust(26)
              + fmt(r.get("composite_score"), "5.1f", 5) + "  "
              + fmt(r.get("price"), ",.2f", 9) + "  "
              + fmt(r.get("revenue_cagr_pct"), "8.1f", 9) + "  "
              + fmt(r.get("operating_margin_pct"), "6.1f", 7) + "  "
              + fmt(r.get("roic_pct"), "6.1f", 7) + "  "
              + fmt(r.get("pe_ratio"), "6.1f", 7) + "  "
              + fmt(r.get("fcf_yield_pct"), "7.1f", 8))
    print("-" * 118)
    print("  n/a = " + config.MISSING + " (never means zero)")
    if unranked:
        print(str(len(unranked)) + " passed filters but could not be ranked on "
              + args.rank_by + " (value unavailable): "
              + ", ".join(r["ticker"] for r in unranked[:15]))

    # ---- Persist ----------------------------------------------------------------------
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    csv_path = config.SCREENS_DIR / ("screen_" + stamp + ".csv")
    for r in rows + excluded + errors:
        r.pop("_fund", None)
    fields = sorted({k for r in rows for k in r})
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(ranked + unranked)

    json_path = config.SCREENS_DIR / ("screen_" + stamp + ".json")
    write_dataset(
        json_path,
        {
            "run": {
                "timestamp_utc": utcnow_iso(),
                "universe": source_label,
                "tickers_attempted": len(entries),
                "passed_filters": len(rows),
                "excluded_by_filters": len(excluded),
                "errors": len(errors),
                "ranked_by": args.rank_by,
                "filters_applied": {
                    k: v for k, v in vars(args).items()
                    if v is not None and k.startswith(("min_", "max_")) or k == "sector" and v
                },
                "elapsed_seconds": round(time.time() - started, 1),
            },
            "results": ranked + unranked,
            "excluded": [{"ticker": r["ticker"], "reason": r.get("filter_result")}
                         for r in excluded],
            "errors": [{"ticker": r["ticker"], "status": r["status"], "error": r.get("error")}
                       for r in errors],
        },
        [Provenance(source="SEC EDGAR XBRL companyfacts", source_url=config.SEC_BASE,
                    retrieved_at_utc=utcnow_iso(), basis="actual",
                    notes="fundamentals"),
         Provenance(source="Yahoo Finance via yfinance", source_url="https://finance.yahoo.com",
                    retrieved_at_utc=utcnow_iso(), basis="market", notes="prices")],
        assumptions=[
            bias_note,
            "composite_score is the sum of the FOUR data-scorable pillars only (growth 15, "
            "valuation 15, financial strength 10, free cash flow 10 = 50 points max). It is "
            "NOT the CLAUDE.md 0-100 score: business quality, moat, catalysts, risk/reward "
            "and management (50 points) require analyst judgment and are not computed here.",
            "A pillar is averaged over whichever components have data, so a company with "
            "thin coverage can score on very few inputs. Check composite_max_available and "
            "metrics_unavailable_count before trusting a rank.",
            "Financial-sector companies are scored on thresholds calibrated for operating "
            "companies and will be mis-ranked on leverage and cash-flow measures.",
            "Ranking is a starting point for research, not a recommendation. Phases 2-5 of "
            "CLAUDE.md must still be done by hand.",
        ],
    )

    md_path = config.SCREEN_REPORTS_DIR / ("screen_" + stamp + ".md")
    with md_path.open("w", encoding="utf-8") as fh:
        fh.write("# Screen - " + stamp + "\n\n")
        fh.write("- **Universe:** " + source_label + "\n")
        fh.write("- **Attempted:** " + str(len(entries)) + " · **Passed:** " + str(len(rows))
                 + " · **Filtered out:** " + str(len(excluded))
                 + " · **No data:** " + str(len(errors)) + "\n")
        fh.write("- **Ranked by:** " + args.rank_by + "\n\n")
        fh.write("> " + bias_note + "\n\n")
        fh.write("> The composite score below is out of **50**, not 100. It covers only the "
                 "pillars a script can compute from filings. Moat, catalysts, management and "
                 "risk/reward are unscored here.\n\n")
        fh.write("| # | Ticker | Company | Score/50 | Price | Rev CAGR | Op margin | ROIC | P/E | FCF yield |\n")
        fh.write("|---|--------|---------|----------|-------|----------|-----------|------|-----|----------|\n")
        for i, r in enumerate(ranked[:args.top], 1):
            def md(v, spec="{:.1f}"):
                return "n/a" if v is None else spec.format(v)
            fh.write("| " + str(i) + " | " + r["ticker"] + " | "
                     + str(r.get("company_name") or "")[:32] + " | " + md(r.get("composite_score"))
                     + " | " + md(r.get("price"), "${:,.2f}") + " | " + md(r.get("revenue_cagr_pct")) + "% | "
                     + md(r.get("operating_margin_pct")) + "% | " + md(r.get("roic_pct")) + "% | "
                     + md(r.get("pe_ratio")) + " | " + md(r.get("fcf_yield_pct")) + "% |\n")

    print("\nsaved: " + str(csv_path.relative_to(config.ROOT)))
    print("saved: " + str(json_path.relative_to(config.ROOT)))
    print("saved: " + str(md_path.relative_to(config.ROOT)))
    print("\nelapsed: " + format(time.time() - started, ".1f") + "s"
          + "   |   " + str(len(errors)) + " ticker(s) had no usable SEC data")
    print("\nREMINDER: this is Phase 1 of 5. A high rank means 'look closer', not 'buy'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Phases 2-3 for a single company: full fundamentals, valuation, and the scoring rubric.

USAGE
    python scripts/score_stock.py AAPL
    python scripts/score_stock.py AAPL --insider --dcf
    python scripts/score_stock.py AAPL --judgment research/judgments/AAPL.json
    python scripts/score_stock.py AAPL --save            # write the full JSON record

WHAT IT PRINTS
    1. Identity and business classification (from the company's own SEC filings)
    2. Multi-year financials, as reported
    3. Derived metrics, with anything uncomputable marked DATA UNAVAILABLE OR UNVERIFIED
    4. Valuation: multiples, a reverse DCF, and (with --dcf) a DCF plus sensitivity grid
    5. The score - the four pillars a script can compute, and an evidence pack for the
       five that need a human

IMPORTANT
    Without a --judgment file the score is PARTIAL and is labelled as such. A script
    cannot judge a moat, a catalyst or a management team, and this one will not pretend
    to. See docs/SCORING.md for how to record those judgments.
"""

from __future__ import annotations

import argparse
import json

import _bootstrap  # noqa: F401
from invest import config, metrics, prices, scoring, valuation
from invest import sec_edgar as sec
from invest.http_cache import write_dataset, Provenance, utcnow_iso, FetchError
from invest.metrics import format_metric as fmt

LINE = "-" * 78


def _row(label: str, value, kind: str = "num", decimals: int = 2) -> None:
    print("  " + label.ljust(30) + fmt(value, kind, decimals))


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze and score one company.")
    ap.add_argument("ticker")
    ap.add_argument("--years", type=int, default=6)
    ap.add_argument("--dcf", action="store_true", help="run a DCF and sensitivity grid")
    ap.add_argument("--insider", action="store_true", help="parse recent Form 4 filings")
    ap.add_argument("--judgment", default=None,
                    help="JSON file with the analyst's scores for the 5 judgment pillars")
    ap.add_argument("--judge", action="store_true",
                    help="score the 5 judgment pillars with a MODEL (claude -p). The model "
                         "returns 5 integers and 5 justifications; 7 deterministic checks "
                         "decide whether that output may contribute to the score. On any "
                         "failure the score falls back to PARTIAL. See docs/MODEL_IN_THE_LOOP.md")
    ap.add_argument("--save", action="store_true", help="write the full record to JSON")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    config.ensure_dirs()
    tk = args.ticker.upper()

    # ---------------- Data ----------------
    print("Pulling SEC filings for " + tk + " ...")
    try:
        fund = sec.fundamentals(tk, years=args.years, refresh=args.refresh, verbose=True)
    except FetchError as exc:
        print("FAILED: " + str(exc))
        return 1

    price, quote = None, None
    try:
        quote = prices.quote(tk, period="2y", verbose=True)
        price = quote["price"]
    except Exception as exc:
        print("WARNING: no market price (" + str(exc)[:120] + ")")
        print("Valuation multiples will be unavailable.")

    m = metrics.compute(fund, price=price)
    insider = None
    if args.insider:
        print("Parsing recent Form 4 filings ...")
        insider = sec.insider_transactions(fund["cik_padded"], refresh=args.refresh)

    judgment = scoring.load_judgment(args.judgment)

    # The model-in-the-loop step. This is the only place a model runs inside the pipeline.
    # An explicit --judgment file always wins: a human overrides the model, never the reverse.
    if args.judge and judgment is None:
        from invest import judge as judge_mod
        if quote:
            m["annual_volatility_pct"] = quote.get("annualized_volatility_pct")
        print()
        print("Scoring the judgment pillars with a model ...")
        judgment = judge_mod.judge(tk, m, fund, insider=insider, refresh=args.refresh)
        if judgment is None:
            print("    model judgment unavailable - falling back to a PARTIAL score")
    score = scoring.score_company(m, fund, insider=insider, judgment=judgment)

    prof = fund["profile"]
    print("\n" + "=" * 78)
    print(str(fund["company_name"]) + "  (" + tk + ")")
    print("=" * 78)
    print("  CIK " + fund["cik_padded"] + "   SIC " + str(prof.get("sic"))
          + " - " + str(prof.get("sic_description")))
    print("  Exchange " + str((prof.get("exchanges") or ["?"])[0])
          + "   Fiscal year ends " + str(prof.get("fiscal_year_end"))
          + "   Latest period " + str(fund.get("latest_fiscal_period_end")))
    if quote:
        print("  Price $" + format(price, ",.2f") + " (" + quote["price_date"] + ")"
              + "   52w $" + format(quote["52w_low"], ",.2f")
              + " - $" + format(quote["52w_high"], ",.2f"))
    reorg = fund.get("reorganization")
    if reorg:
        print()
        print("  ** CORPORATE REORGANIZATION DETECTED **")
        print("     " + reorg["explanation"])
        print("     " + reorg["caution"])

    sect = m.get("_sector", {})
    if sect.get("special"):
        print("\n  ** " + sect["note"] + " **")

    # ---------------- Reported financials ----------------
    print("\n" + LINE + "\nAS REPORTED TO THE SEC (annual, most recent " + str(args.years) + " years)\n" + LINE)
    for label, key in [("Revenue", "revenue"), ("Gross profit", "gross_profit"),
                       ("Operating income", "operating_income"), ("Net income", "net_income"),
                       ("Operating cash flow", "operating_cash_flow"), ("Capex", "capex"),
                       ("Total equity", "equity"), ("Total assets", "total_assets")]:
        rows = fund["annual"].get(key)
        if not rows:
            print("  " + label.ljust(22) + config.MISSING)
            continue
        print("  " + label.ljust(22) + "  ".join(
            r["period_end"][:4] + "=" + fmt(r["value"], "usd") for r in rows[-5:]))

    if m.get("_fallback_tags_used"):
        print("\n  TAG SUBSTITUTIONS (this company does not report the preferred tag):")
        for concept, e in m["_fallback_tags_used"].items():
            print("    " + concept.ljust(24) + "-> " + str(e["tag_used"]))
    if m.get("_stale_inputs_excluded"):
        print("\n  EXCLUDED AS STALE (tag abandoned by the company):")
        for s in m["_stale_inputs_excluded"]:
            print("    " + s)
    if m.get("_composites_suppressed"):
        print("\n  SUPPRESSED COMPOSITES:")
        for s in m["_composites_suppressed"]:
            print("    " + s)

    # ---------------- Derived metrics ----------------
    print("\n" + LINE + "\nDERIVED METRICS\n" + LINE)
    print(" Growth")
    _row("revenue CAGR", m.get("revenue_cagr_pct"), "pct", 1)
    _row("net income CAGR", m.get("net_income_cagr_pct"), "pct", 1)
    _row("FCF CAGR", m.get("fcf_cagr_pct"), "pct", 1)
    _row("latest-year revenue growth", m.get("revenue_growth_latest_pct"), "pct", 1)
    print(" Profitability")
    _row("gross margin", m.get("gross_margin_pct"), "pct", 1)
    _row("operating margin", m.get("operating_margin_pct"), "pct", 1)
    _row("net margin", m.get("net_margin_pct"), "pct", 1)
    _row("FCF margin", m.get("fcf_margin_pct"), "pct", 1)
    _row("ROE", m.get("roe_pct"), "pct", 1)
    _row("ROIC", m.get("roic_pct"), "pct", 1)
    print(" Balance sheet")
    _row("total debt", m.get("total_debt"), "usd")
    _row("cash & short-term investments", m.get("total_cash_and_sti"), "usd")
    _row("net cash position", m.get("net_cash_position"), "usd")
    _row("debt / equity", m.get("debt_to_equity"), "x")
    _row("current ratio", m.get("current_ratio"), "x")
    _row("net debt / EBITDA", m.get("net_debt_to_ebitda"), "x")
    _row("interest coverage", m.get("interest_coverage"), "x")
    print(" Cash quality & shareholders")
    _row("operating cash flow / net income", m.get("ocf_to_net_income"), "x")
    _row("free cash flow", m.get("fcf_latest"), "usd")
    _row("share count change over window", m.get("share_count_change_pct"), "pct", 1)
    _row("buybacks (latest year)", m.get("buybacks_latest"), "usd")
    _row("dividends paid (latest year)", m.get("dividends_paid_latest"), "usd")

    # ---------------- Valuation ----------------
    print("\n" + LINE + "\nVALUATION\n" + LINE)
    _row("market cap", m.get("market_cap"), "usd")
    _row("enterprise value", m.get("enterprise_value"), "usd")
    _row("P/E", m.get("pe_ratio"), "x")
    _row("P/S", m.get("ps_ratio"), "x")
    _row("P/FCF", m.get("pfcf_ratio"), "x")
    _row("P/B", m.get("pb_ratio"), "x")
    _row("EV/EBITDA", m.get("ev_ebitda"), "x")
    _row("PEG", m.get("peg_ratio"), "x")
    _row("FCF yield", m.get("fcf_yield_pct"), "pct", 1)
    _row("earnings yield", m.get("earnings_yield_pct"), "pct", 1)

    fcf, shares = m.get("fcf_latest"), m.get("shares_outstanding")
    net_cash = m.get("net_cash_position") or 0.0

    if price and shares and fcf and fcf > 0:
        rev = valuation.reverse_dcf(price, shares, fcf, net_cash)
        print("\n  REVERSE DCF - what the current price already assumes")
        ig = rev.get("implied_growth_pct")
        print("    implied FCF growth needed : "
              + (config.MISSING if ig is None else format(ig, ".1f") + "% per year"))
        print("    delivered historically    : "
              + fmt(m.get("fcf_cagr_pct"), "pct", 1))
        print("    " + rev["interpretation"][:200])
    else:
        print("\n  REVERSE DCF: " + config.MISSING
              + " (needs a price, a share count and positive free cash flow)")

    if args.dcf:
        if fcf and fcf > 0 and shares:
            g = m.get("fcf_cagr_pct")
            g_dec = (g / 100.0) if g is not None else 0.05
            print("\n  DCF - our own projection")
            print("    NOTE: growth seeded from the historical FCF CAGR ("
                  + (fmt(g, "pct", 1) if g is not None else "unavailable, defaulted to 5%")
                  + "). This is an ASSUMPTION, not a forecast from the company.")
            d = valuation.two_stage_dcf(fcf, g_dec, net_cash=net_cash, shares=shares)
            if d.get("error"):
                print("    " + d["error"])
            else:
                fv = d["fair_value_per_share"]
                print("    fair value estimate       : $" + format(fv, ",.2f"))
                print("    current price             : $" + format(price, ",.2f"))
                print("    implied up/downside       : "
                      + format((fv / price - 1) * 100, "+.1f") + "%")
                print("    terminal value is         : "
                      + format(d["terminal_value_share_of_total_pct"], ".0f")
                      + "% of the total (above ~70% means most of the answer is a guess "
                        "about the distant future)")
                print("\n  SENSITIVITY - fair value per share across assumptions")
                grid = valuation.sensitivity_table(fcf, g_dec, net_cash, shares)["grid"]
                cols = list(next(iter(grid.values())).keys())
                print("    " + "".ljust(18) + "".join(c.rjust(15) for c in cols))
                for rname, rvals in grid.items():
                    print("    " + rname.ljust(18)
                          + "".join(("n/a".rjust(15) if rvals[c] is None
                                     else format(rvals[c], ",.0f").rjust(15)) for c in cols))
        else:
            print("\n  DCF: " + config.MISSING + " (needs positive free cash flow)")

    # ---------------- Score ----------------
    print("\n" + LINE + "\nSCORE\n" + LINE)
    for name, res in score["data_pillars"].items():
        pts = res["points"]
        bar = ("" if pts is None else
               "[" + "#" * int(round((pts / res["max_points"]) * 20)) + "-" *
               (20 - int(round((pts / res["max_points"]) * 20))) + "]")
        print("  " + name.replace("_", " ").ljust(20)
              + (config.MISSING if pts is None
                 else format(pts, "5.1f") + " / " + str(res["max_points"])) + "  " + bar
              + "   (" + str(res["components_scored"]) + "/"
              + str(res["components_total"]) + " components)")
        if res.get("sector_suppressed_components"):
            print("      sector-suppressed: " + ", ".join(res["sector_suppressed_components"]))

    print("\n  Data pillars   : " + format(score["data_points_earned"], ".1f") + " / "
          + format(score["data_points_available"], ".1f") + " available"
          + "  (max possible from filings: " + str(score["data_points_possible"]) + ")")
    if score["judgment_pillars_recorded"]:
        src = "model" if (judgment or {}).get("_model_run") else "analyst"
        print("  Judgment       : " + format(score["judgment_points_earned"], ".1f")
              + "   (written by: " + src + ")")
        if src == "model":
            run = judgment["_model_run"]
            print("                   " + str(len(run["checks_passed"])) + " validation checks "
                  "passed, attempt " + str(run["attempts"]) + ", " + run["at"])
    print("  TOTAL          : " + format(score["total_score"], ".1f")
          + "   -> " + score["verdict_band"])
    print("\n  " + score["interpretation"])

    if score["judgment_pillars_missing"]:
        print("\n" + LINE + "\nEVIDENCE FOR THE PILLARS A SCRIPT CANNOT SCORE\n" + LINE)
        for pillar in score["judgment_pillars_missing"]:
            ev = score["judgment_evidence"][pillar]
            print("\n  " + pillar.upper().replace("_", " ")
                  + "  (" + str(ev["max_points"]) + " points) - NOT SCORED")
            print("    Q: " + ev["question"])
            for k, v in ev["evidence"].items():
                if isinstance(v, float):
                    v = format(v, ".2f")
                print("      " + str(k).ljust(28) + str(v if v is not None else config.MISSING))
            print("    How to judge: " + ev["how_to_judge"])

    if insider:
        s = insider["summary"]
        print("\n" + LINE + "\nINSIDER ACTIVITY (Form 4)\n" + LINE)
        print("  open-market buys : " + str(s["open_market_buys"]) + "  ("
              + fmt(s["buy_value_usd"], "usd") + ")")
        print("  open-market sells: " + str(s["open_market_sells"]) + "  ("
              + fmt(s["sell_value_usd"], "usd") + ")")
        print("  net              : " + fmt(s["net_value_usd"], "usd"))
        for c in insider["caveats"]:
            print("  ! " + c)

    if args.save:
        out = config.FUNDAMENTALS_DIR / (tk + "_analysis.json")
        write_dataset(
            out,
            {"fundamentals": fund, "metrics": m, "score": score,
             "quote": quote, "insider": insider},
            [Provenance(source="SEC EDGAR", source_url=fund["_source_urls"]["companyfacts"],
                        retrieved_at_utc=utcnow_iso(), basis="actual"),
             Provenance(source="Yahoo Finance via yfinance",
                        source_url="https://finance.yahoo.com/quote/" + tk,
                        retrieved_at_utc=utcnow_iso(), basis="market")],
            assumptions=(m.get("_assumptions", []) + [
                "The score is partial unless a --judgment file was supplied.",
                "DCF and reverse-DCF outputs are projections under stated assumptions.",
            ]),
        )
        print("\nsaved: " + str(out.relative_to(config.ROOT)))

    print("\nNot financial advice. This is Phases 2-3 of the CLAUDE.md process; catalysts "
          "(Phase 4)\nand the bear case (Phase 5) still have to be written by hand.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

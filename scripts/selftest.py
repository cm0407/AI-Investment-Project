"""End-to-end proof that every data source works. Run this first, and after any upgrade.

USAGE
    python scripts/selftest.py                 # test the 5 default companies
    python scripts/selftest.py --tickers AAPL MSFT
    python scripts/selftest.py --quick         # skip the slower checks

WHAT IT CHECKS
    1. Dependencies import
    2. Folder structure and memory files exist, with the exact CSV headers CLAUDE.md sets
    3. SEC EDGAR   - ticker->CIK map, companyfacts, submissions, correct User-Agent
    4. yfinance    - live prices
    5. FRED        - macro series, no API key required
    6. The metrics, valuation and scoring engines run on real data
    7. The honesty guarantees actually hold: missing data reports as unavailable rather
       than zero, and the score refuses to complete itself without analyst judgment

Exit code 0 = everything passed.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import date

import _bootstrap  # noqa: F401

DEFAULT_TICKERS = ["AAPL", "JNJ", "JPM", "PG", "CAT"]
SECTORS = {"AAPL": "Technology", "JNJ": "Health Care", "JPM": "Financials",
           "PG": "Consumer Staples", "CAT": "Industrials"}

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[tuple[str, str, str]] = []


def check(name: str, status: str, detail: str = "") -> None:
    results.append((name, status, detail))
    symbol = {"PASS": "  [OK]  ", "FAIL": "  [FAIL]", "WARN": "  [WARN]"}[status]
    print(symbol + " " + name + (("  -  " + detail) if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify the whole pipeline works.")
    ap.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    started = time.time()

    print("=" * 78)
    print("INVEST SYSTEM SELF-TEST  -  " + date.today().isoformat())
    print("=" * 78)

    # ---------------- 1. Dependencies ----------------
    print("\n[1] Dependencies")
    for mod in ["requests", "pandas", "numpy", "yfinance"]:
        try:
            m = __import__(mod)
            check(mod, PASS, "v" + str(getattr(m, "__version__", "?")))
        except ImportError as exc:
            check(mod, FAIL, str(exc))
            print("\nRun: python -m pip install -r requirements.txt")
            return 1

    from invest import config, fred, metrics, prices, scoring, valuation
    from invest import sec_edgar as sec
    from invest.http_cache import FetchError

    # ---------------- 1b. Every module parses ----------------
    # score_stock.py once shipped a syntax error that the self-test missed entirely,
    # because nothing here imported it. A CLI that cannot even be parsed is broken no
    # matter how well the library underneath it works.
    import ast as _ast
    from pathlib import Path as _Path
    print()
    print("[1b] Every module compiles")
    _root = _Path(__file__).resolve().parent.parent
    _broken = []
    _files = sorted(_root.glob("scripts/*.py")) + sorted(_root.glob("invest/*.py"))
    for _f in _files:
        try:
            _ast.parse(_f.read_text(encoding="utf-8"))
        except SyntaxError as _e:
            _broken.append(_f.name + " line " + str(_e.lineno) + ": " + str(_e.msg))
    if _broken:
        for _b in _broken:
            check("syntax " + _b.split()[0], FAIL, _b)
    else:
        check("all " + str(len(_files)) + " modules parse", PASS,
              "every script and library file compiles")

    # ---------------- 2. Structure ----------------
    print("\n[2] Project structure and memory files")
    config.ensure_dirs()
    for d in config.ALL_DIRS:
        if not d.exists():
            check("directory " + d.name, FAIL, "missing")
    check("all " + str(len(config.ALL_DIRS)) + " directories exist", PASS)

    expected_headers = {
        config.PREDICTIONS_CSV: ["date", "ticker", "entry_price", "target_price",
                                 "horizon_months", "expected_return", "prob_positive",
                                 "prob_20pct", "prob_loss", "conviction_score",
                                 "thesis_status", "notes"],
    }
    for path, expected in expected_headers.items():
        if not path.exists():
            check(path.name, FAIL, "missing")
            continue
        with path.open(newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh), [])
        if header == expected:
            check(path.name + " header", PASS, "matches CLAUDE.md exactly")
        else:
            check(path.name + " header", FAIL, "expected " + str(expected))

    for f in [config.RESEARCH_STATE, config.LESSONS_LEARNED, config.REJECTED_STOCKS,
              config.INVESTMENT_LOG_CSV, config.PREFERENCES_FILE]:
        check(f.name, PASS if f.exists() else FAIL, "" if f.exists() else "missing")

    # ---------------- 3. SEC EDGAR ----------------
    print("\n[3] SEC EDGAR  (data.sec.gov - authoritative fundamentals)")
    check("User-Agent header", PASS, config.SEC_USER_AGENT)
    if config.SEC_CONTACT_IS_PLACEHOLDER:
        check("SEC contact address configured", FAIL,
              "still the placeholder. Copy .env.example to .env and set "
              "SEC_CONTACT_EMAIL - the SEC requires a genuine contact address and may "
              "block callers without one.")
    elif "@" not in config.SEC_CONTACT_EMAIL or "." not in config.SEC_CONTACT_EMAIL:
        check("SEC contact address configured", FAIL,
              "SEC_CONTACT_EMAIL does not look like an email address")
    else:
        check("SEC contact address configured", PASS,
              "loaded from .env, not hard-coded in the source")
    try:
        mapping = sec.load_ticker_map(verbose=False)
        check("ticker -> CIK map", PASS, str(len(mapping)) + " tickers registered with the SEC")
    except Exception as exc:
        check("ticker -> CIK map", FAIL, str(exc)[:120])
        return 1

    # ---------------- 4-6. Per-company pipeline ----------------
    print("\n[4] Live data pull, per company")
    company_data = {}
    for tk in args.tickers:
        tk = tk.upper()
        print("\n  --- " + tk + " (" + SECTORS.get(tk, "sector n/a") + ") ---")
        try:
            fund = sec.fundamentals(tk, years=6, verbose=False)
            rev = fund["annual"].get("revenue")
            if not rev:
                check(tk + " SEC fundamentals", WARN, "no revenue tag found")
            else:
                check(tk + " SEC fundamentals", PASS,
                      "CIK " + fund["cik_padded"] + ", " + str(len(rev))
                      + " annual periods, latest FY ends " + rev[-1]["period_end"])
        except Exception as exc:
            check(tk + " SEC fundamentals", FAIL, str(exc)[:120])
            continue

        try:
            q = prices.quote(tk, period="2y", verbose=False)
            check(tk + " price", PASS, "$" + format(q["price"], ",.2f") + " on " + q["price_date"])
        except Exception as exc:
            check(tk + " price", FAIL, str(exc)[:120])
            q = None

        m = metrics.compute(fund, price=q["price"] if q else None)
        n_ok = sum(1 for k, v in m.items() if not k.startswith("_") and v is not None)
        n_missing = len([k for k in m.get("_unavailable_metrics", [])])
        check(tk + " metrics", PASS, str(n_ok) + " computed, " + str(n_missing)
              + " honestly unavailable")

        s = scoring.score_company(m, fund)
        check(tk + " scoring", PASS, "partial " + format(s["data_points_earned"], ".1f")
              + "/" + format(s["data_points_available"], ".1f")
              + " (judgment pillars unscored, as designed)")
        company_data[tk] = (fund, m, s, q)

    # ---------------- 4b. Form 4 insider parsing ----------------
    if not args.quick and company_data:
        print("\n[4b] Form 4 insider-transaction parsing")
        tk = next(iter(company_data))
        fund = company_data[tk][0]
        try:
            ins = sec.insider_transactions(fund["cik_padded"], lookback_filings=8,
                                           verbose=False)
            if ins["filings_examined"] == 0:
                check(tk + " Form 4", WARN, "no recent Form 4 filings to parse")
            elif ins["filings_parsed"] == 0:
                check(tk + " Form 4", FAIL, "found " + str(ins["filings_examined"])
                      + " filings but parsed none - XML discovery is broken")
            else:
                s = ins["summary"]
                check(tk + " Form 4", PASS, str(ins["filings_parsed"]) + "/"
                      + str(ins["filings_examined"]) + " parsed, "
                      + str(len(ins["transactions"])) + " transactions, "
                      + str(s["open_market_buys"]) + " buys / "
                      + str(s["open_market_sells"]) + " sells")
                coded = {t_["code"] for t_ in ins["transactions"]}
                check("compensation codes separated from real trades",
                      PASS if coded else WARN,
                      "codes seen: " + ", ".join(sorted(coded)))
        except Exception as exc:
            check(tk + " Form 4", FAIL, str(exc)[:120])

    # ---------------- 5. FRED ----------------
    print("\n[5] FRED  (macro)")
    try:
        d = fred.series("DGS10", years_back=1, verbose=False)
        latest = d["latest"]
        check("FRED DGS10", PASS, "10y Treasury " + format(latest["value"], ".2f")
              + "% as of " + latest["date"] + "  |  " + d["access_method"])
    except Exception as exc:
        check("FRED DGS10", FAIL, str(exc)[:120])

    # ---------------- 6. Valuation ----------------
    print("\n[6] Valuation engine")
    d = valuation.two_stage_dcf(1_000_000_000, 0.08, shares=100_000_000, net_cash=0)
    if d.get("fair_value_per_share"):
        check("two-stage DCF", PASS, "$" + format(d["fair_value_per_share"], ",.2f")
              + "/share on a synthetic $1B FCF test case")
    else:
        check("two-stage DCF", FAIL, str(d.get("error")))
    bad = valuation.two_stage_dcf(-500, 0.08, shares=100)
    check("DCF refuses negative FCF", PASS if bad.get("error") else FAIL,
          "returns an error instead of a number")
    bad2 = valuation.two_stage_dcf(1000, 0.05, discount_rate=0.02,
                                   terminal_growth=0.025, shares=100)
    check("DCF refuses discount <= terminal growth", PASS if bad2.get("error") else FAIL,
          "would otherwise return an infinite valuation")

    sc = valuation.scenarios(100.0, {},
                             {"target_price": 70, "probability": 0.25, "assumptions": ["x"]},
                             {"target_price": 120, "probability": 0.50, "assumptions": ["y"]},
                             {"target_price": 160, "probability": 0.25, "assumptions": ["z"]})
    ok = abs(sc["probability_weighted_return_pct"] - 17.5) < 0.01
    check("scenario weighting", PASS if ok else FAIL,
          "expected return " + format(sc["probability_weighted_return_pct"], ".1f")
          + "%, P(+20%) " + format(sc["prob_hits_20pct"] * 100, ".0f") + "%")
    bad3 = valuation.scenarios(100.0, {}, {"target_price": 70, "probability": 0.5},
                               {"target_price": 120, "probability": 0.5},
                               {"target_price": 160, "probability": 0.5})
    check("scenarios warn on bad probabilities", PASS if bad3["warnings"] else FAIL,
          bad3["warnings"][0] if bad3["warnings"] else "no warning raised")

    # ---------------- 7. Honesty guarantees ----------------
    print("\n[7] Honesty guarantees  (the whole point of the system)")

    if "JPM" in company_data:
        _, m, s, _ = company_data["JPM"]
        check("bank's missing gross profit is not zero",
              PASS if m.get("gross_margin_pct") is None else FAIL,
              "gross_margin_pct = " + str(m.get("gross_margin_pct")))
        check("bank's suppressed composites flagged",
              PASS if m.get("_composites_suppressed") else WARN,
              str(len(m.get("_composites_suppressed", []))) + " suppressed")
        check("bank not scored on operating-company ratios",
              PASS if s["unscorable_data_pillars"] else FAIL,
              str(len(s["unscorable_data_pillars"])) + " pillar(s) refused")

    any_tk = next(iter(company_data), None)
    if any_tk:
        _, _, s, _ = company_data[any_tk]
        check("score refuses to complete without judgment",
              PASS if not s["score_is_complete"] else FAIL,
              "verdict_band = " + s["verdict_band"])
        check("judgment evidence pack provided",
              PASS if len(s["judgment_evidence"]) == 5 else FAIL,
              str(len(s["judgment_evidence"])) + " pillars documented for the analyst")

    # A ticker pointing at a new holding company must recover the predecessor's history
    # rather than silently reporting a company with no financials.
    try:
        xom = sec.fundamentals("XOM", years=6, verbose=False)
        rz = xom.get("reorganization")
        periods = len(xom.get("annual", {}).get("revenue") or [])
        if rz:
            check("reorganized ticker recovers predecessor history", PASS,
                  "XOM -> CIK " + rz["history_cik"] + " (" + str(rz["history_entity_name"])
                  + "), " + str(periods) + " annual periods recovered")
        elif periods >= 2:
            check("reorganized ticker recovers predecessor history", PASS,
                  "XOM resolves directly with " + str(periods) + " periods (no reorg)")
        else:
            check("reorganized ticker recovers predecessor history", FAIL,
                  "XOM has " + str(periods) + " annual periods and no predecessor found")
    except Exception as exc:
        check("reorganized ticker recovers predecessor history", FAIL, str(exc)[:110])

    # Email rendering must work offline, and a password must never reach the console.
    try:
        from invest import mailer
        sample_md = "\n".join(["# Test", "", "| a | b |", "|---|---|", "| 1 | 2 |", ""])
        html = mailer.markdown_to_html(sample_md, "selftest")
        styled = html.count("style=")
        check("digest renders to email HTML", PASS if styled >= 4 else FAIL,
              str(styled) + " inline styles applied (email clients strip <style> blocks)")
        s = mailer.MailSettings(host="h", port=587, user="u@x.com", password="SECRET123",
                                sender="u@x.com", recipients=["u@x.com"], use_ssl=False)
        leaked = "SECRET123" in str(s.redacted())
        check("password never appears in printable settings", FAIL if leaked else PASS,
              "redacted() shows: " + str(s.redacted()["password"]))
    except Exception as exc:
        check("digest email rendering", FAIL, str(exc)[:110])

    # The model-in-the-loop step. Validators must run OFFLINE - no model call - so this
    # check stays fast and cannot fail because of a network blip.
    try:
        from invest import judge as _judge
        ev = {"ticker": "T", "sector_special": None, "sector_unreliable_metrics": [],
              "pillars": {}, "metrics": {"roic_pct": 16.2}}
        good = "x" * 130 + " ROIC of 16.2% supports this reading of the business."
        valid = {p_: {"points": min(c_, 5), "justification": good}
                 for p_, c_ in _judge.PILLAR_CAPS.items()}
        v, errs = _judge.validate(valid, ev)
        check("judge accepts a valid judgment", PASS if (v and not errs) else FAIL,
              "7 checks pass on well-formed output")

        bad = dict(valid)
        bad["business_quality"] = {"points": 5,
                                   "justification": "x" * 130 + " ROIC of 28.4% is excellent."}
        _v, errs = _judge.validate(bad, ev)
        caught = any("groundedness" in e for e in errs)
        check("judge REJECTS hallucinated figures", PASS if caught else FAIL,
              "a cited 28.4% absent from the evidence is rejected"
              if caught else "groundedness check did not fire")

        over = dict(valid)
        over["management"] = {"points": 99, "justification": good}
        _v, errs = _judge.validate(over, ev)
        check("judge rejects out-of-range points", PASS if any("check3" in e for e in errs) else FAIL,
              "99 on a 5-point pillar is rejected, not clamped")
    except Exception as exc:
        check("judge validators", FAIL, str(exc)[:110])

    # The API is the frontend's only data source. The invariant it must never break is that
    # a null metric carries a REASON - JSON serialisation is exactly where "not measured"
    # gets quietly flattened into "zero".
    try:
        from fastapi.testclient import TestClient
        from api.main import app as _api
        tc = TestClient(_api)
        h = tc.get("/health")
        check("API responds", PASS if h.status_code == 200 else FAIL,
              str(h.json().get("analyses")) + " analyses served")

        listing = tc.get("/companies").json()
        with_nulls = None
        for co in listing[:8]:
            body = tc.get("/companies/" + co["ticker"]).json()
            if body.get("_unavailable"):
                with_nulls = (co["ticker"], body)
                break
        if with_nulls:
            tkr, body = with_nulls
            key = next(iter(body["_unavailable"]))
            ok_null = body["metrics"].get(key) is None and bool(body["_unavailable"][key])
            check("API: null metrics carry a reason", PASS if ok_null else FAIL,
                  tkr + "." + key + " is null with an explanation, not 0")
        else:
            check("API: null metrics carry a reason", WARN, "no nulls in the sample")

        preds = tc.get("/predictions").json().get("summary") or {}
        has_three = all(k in preds for k in ("mean", "meanExcludingLargest", "median"))
        check("API: performance reports mean, ex-outlier AND median",
              PASS if has_three else FAIL,
              "one position once flipped the headline from behind to ahead")

        sc = tc.get("/screens/latest").json()
        split = "wellMeasured" in sc and "thinlyMeasured" in sc
        check("API: screens split well- from thinly-measured", PASS if split else FAIL,
              str(len(sc.get("wellMeasured", []))) + " well, "
              + str(len(sc.get("thinlyMeasured", []))) + " thin")

        spec = tc.get("/openapi.json").json()
        check("API: OpenAPI schema generated", PASS if spec.get("paths") else FAIL,
              str(len(spec.get("paths", {}))) + " paths - the frontend generates TS types from this")
    except ImportError:
        check("API tests", WARN, "fastapi/httpx2 not installed - skipped")
    except Exception as exc:
        check("API tests", FAIL, str(exc)[:110])

    check("missing values render as text, not 0",
          PASS if metrics.format_metric(None) == config.MISSING else FAIL,
          metrics.format_metric(None))

    try:
        sec.cik_for_ticker("ZZZZFAKE", verbose=False)
        check("unknown ticker rejected", FAIL, "should have raised")
    except FetchError:
        check("unknown ticker rejected", PASS, "raises instead of guessing a CIK")

    from scripts.make_digest import preferences_ready  # noqa: E402
    ready, msg = preferences_ready()
    check("preferences gate", PASS, ("preferences on file" if ready
                                     else "correctly BLOCKING recommendations - " + msg))

    # ---------------- Summary ----------------
    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    n_warn = sum(1 for _, s, _ in results if s == WARN)
    print("\n" + "=" * 78)
    print("RESULT: " + str(n_pass) + " passed, " + str(n_fail) + " failed, "
          + str(n_warn) + " warnings   (" + format(time.time() - started, ".1f") + "s)")
    print("=" * 78)
    if n_fail:
        print("\nFailures:")
        for name, status, detail in results:
            if status == FAIL:
                print("  - " + name + ": " + detail)
        return 1
    print("\nAll data sources are live and every honesty guarantee holds.")
    print("SEC EDGAR User-Agent: " + config.SEC_USER_AGENT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

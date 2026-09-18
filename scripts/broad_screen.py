"""Phase 1 done properly: a market-wide scan using SEC's bulk XBRL frames API.

WHY THIS EXISTS
    The starter universe is 184 hand-picked large caps. `memory/lessons_learned.md` records
    the problem with that: "A curated ticker list is a convenience, not a market scan. Any
    'best idea found' that comes out of a curated list must state the universe it was drawn
    from and the bias that universe carries."

    Screening ~10,000 companies one at a time needs one multi-megabyte download each - hours
    of runtime. The frames endpoint returns ONE concept for EVERY filer in a single request:

        https://data.sec.gov/api/xbrl/frames/us-gaap/Revenues/USD/CY2025.json   -> 2,228 filers

    So a genuinely broad, unbiased first pass costs about a dozen requests instead of ten
    thousand. Companies are then ranked on fundamentals alone, and only the survivors get the
    expensive per-company treatment.

USAGE
    python scripts/broad_screen.py
    python scripts/broad_screen.py --year 2025 --top 40
    python scripts/broad_screen.py --refresh

THE GROWTH WINDOW IS DELIBERATE
    Growth is measured CY2022 -> CY2025, a three-year window. Six-year windows start in 2020
    and measure recovery from the pandemic trough rather than growth - the error that made
    EOG look like a 15.5%-a-year grower while its revenue was actually falling 4.2% a year.

KNOWN LIMITS
    * Frames assign an off-calendar fiscal year to the nearest calendar frame, so a company
      with a June year-end is compared slightly out of step. Fine for triage, not for a thesis.
    * Only companies that file the specific tags appear. Banks and insurers are sparse here
      by nature, as are foreign issuers filing 20-F without full XBRL.
    * This stage uses NO price data. It ranks business quality and growth only; valuation
      enters at stage two.
"""

from __future__ import annotations

import argparse
import csv
import json
from typing import Optional

import _bootstrap  # noqa: F401
from invest import config
from invest.http_cache import fetch_json, FetchError

FRAMES = "https://data.sec.gov/api/xbrl/frames"

_FETCH = dict(
    cache_dir=config.SEC_CACHE,
    ttl_hours=168.0,
    headers=config.SEC_HEADERS,
    rate_key="sec",
    rate=config.SEC_MAX_REQUESTS_PER_SECOND,
    timeout=120,
    max_retries=config.SEC_MAX_RETRIES,
    source_name="SEC EDGAR XBRL frames",
    basis="actual",
)


def frame(taxonomy: str, tag: str, unit: str, period: str,
          refresh: bool = False, verbose: bool = True) -> dict[int, dict]:
    """One concept for every filer in a period, keyed by CIK."""
    url = FRAMES + "/" + taxonomy + "/" + tag + "/" + unit + "/" + period + ".json"
    try:
        payload, _ = fetch_json(url, refresh=refresh, verbose=verbose, **_FETCH)
    except FetchError:
        if verbose:
            print("    [frames] no data for " + tag + " " + period)
        return {}
    out: dict[int, dict] = {}
    for row in payload.get("data", []):
        out[int(row["cik"])] = {"val": float(row["val"]), "name": row.get("entityName", ""),
                                "end": row.get("end"), "form": row.get("form")}
    if verbose:
        print("    [frames] " + tag.ljust(52) + period + "  " + str(len(out)) + " filers")
    return out


def merge_revenue(year: int, refresh: bool, verbose: bool) -> dict[int, dict]:
    """Total revenue across both common tags, taking the LARGER where both exist.

    `Revenues` is the total top line. `RevenueFromContractWithCustomerExcludingAssessedTax`
    is the ASC 606 component, which equals the total for most operating companies but NOT
    for lessors, financials or anyone with substantial non-contract revenue.

    Air Lease is the worked example: it files $0.33B under the contract tag and $3.02B under
    `Revenues`, because almost all of its income is aircraft lease revenue rather than
    contracts with customers. Preferring the contract tag understated revenue ninefold and
    produced a 329% net margin and a 452% free-cash-flow margin - impossible figures that
    still ranked the company 20th. Taking the larger value is the correct default: a
    component can never exceed the total.
    """
    period = "CY" + str(year)
    combined: dict[int, dict] = {}
    for tag in ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"):
        for cik, row in frame("us-gaap", tag, "USD", period, refresh, verbose).items():
            prev = combined.get(cik)
            if prev is None or row["val"] > prev["val"]:
                combined[cik] = row
    return combined


def _ratio(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    return num / den


def _cagr(first: Optional[float], last: Optional[float], years: int) -> Optional[float]:
    if first is None or last is None or first <= 0 or last <= 0:
        return None
    return ((last / first) ** (1.0 / years) - 1.0) * 100.0


def main() -> int:
    ap = argparse.ArgumentParser(description="Market-wide fundamental scan via SEC frames.")
    ap.add_argument("--year", type=int, default=2025, help="latest complete calendar year")
    ap.add_argument("--lookback", type=int, default=3, help="growth window in years")
    ap.add_argument("--top", type=int, default=40, help="candidates to carry to stage two")
    ap.add_argument("--min-revenue", type=float, default=300e6,
                    help="minimum latest-year revenue (default $300M)")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    config.ensure_dirs()
    verbose = not args.quiet
    y_now, y_then = args.year, args.year - args.lookback
    qi = "CY" + str(args.year) + "Q4I"          # instant frame, year end

    print("MARKET-WIDE SCAN via SEC XBRL frames")
    print("Growth window: CY" + str(y_then) + " -> CY" + str(y_now)
          + " (" + str(args.lookback) + " years, chosen to avoid the 2020 pandemic base)")
    print()

    rev_now = merge_revenue(y_now, args.refresh, verbose)
    rev_then = merge_revenue(y_then, args.refresh, verbose)
    ni_now = frame("us-gaap", "NetIncomeLoss", "USD", "CY" + str(y_now), args.refresh, verbose)
    ni_then = frame("us-gaap", "NetIncomeLoss", "USD", "CY" + str(y_then), args.refresh, verbose)
    ocf = frame("us-gaap", "NetCashProvidedByUsedInOperatingActivities", "USD",
                "CY" + str(y_now), args.refresh, verbose)
    capex = frame("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment", "USD",
                  "CY" + str(y_now), args.refresh, verbose)
    op_inc = frame("us-gaap", "OperatingIncomeLoss", "USD", "CY" + str(y_now),
                   args.refresh, verbose)
    equity = frame("us-gaap", "StockholdersEquity", "USD", qi, args.refresh, verbose)
    assets = frame("us-gaap", "Assets", "USD", qi, args.refresh, verbose)
    liabs = frame("us-gaap", "Liabilities", "USD", qi, args.refresh, verbose)
    shares = frame("dei", "EntityCommonStockSharesOutstanding", "shares", qi,
                   args.refresh, verbose)

    print()
    print("Universe reporting revenue in CY" + str(y_now) + ": "
          + str(len(rev_now)) + " companies")

    rows: list[dict] = []
    for cik, r in rev_now.items():
        revenue = r["val"]
        if revenue < args.min_revenue:
            continue
        rev0 = (rev_then.get(cik) or {}).get("val")
        ni1 = (ni_now.get(cik) or {}).get("val")
        ni0 = (ni_then.get(cik) or {}).get("val")
        o = (ocf.get(cik) or {}).get("val")
        cx = (capex.get(cik) or {}).get("val")
        oi = (op_inc.get(cik) or {}).get("val")
        eq = (equity.get(cik) or {}).get("val")
        ta = (assets.get(cik) or {}).get("val")
        tl = (liabs.get(cik) or {}).get("val")
        sh = (shares.get(cik) or {}).get("val")

        fcf = (o - abs(cx)) if (o is not None and cx is not None) else None

        rows.append({
            "cik": cik,
            "cik_padded": str(cik).zfill(10),
            "name": r["name"],
            "period_end": r.get("end"),
            "revenue": revenue,
            "revenue_3y_ago": rev0,
            "revenue_cagr_pct": _cagr(rev0, revenue, args.lookback),
            "net_income": ni1,
            "net_income_cagr_pct": _cagr(ni0, ni1, args.lookback),
            "operating_income": oi,
            "operating_margin_pct": (_ratio(oi, revenue) or 0) * 100 if oi is not None else None,
            "net_margin_pct": (_ratio(ni1, revenue) or 0) * 100 if ni1 is not None else None,
            "ocf": o,
            "fcf": fcf,
            "fcf_margin_pct": (_ratio(fcf, revenue) or 0) * 100 if fcf is not None else None,
            "ocf_to_net_income": _ratio(o, ni1) if (ni1 and ni1 > 0) else None,
            "equity": eq,
            "roe_pct": (_ratio(ni1, eq) or 0) * 100 if (ni1 is not None and eq and eq > 0) else None,
            "liabilities_to_assets": _ratio(tl, ta),
            "shares_outstanding": sh,
        })

    print("Above the $" + format(args.min_revenue / 1e6, ",.0f") + "M revenue floor: "
          + str(len(rows)))

    # ---- Quality + growth filter. Deliberately NO price data at this stage. ----------
    def keeps(x: dict) -> tuple[bool, str]:
        if x["revenue_cagr_pct"] is None:
            return False, "no comparable revenue " + str(y_then)
        if x["net_income"] is None or x["net_income"] <= 0:
            return False, "not profitable"
        if x["fcf"] is None:
            return False, "free cash flow not computable"
        if x["fcf"] <= 0:
            return False, "negative free cash flow"
        # Impossible ratios indicate a tag mismatch, not an extraordinary company.
        if x["net_margin_pct"] is not None and x["net_margin_pct"] > 100.0:
            return False, ("net margin of " + format(x["net_margin_pct"], ".0f")
                           + "% is impossible - revenue tag mismatch")
        if x["fcf_margin_pct"] is not None and x["fcf_margin_pct"] > 100.0:
            return False, ("FCF margin of " + format(x["fcf_margin_pct"], ".0f")
                           + "% is impossible - revenue tag mismatch")
        # A CAGR off a near-zero base is arithmetic, not a growth rate. CorMedix went from
        # $0.1M to $311.7M of revenue: a real commercialisation ramp, but 1,583% a year
        # describes a product launch, not a business trend worth ranking on.
        if x["revenue_3y_ago"] is not None and x["revenue_3y_ago"] < 25e6:
            return False, ("growth measured from a negligible base ($"
                           + format(x["revenue_3y_ago"] / 1e6, ".1f") + "M) - not a trend")
        # PROFIT MUST KEEP PACE WITH REVENUE.
        # The composite weights revenue growth at 30% and nothing checked whether profit
        # followed. That put Harmony Biosciences top of the screen at 95.9% - revenue up
        # 98% over three years while net income FELL 13% - and Doximity second, with
        # operating and net income both down in the latest year. Revenue growing while
        # profit stalls is the signature of discounting, cost inflation or an acquisition
        # spree, and it is precisely what `lessons_learned.md` already warned about under
        # "Read the profit line, not the per-share line".
        if x["net_income_cagr_pct"] is not None and x["revenue_cagr_pct"] is not None:
            gap = x["revenue_cagr_pct"] - x["net_income_cagr_pct"]
            if gap > 10.0:
                return False, ("revenue growing " + format(x["revenue_cagr_pct"], ".0f")
                               + "%/yr but profit only "
                               + format(x["net_income_cagr_pct"], ".0f")
                               + "%/yr - profit is not keeping pace with sales")
        if x["revenue_cagr_pct"] < 5.0:
            return False, "revenue CAGR below 5%"
        if x["net_margin_pct"] is None or x["net_margin_pct"] < 5.0:
            return False, "net margin below 5%"
        if x["fcf_margin_pct"] is None or x["fcf_margin_pct"] < 5.0:
            return False, "FCF margin below 5%"
        if x["ocf_to_net_income"] is not None and x["ocf_to_net_income"] < 0.8:
            return False, "cash conversion below 0.8x - earnings quality flag"
        if x["liabilities_to_assets"] is not None and x["liabilities_to_assets"] > 0.80:
            return False, "liabilities above 80% of assets"
        if x["roe_pct"] is not None and x["roe_pct"] < 10.0:
            return False, "ROE below 10%"
        return True, "passed"

    survivors, rejected = [], []
    for x in rows:
        ok, why = keeps(x)
        x["stage1_result"] = why
        (survivors if ok else rejected).append(x)

    print("Passed the quality + growth filter: " + str(len(survivors)))
    print()

    # Composite of growth and quality only. Valuation is applied at stage two.
    def composite(x: dict) -> float:
        def band(v, lo, hi):
            if v is None:
                return 0.0
            return max(0.0, min(1.0, (v - lo) / (hi - lo)))
        return (band(x["revenue_cagr_pct"], 5, 30) * 30
                + band(x["fcf_margin_pct"], 5, 30) * 25
                + band(x["net_margin_pct"], 5, 25) * 20
                + band(x["roe_pct"], 10, 40) * 15
                + band(x["net_income_cagr_pct"], 0, 30) * 10)

    for x in survivors:
        x["stage1_score"] = round(composite(x), 1)
    survivors.sort(key=lambda x: -x["stage1_score"])

    out = config.SCREENS_DIR / ("broad_screen_CY" + str(y_now) + ".csv")
    fields = sorted({k for x in survivors for k in x})
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(survivors)

    print("=" * 104)
    print("TOP " + str(args.top) + " BY STAGE-1 COMPOSITE (growth + quality; no valuation yet)")
    print("=" * 104)
    print("  #  CIK         COMPANY".ljust(48) + "SCORE  REV CAGR  NET MGN  FCF MGN    ROE   REVENUE")
    print("-" * 104)
    for i, x in enumerate(survivors[:args.top], 1):
        def f(v, w=7, d=1):
            return ("n/a".rjust(w) if v is None else format(v, "." + str(d) + "f").rjust(w))
        print("  " + str(i).rjust(2) + " " + x["cik_padded"] + "  "
              + x["name"][:26].ljust(28)
              + format(x["stage1_score"], "5.1f") + "  " + f(x["revenue_cagr_pct"], 7)
              + "%  " + f(x["net_margin_pct"], 6) + "%  " + f(x["fcf_margin_pct"], 6) + "%  "
              + f(x["roe_pct"], 5) + "%  $" + format(x["revenue"] / 1e9, ">6.1f") + "B")
    print("-" * 104)
    print("\nsaved: " + str(out.relative_to(config.ROOT)))
    print("\nThis is a fundamentals-only triage across every SEC filer that reports the")
    print("required tags - NOT a curated list. Valuation, preferences and the full")
    print("five-phase process are applied to the survivors at stage two.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

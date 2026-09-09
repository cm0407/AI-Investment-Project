"""Derived financial metrics, computed from SEC-filed figures only.

Every function here follows one rule: if an input is missing, the output is None, which
renders downstream as "DATA UNAVAILABLE OR UNVERIFIED". Nothing is imputed, defaulted to
zero, or carried forward from a prior year. A missing gross margin for a bank is
information; a fabricated 0% gross margin is a lie that will propagate into a score.

Formulas are documented inline because a metric you cannot reproduce by hand is a metric
you cannot argue with.
"""

from __future__ import annotations

from typing import Any, Optional

from . import config
from .sec_edgar import DURATION_CONCEPTS, INSTANT_CONCEPTS

# The first (preferred) tag for each concept. When the resolved tag differs, a fallback
# was used and the substitution is surfaced rather than hidden.
DURATION_TAG_PRIMARY = {k: v[0] for k, v in DURATION_CONCEPTS.items() if v}
INSTANT_TAG_PRIMARY = {k: v[0] for k, v in INSTANT_CONCEPTS.items() if v}


def _v(series: list[dict] | None, idx: int = -1) -> Optional[float]:
    """Value at index of an annual series (default: most recent). None if absent."""
    if not series:
        return None
    try:
        return float(series[idx]["value"])
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def _safe_div(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    return num / den


def _pct(x: Optional[float]) -> Optional[float]:
    return None if x is None else x * 100.0


def cagr(first: Optional[float], last: Optional[float], years: float) -> Optional[float]:
    """Compound annual growth rate, in percent.

    Undefined when the starting value is negative or zero - you cannot compound out of a
    loss in a way that means anything. We return None rather than a nonsense number.
    """
    if first is None or last is None or years <= 0 or first <= 0 or last <= 0:
        return None
    return ((last / first) ** (1.0 / years) - 1.0) * 100.0


def yoy_growth(series: list[dict] | None) -> list[Optional[float]]:
    """Year-over-year % change for each consecutive pair in an annual series."""
    if not series or len(series) < 2:
        return []
    out: list[Optional[float]] = []
    for prev, cur in zip(series, series[1:]):
        p, c = _v([prev]), _v([cur])
        out.append(((c / p - 1.0) * 100.0) if (p and c and p > 0) else None)
    return out


# SIC code ranges where the standard operating-company yardsticks simply do not apply.
# Source: SEC Division of Corporation Finance SIC code list.
_SPECIAL_SECTORS = [
    # A bank's operating cash flow swings by hundreds of billions as its loan and trading
    # books move; it says nothing about earnings quality the way it does for a retailer.
    ((6000, 6199), "banking/credit",
     ["debt_to_equity", "current_ratio", "net_debt_to_ebitda", "cash_to_debt",
      "roic_pct", "fcf_margin_pct", "capex_to_revenue_pct", "interest_coverage",
      "ocf_to_net_income", "fcf_latest", "fcf_cagr_pct", "pfcf_ratio", "fcf_yield_pct",
      "ev_ebitda", "enterprise_value"]),
    ((6200, 6299), "brokerage/exchanges",
     ["debt_to_equity", "current_ratio", "net_debt_to_ebitda", "roic_pct",
      "ocf_to_net_income", "ev_ebitda", "fcf_margin_pct", "fcf_latest", "fcf_cagr_pct", "pfcf_ratio", "fcf_yield_pct"]),
    ((6300, 6499), "insurance",
     ["debt_to_equity", "current_ratio", "net_debt_to_ebitda", "roic_pct",
      "capex_to_revenue_pct", "ocf_to_net_income", "ev_ebitda", "fcf_margin_pct", "fcf_latest", "fcf_cagr_pct", "pfcf_ratio", "fcf_yield_pct"]),
    ((6500, 6599), "real estate",
     ["debt_to_equity", "net_debt_to_ebitda", "pe_ratio", "fcf_margin_pct", "fcf_latest", "fcf_cagr_pct", "pfcf_ratio", "fcf_yield_pct"]),
    ((6798, 6798), "REIT",
     ["debt_to_equity", "net_debt_to_ebitda", "pe_ratio", "fcf_margin_pct", "fcf_latest", "fcf_cagr_pct", "pfcf_ratio", "fcf_yield_pct"]),
    ((4900, 4999), "utilities",
     ["debt_to_equity", "net_debt_to_ebitda", "fcf_margin_pct", "capex_to_revenue_pct"]),
]


def classify_sector(sic: Optional[str | int]) -> dict:
    """Flag industries where the standard ratios mislead rather than inform.

    A bank with debt/equity of 10x is not distressed - borrowing is its raw material.
    A REIT's P/E looks awful because depreciation swamps GAAP earnings. Ranking these
    companies against an industrial on the same yardstick produces confident nonsense,
    so the metrics are computed but marked not-meaningful.
    """
    try:
        code = int(sic)
    except (TypeError, ValueError):
        return {"special": False, "kind": None, "unreliable_metrics": []}
    for (lo, hi), kind, unreliable in _SPECIAL_SECTORS:
        if lo <= code <= hi:
            return {"special": True, "kind": kind, "sic": code,
                    "unreliable_metrics": unreliable,
                    "note": ("SIC " + str(code) + " (" + kind + "): the metrics listed in "
                             "unreliable_metrics are computed but are NOT comparable with "
                             "an ordinary operating company. Judge this business on "
                             "sector-appropriate measures instead.")}
    return {"special": False, "kind": None, "unreliable_metrics": []}


def compute(fund: dict, price: Optional[float] = None) -> dict:
    """Turn a sec_edgar.fundamentals() record into the metric set the system scores on.

    Args:
        fund:  output of sec_edgar.fundamentals()
        price: current market price (from prices.quote). Optional - without it, the
               valuation multiples are simply reported as unavailable.
    """
    a = dict(fund.get("annual", {}))

    # Refuse to treat an abandoned XBRL tag's last value as a current figure. sec_edgar
    # flags any concept that has not been updated in ~13 months relative to the newest
    # fiscal period; using JPMorgan's 2018 cash balance as "cash today" would poison net
    # cash, enterprise value and every multiple built on it.
    stale = fund.get("concepts_stale") or {}
    stale_excluded: list[str] = []
    for concept, detail in stale.items():
        if concept in a:
            del a[concept]
            stale_excluded.append(
                concept + " (last reported " + str(detail.get("latest_period_end"))
                + ", " + str(detail.get("days_behind")) + " days behind the newest period)"
            )

    rev = a.get("revenue")
    gp = a.get("gross_profit")
    op = a.get("operating_income")
    ni = a.get("net_income")
    ocf = a.get("operating_cash_flow")
    capex = a.get("capex")
    tax = a.get("income_tax")
    pretax = a.get("pretax_income")
    eps = a.get("eps_diluted")
    cash = a.get("cash")
    sti = a.get("short_term_investments")
    ltd = a.get("long_term_debt")
    std = a.get("short_term_debt")
    eq = a.get("equity")
    assets = a.get("total_assets")
    cur_assets = a.get("current_assets")
    cur_liab = a.get("current_liabilities")
    liab = a.get("total_liabilities")
    dilshares = a.get("shares_diluted_wa")
    buybacks = a.get("buybacks")
    divs = a.get("dividends_paid")
    interest = a.get("interest_expense")
    da = a.get("depreciation_amortization")
    goodwill = a.get("goodwill")

    latest_rev, latest_ni, latest_op = _v(rev), _v(ni), _v(op)
    latest_ocf, latest_capex = _v(ocf), _v(capex)
    latest_eq, latest_assets = _v(eq), _v(assets)

    # ---- Free cash flow -------------------------------------------------------------
    # FCF = cash from operations - capital expenditure.
    # If a company reports no capex tag (common for banks/insurers), FCF is left
    # undefined rather than silently set equal to operating cash flow.
    fcf_series: list[dict] = []
    if ocf and capex:
        capex_by_end = {c["period_end"]: c["value"] for c in capex}
        for o in ocf:
            cx = capex_by_end.get(o["period_end"])
            if cx is not None:
                fcf_series.append({
                    "period_end": o["period_end"],
                    "value": o["value"] - abs(cx),  # capex is filed as a positive outflow
                    "concept": "free_cash_flow",
                })
    latest_fcf = _v(fcf_series)

    # ---- Balance sheet aggregates ---------------------------------------------------
    # A composite (total debt = long-term + short-term) is only trustworthy when no
    # component is KNOWN to be missing. If a company reported long-term debt for years
    # and then stopped tagging it, summing what is left understates the total and every
    # figure built on it - net cash, enterprise value, ROIC - is quietly wrong rather
    # than honestly absent. JPMorgan is the live example: its LongTermDebt tag stops in
    # 2013, so a naive sum drops several hundred billion dollars of debt and produces an
    # ROIC near 70% for a bank that earns nothing like that.
    stale_names = set(stale.keys())
    suppressed: list[str] = []

    def _composite(parts: list[tuple[str, list[dict] | None]], label: str) -> Optional[float]:
        dropped = [name for name, _ in parts if name in stale_names]
        if dropped:
            suppressed.append(
                label + " suppressed: component(s) " + ", ".join(dropped)
                + " were reported historically but are no longer tagged, so any sum would "
                "understate the true figure."
            )
            return None
        vals = [_v(series) for _, series in parts]
        if all(v is None for v in vals):
            return None
        return sum(v or 0.0 for v in vals)

    total_debt = _composite([("long_term_debt", ltd), ("short_term_debt", std)], "total_debt")
    total_cash = _composite([("cash", cash), ("short_term_investments", sti)],
                            "total_cash_and_sti")
    net_cash = (total_cash - total_debt) if (total_cash is not None and total_debt is not None) else None

    # ---- Effective tax rate & NOPAT --------------------------------------------------
    eff_tax = _safe_div(_v(tax), _v(pretax))
    if eff_tax is not None and not (0.0 <= eff_tax <= 0.60):
        eff_tax = None  # a wild rate means an unusual year; refuse to build ROIC on it
    nopat = None
    if latest_op is not None and eff_tax is not None:
        nopat = latest_op * (1.0 - eff_tax)

    # ---- Invested capital ------------------------------------------------------------
    # Invested capital = total debt + shareholders' equity - cash & equivalents.
    # ASSUMPTION: excess cash is not "invested" in operations. Defensible, and it is the
    # most common convention, but it flatters cash-rich companies' ROIC. Stated openly.
    # All three inputs must be genuinely known. Treating a suppressed cash balance as
    # zero would inflate invested capital; treating suppressed debt as zero deflates it.
    invested_capital = None
    if latest_eq is not None and total_debt is not None and total_cash is not None:
        invested_capital = latest_eq + total_debt - total_cash
        if invested_capital <= 0:
            invested_capital = None  # negative invested capital makes ROIC meaningless

    n_years = len(rev) if rev else 0
    span = max(n_years - 1, 0)

    metrics: dict[str, Any] = {
        # ---------- Scale ----------
        "revenue_latest": latest_rev,
        "revenue_period": rev[-1]["period_end"] if rev else None,
        "net_income_latest": latest_ni,
        "operating_income_latest": latest_op,
        "fcf_latest": latest_fcf,
        "eps_diluted_latest": _v(eps),
        "total_assets": latest_assets,
        "total_equity": latest_eq,
        "total_debt": total_debt,
        "total_cash_and_sti": total_cash,
        "net_cash_position": net_cash,
        "goodwill": _v(goodwill),

        # ---------- Growth (%) ----------
        "revenue_cagr_pct": cagr(_v(rev, 0), latest_rev, span),
        "net_income_cagr_pct": cagr(_v(ni, 0), latest_ni, span),
        "fcf_cagr_pct": cagr(_v(fcf_series, 0), latest_fcf, max(len(fcf_series) - 1, 0)),
        "eps_cagr_pct": cagr(_v(eps, 0), _v(eps), max(len(eps) - 1, 0) if eps else 0),
        "revenue_growth_yoy_pct": yoy_growth(rev),
        "net_income_growth_yoy_pct": yoy_growth(ni),
        "revenue_growth_latest_pct": (yoy_growth(rev)[-1] if len(yoy_growth(rev)) else None),
        "growth_years_covered": span,

        # A CAGR is only as honest as the year it starts from. Booking Holdings' 2020
        # revenue was the COVID travel trough ($6.8B), so a six-year CAGR reads 31.7%
        # while the last two years grew 11% and 13%. EOG's 2020 was the oil-price crash,
        # giving a +15.5% CAGR over three consecutive years of DECLINING revenue.
        # The recent-3-year CAGR is computed alongside so the distortion is visible.
        "revenue_cagr_3y_pct": cagr(_v(rev, -4), latest_rev, 3) if (rev and len(rev) >= 4) else None,
        "net_income_cagr_3y_pct": cagr(_v(ni, -4), latest_ni, 3) if (ni and len(ni) >= 4) else None,

        # ---------- Margins (%) ----------
        "gross_margin_pct": _pct(_safe_div(_v(gp), latest_rev)),
        "operating_margin_pct": _pct(_safe_div(latest_op, latest_rev)),
        "net_margin_pct": _pct(_safe_div(latest_ni, latest_rev)),
        "fcf_margin_pct": _pct(_safe_div(latest_fcf, latest_rev)),

        # ---------- Returns (%) ----------
        "roe_pct": _pct(_safe_div(latest_ni, latest_eq)),
        "roa_pct": _pct(_safe_div(latest_ni, latest_assets)),
        "roic_pct": _pct(_safe_div(nopat, invested_capital)),
        "effective_tax_rate_pct": _pct(eff_tax),
        "nopat": nopat,
        "invested_capital": invested_capital,

        # ---------- Balance sheet health ----------
        "debt_to_equity": _safe_div(total_debt, latest_eq),
        "net_debt_to_ebitda": None,  # filled below when D&A is available
        "current_ratio": _safe_div(_v(cur_assets), _v(cur_liab)),
        "liabilities_to_assets": _safe_div(_v(liab), latest_assets),
        "interest_coverage": _safe_div(latest_op, abs(_v(interest)) if _v(interest) else None),
        "cash_to_debt": _safe_div(total_cash, total_debt),

        # ---------- Cash quality ----------
        "ocf_to_net_income": _safe_div(latest_ocf, latest_ni),
        "capex_to_revenue_pct": _pct(_safe_div(abs(latest_capex) if latest_capex else None,
                                               latest_rev)),

        # ---------- Shareholder flows ----------
        "buybacks_latest": _v(buybacks),
        "dividends_paid_latest": _v(divs),
        "shares_diluted_wa_latest": _v(dilshares),
        "share_count_change_pct": (
            ((_v(dilshares) / _v(dilshares, 0) - 1.0) * 100.0)
            if (_v(dilshares) and _v(dilshares, 0)) else None
        ),
    }

    # EBITDA = operating income + depreciation & amortization (a proxy, not a GAAP figure)
    ebitda = None
    if latest_op is not None and _v(da) is not None:
        ebitda = latest_op + _v(da)
        metrics["ebitda_proxy"] = ebitda
        if total_debt is not None and total_cash is not None and ebitda > 0:
            metrics["net_debt_to_ebitda"] = (total_debt - total_cash) / ebitda
    else:
        metrics["ebitda_proxy"] = None

    # ---- Valuation multiples (need a market price) -----------------------------------
    shares_fact = fund.get("shares_outstanding_latest")
    shares = float(shares_fact["value"]) if shares_fact else None
    metrics["shares_outstanding"] = shares
    metrics["shares_outstanding_asof"] = shares_fact["period_end"] if shares_fact else None

    if price is not None and shares:
        mcap = price * shares
        ev = None
        if total_debt is not None and total_cash is not None:
            ev = mcap + total_debt - total_cash
        metrics.update({
            "price": price,
            "market_cap": mcap,
            "enterprise_value": ev,
            "pe_ratio": _safe_div(mcap, latest_ni) if (latest_ni and latest_ni > 0) else None,
            "ps_ratio": _safe_div(mcap, latest_rev),
            "pfcf_ratio": _safe_div(mcap, latest_fcf) if (latest_fcf and latest_fcf > 0) else None,
            "pb_ratio": _safe_div(mcap, latest_eq) if (latest_eq and latest_eq > 0) else None,
            "ev_ebitda": _safe_div(ev, ebitda) if (ebitda and ebitda > 0) else None,
            "ev_sales": _safe_div(ev, latest_rev),
            "fcf_yield_pct": _pct(_safe_div(latest_fcf, mcap)),
            "earnings_yield_pct": _pct(_safe_div(latest_ni, mcap)),
        })
        # PEG = P/E divided by earnings growth rate. Only meaningful with positive growth.
        pe = metrics.get("pe_ratio")
        g = metrics.get("net_income_cagr_pct")
        metrics["peg_ratio"] = (pe / g) if (pe and g and g > 0) else None
    else:
        for k in ["price", "market_cap", "enterprise_value", "pe_ratio", "ps_ratio",
                  "pfcf_ratio", "pb_ratio", "ev_ebitda", "ev_sales", "fcf_yield_pct",
                  "earnings_yield_pct", "peg_ratio"]:
            metrics[k] = None

    # ---- Honest accounting of what is missing and why ---------------------------------
    # ---- Which XBRL tag actually produced each headline figure -----------------------
    # A concept can resolve to a fallback tag that is close but not identical in meaning.
    # Johnson & Johnson stopped tagging OperatingIncomeLoss in 2014, so "operating income"
    # falls back to pre-tax income, which includes non-operating items and therefore
    # overstates the true operating margin. That substitution must be visible, not buried.
    primary_tag = {**DURATION_TAG_PRIMARY, **INSTANT_TAG_PRIMARY}
    tags_used: dict[str, dict] = {}
    for concept, rows in a.items():
        if not rows:
            continue
        tag = rows[-1].get("tag")
        entry = {"tag_used": tag, "period_end": rows[-1].get("period_end")}
        expected = primary_tag.get(concept)
        if expected and tag != expected:
            entry["fallback"] = True
            entry["preferred_tag"] = expected
            entry["caution"] = ("This company does not report '" + expected + "'. The "
                                "figure comes from '" + str(tag) + "' instead, which may "
                                "not mean exactly the same thing.")
        tags_used[concept] = entry

    # Flag a CAGR whose starting year makes it misleading.
    base_warn = None
    full_c, recent_c = metrics.get("revenue_cagr_pct"), metrics.get("revenue_cagr_3y_pct")
    if full_c is not None and recent_c is not None and (full_c - recent_c) >= 5.0:
        base_warn = (
            "BASE-YEAR DISTORTION: the " + str(span) + "-year revenue CAGR of "
            + format(full_c, ".1f") + "% is far above the recent 3-year CAGR of "
            + format(recent_c, ".1f") + "%. The window starts at "
            + (rev[0]["period_end"][:4] if rev else "?")
            + ", so the long CAGR is measuring recovery from a depressed base, not "
            "underlying growth. Judge this company on the recent figure and the "
            "year-by-year series, not the headline CAGR."
        )
    metrics["_growth_base_warning"] = base_warn

    # Detect a stock split that historical per-share figures do not reflect.
    # Booking Holdings files 751m shares on its latest cover page while the diluted
    # weighted-average count in the same filings reads 33m - a ~23x gap from a split.
    # Its filed EPS of $165.57 therefore sits on a pre-split share base and CANNOT be
    # compared with a $180 market price. Ratios built on market cap / net income are
    # unaffected (both sides scale), but anything per-share is not.
    split_warn = None
    wa = _v(dilshares)
    if shares and wa and wa > 0:
        ratio = shares / wa
        if ratio > 1.5 or ratio < 0.67:
            split_warn = (
                "PER-SHARE FIGURES ARE NOT COMPARABLE WITH TODAY'S PRICE: the latest cover-"
                "page share count (" + format(shares, ",.0f") + ") is "
                + format(ratio, ".1f") + "x the diluted weighted-average count in the "
                "filings (" + format(wa, ",.0f") + "). That gap indicates a stock split "
                "or major issuance not reflected in the historical per-share series. "
                "Reported EPS and any per-share history are on the OLD share base. "
                "Whole-company ratios (P/E from market cap over net income, P/FCF, "
                "EV/EBITDA) remain valid because both sides scale together."
            )
    metrics["_per_share_split_warning"] = split_warn
    metrics["_shares_to_wa_ratio"] = (shares / wa) if (shares and wa) else None

    metrics["_sector"] = classify_sector((fund.get("profile") or {}).get("sic"))
    metrics["_concept_tags_used"] = tags_used
    metrics["_fallback_tags_used"] = {c: e for c, e in tags_used.items() if e.get("fallback")}
    metrics["_composites_suppressed"] = suppressed

    missing = sorted([k for k, v in metrics.items() if v is None])
    metrics["_unavailable_metrics"] = missing
    metrics["_stale_inputs_excluded"] = stale_excluded
    if stale_excluded:
        metrics["_stale_inputs_note"] = (
            "The concepts above were dropped before computing anything because the company "
            "stopped reporting those tags. Metrics that depended on them are unavailable "
            "rather than wrong."
        )
    metrics["_unavailable_note"] = (
        "Each metric listed above could not be computed from this company's SEC filings "
        "and must be reported as '" + config.MISSING + "'. Common legitimate reasons: "
        "banks and insurers file no gross profit or capex; loss-making firms have no "
        "meaningful P/E; young companies lack the history for a CAGR."
    )
    metrics["_formulas"] = {
        "free_cash_flow": "operating cash flow - |capital expenditure|",
        "roic_pct": "NOPAT / invested capital, where NOPAT = operating income x (1 - effective tax rate) "
                    "and invested capital = total debt + equity - cash & short-term investments",
        "ebitda_proxy": "operating income + depreciation & amortization (a proxy; EBITDA is not GAAP)",
        "enterprise_value": "market cap + total debt - cash & short-term investments",
        "peg_ratio": "P/E divided by the multi-year net income CAGR (%)",
        "market_cap": "market price x share count from the latest SEC cover page (dei tag)",
        "share_count_change_pct": "change in weighted-average diluted shares over the window; "
                                  "positive = dilution, negative = net buybacks",
    }
    metrics["_assumptions"] = [
        "Invested capital excludes cash, which flatters the ROIC of cash-rich companies.",
        "EBITDA is approximated as operating income + D&A; companies define it differently.",
        "Multi-year CAGRs use the first and last year in the window only, so a single "
        "unusual endpoint year can distort them. The year-by-year series is provided "
        "alongside for exactly this reason.",
        "All figures are as-reported (including restatements picked up from later filings); "
        "no adjustment is made for one-off items, and 'adjusted' non-GAAP figures that "
        "management prefers are deliberately ignored.",
    ]
    return metrics


def format_metric(value: Optional[float], kind: str = "num", decimals: int = 2) -> str:
    """Render a metric for display, never inventing a number for a missing one."""
    if value is None:
        return config.MISSING
    if kind == "pct":
        return format(value, "." + str(decimals) + "f") + "%"
    if kind == "usd":
        for cutoff, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
            if abs(value) >= cutoff:
                return "$" + format(value / cutoff, ".2f") + suffix
        return "$" + format(value, ".2f")
    if kind == "x":
        return format(value, "." + str(decimals) + "f") + "x"
    return format(value, "," + "." + str(decimals) + "f")

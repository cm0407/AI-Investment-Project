"""Valuation: several methods, never one, plus explicit bear / base / bull cases.

CLAUDE.md Phase 3 requires multiple approaches. This module implements:

  * Multiples          - P/E, forward P/E, PEG, EV/EBITDA, P/S, P/FCF (from metrics.py)
  * Reverse DCF        - what growth rate does today's price already assume?
  * Two-stage DCF      - a fair value estimate from projected free cash flow
  * Historical bands   - where the current multiple sits versus its own recent history
  * Scenario engine    - bear/base/bull target prices with stated assumptions

EVERY OUTPUT HERE IS A PROJECTION (basis="projected"). A DCF is an opinion dressed in
arithmetic: change the discount rate by two points and the answer moves 40%. The
sensitivity table is printed for exactly that reason - so the reader sees how fragile the
number is instead of trusting it.
"""

from __future__ import annotations

from typing import Any, Optional

from . import config


def two_stage_dcf(
    fcf_base: float,
    growth_rate: float,
    discount_rate: float = None,
    terminal_growth: float = None,
    years: int = None,
    net_cash: float = 0.0,
    shares: Optional[float] = None,
    fade: bool = True,
) -> dict:
    """Discount projected free cash flow back to today.

    Args:
        fcf_base:        latest annual free cash flow, in dollars
        growth_rate:     starting FCF growth rate, as a decimal (0.08 = 8%)
        discount_rate:   required annual return (default 10%)
        terminal_growth: perpetual growth after the projection window (default 2.5%)
        years:           projection window (default 10)
        net_cash:        cash minus debt, added to enterprise value
        shares:          share count, to convert to a per-share value
        fade:            if True, growth declines linearly toward terminal growth

    Returns a dict including per-year detail so the arithmetic can be audited.
    """
    d = config.DCF_DEFAULTS
    discount_rate = d["discount_rate"] if discount_rate is None else discount_rate
    terminal_growth = d["terminal_growth"] if terminal_growth is None else terminal_growth
    years = d["projection_years"] if years is None else years

    if fcf_base is None or fcf_base <= 0:
        return {
            "error": "DCF requires positive free cash flow. Base FCF was "
                     + str(fcf_base) + ". A DCF on negative cash flow is arithmetic "
                     "theatre - use another method.",
            "fair_value_per_share": None,
        }
    if discount_rate <= terminal_growth:
        return {
            "error": "Discount rate must exceed terminal growth or the model divides by "
                     "a negative number and returns an infinite valuation.",
            "fair_value_per_share": None,
        }

    rows: list[dict] = []
    pv_sum = 0.0
    fcf = float(fcf_base)
    for yr in range(1, years + 1):
        if fade:
            # Growth glides from the starting rate to the terminal rate over the window.
            g = growth_rate + (terminal_growth - growth_rate) * (yr - 1) / max(years - 1, 1)
        else:
            g = growth_rate
        fcf = fcf * (1.0 + g)
        pv = fcf / ((1.0 + discount_rate) ** yr)
        pv_sum += pv
        rows.append({
            "year": yr,
            "growth_applied_pct": g * 100.0,
            "projected_fcf": fcf,
            "discount_factor": 1.0 / ((1.0 + discount_rate) ** yr),
            "present_value": pv,
        })

    terminal_fcf = fcf * (1.0 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / ((1.0 + discount_rate) ** years)

    enterprise_value = pv_sum + pv_terminal
    equity_value = enterprise_value + (net_cash or 0.0)
    per_share = (equity_value / shares) if shares else None

    return {
        "fair_value_per_share": per_share,
        "equity_value": equity_value,
        "enterprise_value": enterprise_value,
        "pv_of_projection_window": pv_sum,
        "pv_of_terminal_value": pv_terminal,
        "terminal_value_share_of_total_pct": (pv_terminal / enterprise_value * 100.0)
                                             if enterprise_value else None,
        "inputs": {
            "fcf_base": fcf_base,
            "starting_growth_pct": growth_rate * 100.0,
            "discount_rate_pct": discount_rate * 100.0,
            "terminal_growth_pct": terminal_growth * 100.0,
            "projection_years": years,
            "growth_fades_to_terminal": fade,
            "net_cash_added": net_cash,
            "shares": shares,
        },
        "projection": rows,
        "_basis": "projected - this is OUR forecast under OUR assumptions, not a fact",
        "_health_warning": (
            "If 'terminal_value_share_of_total_pct' is above ~70%, most of this valuation "
            "rests on a guess about the year-11-and-beyond world. Treat it as a rough "
            "bound, not a price target."
        ),
    }


def reverse_dcf(price: float, shares: float, fcf_base: float, net_cash: float = 0.0,
                discount_rate: float = None, terminal_growth: float = None,
                years: int = None) -> dict:
    """What FCF growth rate does today's price already bake in?

    Often more useful than a forward DCF: instead of us guessing growth and producing a
    'fair value', it asks what the market is currently assuming, and lets us judge whether
    that assumption is easy or hard to beat.
    """
    d = config.DCF_DEFAULTS
    discount_rate = d["discount_rate"] if discount_rate is None else discount_rate
    terminal_growth = d["terminal_growth"] if terminal_growth is None else terminal_growth
    years = d["projection_years"] if years is None else years

    if not (price and shares and fcf_base and fcf_base > 0):
        return {"implied_growth_pct": None,
                "error": "Needs positive FCF, a share count and a price."}

    target_equity_value = price * shares
    lo, hi = -0.50, 1.00
    implied = None
    for _ in range(80):  # bisection
        mid = (lo + hi) / 2.0
        val = two_stage_dcf(fcf_base, mid, discount_rate, terminal_growth, years,
                            net_cash, shares)
        v = val.get("equity_value")
        if v is None:
            break
        if v < target_equity_value:
            lo = mid
        else:
            hi = mid
        implied = mid
        if abs(v - target_equity_value) / target_equity_value < 1e-6:
            break

    return {
        "implied_growth_pct": implied * 100.0 if implied is not None else None,
        "interpretation": (
            "To justify today's price, free cash flow must grow at roughly this rate per "
            "year (fading to " + format(terminal_growth * 100, ".1f") + "% terminal) for "
            + str(years) + " years, at a "
            + format(discount_rate * 100, ".1f") + "% required return. Compare it with the "
            "growth the company has actually delivered: if the market demands far more "
            "than history supports, the price carries a high bar."
        ),
        "assumptions": {
            "discount_rate_pct": discount_rate * 100.0,
            "terminal_growth_pct": terminal_growth * 100.0,
            "years": years,
        },
        "_basis": "projected",
    }


def sensitivity_table(fcf_base: float, growth_rate: float, net_cash: float,
                      shares: float) -> dict:
    """Fair value across a grid of discount rates and growth rates.

    The point of this table is humility: it shows how much the 'answer' moves when two
    debatable inputs move a little.
    """
    discount_rates = [0.08, 0.09, 0.10, 0.11, 0.12]
    growth_deltas = [-0.04, -0.02, 0.0, 0.02, 0.04]
    grid: dict[str, dict[str, Optional[float]]] = {}
    for dr in discount_rates:
        row: dict[str, Optional[float]] = {}
        for gd in growth_deltas:
            g = max(growth_rate + gd, -0.10)
            res = two_stage_dcf(fcf_base, g, dr, shares=shares, net_cash=net_cash)
            row[format((growth_rate + gd) * 100, ".1f") + "% growth"] = res.get(
                "fair_value_per_share")
        grid[format(dr * 100, ".1f") + "% discount"] = row
    return {
        "grid": grid,
        "note": "Rows = required return (discount rate). Columns = starting FCF growth. "
                "The spread across this table is the honest uncertainty in the estimate.",
    }


def multiples_valuation(metrics: dict, target_multiples: dict[str, float]) -> dict:
    """Value the company by applying a target multiple to its actual results.

    target_multiples maps e.g. {"pe": 22, "ps": 4.5, "pfcf": 25} and the caller must
    justify where those targets came from (peer median, the stock's own history, etc.).
    """
    shares = metrics.get("shares_outstanding")
    out: dict[str, Any] = {}

    def per_share(total: Optional[float]) -> Optional[float]:
        return (total / shares) if (total is not None and shares) else None

    if "pe" in target_multiples and metrics.get("net_income_latest"):
        out["from_pe"] = {
            "target_multiple": target_multiples["pe"],
            "applied_to": "net income " + str(metrics["net_income_latest"]),
            "implied_price": per_share(metrics["net_income_latest"] * target_multiples["pe"]),
        }
    if "ps" in target_multiples and metrics.get("revenue_latest"):
        out["from_ps"] = {
            "target_multiple": target_multiples["ps"],
            "applied_to": "revenue " + str(metrics["revenue_latest"]),
            "implied_price": per_share(metrics["revenue_latest"] * target_multiples["ps"]),
        }
    if "pfcf" in target_multiples and metrics.get("fcf_latest"):
        out["from_pfcf"] = {
            "target_multiple": target_multiples["pfcf"],
            "applied_to": "free cash flow " + str(metrics["fcf_latest"]),
            "implied_price": per_share(metrics["fcf_latest"] * target_multiples["pfcf"]),
        }
    if "ev_ebitda" in target_multiples and metrics.get("ebitda_proxy"):
        ev = metrics["ebitda_proxy"] * target_multiples["ev_ebitda"]
        equity = ev - (metrics.get("total_debt") or 0.0) + (metrics.get("total_cash_and_sti") or 0.0)
        out["from_ev_ebitda"] = {
            "target_multiple": target_multiples["ev_ebitda"],
            "applied_to": "EBITDA proxy " + str(metrics["ebitda_proxy"]),
            "implied_price": per_share(equity),
        }
    out["_basis"] = "projected - depends entirely on the target multiple chosen"
    out["_caution"] = ("A target multiple is an assumption about what the market will be "
                       "willing to pay later. Justify it with peers or the company's own "
                       "history, or it is circular reasoning.")
    return out


def check_scenario_width(bear_pct: float, bull_pct: float,
                         annual_volatility_pct: Optional[float]) -> dict:
    """Is this bear-to-bull range wide enough to mean anything for THIS stock?

    Added 2026-10-23 after a calibration review found six of eleven positions at or within
    3% of a TWELVE-MONTH target after about 12% of the horizon, while another was already
    41% of the way to its bear case. Both ends arriving too fast indicted the ranges, not
    the direction.

    Testing every scenario span against the stock's own annualised volatility found 10 of
    10 narrower than a two-sigma annual move. NICE carries 47.9% volatility and had been
    given a -33%/+50% span; Intuit 42.5% against -28%/+50%. Those are not extremes - for a
    stock that routinely swings 40%+ a year, they describe an ordinary year.

    The consequence is not merely cosmetic. If the "bear case" is really a common outcome
    rather than a bad one, then a stated 30% probability attached to it is not conservative;
    it may be optimistic. Narrow ranges make the whole scenario apparatus look more precise
    than it is.

    Rule of thumb used here: one standard deviation of annual return is roughly the
    volatility figure itself. A bear case should sit at or beyond -1 sigma and a bull case
    at or beyond +1 sigma, so a defensible span is at least ~2x volatility wide.
    """
    if annual_volatility_pct is None or annual_volatility_pct <= 0:
        return {"checked": False,
                "reason": "annualised volatility unavailable - cannot size the range"}

    span = bull_pct - bear_pct
    one_sigma = annual_volatility_pct
    min_span = 2.0 * one_sigma

    return {
        "checked": True,
        "annual_volatility_pct": annual_volatility_pct,
        "span_pct": span,
        "minimum_defensible_span_pct": min_span,
        "bear_in_sigmas": bear_pct / one_sigma,
        "bull_in_sigmas": bull_pct / one_sigma,
        "too_narrow": span < min_span,
        "suggested_bear_pct": -one_sigma * 1.25,
        "suggested_bull_pct": one_sigma * 1.25,
        "warning": (
            "RANGE TOO NARROW: this stock's annualised volatility is "
            + format(one_sigma, ".1f") + "%, so a one-sigma year is about that much in "
            "either direction. The span given (" + format(bear_pct, "+.0f") + "% to "
            + format(bull_pct, "+.0f") + "%, " + format(span, ".0f") + " points wide) is "
            "below the ~" + format(min_span, ".0f") + " points a two-sigma range needs. "
            "The bear case sits at " + format(bear_pct / one_sigma, ".2f")
            + " sigma and the bull at " + format(bull_pct / one_sigma, "+.2f")
            + " sigma - these describe an ORDINARY year, not the tails, and the "
            "probabilities attached to them are correspondingly overconfident."
        ) if span < min_span else None,
    }


def scenarios(price: float, metrics: dict, bear: dict, base: dict, bull: dict,
              annual_volatility_pct: Optional[float] = None) -> dict:
    """Assemble bear / base / bull cases into one probability-weighted view.

    Each case dict needs: {"target_price": float, "probability": 0..1,
                           "assumptions": [str, ...]}
    Probabilities must sum to ~1.0; a warning is emitted otherwise rather than silently
    normalising, because a probability set that does not sum to one usually means the
    thinking is not finished.
    """
    cases = {"bear": bear, "base": base, "bull": bull}
    total_p = sum(c.get("probability", 0) for c in cases.values())
    warnings: list[str] = []
    if abs(total_p - 1.0) > 0.01:
        warnings.append("Probabilities sum to " + format(total_p, ".2f")
                        + ", not 1.00. Re-check the scenario weights.")

    enriched: dict[str, Any] = {}
    expected_return = 0.0
    prob_positive = 0.0
    prob_20pct = 0.0
    prob_loss = 0.0

    for name, c in cases.items():
        tgt = c.get("target_price")
        p = c.get("probability", 0.0)
        ret = ((tgt / price - 1.0) * 100.0) if (tgt and price) else None
        enriched[name] = {
            "target_price": tgt,
            "return_pct": ret,
            "probability": p,
            "assumptions": c.get("assumptions", []),
        }
        if ret is not None:
            expected_return += (ret * p)
            if ret > 0:
                prob_positive += p
            if ret >= 20.0:
                prob_20pct += p
            if ret < 0:
                prob_loss += p

    width = check_scenario_width(
        enriched["bear"]["return_pct"] if enriched["bear"]["return_pct"] is not None else 0.0,
        enriched["bull"]["return_pct"] if enriched["bull"]["return_pct"] is not None else 0.0,
        annual_volatility_pct,
    )
    if width.get("warning"):
        warnings.append(width["warning"])

    return {
        "current_price": price,
        "cases": enriched,
        "range_check": width,
        "probability_weighted_return_pct": expected_return,
        "prob_positive": prob_positive,
        "prob_hits_20pct": prob_20pct,
        "prob_loss": prob_loss,
        "warnings": warnings,
        "_basis": "projected",
        "_note": (
            "These probabilities are informed estimates, not measurements. Their value is "
            "in being written down BEFORE the outcome, so that calibration can be checked "
            "later in predictions.csv. Scenario probabilities that are never scored are "
            "just decoration."
        ),
    }


def historical_multiple_band(metrics_by_year: list[dict], current_multiple: Optional[float],
                             key: str = "pe_ratio") -> dict:
    """Where does today's multiple sit against its own history?

    Answers 'is this cheap relative to itself?', which is a different and often more
    honest question than 'is this cheap relative to some peer I chose'.
    """
    vals = [m.get(key) for m in metrics_by_year if m.get(key)]
    if not vals or current_multiple is None:
        return {"available": False, "reason": config.MISSING}
    vals_sorted = sorted(vals)
    n = len(vals_sorted)
    below = sum(1 for v in vals_sorted if v < current_multiple)
    return {
        "available": True,
        "current": current_multiple,
        "min": vals_sorted[0],
        "median": vals_sorted[n // 2],
        "max": vals_sorted[-1],
        "percentile_of_history": (below / n) * 100.0,
        "years_of_history": n,
        "interpretation": (
            "A low percentile means the stock is cheap versus its own past. It does not "
            "mean the stock is cheap: a business whose prospects have permanently worsened "
            "deserves a lower multiple than it used to have."
        ),
    }

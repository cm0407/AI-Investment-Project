"""The 0-100 scoring engine from CLAUDE.md.

    Business quality 15 · Growth 15 · Valuation 15 · Financial strength 10 ·
    Free cash flow 10 · Competitive advantage 10 · Catalysts 10 · Risk/reward 10 ·
    Management & capital allocation 5

A DELIBERATE DESIGN DECISION
---------------------------
Only four of those nine pillars can be scored honestly by a script:

    growth (15) · valuation (15) · financial strength (10) · free cash flow (10)  = 50 pts

The other five require judgment a program does not have. Whether a moat is durable,
whether a catalyst is real or wishful, whether management allocates capital well - these
are readings, not calculations. A script that emits "Competitive advantage: 7/10" has
invented that number, and CLAUDE.md forbids inventing numbers.

So this module returns a PARTIAL score out of the 50 data-scorable points, plus an
evidence pack for the analyst to score the remaining 50 by hand. The final score is only
complete once those judgments are recorded (with written justification) in a small JSON
file passed via --judgment. Until then the output says so, loudly.

Every threshold below is a stated convention, not a law of nature. They are listed in
docs/ASSUMPTIONS.md so they can be argued with and changed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from . import config


# --------------------------------------------------------------------------------------
# Scoring helpers
# --------------------------------------------------------------------------------------
def _band_score(value: Optional[float], bands: list[tuple[float, float]],
                higher_is_better: bool = True) -> tuple[Optional[float], str]:
    """Map a value onto 0..1 using (threshold, score) bands. Returns (score, explanation)."""
    if value is None:
        return None, config.MISSING
    ordered = sorted(bands, key=lambda b: b[0], reverse=higher_is_better)
    for threshold, score in ordered:
        if (higher_is_better and value >= threshold) or \
           (not higher_is_better and value <= threshold):
            comparator = ">=" if higher_is_better else "<="
            return score, (format(value, ".2f") + " " + comparator + " "
                           + format(threshold, ".2f") + " -> " + format(score, ".2f"))
    return 0.0, format(value, ".2f") + " fell below every band -> 0.00"


def _avg(scores: list[Optional[float]]) -> tuple[Optional[float], int, int]:
    """Average the components that exist. Returns (avg, n_scored, n_total)."""
    present = [s for s in scores if s is not None]
    if not present:
        return None, 0, len(scores)
    return sum(present) / len(present), len(present), len(scores)


def _get(m: dict, key: str) -> Optional[float]:
    """Read a metric, returning None when it is meaningless for this company's sector.

    A bank's debt-to-equity of 11x is not a warning sign, it is banking. Scoring it on an
    industrial's thresholds would hand out a confident, wrong number. The metrics module
    flags these per SIC code; here we simply refuse to score them, which shows up honestly
    as a thinner components_scored count or an unscorable pillar.
    """
    if key in ((m.get("_sector") or {}).get("unreliable_metrics") or []):
        return None
    return m.get(key)


def _sector_suppressed(m: dict, keys: list[str]) -> list[str]:
    unreliable = (m.get("_sector") or {}).get("unreliable_metrics") or []
    return [k for k in keys if k in unreliable]


# --------------------------------------------------------------------------------------
# Pillar 1: GROWTH (15 points)
# --------------------------------------------------------------------------------------
def score_growth(m: dict) -> dict:
    components: dict[str, Any] = {}

    s1, e1 = _band_score(_get(m, "revenue_cagr_pct"),
                         [(20, 1.0), (12, 0.85), (8, 0.7), (5, 0.5), (2, 0.3), (0, 0.15)])
    components["revenue_cagr"] = {"value": _get(m, "revenue_cagr_pct"), "score": s1, "why": e1}

    s2, e2 = _band_score(_get(m, "net_income_cagr_pct"),
                         [(20, 1.0), (12, 0.85), (8, 0.7), (5, 0.5), (2, 0.3), (0, 0.15)])
    components["net_income_cagr"] = {"value": _get(m, "net_income_cagr_pct"), "score": s2, "why": e2}

    s3, e3 = _band_score(_get(m, "fcf_cagr_pct"),
                         [(20, 1.0), (12, 0.85), (8, 0.7), (5, 0.5), (2, 0.3), (0, 0.15)])
    components["fcf_cagr"] = {"value": _get(m, "fcf_cagr_pct"), "score": s3, "why": e3}

    s4, e4 = _band_score(_get(m, "revenue_growth_latest_pct"),
                         [(15, 1.0), (10, 0.85), (6, 0.7), (3, 0.5), (0, 0.3)])
    components["most_recent_year_revenue_growth"] = {
        "value": _get(m, "revenue_growth_latest_pct"), "score": s4, "why": e4}

    # Is growth accelerating or decelerating? A trend matters as much as a level.
    yoy = [g for g in (m.get("revenue_growth_yoy_pct") or []) if g is not None]
    trend_note = config.MISSING
    if len(yoy) >= 3:
        recent, earlier = yoy[-1], sum(yoy[:-1]) / len(yoy[:-1])
        if recent > earlier + 2:
            trend_note = ("ACCELERATING: latest year " + format(recent, ".1f")
                          + "% vs " + format(earlier, ".1f") + "% average of prior years")
        elif recent < earlier - 2:
            trend_note = ("DECELERATING: latest year " + format(recent, ".1f")
                          + "% vs " + format(earlier, ".1f") + "% average of prior years")
        else:
            trend_note = "STEADY: latest year in line with the prior-year average"

    avg, n, total = _avg([s1, s2, s3, s4])
    return {
        "pillar": "growth",
        "max_points": config.SCORE_WEIGHTS["growth"],
        "normalized_score": avg,
        "points": (avg * config.SCORE_WEIGHTS["growth"]) if avg is not None else None,
        "components_scored": n, "components_total": total,
        "components": components,
        "sector_suppressed_components": _sector_suppressed(
            m, ["revenue_cagr_pct", "net_income_cagr_pct", "fcf_cagr_pct",
                "revenue_growth_latest_pct"]),
        "trend": trend_note,
        "yoy_series_pct": yoy,
    }


# --------------------------------------------------------------------------------------
# Pillar 2: VALUATION (15 points)
# --------------------------------------------------------------------------------------
def score_valuation(m: dict) -> dict:
    components: dict[str, Any] = {}

    s1, e1 = _band_score(_get(m, "pe_ratio"),
                         [(10, 1.0), (15, 0.85), (20, 0.7), (25, 0.55), (35, 0.35), (50, 0.15)],
                         higher_is_better=False)
    components["pe_ratio"] = {"value": _get(m, "pe_ratio"), "score": s1, "why": e1}

    s2, e2 = _band_score(_get(m, "pfcf_ratio"),
                         [(12, 1.0), (18, 0.85), (25, 0.7), (35, 0.5), (50, 0.3)],
                         higher_is_better=False)
    components["pfcf_ratio"] = {"value": _get(m, "pfcf_ratio"), "score": s2, "why": e2}

    s3, e3 = _band_score(_get(m, "ev_ebitda"),
                         [(8, 1.0), (12, 0.85), (16, 0.65), (22, 0.45), (30, 0.25)],
                         higher_is_better=False)
    components["ev_ebitda"] = {"value": _get(m, "ev_ebitda"), "score": s3, "why": e3}

    s4, e4 = _band_score(_get(m, "fcf_yield_pct"),
                         [(8, 1.0), (6, 0.85), (4, 0.65), (2.5, 0.45), (1, 0.25)])
    components["fcf_yield"] = {"value": _get(m, "fcf_yield_pct"), "score": s4, "why": e4}

    s5, e5 = _band_score(_get(m, "peg_ratio"),
                         [(0.8, 1.0), (1.2, 0.8), (1.8, 0.6), (2.5, 0.4), (4.0, 0.2)],
                         higher_is_better=False)
    components["peg_ratio"] = {"value": _get(m, "peg_ratio"), "score": s5, "why": e5}

    avg, n, total = _avg([s1, s2, s3, s4, s5])
    return {
        "pillar": "valuation",
        "max_points": config.SCORE_WEIGHTS["valuation"],
        "normalized_score": avg,
        "points": (avg * config.SCORE_WEIGHTS["valuation"]) if avg is not None else None,
        "components_scored": n, "components_total": total,
        "components": components,
        "sector_suppressed_components": _sector_suppressed(
            m, ["pe_ratio", "pfcf_ratio", "ev_ebitda", "fcf_yield_pct", "peg_ratio"]),
        "caution": (
            "A cheap multiple is not the same as an undervalued business. Stocks are often "
            "cheap because the market has correctly judged that earnings are about to fall. "
            "This pillar must be read next to the growth and quality pillars, never alone."
        ),
    }


# --------------------------------------------------------------------------------------
# Pillar 3: FINANCIAL STRENGTH (10 points)
# --------------------------------------------------------------------------------------
def score_financial_strength(m: dict) -> dict:
    components: dict[str, Any] = {}

    s1, e1 = _band_score(_get(m, "debt_to_equity"),
                         [(0.3, 1.0), (0.6, 0.85), (1.0, 0.65), (2.0, 0.4), (3.0, 0.2)],
                         higher_is_better=False)
    components["debt_to_equity"] = {"value": _get(m, "debt_to_equity"), "score": s1, "why": e1}

    s2, e2 = _band_score(_get(m, "current_ratio"),
                         [(2.0, 1.0), (1.5, 0.85), (1.2, 0.7), (1.0, 0.5), (0.8, 0.25)])
    components["current_ratio"] = {"value": _get(m, "current_ratio"), "score": s2, "why": e2}

    s3, e3 = _band_score(_get(m, "interest_coverage"),
                         [(15, 1.0), (8, 0.85), (5, 0.7), (3, 0.5), (1.5, 0.25)])
    components["interest_coverage"] = {"value": _get(m, "interest_coverage"), "score": s3, "why": e3}

    s4, e4 = _band_score(_get(m, "net_debt_to_ebitda"),
                         [(0.0, 1.0), (1.0, 0.85), (2.0, 0.7), (3.0, 0.5), (4.0, 0.25)],
                         higher_is_better=False)
    components["net_debt_to_ebitda"] = {"value": _get(m, "net_debt_to_ebitda"), "score": s4, "why": e4}

    avg, n, total = _avg([s1, s2, s3, s4])
    return {
        "pillar": "financial_strength",
        "max_points": config.SCORE_WEIGHTS["financial_strength"],
        "normalized_score": avg,
        "points": (avg * config.SCORE_WEIGHTS["financial_strength"]) if avg is not None else None,
        "components_scored": n, "components_total": total,
        "components": components,
        "sector_suppressed_components": _sector_suppressed(
            m, ["debt_to_equity", "current_ratio", "interest_coverage",
                "net_debt_to_ebitda"]),
        "sector_caveat": (
            "These thresholds are calibrated for operating companies. Banks, insurers, "
            "REITs and utilities run structurally different balance sheets - high leverage "
            "is their business model, not a warning sign. Do not apply this pillar to a "
            "financial company without adjusting the yardstick."
        ),
    }


# --------------------------------------------------------------------------------------
# Pillar 4: FREE CASH FLOW (10 points)
# --------------------------------------------------------------------------------------
def score_free_cash_flow(m: dict) -> dict:
    components: dict[str, Any] = {}

    s1, e1 = _band_score(_get(m, "fcf_margin_pct"),
                         [(25, 1.0), (18, 0.85), (12, 0.7), (7, 0.5), (3, 0.3), (0, 0.15)])
    components["fcf_margin"] = {"value": _get(m, "fcf_margin_pct"), "score": s1, "why": e1}

    s2, e2 = _band_score(_get(m, "ocf_to_net_income"),
                         [(1.3, 1.0), (1.1, 0.9), (0.95, 0.75), (0.8, 0.5), (0.6, 0.25)])
    components["ocf_to_net_income"] = {
        "value": _get(m, "ocf_to_net_income"), "score": s2, "why": e2,
        "meaning": ("Cash from operations divided by reported profit. Comfortably above 1 "
                    "means profits arrive as real cash. Persistently below 1 is one of the "
                    "oldest accounting red flags there is."),
    }

    s3, e3 = _band_score(_get(m, "fcf_latest"), [(0.01, 1.0)])
    components["fcf_positive"] = {"value": _get(m, "fcf_latest"), "score": s3, "why": e3}

    avg, n, total = _avg([s1, s2, s3])
    return {
        "pillar": "free_cash_flow",
        "max_points": config.SCORE_WEIGHTS["free_cash_flow"],
        "normalized_score": avg,
        "points": (avg * config.SCORE_WEIGHTS["free_cash_flow"]) if avg is not None else None,
        "components_scored": n, "components_total": total,
        "components": components,
        "sector_suppressed_components": _sector_suppressed(
            m, ["fcf_margin_pct", "ocf_to_net_income", "fcf_latest"]),
    }


# --------------------------------------------------------------------------------------
# Evidence packs for the pillars a script must NOT score by itself
# --------------------------------------------------------------------------------------
def judgment_evidence(m: dict, fund: dict, insider: Optional[dict] = None) -> dict:
    """Assemble the facts an analyst needs to score the five judgment pillars.

    This returns EVIDENCE, not scores. Nothing here produces a number.
    """
    profile = fund.get("profile", {})

    return {
        "business_quality": {
            "max_points": config.SCORE_WEIGHTS["business_quality"],
            "question": "Is this a genuinely good business, independent of its price?",
            "evidence": {
                "industry (SEC SIC code)": str(profile.get("sic")) + " - "
                                           + str(profile.get("sic_description")),
                "gross_margin_pct": m.get("gross_margin_pct"),
                "operating_margin_pct": m.get("operating_margin_pct"),
                "net_margin_pct": m.get("net_margin_pct"),
                "roe_pct": m.get("roe_pct"),
                "roic_pct": m.get("roic_pct"),
                "capex_to_revenue_pct": m.get("capex_to_revenue_pct"),
            },
            "how_to_judge": (
                "High and STABLE margins plus ROIC comfortably above ~10% suggests real "
                "quality. Read the 10-K's business section for what actually drives it. "
                "One good year is noise; five is a pattern."
            ),
        },
        "competitive_advantage": {
            "max_points": config.SCORE_WEIGHTS["competitive_advantage"],
            "question": "Is there a moat, and is it widening or narrowing?",
            "evidence": {
                "margin_trend": "compare the multi-year margin series in the fundamentals file",
                "roic_pct": m.get("roic_pct"),
                "goodwill_vs_assets": (
                    (m["goodwill"] / m["total_assets"] * 100.0)
                    if (m.get("goodwill") and m.get("total_assets")) else None
                ),
            },
            "how_to_judge": (
                "A moat shows up as pricing power that survives competition: margins that "
                "hold or rise while the business grows. Read the 10-K Competition and Risk "
                "Factors sections. Heavy goodwill means growth was bought, not built - "
                "check whether it was ever written down."
            ),
        },
        "catalysts": {
            "max_points": config.SCORE_WEIGHTS["catalysts"],
            "question": "What specific, dated events could re-rate this stock?",
            "evidence": {
                "recent_filings": "see the filings list in the fundamentals file",
                "insider_activity": (insider or {}).get("summary"),
            },
            "how_to_judge": (
                "A catalyst has a date and a mechanism: an earnings report, a product "
                "launch, a contract decision, a margin inflection with a stated cause. "
                "'The sector should recover' is not a catalyst, it is a hope. Per CLAUDE.md "
                "Phase 4, separate genuine catalysts from vague optimism."
            ),
        },
        "risk_reward": {
            "max_points": config.SCORE_WEIGHTS["risk_reward"],
            "question": "Is the upside big enough to justify the realistic downside?",
            "evidence": {
                "note": "Score this only AFTER building bear/base/bull cases in valuation.py",
            },
            "how_to_judge": (
                "Compare probability-weighted upside against the bear-case loss. An idea "
                "with +30% upside and -40% downside at even odds is a bad bet no matter "
                "how good the story is."
            ),
        },
        "management": {
            "max_points": config.SCORE_WEIGHTS["management"],
            "question": "Do they allocate capital well and tell the truth?",
            "evidence": {
                "share_count_change_pct": m.get("share_count_change_pct"),
                "buybacks_latest": m.get("buybacks_latest"),
                "dividends_paid_latest": m.get("dividends_paid_latest"),
                "insider_open_market_buys": (insider or {}).get("summary", {}).get("open_market_buys"),
                "insider_open_market_sells": (insider or {}).get("summary", {}).get("open_market_sells"),
            },
            "how_to_judge": (
                "Check whether buybacks happened at sensible prices or at the top. Rising "
                "share count with heavy stock compensation transfers value from you to "
                "employees. Compare past guidance with what was actually delivered - that "
                "is the single best test of management credibility."
            ),
        },
    }


# --------------------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------------------
def score_company(m: dict, fund: dict, insider: Optional[dict] = None,
                  judgment: Optional[dict] = None) -> dict:
    """Produce the full score record: data pillars computed, judgment pillars declared.

    judgment (optional): {"business_quality": {"points": 11, "justification": "..."} , ...}
    Without it, the total is explicitly PARTIAL and must not be compared with the
    CLAUDE.md 0-100 bands.
    """
    pillars = {
        "growth": score_growth(m),
        "valuation": score_valuation(m),
        "financial_strength": score_financial_strength(m),
        "free_cash_flow": score_free_cash_flow(m),
    }

    data_points = 0.0
    data_max_available = 0.0
    data_max_possible = sum(config.SCORE_WEIGHTS[p] for p in config.DATA_SCORED_PILLARS)
    unscorable: list[str] = []

    for name, res in pillars.items():
        if res["points"] is not None:
            data_points += res["points"]
            data_max_available += res["max_points"]
        else:
            unscorable.append(name + " (no usable data - " + str(res["components_total"])
                              + " components, 0 computable)")

    evidence = judgment_evidence(m, fund, insider)

    judgment_points = 0.0
    judgment_recorded: dict[str, Any] = {}
    judgment_missing: list[str] = []
    for pillar in config.JUDGMENT_PILLARS:
        entry = (judgment or {}).get(pillar)
        if entry and entry.get("points") is not None:
            pts = float(entry["points"])
            cap = config.SCORE_WEIGHTS[pillar]
            pts = max(0.0, min(pts, cap))
            judgment_points += pts
            judgment_recorded[pillar] = {
                "points": pts, "max_points": cap,
                "justification": entry.get("justification", "NO JUSTIFICATION RECORDED"),
            }
        else:
            judgment_missing.append(pillar)

    complete = not judgment_missing and not unscorable
    total = data_points + judgment_points

    sector = m.get("_sector") or {}
    for name, res in pillars.items():
        if res["points"] is None and res.get("sector_suppressed_components"):
            unscorable = [u for u in unscorable if not u.startswith(name + " ")]
            unscorable.append(
                name + " (not scored: every component is meaningless for a "
                + str(sector.get("kind")) + " company - "
                + ", ".join(res["sector_suppressed_components"]) + ")"
            )

    result: dict[str, Any] = {
        "sector_context": sector,
        "data_pillars": pillars,
        "data_points_earned": round(data_points, 2),
        "data_points_available": round(data_max_available, 2),
        "data_points_possible": data_max_possible,
        "judgment_pillars_recorded": judgment_recorded,
        "judgment_points_earned": round(judgment_points, 2),
        "judgment_pillars_missing": judgment_missing,
        "judgment_evidence": evidence,
        "unscorable_data_pillars": unscorable,
        "total_score": round(total, 1),
        "score_is_complete": complete,
    }

    if complete:
        result["verdict_band"] = config.band_for_score(total)
        result["interpretation"] = (
            "Complete score of " + format(total, ".1f") + "/100 -> "
            + result["verdict_band"] + " per the CLAUDE.md bands."
        )
    else:
        result["verdict_band"] = "INCOMPLETE - DO NOT COMPARE TO THE 0-100 BANDS"
        result["interpretation"] = (
            "PARTIAL SCORE: " + format(data_points, ".1f") + " of "
            + format(data_max_available, ".1f") + " points available from filings"
            + (" (of " + str(data_max_possible) + " data-scorable points; "
               + str(len(unscorable)) + " pillar(s) had no usable data)"
               if unscorable else "")
            + ". The " + str(len(judgment_missing)) + " judgment pillar(s) "
            + ", ".join(judgment_missing) + " (worth "
            + str(sum(config.SCORE_WEIGHTS[p] for p in judgment_missing))
            + " points) have NOT been scored - a script cannot judge a moat or a "
            "catalyst. Score them by hand from the evidence pack and pass them back "
            "with --judgment. Until then this number is not a CLAUDE.md score and must "
            "not be presented as one."
        )

    result["_scoring_note"] = (
        "Thresholds are conventions chosen at build time, documented in docs/ASSUMPTIONS.md. "
        "A pillar with missing inputs is averaged over the components that DO exist, and the "
        "count is reported as components_scored/components_total so thin coverage is visible "
        "rather than hidden."
    )
    return result


def load_judgment(path: Optional[str]) -> Optional[dict]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("Judgment file not found: " + str(p))
    return json.loads(p.read_text(encoding="utf-8"))

"""Read-only HTTP API over the INVEST pipeline. The frontend's only data source.

RUN
    uvicorn api.main:app --reload --port 8000
    open http://localhost:8000/docs          interactive API browser
    curl http://localhost:8000/openapi.json  the schema the frontend generates types from

DESIGN RULES
------------
1. **Read-only, and it never recomputes on request.** Screening a company downloads several
   megabytes from the SEC and takes seconds. This serves what the pipeline already wrote to
   `data/` and `memory/`. A request must never trigger a network call to the SEC.

2. **A missing metric serialises as null PLUS a reason - never as 0.** This is the single most
   important invariant in the whole system. `invest/metrics.py` goes to considerable trouble to
   distinguish "measured and it was zero" from "not measured"; JSON serialisation is exactly
   where that distinction gets quietly destroyed. Every response that carries metrics also
   carries `_unavailable`, a map of metric name -> why it is absent.

3. **Judgments say who wrote them.** Five of the nine score pillars may be written by a model
   (`invest/judge.py`). `judgmentSource` is "model" or "analyst" on every thesis response, so
   the UI can show which, for the same reason it shows which XBRL tag produced a figure.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Query          # noqa: E402
from fastapi.middleware.cors import CORSMiddleware         # noqa: E402

from invest import config                                   # noqa: E402

app = FastAPI(
    title="INVEST API",
    version="1.0.0",
    description=(
        "Read-only access to an SEC-filings-based equity research pipeline.\n\n"
        "**A null metric is not zero.** Any metric that could not be computed is `null`, and "
        "the reason appears in the `_unavailable` map on the same response. Rendering a null "
        "as `0` misrepresents the data this system is built to report honestly."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def _read_json(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found: " + path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def split_metrics(metrics: dict) -> tuple[dict, dict]:
    """Separate values from the reasons values are missing.

    The pipeline records several distinct kinds of absence. Collapsing them into a bare
    `null` would lose the explanation, which is the part a reader actually needs.
    """
    sector = metrics.get("_sector") or {}
    unreliable = set(sector.get("unreliable_metrics") or [])
    stale = metrics.get("_stale_inputs_excluded") or []
    suppressed = metrics.get("_composites_suppressed") or []

    values: dict[str, Any] = {}
    unavailable: dict[str, str] = {}

    for key, val in metrics.items():
        if key.startswith("_"):
            continue
        values[key] = val
        if val is not None:
            continue
        if key in unreliable:
            unavailable[key] = (
                "not meaningful for a " + str(sector.get("kind")) + " company - "
                "this ratio is computed but does not transfer to this industry"
            )
        elif any(key in s for s in suppressed):
            unavailable[key] = next(s for s in suppressed if key in s)
        elif any(key in s for s in stale):
            unavailable[key] = next(s for s in stale if key in s)
        else:
            unavailable[key] = "could not be computed from this company's filings"

    return values, unavailable


def collect_caveats(metrics: dict, fund: dict) -> list[dict]:
    """Every data caution the pipeline detected, in one renderable list."""
    out: list[dict] = []

    for concept, e in (metrics.get("_fallback_tags_used") or {}).items():
        out.append({
            "kind": "fallback_tag", "severity": "info",
            "message": (concept + " came from the tag '" + str(e.get("tag_used"))
                        + "' rather than the preferred '" + str(e.get("preferred_tag"))
                        + "', which may not mean exactly the same thing"),
            "affectedMetrics": [concept],
        })
    for s in (metrics.get("_stale_inputs_excluded") or []):
        out.append({"kind": "stale_input", "severity": "warning",
                    "message": s, "affectedMetrics": [s.split(" ")[0]]})
    for s in (metrics.get("_composites_suppressed") or []):
        out.append({"kind": "suppressed_composite", "severity": "warning",
                    "message": s, "affectedMetrics": [s.split(" ")[0]]})
    for key, kind, sev in (("_growth_base_warning", "growth_base", "critical"),
                           ("_per_share_split_warning", "per_share_split", "critical"),
                           ("_share_count_warning", "share_count", "critical")):
        if metrics.get(key):
            out.append({"kind": kind, "severity": sev,
                        "message": metrics[key], "affectedMetrics": []})
    if fund.get("reorganization"):
        r = fund["reorganization"]
        out.append({"kind": "reorganization", "severity": "critical",
                    "message": r["explanation"] + " " + r["caution"], "affectedMetrics": []})
    return out


# --------------------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "analyses": len(list(config.FUNDAMENTALS_DIR.glob("*_analysis.json"))),
        "predictions": max(len(_read_csv(config.PREDICTIONS_CSV)), 0),
        "digests": len(list(config.DAILY_REPORTS_DIR.glob("digest_*.md"))),
    }


@app.get("/companies", tags=["companies"])
def list_companies() -> list[dict]:
    """Every company with a saved deep-dive analysis."""
    out = []
    for p in sorted(config.FUNDAMENTALS_DIR.glob("*_analysis.json")):
        try:
            d = _read_json(p)["data"]
        except (KeyError, json.JSONDecodeError):
            continue
        m = d.get("metrics") or {}
        out.append({
            "ticker": p.stem.replace("_analysis", ""),
            "name": (d.get("fundamentals") or {}).get("company_name"),
            "price": m.get("price"),
            "marketCap": m.get("market_cap"),
            "sectorSpecial": (m.get("_sector") or {}).get("kind"),
        })
    return out


@app.get("/companies/{ticker}", tags=["companies"])
def get_company(ticker: str) -> dict:
    """Metrics, financial history, caveats and provenance for one company.

    `metrics` may contain nulls. For every null there is an entry in `_unavailable`
    explaining why. **Never render a null as 0.**
    """
    d = _read_json(config.FUNDAMENTALS_DIR / (ticker.upper() + "_analysis.json"))["data"]
    fund, m = d.get("fundamentals") or {}, d.get("metrics") or {}
    profile = fund.get("profile") or {}
    values, unavailable = split_metrics(m)

    financials = []
    revenue = (fund.get("annual") or {}).get("revenue") or []
    for i, row in enumerate(revenue[-6:]):
        period = row["period_end"]

        def at(key: str) -> Optional[float]:
            rows = (fund.get("annual") or {}).get(key) or []
            hit = next((r for r in rows if r["period_end"] == period), None)
            return hit["value"] if hit else None

        financials.append({
            "periodEnd": period,
            "revenue": row["value"],
            "operatingIncome": at("operating_income"),
            "netIncome": at("net_income"),
            "operatingCashFlow": at("operating_cash_flow"),
            "sourceTag": row.get("tag"),
            "sourceForm": row.get("form"),
            "sourceAccession": row.get("accession"),
        })

    return {
        "ticker": ticker.upper(),
        "name": fund.get("company_name"),
        "cik": fund.get("cik_padded"),
        "sic": profile.get("sic"),
        "sicDescription": profile.get("sic_description"),
        "sectorSpecial": (m.get("_sector") or {}).get("kind"),
        "sectorUnreliableMetrics": (m.get("_sector") or {}).get("unreliable_metrics") or [],
        "metrics": values,
        "_unavailable": unavailable,
        "financials": financials,
        "caveats": collect_caveats(m, fund),
        "latestFiscalPeriodEnd": fund.get("latest_fiscal_period_end"),
    }


@app.get("/companies/{ticker}/thesis", tags=["companies"])
def get_thesis(ticker: str) -> dict:
    """Score, pillar breakdown and judgments.

    `judgmentSource` is "model" when `invest/judge.py` wrote the judgment pillars and
    "analyst" when a person did. The UI must show which.
    """
    tk = ticker.upper()
    doc = _read_json(config.FUNDAMENTALS_DIR / (tk + "_analysis.json"))
    d = doc["data"]
    score = d.get("score") or {}
    data_scored_at = (doc.get("_meta") or {}).get("generated_at_utc")

    judgment_path = config.RESEARCH_DIR / "judgments" / (tk + ".json")
    judgment, source, model_run = None, None, None
    if judgment_path.exists():
        judgment = json.loads(judgment_path.read_text(encoding="utf-8"))
        model_run = judgment.get("_model_run")
        source = "model" if model_run else "analyst"

    pillars = []
    for name, res in (score.get("data_pillars") or {}).items():
        pillars.append({
            "name": name, "points": res.get("points"), "maxPoints": res.get("max_points"),
            "componentsScored": res.get("components_scored"),
            "componentsTotal": res.get("components_total"),
            "sectorSuppressed": res.get("sector_suppressed_components") or [],
        })

    judgment_pillars = []
    if judgment:
        for name in ("business_quality", "competitive_advantage", "catalysts",
                     "risk_reward", "management"):
            entry = judgment.get(name) or {}
            judgment_pillars.append({
                "name": name,
                "points": entry.get("points"),
                "justification": entry.get("justification"),
                "source": source,
                "modelRun": {
                    "at": model_run.get("at"),
                    "validationsPassed": model_run.get("checks_passed", []),
                    "attempts": model_run.get("attempts"),
                } if model_run else None,
            })

    # The saved analysis holds the DATA pillars; the judgment file holds the other five.
    # They are written at different times by different processes, so the stored total can be
    # a partial score even when a judgment now exists. Combine them here rather than serving
    # a number that contradicts the judgments shown beside it.
    total = score.get("total_score")
    band = score.get("verdict_band")
    is_complete = score.get("score_is_complete")
    if judgment_pillars and all(jp["points"] is not None for jp in judgment_pillars):
        judgment_points = sum(jp["points"] for jp in judgment_pillars)
        total = round((score.get("data_points_earned") or 0) + judgment_points, 1)
        is_complete = not (score.get("unscorable_data_pillars") or [])
        band = config.band_for_score(total) if is_complete else (
            "INCOMPLETE - some data pillars could not be scored")

    # The two halves of this total are written by different processes at different times:
    # the data pillars when score_stock.py --save last ran, the judgment when judge.py last
    # ran. Adding them is only honest if they describe the same moment. PAYX once served a
    # total built from a data score 44 days older than its judgment, presented as one
    # current number - the same mistake as reading a stale XBRL tag as current.
    freshness = None
    judged_at = model_run.get("at") if model_run else None
    if data_scored_at and judged_at:
        try:
            gap = abs((datetime.fromisoformat(judged_at.replace("Z", "+00:00"))
                       - datetime.fromisoformat(data_scored_at.replace("Z", "+00:00"))).days)
        except ValueError:
            gap = None
        if gap is not None and gap > 14:
            freshness = (
                "The two halves of this score are " + str(gap) + " days apart. The data "
                "pillars were scored on " + data_scored_at[:10] + " and the judgment "
                "pillars on " + judged_at[:10] + ". Re-run "
                "`python scripts/score_stock.py " + tk + " --judge --save` to bring them "
                "into line before relying on the total.")

    return {
        "ticker": tk,
        "total": total,
        "band": band,
        "isComplete": is_complete,
        "judgmentPointsEarned": (sum(jp["points"] for jp in judgment_pillars)
                                 if judgment_pillars and
                                 all(jp["points"] is not None for jp in judgment_pillars)
                                 else None),
        "dataScoredAt": data_scored_at,
        "judgmentAt": judged_at,
        "freshnessWarning": freshness,
        "dataPointsEarned": score.get("data_points_earned"),
        "dataPointsAvailable": score.get("data_points_available"),
        "dataPointsPossible": score.get("data_points_possible"),
        "componentsScored": sum(p["componentsScored"] or 0 for p in pillars),
        "componentsTotal": sum(p["componentsTotal"] or 0 for p in pillars),
        "pillars": pillars,
        "judgmentPillars": judgment_pillars,
        "judgmentSource": source,
        "unscorablePillars": score.get("unscorable_data_pillars") or [],
        "interpretation": score.get("interpretation"),
    }


@app.get("/screens/latest", tags=["screens"])
def latest_screen(limit: int = Query(50, le=500)) -> dict:
    """Most recent screen run, split into well-measured and thinly-measured.

    The split is not cosmetic. A 93% scored on 6 of 16 components is not comparable with an
    81% scored on 15, and ranking them in one list once put the least-measured company top.
    """
    files = sorted(config.SCREENS_DIR.glob("screen_*.csv"))
    if not files:
        raise HTTPException(status_code=404, detail="No screens have been run")
    rows = _read_csv(files[-1])

    def shape(r: dict) -> dict:
        return {
            "ticker": r.get("ticker"), "name": r.get("company_name"),
            "compositePct": _num(r.get("composite_pct")),
            "pointsEarned": _num(r.get("composite_score")),
            "pointsAvailable": _num(r.get("composite_max_available")),
            "componentsScored": int(_num(r.get("components_scored")) or 0),
            "price": _num(r.get("price")),
            "revenueCagrPct": _num(r.get("revenue_cagr_pct")),
            "operatingMarginPct": _num(r.get("operating_margin_pct")),
            "roicPct": _num(r.get("roic_pct")),
            "peRatio": _num(r.get("pe_ratio")),
            "fcfYieldPct": _num(r.get("fcf_yield_pct")),
            "sectorSpecial": r.get("sector_special") or None,
        }

    shaped = [shape(r) for r in rows if r.get("filter_result") == "passed"]
    well = sorted([s for s in shaped if s["componentsScored"] >= 10],
                  key=lambda s: -(s["compositePct"] or 0))
    thin = sorted([s for s in shaped if s["componentsScored"] < 10],
                  key=lambda s: -(s["compositePct"] or 0))
    return {
        "runFile": files[-1].name,
        "wellMeasured": well[:limit],
        "thinlyMeasured": thin[:limit],
        "note": ("thinlyMeasured companies are scored on fewer than 10 of 16 components and "
                 "must NOT be ranked alongside wellMeasured ones"),
    }


@app.get("/predictions", tags=["predictions"])
def get_predictions() -> dict:
    """Every prediction, its latest review, and performance against the benchmark.

    `predictions.csv` is append-only. Nothing here edits it.
    """
    preds = _read_csv(config.PREDICTIONS_CSV)
    reviews = _read_csv(config.PREDICTION_REVIEWS_CSV)

    latest: dict[str, dict] = {}
    for r in reviews:
        key = r["ticker"] + "|" + r["original_prediction_date"]
        if key not in latest or r["review_date"] >= latest[key]["review_date"]:
            latest[key] = r

    out = []
    for p in preds:
        rev = latest.get(p["ticker"] + "|" + p["date"])
        out.append({
            "date": p["date"], "ticker": p["ticker"],
            "entryPrice": _num(p["entry_price"]), "targetPrice": _num(p["target_price"]),
            "horizonMonths": int(_num(p["horizon_months"]) or 0),
            "expectedReturnPct": _num(p["expected_return"]),
            "probPositive": _num(p.get("prob_positive")),
            "probHits20Pct": _num(p.get("prob_20pct")),
            "probLoss": _num(p.get("prob_loss")),
            "convictionScore": _num(p.get("conviction_score")),
            "thesisStatus": p.get("thesis_status"),
            "notes": p.get("notes"),
            "latestReview": {
                "reviewDate": rev["review_date"],
                "priceAtReview": _num(rev["price_at_review"]),
                "pctMoveSinceEntry": _num(rev["pct_move_since_entry"]),
                "pctOfHorizonElapsed": _num(rev["pct_of_horizon_elapsed"]),
                "assumptionsHeld": rev.get("assumptions_held") or None,
                "assumptionsBroken": rev.get("assumptions_broken") or None,
            } if rev else None,
        })

    moves = [o["latestReview"]["pctMoveSinceEntry"] for o in out
             if o["latestReview"] and o["latestReview"]["pctMoveSinceEntry"] is not None]
    summary = None
    if moves:
        ordered = sorted(moves)
        largest = max(moves, key=abs)
        ex = [m for m in moves if m != largest] or moves
        summary = {
            "mean": sum(moves) / len(moves),
            "meanExcludingLargest": sum(ex) / len(ex),
            "median": ordered[len(ordered) // 2],
            "count": len(moves),
            "note": ("Report all three together. One takeover once made the book look 3 points "
                     "ahead of the index when, excluding it, it was 1.6 points behind."),
        }
    return {"predictions": out, "summary": summary}


@app.get("/digests", tags=["digests"])
def list_digests() -> list[dict]:
    out = []
    for p in sorted(config.DAILY_REPORTS_DIR.glob("digest_*.md"), reverse=True):
        date = p.stem.replace("digest_", "")
        first = next((ln.lstrip("# ").strip() for ln in
                      p.read_text(encoding="utf-8").splitlines() if ln.startswith("#")), date)
        out.append({"date": date, "title": first, "sizeBytes": p.stat().st_size})
    return out


@app.get("/digests/{date}", tags=["digests"])
def get_digest(date: str) -> dict:
    p = config.DAILY_REPORTS_DIR / ("digest_" + date + ".md")
    if not p.exists():
        raise HTTPException(status_code=404, detail="No digest for " + date)
    return {"date": date, "markdown": p.read_text(encoding="utf-8")}


@app.get("/macro", tags=["macro"])
def get_macro() -> dict:
    d = _read_json(config.MACRO_DIR / "fred_dashboard.json")["data"]
    series = []
    for sid, s in (d.get("series") or {}).items():
        latest = s.get("latest") or {}
        prior = s.get("prior") or {}
        series.append({
            "id": sid, "description": s.get("description"),
            "latest": latest.get("value"), "latestDate": latest.get("date"),
            "prior": prior.get("value"),
            "change": (latest.get("value") - prior.get("value"))
                      if latest.get("value") is not None and prior.get("value") is not None
                      else None,
        })
    return {"retrievedAt": d.get("retrieved_at_utc"), "series": series}

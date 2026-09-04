"""FRED (Federal Reserve Bank of St. Louis) - official macroeconomic data.

Two access paths, chosen automatically:

  1. NO API KEY (default) - FRED's public CSV endpoint, fredgraph.csv. No registration,
     no key, no quota to manage. This is what runs out of the box.
  2. WITH AN API KEY - set FRED_API_KEY in your environment and the richer JSON API is
     used instead, which also gives series titles, units and update frequency.

Free key (optional): https://fredaccount.stlouisfed.org/apikeys

Macro data does not pick stocks. It sets the backdrop: what the risk-free rate is (which
is what every valuation discounts against), whether credit is tightening, whether the
consumer is cracking. It belongs in the file so that a thesis can be checked against the
world it assumes.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from . import config
from .http_cache import Provenance, fetch, fetch_json, utcnow_iso, FetchError


def _default_start(years_back: int = 10) -> str:
    return (datetime.now() - timedelta(days=365 * years_back)).strftime("%Y-%m-%d")


def series(series_id: str, start: Optional[str] = None, years_back: int = 10,
           refresh: bool = False, verbose: bool = True) -> dict:
    """Fetch one FRED series as a list of {date, value} observations, oldest first."""
    start = start or _default_start(years_back)
    using_key = bool(config.FRED_API_KEY)

    if using_key:
        payload, prov = fetch_json(
            config.FRED_API_URL,
            params={
                "series_id": series_id, "api_key": config.FRED_API_KEY,
                "file_type": "json", "observation_start": start,
            },
            cache_dir=config.FRED_CACHE,
            ttl_hours=config.CACHE_TTL_HOURS["fred"],
            rate_key="fred", rate=8.0, timeout=config.FRED_TIMEOUT_SECONDS,
            refresh=refresh, verbose=verbose,
            source_name="FRED API (St. Louis Fed)", basis="official_stat",
        )
        obs = [
            {"date": o["date"], "value": (None if o["value"] in (".", "")
                                          else float(o["value"]))}
            for o in payload.get("observations", [])
        ]
        access = "FRED JSON API (using FRED_API_KEY)"
    else:
        text, prov = fetch(
            config.FRED_CSV_URL,
            params={"id": series_id, "cosd": start},
            cache_dir=config.FRED_CACHE,
            ttl_hours=config.CACHE_TTL_HOURS["fred"],
            rate_key="fred", rate=8.0, timeout=config.FRED_TIMEOUT_SECONDS,
            refresh=refresh, verbose=verbose,
            source_name="FRED public CSV (St. Louis Fed)", basis="official_stat",
        )
        reader = csv.DictReader(io.StringIO(text))
        fields = reader.fieldnames or []
        if len(fields) < 2:
            raise FetchError("Unexpected FRED CSV shape for " + series_id
                             + ": columns = " + str(fields))
        date_col, value_col = fields[0], fields[1]
        obs = []
        for row in reader:
            raw = (row.get(value_col) or "").strip()
            obs.append({
                "date": row[date_col],
                "value": None if raw in (".", "", "NA") else float(raw),
            })
        access = "FRED public CSV endpoint (no API key required)"

    valid = [o for o in obs if o["value"] is not None]
    latest = valid[-1] if valid else None

    def value_n_ago(n: int) -> Optional[dict]:
        return valid[-1 - n] if len(valid) > n else None

    return {
        "series_id": series_id,
        "description": config.FRED_DEFAULT_SERIES.get(series_id, "(no local description)"),
        "observations": obs,
        "observation_count": len(obs),
        "latest": latest,
        "prior": value_n_ago(1),
        "year_ago": value_n_ago(12),
        "change_since_prior": (
            (latest["value"] - value_n_ago(1)["value"])
            if latest and value_n_ago(1) else None
        ),
        "access_method": access,
        "_basis": "official_stat - published by a U.S. government statistical agency",
        "_provenance": prov.to_dict(),
        "_series_page": "https://fred.stlouisfed.org/series/" + series_id,
    }


def dashboard(series_ids: Optional[list[str]] = None, years_back: int = 10,
              refresh: bool = False, verbose: bool = True) -> dict:
    """Pull the standard macro watchlist in one go."""
    ids = series_ids or list(config.FRED_DEFAULT_SERIES)
    out: dict[str, dict] = {}
    failures: dict[str, str] = {}
    for sid in ids:
        try:
            if verbose:
                print("  [fred] " + sid)
            out[sid] = series(sid, years_back=years_back, refresh=refresh, verbose=verbose)
        except Exception as exc:
            failures[sid] = type(exc).__name__ + ": " + str(exc)
            if verbose:
                print("    [fred] FAILED " + sid + " -> " + str(exc))
    return {
        "retrieved_at_utc": utcnow_iso(),
        "series": out,
        "failed": failures,
        "note": (
            "Macro context only. These figures describe the economy, not any single "
            "company. They are used to sanity-check the discount rate and to notice when "
            "a thesis depends on a macro assumption (rates falling, consumer holding up) "
            "that the data does not support."
        ),
    }


def summarize(dash: dict) -> list[str]:
    """Plain-English one-liners for the digest. States facts, draws no conclusions."""
    lines: list[str] = []
    for sid, data in dash.get("series", {}).items():
        latest = data.get("latest")
        if not latest:
            lines.append(sid + ": " + config.MISSING)
            continue
        desc = data.get("description", sid)
        prior = data.get("prior")
        direction = ""
        if prior and prior.get("value") is not None:
            delta = latest["value"] - prior["value"]
            arrow = "up" if delta > 0 else ("down" if delta < 0 else "flat")
            direction = " (" + arrow + " from " + format(prior["value"], ".2f") + ")"
        lines.append(
            sid + " = " + format(latest["value"], ".2f") + " as of " + latest["date"]
            + direction + " - " + desc
        )
    return lines

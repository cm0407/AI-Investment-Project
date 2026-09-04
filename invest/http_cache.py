"""Polite, cached HTTP with provenance tracking.

Three jobs:
  1. Rate-limit outbound requests so we stay inside the SEC's published limits.
  2. Cache raw responses on disk so re-running a script does not re-hammer a free API.
  3. Stamp everything with where it came from and when, so no figure in this system is
     ever an orphan.

Nothing in this module interprets data. It only moves bytes and records provenance.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

from . import config


# --------------------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------------------
@dataclass
class Provenance:
    """Where a number came from. Attached to every dataset this system produces.

    basis:
        "actual"          - a figure a company actually reported in an SEC filing
        "market"          - an observed market price/volume
        "official_stat"   - a government statistical release (FRED)
        "vendor_estimate" - a third party's forecast (e.g. Yahoo consensus). An OPINION.
        "derived"         - computed by us from the above (the formula is recorded)
        "projected"       - a forward number WE made up under stated assumptions
    """

    source: str
    source_url: str
    retrieved_at_utc: str
    basis: str
    period: Optional[str] = None
    notes: Optional[str] = None
    from_cache: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# --------------------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------------------
class RateLimiter:
    """Simple blocking rate limiter, shared per host."""

    def __init__(self, max_per_second: float):
        self.min_interval = 1.0 / max_per_second if max_per_second > 0 else 0.0
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.monotonic()


_LIMITERS: dict[str, RateLimiter] = {}


def limiter_for(host_key: str, rate: float) -> RateLimiter:
    if host_key not in _LIMITERS:
        _LIMITERS[host_key] = RateLimiter(rate)
    return _LIMITERS[host_key]


# --------------------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------------------
def _cache_key(url: str, params: Optional[dict] = None) -> str:
    raw = url + "|" + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _cache_paths(cache_dir: Path, key: str, suffix: str) -> tuple[Path, Path]:
    return cache_dir / (key + suffix), cache_dir / (key + ".meta.json")


def _cache_is_fresh(meta_path: Path, ttl_hours: float) -> bool:
    if ttl_hours <= 0 or not meta_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        fetched = datetime.strptime(meta["retrieved_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
        fetched = fetched.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    age_hours = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600.0
    return age_hours < ttl_hours


class FetchError(RuntimeError):
    """Raised when a source cannot be reached or returns an error we should not paper over."""


def fetch(
    url: str,
    *,
    cache_dir: Path,
    ttl_hours: float,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    rate_key: str = "default",
    rate: float = 5.0,
    timeout: int = 30,
    max_retries: int = 3,
    binary: bool = False,
    refresh: bool = False,
    source_name: str = "",
    basis: str = "actual",
    verbose: bool = True,
) -> tuple[Any, Provenance]:
    """Fetch a URL with caching, rate limiting, retries and provenance.

    Returns (payload, Provenance). Payload is bytes if binary=True, else text.
    Raises FetchError if the resource cannot be retrieved and no cache exists.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(url, params)
    suffix = ".bin" if binary else ".txt"
    data_path, meta_path = _cache_paths(cache_dir, key, suffix)

    if not refresh and data_path.exists() and _cache_is_fresh(meta_path, ttl_hours):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        payload = data_path.read_bytes() if binary else data_path.read_text(encoding="utf-8")
        prov = Provenance(
            source=meta.get("source", source_name),
            source_url=url,
            retrieved_at_utc=meta["retrieved_at_utc"],
            basis=meta.get("basis", basis),
            notes="served from local cache; re-run with --refresh to force a new pull",
            from_cache=True,
        )
        return payload, prov

    limiter = limiter_for(rate_key, rate)
    last_err: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        limiter.wait()
        try:
            resp = requests.get(url, headers=headers or {}, params=params, timeout=timeout)
            if resp.status_code == 200:
                payload = resp.content if binary else resp.text
                data_path.write_bytes(resp.content) if binary else data_path.write_text(
                    resp.text, encoding="utf-8"
                )
                meta = {
                    "source": source_name,
                    "source_url": resp.url,
                    "retrieved_at_utc": utcnow_iso(),
                    "basis": basis,
                    "http_status": resp.status_code,
                }
                meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                return payload, Provenance(
                    source=source_name,
                    source_url=resp.url,
                    retrieved_at_utc=meta["retrieved_at_utc"],
                    basis=basis,
                    from_cache=False,
                )
            if resp.status_code == 404:
                raise FetchError("404 Not Found: " + url)
            if resp.status_code in (403, 429, 500, 502, 503, 504):
                wait = min(2 ** attempt, 20)
                if verbose:
                    print("    [http] " + str(resp.status_code) + " from " + url
                          + " - backing off " + str(wait) + "s (attempt "
                          + str(attempt) + "/" + str(max_retries) + ")")
                time.sleep(wait)
                last_err = FetchError("HTTP " + str(resp.status_code) + " for " + url)
                continue
            raise FetchError("HTTP " + str(resp.status_code) + " for " + url)
        except FetchError:
            raise
        except Exception as exc:  # network errors, timeouts, DNS
            last_err = exc
            wait = min(2 ** attempt, 20)
            if verbose:
                print("    [http] " + type(exc).__name__ + " on " + url
                      + " - retrying in " + str(wait) + "s")
            time.sleep(wait)

    # Every retry failed. A stale cache beats inventing data - but say so loudly.
    if data_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        payload = data_path.read_bytes() if binary else data_path.read_text(encoding="utf-8")
        if verbose:
            print("    [http] WARNING: live fetch failed; using STALE cache from "
                  + str(meta.get("retrieved_at_utc", "unknown time")))
        return payload, Provenance(
            source=meta.get("source", source_name),
            source_url=url,
            retrieved_at_utc=meta.get("retrieved_at_utc", "unknown"),
            basis=basis,
            notes="STALE CACHE - live fetch failed, data may be out of date",
            from_cache=True,
        )

    raise FetchError("Could not fetch " + url + " after " + str(max_retries)
                     + " attempts: " + str(last_err))


def fetch_json(url: str, **kwargs) -> tuple[Any, Provenance]:
    """fetch() plus JSON parsing."""
    text, prov = fetch(url, **kwargs)
    try:
        return json.loads(text), prov
    except json.JSONDecodeError as exc:
        raise FetchError("Response from " + url + " was not valid JSON: " + str(exc))


# --------------------------------------------------------------------------------------
# Writing datasets with provenance attached
# --------------------------------------------------------------------------------------
def write_dataset(path: Path, payload: dict, provenance: list[Provenance] | Provenance,
                  assumptions: Optional[list[str]] = None) -> Path:
    """Write a JSON dataset with a mandatory provenance block."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(provenance, Provenance):
        provenance = [provenance]
    doc = {
        "_meta": {
            "generated_at_utc": utcnow_iso(),
            "generator": "INVEST v" + __import__("invest").__version__,
            "provenance": [p.to_dict() for p in provenance],
            "assumptions": assumptions or [],
            "disclaimer": (
                "Research output, not financial advice. Figures marked basis=vendor_estimate "
                "or basis=projected are forecasts, not reported facts."
            ),
        },
        "data": payload,
    }
    path.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    return path

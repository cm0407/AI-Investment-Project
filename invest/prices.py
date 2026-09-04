"""Market price data via yfinance (Yahoo Finance).

IMPORTANT BOUNDARY: this module supplies *market* data only - price, volume, returns,
volatility - plus a small set of clearly-labelled vendor figures. It is deliberately NOT
the source of fundamentals. Revenue, margins, debt and share counts come from SEC filings
(see sec_edgar.py), because Yahoo is an unofficial, unaudited, occasionally-wrong
aggregator and CLAUDE.md puts filings first.

Anything sourced here is tagged basis="market" (observed prices) or
basis="vendor_estimate" (someone's forecast, e.g. forward P/E). A vendor estimate is an
opinion with a number attached, and is never allowed into an intrinsic-value calculation.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Optional

from . import config
from .http_cache import Provenance, utcnow_iso

_YF_URL = "https://finance.yahoo.com/quote/"


def _import_yf():
    try:
        import yfinance as yf
        return yf
    except ImportError as exc:
        raise RuntimeError(
            "yfinance is not installed. Run: python -m pip install -r requirements.txt"
        ) from exc


def _clean(x: Any) -> Optional[float]:
    """Coerce to float, mapping NaN/None/garbage to None so it renders as UNAVAILABLE."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def price_history(ticker: str, period: str = "2y", interval: str = "1d",
                  verbose: bool = True):
    """Daily OHLCV history as a pandas DataFrame. Raises if Yahoo returns nothing."""
    yf = _import_yf()
    t = yf.Ticker(ticker)
    hist = t.history(period=period, interval=interval, auto_adjust=True)
    if hist is None or hist.empty:
        raise RuntimeError(
            "No price history returned for '" + ticker + "'. The ticker may be wrong, "
            "delisted, or Yahoo may be rate-limiting. No data means no analysis."
        )
    return hist


def quote(ticker: str, period: str = "2y", verbose: bool = True) -> dict:
    """Current price plus computed return/volatility statistics.

    Everything here is either an observed market fact or arithmetic on observed prices.
    The formula for each derived figure is stated in the output.
    """
    hist = price_history(ticker, period=period, verbose=verbose)
    close = hist["Close"].dropna()
    last = float(close.iloc[-1])
    last_date = close.index[-1].strftime("%Y-%m-%d")

    def ret_over(days: int) -> Optional[float]:
        if len(close) <= days:
            return None
        prior = float(close.iloc[-1 - days])
        return (last / prior - 1.0) * 100.0 if prior else None

    # ~21 trading days a month, ~252 a year.
    returns = {
        "1_week_pct": ret_over(5),
        "1_month_pct": ret_over(21),
        "3_month_pct": ret_over(63),
        "6_month_pct": ret_over(126),
        "1_year_pct": ret_over(252),
    }

    daily_ret = close.pct_change().dropna()
    ann_vol = float(daily_ret.std() * (252 ** 0.5) * 100.0) if len(daily_ret) > 20 else None

    window = close.tail(252) if len(close) >= 252 else close
    hi_52 = float(window.max())
    lo_52 = float(window.min())

    # Max drawdown over the loaded window: the worst peak-to-trough fall.
    running_max = close.cummax()
    drawdown = (close / running_max - 1.0) * 100.0
    max_dd = float(drawdown.min())

    ma50 = float(close.tail(50).mean()) if len(close) >= 50 else None
    ma200 = float(close.tail(200).mean()) if len(close) >= 200 else None

    return {
        "ticker": ticker.upper(),
        "price": last,
        "price_date": last_date,
        "currency": "USD (assumed - verify for non-US listings)",
        "returns": returns,
        "annualized_volatility_pct": ann_vol,
        "52w_high": hi_52,
        "52w_low": lo_52,
        "pct_below_52w_high": ((last / hi_52 - 1.0) * 100.0) if hi_52 else None,
        "pct_above_52w_low": ((last / lo_52 - 1.0) * 100.0) if lo_52 else None,
        "max_drawdown_pct_in_window": max_dd,
        "ma_50": ma50,
        "ma_200": ma200,
        "avg_daily_volume_3m": (float(hist["Volume"].tail(63).mean())
                                if "Volume" in hist else None),
        "history_rows": len(close),
        "history_start": close.index[0].strftime("%Y-%m-%d"),
        "_basis": {
            "price": "market - last close observed by Yahoo Finance",
            "returns": "derived - (price_now / price_then - 1) using adjusted closes",
            "annualized_volatility_pct": "derived - stdev(daily returns) * sqrt(252)",
            "max_drawdown_pct_in_window": "derived - worst peak-to-trough decline in window",
        },
        "_provenance": Provenance(
            source="Yahoo Finance via yfinance",
            source_url=_YF_URL + ticker.upper(),
            retrieved_at_utc=utcnow_iso(),
            basis="market",
            period=period,
            notes="Third-party market data. Prices are adjusted for splits and dividends.",
        ).to_dict(),
    }


# Yahoo fields we accept, split by how much they can be trusted.
_VENDOR_FACTUAL = [
    "shortName", "longName", "sector", "industry", "country", "fullTimeEmployees",
    "marketCap", "sharesOutstanding", "floatShares", "beta",
    "trailingPE", "priceToBook", "enterpriseValue", "dividendYield", "payoutRatio",
    "enterpriseToEbitda", "enterpriseToRevenue", "priceToSalesTrailing12Months",
    "totalCash", "totalDebt", "freeCashflow", "operatingCashflow", "returnOnEquity",
    "profitMargins", "grossMargins", "operatingMargins", "heldPercentInstitutions",
    "heldPercentInsiders", "shortPercentOfFloat",
]
_VENDOR_ESTIMATES = [
    "forwardPE", "forwardEps", "pegRatio", "targetMeanPrice", "targetHighPrice",
    "targetLowPrice", "numberOfAnalystOpinions", "recommendationKey",
    "earningsGrowth", "revenueGrowth", "earningsQuarterlyGrowth",
]


def vendor_snapshot(ticker: str, verbose: bool = True) -> dict:
    """Yahoo's own summary fields, split into 'observed-ish' and 'someone's forecast'.

    Why bother, if SEC data is better? Two reasons: sector/industry labels for screening,
    and cross-checks. If Yahoo's market cap and our (SEC shares x market price) disagree
    badly, something is wrong and we want to see it.
    """
    yf = _import_yf()
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception as exc:
        if verbose:
            print("    [prices] Yahoo .info failed for " + ticker + ": " + str(exc))
        info = {}

    factual = {k: _clean(info.get(k)) if isinstance(info.get(k), (int, float))
               else info.get(k) for k in _VENDOR_FACTUAL if k in info}
    estimates = {k: _clean(info.get(k)) if isinstance(info.get(k), (int, float))
                 else info.get(k) for k in _VENDOR_ESTIMATES if k in info}

    return {
        "ticker": ticker.upper(),
        "vendor_reported": factual,
        "vendor_estimates": estimates,
        "_warning": (
            "vendor_estimates are ANALYST FORECASTS supplied by a third party, not facts. "
            "Per CLAUDE.md an analyst price target is never intrinsic value. Fundamentals "
            "used for valuation come from SEC filings, not from this block."
        ),
        "_provenance": Provenance(
            source="Yahoo Finance via yfinance (.info)",
            source_url=_YF_URL + ticker.upper(),
            retrieved_at_utc=utcnow_iso(),
            basis="vendor_estimate",
            notes="Unofficial API. Fields appear and disappear without notice.",
        ).to_dict(),
    }


def batch_prices(tickers: list[str], verbose: bool = True) -> dict[str, Optional[float]]:
    """Last close for many tickers in one download - used by the screener.

    Falls back to per-ticker requests if the bulk download misbehaves.
    """
    yf = _import_yf()
    out: dict[str, Optional[float]] = {}
    try:
        data = yf.download(tickers, period="5d", interval="1d", progress=False,
                           auto_adjust=True, threads=True)
        if data is None or data.empty:
            raise RuntimeError("empty batch download")
        if len(tickers) == 1:
            closes = data["Close"].dropna()
            out[tickers[0].upper()] = float(closes.iloc[-1]) if len(closes) else None
        else:
            close_block = data["Close"]
            for tk in tickers:
                try:
                    series = close_block[tk].dropna()
                    out[tk.upper()] = float(series.iloc[-1]) if len(series) else None
                except Exception:
                    out[tk.upper()] = None
    except Exception as exc:
        if verbose:
            print("    [prices] batch download failed (" + str(exc)
                  + "); falling back to one-by-one")
        for tk in tickers:
            try:
                out[tk.upper()] = float(price_history(tk, period="5d")["Close"].iloc[-1])
            except Exception:
                out[tk.upper()] = None
    return out


def market_cap_from_filings(price: float, shares_outstanding: Optional[float]) -> Optional[float]:
    """Market cap computed the way CLAUDE.md prefers: market price x SEC-filed share count.

    Yahoo's own marketCap is kept only as a cross-check.
    """
    if price is None or shares_outstanding is None:
        return None
    return price * shares_outstanding

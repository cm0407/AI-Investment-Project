"""Central configuration. Every path and knob lives here so nothing is hard-coded elsewhere."""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------------------
# Local settings (.env)
# --------------------------------------------------------------------------------------
def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from a .env file into the environment.

    Deliberately tiny and dependency-free. Real environment variables always win, so
    exporting SEC_CONTACT_EMAIL in your shell overrides whatever the file says.

    The .env file is gitignored. It is where anything personal lives - your contact
    address, and an optional FRED key - so that the committed code can be published
    without carrying your details into a public repository.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")

MEMORY_DIR = ROOT / "memory"
PORTFOLIO_DIR = ROOT / "portfolio"
REPORTS_DIR = ROOT / "reports"
DAILY_REPORTS_DIR = REPORTS_DIR / "daily"
SCREEN_REPORTS_DIR = REPORTS_DIR / "screens"
RESEARCH_DIR = ROOT / "research"
THESES_DIR = RESEARCH_DIR / "theses"
NOTES_DIR = ROOT / "notes"
DOCS_DIR = ROOT / "docs"
LOGS_DIR = ROOT / "logs"

DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
SEC_CACHE = CACHE_DIR / "sec"
PRICE_CACHE = CACHE_DIR / "prices"
FRED_CACHE = CACHE_DIR / "fred"
FUNDAMENTALS_DIR = DATA_DIR / "fundamentals"
PRICES_DIR = DATA_DIR / "prices"
MACRO_DIR = DATA_DIR / "macro"
UNIVERSE_DIR = DATA_DIR / "universe"
SCREENS_DIR = DATA_DIR / "screens"

PREDICTIONS_CSV = MEMORY_DIR / "predictions.csv"
PREDICTION_REVIEWS_CSV = MEMORY_DIR / "prediction_reviews.csv"
INVESTMENT_LOG_CSV = PORTFOLIO_DIR / "investment_log.csv"
RESEARCH_STATE = MEMORY_DIR / "research_state.md"
LESSONS_LEARNED = MEMORY_DIR / "lessons_learned.md"
REJECTED_STOCKS = MEMORY_DIR / "rejected_stocks.md"
PREFERENCES_FILE = NOTES_DIR / "my_investing_preferences.md"

STARTER_UNIVERSE = UNIVERSE_DIR / "starter_universe.csv"
FULL_UNIVERSE = UNIVERSE_DIR / "sec_universe.csv"

ALL_DIRS = [
    MEMORY_DIR, PORTFOLIO_DIR, REPORTS_DIR, DAILY_REPORTS_DIR, SCREEN_REPORTS_DIR,
    RESEARCH_DIR, THESES_DIR, NOTES_DIR, DOCS_DIR, LOGS_DIR, DATA_DIR, CACHE_DIR,
    SEC_CACHE, PRICE_CACHE, FRED_CACHE, FUNDAMENTALS_DIR, PRICES_DIR, MACRO_DIR,
    UNIVERSE_DIR, SCREENS_DIR,
]


def ensure_dirs() -> None:
    """Create any missing project directory. Safe to call repeatedly."""
    for d in ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------------------
# SEC EDGAR
# --------------------------------------------------------------------------------------
# The SEC requires a declared User-Agent identifying who is making the request.
# Reference: https://www.sec.gov/os/webmaster-faq#developers
#
# Set your real address in the .env file (gitignored), NOT here - this default is a
# placeholder so that the committed code carries nobody's personal email:
#     SEC_CONTACT_EMAIL=you@example.com
# Copy .env.example to .env to get started. Leaving the placeholder in place will make
# selftest.py fail, because the SEC asks for a genuine contact address.
SEC_PLACEHOLDER_EMAIL = "your-email@example.com"
SEC_CONTACT_EMAIL = os.environ.get("SEC_CONTACT_EMAIL", SEC_PLACEHOLDER_EMAIL)
SEC_USER_AGENT = "INVEST-Research/1.0 (" + SEC_CONTACT_EMAIL + ")"
SEC_CONTACT_IS_PLACEHOLDER = SEC_CONTACT_EMAIL == SEC_PLACEHOLDER_EMAIL

SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json, text/html, */*",
}

# SEC's published ceiling is 10 requests/second. We deliberately run well under it.
SEC_MAX_REQUESTS_PER_SECOND = 5.0
SEC_TIMEOUT_SECONDS = 30
SEC_MAX_RETRIES = 3

SEC_BASE = "https://data.sec.gov"
SEC_WWW = "https://www.sec.gov"
SEC_TICKER_MAP_URL = SEC_WWW + "/files/company_tickers.json"
SEC_TICKER_EXCHANGE_URL = SEC_WWW + "/files/company_tickers_exchange.json"

# --------------------------------------------------------------------------------------
# FRED
# --------------------------------------------------------------------------------------
# An API key is OPTIONAL. Without one we use FRED's public CSV download endpoint, which
# needs no registration. Set FRED_API_KEY in your environment to use the JSON API instead.
FRED_API_KEY = os.environ.get("FRED_API_KEY", "").strip()
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_SERIES_INFO_URL = "https://api.stlouisfed.org/fred/series"
FRED_TIMEOUT_SECONDS = 30

# The macro series the system watches by default, with plain-English labels for the digest.
FRED_DEFAULT_SERIES = {
    "DGS10": "10-year Treasury yield (%) - the risk-free rate everything is priced against",
    "DGS2": "2-year Treasury yield (%)",
    "T10Y2Y": "10y minus 2y spread - negative has historically preceded recessions",
    "FEDFUNDS": "Fed funds rate (%) - the Federal Reserve policy rate",
    "CPIAUCSL": "Consumer Price Index - the headline inflation index",
    "UNRATE": "Unemployment rate (%)",
    "PAYEMS": "Total nonfarm payrolls (thousands of jobs)",
    "GDPC1": "Real GDP (inflation-adjusted, billions of 2017 dollars)",
    "INDPRO": "Industrial production index",
    "UMCSENT": "University of Michigan consumer sentiment",
    "BAMLH0A0HYM2": "High-yield bond spread - a live gauge of credit stress",
    "MORTGAGE30US": "30-year fixed mortgage rate (%)",
}

# --------------------------------------------------------------------------------------
# Cache time-to-live, in hours. Re-running a script after the TTL expires refetches.
# Pass --refresh to any script to force a fresh pull regardless of TTL.
# --------------------------------------------------------------------------------------
CACHE_TTL_HOURS = {
    "sec_facts": 24.0,        # filings change only when a company files
    "sec_submissions": 12.0,
    "sec_tickers": 168.0,     # the ticker->CIK map changes slowly
    "sec_filing_doc": 720.0,  # an individual filed document never changes once filed
    "prices": 4.0,
    "fred": 12.0,
    "vendor_info": 12.0,
}

# --------------------------------------------------------------------------------------
# Valuation assumptions. These are OUR assumptions, not facts. They are surfaced in every
# report so the reader can disagree with them.
# --------------------------------------------------------------------------------------
DCF_DEFAULTS = {
    "discount_rate": 0.10,     # 10% required return on equity
    "terminal_growth": 0.025,  # 2.5% perpetual growth, ~long-run nominal GDP
    "projection_years": 10,
    "fade_to_terminal": True,  # growth fades linearly toward terminal over the window
    "margin_of_safety": 0.25,  # we want to buy 25% below our estimate of fair value
}

# Scoring weights, straight from CLAUDE.md. Total = 100.
SCORE_WEIGHTS = {
    "business_quality": 15,
    "growth": 15,
    "valuation": 15,
    "financial_strength": 10,
    "free_cash_flow": 10,
    "competitive_advantage": 10,
    "catalysts": 10,
    "risk_reward": 10,
    "management": 5,
}

# Which pillars a machine can score from filings alone, and which need an analyst read.
# Being explicit about this is the point: the script will NOT fake the judgment pillars.
DATA_SCORED_PILLARS = ["growth", "valuation", "financial_strength", "free_cash_flow"]
JUDGMENT_PILLARS = ["business_quality", "competitive_advantage", "catalysts",
                    "risk_reward", "management"]

SCORE_BANDS = [
    (90, 100, "EXCEPTIONAL"),
    (80, 89, "STRONG"),
    (70, 79, "WORTH MONITORING"),
    (60, 69, "SPECULATIVE / INCOMPLETE"),
    (0, 59, "REJECT"),
]

MISSING = "DATA UNAVAILABLE OR UNVERIFIED"


def band_for_score(score: float) -> str:
    """Return the CLAUDE.md verdict band for a 0-100 score."""
    for lo, hi, label in SCORE_BANDS:
        if lo <= score <= hi:
            return label
    return "OUT OF RANGE"

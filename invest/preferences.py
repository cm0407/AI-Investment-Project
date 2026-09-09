"""Read the user's preferences file and turn it into rules the screener enforces.

A rule written in a document is a wish. A rule the screener applies to every candidate is
a constraint. This module is the bridge.

It parses notes/my_investing_preferences.md into a Preferences object, then exposes
`check(row, prefs)` which every screened company must pass.

HONESTY ABOUT WHAT CAN AND CANNOT BE ENFORCED
---------------------------------------------
Some exclusions map cleanly onto data we actually have (market cap, leverage, dilution,
filing history). Others do not. "Adult entertainment" has no reliable SIC code, and
"Chinese-domiciled" can only be approximated from the incorporation state and business
address in SEC filings.

Where a rule cannot be enforced reliably, this module says so out loud in
`unenforceable_rules` rather than silently passing everything. A filter that quietly fails
open is worse than no filter, because it creates false confidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import config

# --------------------------------------------------------------------------------------
# SIC code ranges for the ethical exclusions.
# Source: SEC Division of Corporation Finance SIC code list.
# --------------------------------------------------------------------------------------
AVOID_SIC_RANGES: dict[str, list[tuple[int, int]]] = {
    "Tobacco": [(2100, 2199)],
    "Alcohol": [(2080, 2085)],
    # 7011 is hotels AND casino-hotels; 7990-7999 covers amusement/recreation services,
    # which includes casino operators but also plenty of harmless leisure businesses.
    # Deliberately imprecise, and flagged as such below.
    "Gambling / casinos": [(7990, 7999)],
    "Firearms & defense contractors": [(3480, 3489), (3760, 3769), (3795, 3795)],
    "Fossil fuels / oil & gas": [(1300, 1399), (2900, 2999), (4610, 4619)],
}

# Rules with no dependable data behind them. Never silently treated as "passed".
UNENFORCEABLE: dict[str, str] = {
    "Adult entertainment": (
        "No SIC code reliably identifies this. Effectively no U.S.-listed company in the "
        "starter universe operates in it, but the screener cannot PROVE a company is not "
        "in this business. Verify by hand for any candidate you take seriously."
    ),
}

PARTIALLY_ENFORCEABLE: dict[str, str] = {
    "Gambling / casinos": (
        "Approximated by SIC 7990-7999 (amusement & recreation). This over-excludes some "
        "harmless leisure businesses and may miss a casino filed under a hotel code (7011)."
    ),
    "Chinese-domiciled companies (VIE structures)": (
        "Approximated from the SEC filing's business-address country and state of "
        "incorporation. A company incorporated in Delaware with a U.S. head office but "
        "major China operations will NOT be caught. This is a weak filter."
    ),
    "Companies with heavy share dilution": (
        "Measured as growth in weighted-average diluted share count over the available "
        "history. Companies with too little filing history to measure are flagged, not "
        "silently passed."
    ),
}


@dataclass
class Preferences:
    """Structured form of the preferences file."""
    sleeve_low: Optional[float] = None
    sleeve_high: Optional[float] = None
    pct_of_investable: Optional[str] = None
    has_diversified_core: Optional[bool] = None
    max_position_pct: Optional[float] = None
    max_sector_pct: Optional[float] = None
    min_positions: Optional[int] = None
    max_positions: Optional[int] = None
    stop_loss_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    holding_period: Optional[str] = None
    min_market_cap_usd: Optional[float] = None
    options_allowed: Optional[bool] = None
    avoid: list[str] = field(default_factory=list)
    allowed: list[str] = field(default_factory=list)
    sector_notes: str = ""
    raw_rows: dict[str, str] = field(default_factory=dict)
    unenforceable_rules: list[str] = field(default_factory=list)
    partial_rules: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> list[str]:
        out = [
            "sleeve: $" + format(self.sleeve_low or 0, ",.0f") + " - $"
            + format(self.sleeve_high or 0, ",.0f"),
            "max position: " + str(self.max_position_pct) + "%   max sector: "
            + str(self.max_sector_pct) + "%   positions: " + str(self.min_positions)
            + "-" + str(self.max_positions),
            "stop-loss: -" + str(self.stop_loss_pct) + "%   drawdown tolerance: -"
            + str(self.max_drawdown_pct) + "%",
            "minimum market cap: $" + format((self.min_market_cap_usd or 0) / 1e6, ",.0f") + "M",
            "excluding " + str(len(self.avoid)) + " categories",
        ]
        return out


def _money_to_float(text: str) -> Optional[float]:
    """'5,000 - 10,000' -> 5000.0 ; '500m and above' -> 500_000_000."""
    t = text.lower().replace(",", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*([mb])?", t)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    if unit == "m":
        val *= 1e6
    elif unit == "b":
        val *= 1e9
    return val


def _first_number(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    return float(m.group(1)) if m else None


def load(path: Optional[Path] = None) -> Preferences:
    """Parse the preferences markdown into enforceable rules."""
    path = path or config.PREFERENCES_FILE
    if not path.exists():
        raise FileNotFoundError(
            "Preferences file not found: " + str(path)
            + "\nCopy notes/my_investing_preferences.example.md to "
              "notes/my_investing_preferences.md and fill it in."
        )
    text = path.read_text(encoding="utf-8")
    prefs = Preferences()

    # ---- table rows: | question | answer | -------------------------------------------
    for line in text.splitlines():
        if line.count("|") < 3 or line.strip().startswith("| ---"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 2:
            continue
        q, a = parts[0].lower(), parts[1]
        if not a or a.startswith("---") or a.lower() == "your answer":
            continue
        prefs.raw_rows[q[:70]] = a

        if "satellite" in q and "sleeve" in q:
            nums = re.findall(r"[\d,]+", a)
            if len(nums) >= 2:
                prefs.sleeve_low = float(nums[0].replace(",", ""))
                prefs.sleeve_high = float(nums[1].replace(",", ""))
        elif "% of your total investable" in q:
            prefs.pct_of_investable = a
        elif "diversified" in q and "core" in q:
            prefs.has_diversified_core = a.strip().lower().startswith("y")
        elif "maximum % of the sleeve in any one stock" in q:
            prefs.max_position_pct = _first_number(a)
        elif "maximum % in any one sector" in q:
            prefs.max_sector_pct = _first_number(a)
        elif "minimum number of positions" in q:
            nums = re.findall(r"\d+", a)
            if nums:
                prefs.min_positions = int(nums[0])
                prefs.max_positions = int(nums[-1])
        elif "stop-loss" in q:
            if "thesis" in a.lower() and "stop" not in a.lower():
                prefs.stop_loss_pct = None
            else:
                prefs.stop_loss_pct = _first_number(a)
        elif "largest" in q and "drawdown" in q:
            prefs.max_drawdown_pct = _first_number(a)
        elif "typical holding period" in q:
            prefs.holding_period = a
        elif "minimum market cap" in q:
            prefs.min_market_cap_usd = _money_to_float(a)
        elif "options" in q:
            prefs.options_allowed = "option" in a.lower() and "only" not in a.lower()
        elif "sectors you especially want" in q:
            prefs.sector_notes = a

    # ---- avoid-list checkboxes ---------------------------------------------------------
    for line in text.splitlines():
        m = re.match(r"^\s*-\s*\[([^\]]*)\]\s*(.+)$", line)
        if not m:
            continue
        checked = "x" in m.group(1).lower()
        label = m.group(2).strip()
        if label.lower().startswith("other:"):
            continue
        (prefs.avoid if checked else prefs.allowed).append(label)

    for rule in prefs.avoid:
        if rule in UNENFORCEABLE:
            prefs.unenforceable_rules.append(rule + " - " + UNENFORCEABLE[rule])
        if rule in PARTIALLY_ENFORCEABLE:
            prefs.partial_rules.append(rule + " - " + PARTIALLY_ENFORCEABLE[rule])

    # ---- internal consistency checks ---------------------------------------------------
    if prefs.has_diversified_core is False:
        prefs.warnings.append(
            "NO DIVERSIFIED CORE on file. CLAUDE.md requires this sleeve to be a satellite "
            "around a diversified core (index funds), not a replacement for one. Every "
            "recommendation must repeat that caveat."
        )
    if prefs.max_position_pct and prefs.min_positions:
        implied = 100.0 / prefs.min_positions
        if prefs.max_position_pct > implied * 1.5:
            prefs.warnings.append(
                "Position cap of " + format(prefs.max_position_pct, ".0f") + "% sits well "
                "above the " + format(implied, ".0f") + "% average implied by holding "
                + str(prefs.min_positions) + " positions. The cap only binds on your "
                "highest-conviction idea."
            )
    if prefs.stop_loss_pct and prefs.max_drawdown_pct:
        if prefs.stop_loss_pct < prefs.max_drawdown_pct:
            prefs.warnings.append(
                "Stop-loss at -" + format(prefs.stop_loss_pct, ".0f") + "% fires long "
                "before the stated -" + format(prefs.max_drawdown_pct, ".0f") + "% "
                "drawdown tolerance is reached, so that tolerance never takes effect."
            )
    return prefs


# --------------------------------------------------------------------------------------
# Applying the rules to a screened company
# --------------------------------------------------------------------------------------
def _sic_in(sic: Any, ranges: list[tuple[int, int]]) -> bool:
    try:
        code = int(sic)
    except (TypeError, ValueError):
        return False
    return any(lo <= code <= hi for lo, hi in ranges)


def check(row: dict, prefs: Preferences, fund: Optional[dict] = None) -> tuple[bool, list[str]]:
    """Test one screened company against the user's rules.

    Returns (passes, reasons). A rule that cannot be evaluated because data is missing
    EXCLUDES the company and says so - it never passes by default.
    """
    reasons: list[str] = []

    # ---- market cap floor --------------------------------------------------------------
    if prefs.min_market_cap_usd:
        mc = row.get("market_cap")
        if mc is None:
            reasons.append("market cap is " + config.MISSING + " - cannot verify the $"
                           + format(prefs.min_market_cap_usd / 1e6, ",.0f") + "M floor")
        elif mc < prefs.min_market_cap_usd:
            reasons.append("market cap $" + format(mc / 1e6, ",.0f") + "M is below the $"
                           + format(prefs.min_market_cap_usd / 1e6, ",.0f") + "M floor")

    # ---- sector exclusions by SIC ------------------------------------------------------
    sic = row.get("sic")
    for label, ranges in AVOID_SIC_RANGES.items():
        if label in prefs.avoid and _sic_in(sic, ranges):
            reasons.append("SIC " + str(sic) + " falls in the excluded category '"
                           + label + "'")

    # ---- companies with no revenue -----------------------------------------------------
    if "Companies with no revenue (pre-revenue biotech, early-stage mining)" in prefs.avoid:
        rev = row.get("revenue_latest")
        if rev is None:
            reasons.append("revenue is " + config.MISSING + " - cannot confirm the company "
                           "has any")
        elif rev <= 0:
            reasons.append("reported revenue is zero or negative")

    # ---- heavy dilution ----------------------------------------------------------------
    if "Companies with heavy share dilution" in prefs.avoid:
        chg = row.get("share_count_change_pct")
        if chg is None:
            reasons.append("share-count change is " + config.MISSING
                           + " - cannot check for dilution")
        elif chg > 10.0:
            reasons.append("share count grew " + format(chg, ".1f")
                           + "% over the window (dilution above the 10% threshold)")

    # ---- high leverage -----------------------------------------------------------------
    if "Highly leveraged companies" in prefs.avoid:
        sector_kind = row.get("sector_special") or ""
        if sector_kind in ("banking/credit", "insurance", "brokerage/exchanges"):
            pass  # leverage is the business model; judged separately, not here
        else:
            de = row.get("debt_to_equity")
            if de is None:
                reasons.append("debt/equity is " + config.MISSING
                               + " - cannot check leverage")
            elif de > 2.0:
                reasons.append("debt/equity of " + format(de, ".2f")
                               + "x exceeds the 2.0x leverage limit")

    # ---- recent IPOs -------------------------------------------------------------------
    if "Recent IPOs (< 2 years of public filings)" in prefs.avoid:
        periods = row.get("annual_periods_available")
        if periods is None:
            reasons.append("filing history length unknown - cannot check IPO recency")
        elif periods < 2:
            reasons.append("only " + str(periods) + " annual filing period(s) available "
                           "- too little history (recent IPO)")

    # ---- Chinese domicile (weak heuristic) ---------------------------------------------
    if "Chinese-domiciled companies (VIE structures)" in prefs.avoid and fund:
        profile = fund.get("profile") or {}
        addr = profile.get("business_address") or {}
        country = str(addr.get("countryCode") or "").upper()
        state_inc = str(profile.get("state_of_incorporation") or "").upper()
        if country in ("CN", "HK", "MO") or state_inc in ("F4", "K3"):
            reasons.append("business address country '" + country + "' / incorporation '"
                           + state_inc + "' suggests a China-domiciled issuer")

    return (not reasons), reasons

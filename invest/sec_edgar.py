"""SEC EDGAR client - the authoritative source for U.S. company fundamentals.

Free, no API key, no rate-limit tier. The SEC asks two things of us:
  1. Declare a User-Agent with a real contact email  (config.SEC_USER_AGENT)
  2. Stay under 10 requests/second                   (we run at 5)

Endpoints used
--------------
  https://www.sec.gov/files/company_tickers.json                 ticker -> CIK map
  https://data.sec.gov/submissions/CIK##########.json            filing history, SIC, exchange
  https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json  every XBRL fact ever filed
  https://data.sec.gov/api/xbrl/companyconcept/.../<tag>.json    one tag's full history

Design principle
----------------
US-GAAP lets companies tag the same economic concept differently, and lets them omit tags
that do not apply to their industry (a bank reports no "GrossProfit" and no capital
expenditure). So every concept here is a PRIORITISED LIST of candidate tags, and when none
of them are present we return None, which downstream renders as
"DATA UNAVAILABLE OR UNVERIFIED". We never substitute zero for missing.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from . import config
from .http_cache import Provenance, fetch, fetch_json, FetchError

_SEC_FETCH = dict(
    headers=config.SEC_HEADERS,
    rate_key="sec",
    rate=config.SEC_MAX_REQUESTS_PER_SECOND,
    timeout=config.SEC_TIMEOUT_SECONDS,
    max_retries=config.SEC_MAX_RETRIES,
    source_name="SEC EDGAR",
    basis="actual",
)


# --------------------------------------------------------------------------------------
# Concept dictionaries: ordered candidate US-GAAP tags per economic concept
# --------------------------------------------------------------------------------------
DURATION_CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "RevenuesNetOfInterestExpense",          # banks
        "InterestAndDividendIncomeOperating",    # banks fallback
    ],
    "cost_of_revenue": [
        "CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": [
        "OperatingIncomeLoss",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
    "eps_basic": ["EarningsPerShareBasic", "EarningsPerShareBasicAndDiluted"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsForCapitalImprovements",
        "PaymentsToAcquireOtherPropertyPlantAndEquipment",
    ],
    "rnd_expense": ["ResearchAndDevelopmentExpense"],
    "sga_expense": [
        "SellingGeneralAndAdministrativeExpense",
        "GeneralAndAdministrativeExpense",
    ],
    "interest_expense": [
        "InterestExpense", "InterestExpenseDebt", "InterestIncomeExpenseNet",
    ],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
    "dividends_paid": [
        "PaymentsOfDividendsCommonStock", "PaymentsOfDividends",
        "PaymentsOfDividendsMinorityInterest",
    ],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "stock_comp": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "shares_diluted_wa": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasicAndDiluted",
    ],
    "shares_basic_wa": ["WeightedAverageNumberOfSharesOutstandingBasic"],
}

INSTANT_CONCEPTS: dict[str, list[str]] = {
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "CashAndDueFromBanks",
    ],
    "short_term_investments": [
        "ShortTermInvestments", "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
        "OtherShortTermInvestments",
    ],
    "total_assets": ["Assets"],
    "current_assets": ["AssetsCurrent"],
    "total_liabilities": ["Liabilities"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "long_term_debt": [
        "LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations",
    ],
    "short_term_debt": [
        "LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings",
        "OtherShortTermBorrowings",
    ],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "inventory": ["InventoryNet"],
    "goodwill": ["Goodwill"],
    "intangibles": ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
    "ppe_net": ["PropertyPlantAndEquipmentNet"],
    "shares_outstanding": [
        "CommonStockSharesOutstanding", "CommonStockSharesIssued",
    ],
}

# dei taxonomy - cover-page share count, the most current share number in the filings
DEI_CONCEPTS: dict[str, list[str]] = {
    "shares_outstanding_dei": ["EntityCommonStockSharesOutstanding"],
    "public_float": ["EntityPublicFloat"],
}


@dataclass
class Fact:
    """One reported XBRL figure with everything needed to trace it back to a filing."""
    concept: str
    tag: str
    taxonomy: str
    value: float
    unit: str
    period_start: Optional[str]
    period_end: str
    fiscal_year: Optional[int]
    fiscal_period: Optional[str]
    form: str
    filed: str
    accession: str
    frame: Optional[str] = None

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["basis"] = "actual"
        d["source"] = "SEC EDGAR XBRL companyfacts"
        return d


# --------------------------------------------------------------------------------------
# Ticker <-> CIK
# --------------------------------------------------------------------------------------
_TICKER_MAP_CACHE: Optional[dict[str, dict]] = None


def load_ticker_map(refresh: bool = False, verbose: bool = True) -> dict[str, dict]:
    """Download the SEC's official ticker -> CIK map. Keys are UPPERCASE tickers."""
    global _TICKER_MAP_CACHE
    if _TICKER_MAP_CACHE is not None and not refresh:
        return _TICKER_MAP_CACHE

    payload, _prov = fetch_json(
        config.SEC_TICKER_MAP_URL,
        cache_dir=config.SEC_CACHE,
        ttl_hours=config.CACHE_TTL_HOURS["sec_tickers"],
        refresh=refresh,
        verbose=verbose,
        **_SEC_FETCH,
    )
    mapping: dict[str, dict] = {}
    for entry in payload.values():
        ticker = str(entry.get("ticker", "")).upper().strip()
        if not ticker:
            continue
        mapping[ticker] = {
            "ticker": ticker,
            "cik": int(entry["cik_str"]),
            "cik_padded": str(entry["cik_str"]).zfill(10),
            "name": entry.get("title", ""),
        }
    _TICKER_MAP_CACHE = mapping
    return mapping


def cik_for_ticker(ticker: str, refresh: bool = False, verbose: bool = True) -> dict:
    """Resolve a ticker to its SEC CIK. Raises FetchError if the SEC does not list it."""
    mapping = load_ticker_map(refresh=refresh, verbose=verbose)
    key = ticker.upper().strip()
    if key in mapping:
        return mapping[key]
    # Some tickers use "." vs "-" for share classes (BRK.B vs BRK-B).
    for alt in (key.replace(".", "-"), key.replace("-", ".")):
        if alt in mapping:
            return mapping[alt]
    raise FetchError(
        "Ticker '" + ticker + "' is not in the SEC company_tickers.json map. "
        "It may be a foreign issuer, an ETF, or delisted. No CIK, no filings, no analysis."
    )


# --------------------------------------------------------------------------------------
# Raw endpoint wrappers
# --------------------------------------------------------------------------------------
def get_submissions(cik_padded: str, refresh: bool = False, verbose: bool = True):
    url = config.SEC_BASE + "/submissions/CIK" + cik_padded + ".json"
    return fetch_json(
        url, cache_dir=config.SEC_CACHE,
        ttl_hours=config.CACHE_TTL_HOURS["sec_submissions"],
        refresh=refresh, verbose=verbose, **_SEC_FETCH,
    )


def get_company_facts(cik_padded: str, refresh: bool = False, verbose: bool = True):
    url = config.SEC_BASE + "/api/xbrl/companyfacts/CIK" + cik_padded + ".json"
    return fetch_json(
        url, cache_dir=config.SEC_CACHE,
        ttl_hours=config.CACHE_TTL_HOURS["sec_facts"],
        refresh=refresh, verbose=verbose, **_SEC_FETCH,
    )


def get_company_concept(cik_padded: str, tag: str, taxonomy: str = "us-gaap",
                        refresh: bool = False, verbose: bool = True):
    url = (config.SEC_BASE + "/api/xbrl/companyconcept/CIK" + cik_padded
           + "/" + taxonomy + "/" + tag + ".json")
    return fetch_json(
        url, cache_dir=config.SEC_CACHE,
        ttl_hours=config.CACHE_TTL_HOURS["sec_facts"],
        refresh=refresh, verbose=verbose, **_SEC_FETCH,
    )


# --------------------------------------------------------------------------------------
# Fact extraction
# --------------------------------------------------------------------------------------
_ANNUAL_FORMS = ("10-K", "10-K/A", "20-F", "40-F")
_QUARTERLY_FORMS = ("10-Q", "10-Q/A")


def _days_between(start: str, end: str) -> Optional[int]:
    from datetime import date
    try:
        y1, m1, d1 = (int(x) for x in start.split("-"))
        y2, m2, d2 = (int(x) for x in end.split("-"))
        return (date(y2, m2, d2) - date(y1, m1, d1)).days
    except Exception:
        return None


def _iter_units(fact_block: dict) -> Iterable[tuple[str, list[dict]]]:
    for unit, rows in (fact_block.get("units") or {}).items():
        yield unit, rows


def extract_facts(facts_json: dict, concept: str, tags: list[str], *,
                  taxonomy: str = "us-gaap", kind: str = "duration",
                  annual_only: bool = True) -> list[Fact]:
    """Pull every reported value for the first candidate tag that exists.

    kind="duration" -> income-statement / cash-flow items (have a start and an end)
    kind="instant"  -> balance-sheet items (a snapshot on one date)
    """
    tax_block = (facts_json.get("facts") or {}).get(taxonomy) or {}
    candidates: list[tuple[int, str, list[Fact]]] = []

    for priority, tag in enumerate(tags):
        block = tax_block.get(tag)
        if not block:
            continue
        out: list[Fact] = []
        for unit, rows in _iter_units(block):
            for row in rows:
                form = row.get("form", "")
                if annual_only and form not in _ANNUAL_FORMS:
                    continue
                end = row.get("end")
                start = row.get("start")
                if not end:
                    continue
                if kind == "duration":
                    if not start:
                        continue
                    span = _days_between(start, end)
                    # An annual figure spans ~a year. This filters out the quarterly and
                    # year-to-date stubs that also appear inside a 10-K.
                    if annual_only and (span is None or not (300 <= span <= 400)):
                        continue
                out.append(Fact(
                    concept=concept, tag=tag, taxonomy=taxonomy,
                    value=float(row["val"]), unit=unit,
                    period_start=start, period_end=end,
                    fiscal_year=row.get("fy"), fiscal_period=row.get("fp"),
                    form=form, filed=row.get("filed", ""),
                    accession=row.get("accn", ""), frame=row.get("frame"),
                ))
        if out:
            # Deduplicate: a figure gets restated across filings. Keep the most recently
            # FILED version of each period - that is the company's latest word on it.
            best: dict[str, Fact] = {}
            for f in out:
                k = (f.period_start or "") + "|" + f.period_end
                if k not in best or f.filed > best[k].filed:
                    best[k] = f
            candidates.append((priority, tag, sorted(best.values(), key=lambda f: f.period_end)))

    if not candidates:
        return []

    # Choose among candidate tags by CURRENCY FIRST, priority second.
    #
    # Taking simply the first tag that has any data is a trap. Caterpillar last tagged
    # NetIncomeLoss in 2010 and reports ProfitLoss now; Johnson & Johnson abandoned
    # OperatingIncomeLoss after 2014. A naive first-match returns a fifteen-year-old
    # number and presents it as the latest year. So: find the newest period any candidate
    # reaches, keep every candidate that reaches within ~13 months of it, and among those
    # honour the priority order of the concept dictionary.
    newest = max(c[2][-1].period_end for c in candidates)
    current = [c for c in candidates
               if (_days_between(c[2][-1].period_end, newest) or 0) <= 400]
    chosen = min(current or candidates, key=lambda c: c[0])
    return chosen[2]


def annual_series(facts_json: dict, concept: str, years: int = 6) -> list[Fact]:
    """The last N annual values of one concept, oldest first."""
    if concept in DURATION_CONCEPTS:
        facts = extract_facts(facts_json, concept, DURATION_CONCEPTS[concept], kind="duration")
    elif concept in INSTANT_CONCEPTS:
        facts = extract_facts(facts_json, concept, INSTANT_CONCEPTS[concept], kind="instant")
    elif concept in DEI_CONCEPTS:
        facts = extract_facts(facts_json, concept, DEI_CONCEPTS[concept],
                              taxonomy="dei", kind="instant", annual_only=False)
    else:
        raise KeyError("Unknown concept: " + concept)
    return facts[-years:] if years else facts


def latest_fact(facts_json: dict, concept: str) -> Optional[Fact]:
    series = annual_series(facts_json, concept, years=0)
    return series[-1] if series else None


def latest_shares_outstanding(facts_json: dict) -> Optional[Fact]:
    """Most current share count. Prefers the dei cover-page tag (most recent), then us-gaap.

    Share count matters more than most numbers: it is the denominator of per-share value.
    """
    dei_block = (facts_json.get("facts") or {}).get("dei") or {}
    for tag in DEI_CONCEPTS["shares_outstanding_dei"]:
        block = dei_block.get(tag)
        if not block:
            continue
        rows: list[Fact] = []
        for unit, entries in _iter_units(block):
            for row in entries:
                if not row.get("end"):
                    continue
                rows.append(Fact(
                    concept="shares_outstanding", tag=tag, taxonomy="dei",
                    value=float(row["val"]), unit=unit,
                    period_start=row.get("start"), period_end=row["end"],
                    fiscal_year=row.get("fy"), fiscal_period=row.get("fp"),
                    form=row.get("form", ""), filed=row.get("filed", ""),
                    accession=row.get("accn", ""),
                ))
        if rows:
            return max(rows, key=lambda f: (f.filed, f.period_end))
    facts = extract_facts(facts_json, "shares_outstanding",
                          INSTANT_CONCEPTS["shares_outstanding"], kind="instant",
                          annual_only=False)
    return facts[-1] if facts else None


# --------------------------------------------------------------------------------------
# Company profile + filing history
# --------------------------------------------------------------------------------------
def company_profile(cik_padded: str, refresh: bool = False, verbose: bool = True) -> dict:
    subs, prov = get_submissions(cik_padded, refresh=refresh, verbose=verbose)
    return {
        "name": subs.get("name"),
        "cik": subs.get("cik"),
        "sic": subs.get("sic"),
        "sic_description": subs.get("sicDescription"),
        "exchanges": subs.get("exchanges"),
        "tickers": subs.get("tickers"),
        "fiscal_year_end": subs.get("fiscalYearEnd"),
        "state_of_incorporation": subs.get("stateOfIncorporation"),
        "entity_type": subs.get("entityType"),
        "category": subs.get("category"),
        "website": subs.get("website"),
        "investor_website": subs.get("investorWebsite"),
        "phone": subs.get("phone"),
        "business_address": subs.get("addresses", {}).get("business"),
        "_provenance": prov.to_dict(),
    }


def recent_filings(cik_padded: str, forms: Optional[tuple[str, ...]] = None,
                   limit: int = 20, refresh: bool = False, verbose: bool = True) -> list[dict]:
    """Recent filings, newest first, each with a direct EDGAR URL."""
    subs, _prov = get_submissions(cik_padded, refresh=refresh, verbose=verbose)
    recent = (subs.get("filings") or {}).get("recent") or {}
    cols = ["accessionNumber", "filingDate", "reportDate", "form", "primaryDocument",
            "primaryDocDescription"]
    n = len(recent.get("accessionNumber", []))
    rows: list[dict] = []
    for i in range(n):
        rec = {c: (recent.get(c) or [None] * n)[i] for c in cols}
        if forms and rec["form"] not in forms:
            continue
        acc_nodash = (rec["accessionNumber"] or "").replace("-", "")
        rec["url"] = (config.SEC_WWW + "/Archives/edgar/data/" + str(int(cik_padded))
                      + "/" + acc_nodash + "/" + str(rec["primaryDocument"]))
        rec["filing_index_url"] = (config.SEC_WWW + "/Archives/edgar/data/"
                                   + str(int(cik_padded)) + "/" + acc_nodash)
        rows.append(rec)
        if len(rows) >= limit:
            break
    return rows


# --------------------------------------------------------------------------------------
# Insider transactions (Form 4)
# --------------------------------------------------------------------------------------
# Transaction codes that matter most. Full list in SEC Form 4 instructions.
_TXN_CODES = {
    "P": ("open-market purchase", "buy"),
    "S": ("open-market sale", "sell"),
    "A": ("grant/award (compensation, not a market buy)", "neutral"),
    "M": ("option exercise", "neutral"),
    "F": ("shares withheld for taxes", "neutral"),
    "G": ("gift", "neutral"),
    "D": ("disposition to issuer", "neutral"),
    "C": ("conversion", "neutral"),
    "X": ("option exercise (in-the-money)", "neutral"),
}


_LINKBASE_SUFFIXES = ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml")


def _find_form4_xml_url(index_url: str, primary_document: Optional[str] = None,
                        refresh: bool = False, verbose: bool = True) -> Optional[str]:
    """Locate the machine-readable XML inside a Form 4 filing.

    EDGAR serves Form 4 twice: a human-readable rendering under an `xslF345X0*/` path,
    and the raw XML alongside it. `primaryDocument` points at the rendered version, so
    stripping that one directory component gives the raw XML directly - no extra request.
    The directory listing is only scanned if that shortcut does not pan out.
    """
    if primary_document:
        parts = primary_document.split("/")
        if len(parts) > 1 and parts[0].lower().startswith("xsl"):
            return index_url + "/" + "/".join(parts[1:])
        if primary_document.lower().endswith(".xml"):
            return index_url + "/" + primary_document

    try:
        text, _ = fetch(
            index_url + "/", cache_dir=config.SEC_CACHE,
            ttl_hours=config.CACHE_TTL_HOURS["sec_filing_doc"],
            refresh=refresh, verbose=verbose, **_SEC_FETCH,
        )
    except FetchError:
        return None
    for href in re.findall(r'href="([^"]+\.xml)"', text):
        low = href.lower()
        if low.endswith(_LINKBASE_SUFFIXES) or "/xsl" in low:
            continue
        return config.SEC_WWW + href if href.startswith("/") else index_url + "/" + href
    return None


def insider_transactions(cik_padded: str, lookback_filings: int = 25,
                         refresh: bool = False, verbose: bool = True) -> dict:
    """Parse recent Form 4 filings into a buy/sell summary.

    Caveat recorded in the output: option grants (code A) and tax withholding (code F) are
    compensation mechanics, not conviction signals. Only code P (open-market purchase) and
    code S (open-market sale) are counted as directional.
    """
    filings = recent_filings(cik_padded, forms=("4",), limit=lookback_filings,
                             refresh=refresh, verbose=verbose)
    txns: list[dict] = []
    parsed_ok, parse_failed = 0, 0

    for f in filings:
        xml_url = _find_form4_xml_url(f["filing_index_url"], f.get("primaryDocument"),
                                      refresh=refresh, verbose=verbose)
        if not xml_url:
            parse_failed += 1
            continue
        try:
            raw, _ = fetch(
                xml_url, cache_dir=config.SEC_CACHE,
                ttl_hours=config.CACHE_TTL_HOURS["sec_filing_doc"],
                refresh=refresh, verbose=verbose, **_SEC_FETCH,
            )
            root = ET.fromstring(raw)
        except Exception:
            parse_failed += 1
            continue

        owner = root.findtext(".//reportingOwner/reportingOwnerId/rptOwnerName") or "unknown"
        rel = root.find(".//reportingOwner/reportingOwnerRelationship")
        roles = []
        if rel is not None:
            if (rel.findtext("isDirector") or "0") in ("1", "true"):
                roles.append("director")
            if (rel.findtext("isOfficer") or "0") in ("1", "true"):
                roles.append(rel.findtext("officerTitle") or "officer")
            if (rel.findtext("isTenPercentOwner") or "0") in ("1", "true"):
                roles.append("10% owner")

        for t in root.findall(".//nonDerivativeTransaction"):
            code = t.findtext(".//transactionCoding/transactionCode") or "?"
            shares = t.findtext(".//transactionAmounts/transactionShares/value")
            price = t.findtext(".//transactionAmounts/transactionPricePerShare/value")
            date = t.findtext(".//transactionDate/value")
            acq_disp = t.findtext(".//transactionAmounts/transactionAcquiredDisposedCode/value")
            try:
                shares_f = float(shares) if shares else None
                price_f = float(price) if price else None
            except ValueError:
                shares_f, price_f = None, None
            label, direction = _TXN_CODES.get(code, ("code " + code, "neutral"))
            txns.append({
                "date": date, "owner": owner, "roles": roles, "code": code,
                "code_meaning": label, "direction": direction,
                "acquired_disposed": acq_disp,
                "shares": shares_f, "price_per_share": price_f,
                "value_usd": (shares_f * price_f) if (shares_f and price_f) else None,
                "source_url": xml_url, "filed": f["filingDate"],
            })
        parsed_ok += 1

    buys = [t for t in txns if t["direction"] == "buy"]
    sells = [t for t in txns if t["direction"] == "sell"]
    buy_val = sum(t["value_usd"] or 0 for t in buys)
    sell_val = sum(t["value_usd"] or 0 for t in sells)

    return {
        "filings_examined": len(filings),
        "filings_parsed": parsed_ok,
        "filings_unparsed": parse_failed,
        "transactions": txns,
        "summary": {
            "open_market_buys": len(buys),
            "open_market_sells": len(sells),
            "buy_value_usd": buy_val,
            "sell_value_usd": sell_val,
            "net_value_usd": buy_val - sell_val,
            "earliest_txn": min((t["date"] for t in txns if t["date"]), default=None),
            "latest_txn": max((t["date"] for t in txns if t["date"]), default=None),
        },
        "caveats": [
            "Only the most recent " + str(lookback_filings) + " Form 4 filings were examined; "
            "this is a recent-activity snapshot, not a complete history.",
            "Codes A (grants) and F (tax withholding) are compensation mechanics and are NOT "
            "counted as buys or sells.",
            "Sales are often pre-scheduled under Rule 10b5-1 plans and can be routine "
            "diversification rather than a signal. Check the filing footnotes before drawing "
            "any conclusion.",
            "Derivative (option) transactions are excluded; only non-derivative share "
            "transactions are parsed.",
        ],
    }


# --------------------------------------------------------------------------------------
# The one function most callers want
# --------------------------------------------------------------------------------------
def fundamentals(ticker: str, years: int = 6, refresh: bool = False,
                 verbose: bool = True) -> dict:
    """Full multi-year fundamental record for a ticker, straight from XBRL filings.

    Returns a dict with: identity, profile, annual series per concept, latest share count,
    and a per-concept availability report naming what could NOT be found.
    """
    ident = cik_for_ticker(ticker, verbose=verbose)
    cikp = ident["cik_padded"]
    facts, prov = get_company_facts(cikp, refresh=refresh, verbose=verbose)
    profile = company_profile(cikp, refresh=refresh, verbose=verbose)

    # A ticker can point at a freshly-registered holding company that carries none of the
    # operating history (see the ExxonMobil note above). When that happens, look for the
    # predecessor entity and analyse ITS filings instead - loudly, never silently.
    reorg: Optional[dict] = None
    if len(annual_series(facts, "revenue", years=0)) < 2:
        pred = find_predecessor(profile.get("name") or ident["name"], profile.get("sic"),
                                cikp, refresh=refresh, verbose=verbose)
        if pred:
            reorg = {
                "detected": True,
                "ticker_cik": cikp,
                "ticker_entity_name": profile.get("name"),
                "history_cik": pred["cik_padded"],
                "history_entity_name": pred["name"],
                "annual_periods_recovered": pred["annual_periods"],
                "explanation": pred["why"],
                "caution": (
                    "Financials below come from the PREDECESSOR entity, not from the CIK "
                    "the ticker resolves to. Verify the reorganization was a pure holding-"
                    "company restructuring before comparing these figures across the "
                    "transition - if assets were spun off or acquired, the history is not "
                    "continuous with the entity you would be buying today."
                ),
            }
            if verbose:
                print("    [sec] " + ticker.upper() + ": ticker maps to a new entity with "
                      "no history; using predecessor CIK " + pred["cik_padded"]
                      + " (" + str(pred["name"]) + ")")
            cikp = pred["cik_padded"]
            facts, prov = get_company_facts(cikp, refresh=refresh, verbose=verbose)
            profile = company_profile(cikp, refresh=refresh, verbose=verbose)

    series: dict[str, list[dict]] = {}
    unavailable: list[str] = []

    for concept in list(DURATION_CONCEPTS) + list(INSTANT_CONCEPTS):
        try:
            facts_list = annual_series(facts, concept, years=years)
        except KeyError:
            facts_list = []
        if facts_list:
            series[concept] = [f.as_dict() for f in facts_list]
        else:
            unavailable.append(concept)

    shares = latest_shares_outstanding(facts)

    # ---- Staleness check -------------------------------------------------------------
    # A tag can EXIST in the filings yet have been abandoned years ago. JPMorgan, for
    # example, stopped tagging CashAndCashEquivalentsAtCarryingValue after FY2018. Pulling
    # "the latest value" for that concept silently hands you a figure from 2018 and calls
    # it current. Anything materially older than the newest fiscal period is flagged so
    # downstream code can refuse to use it.
    anchor = None
    for key in ("revenue", "net_income", "total_assets", "equity"):
        if series.get(key):
            end = series[key][-1]["period_end"]
            anchor = max(anchor, end) if anchor else end
    stale: dict[str, dict] = {}
    if anchor:
        for concept, rows in series.items():
            latest_end = rows[-1]["period_end"]
            gap = _days_between(latest_end, anchor)
            if gap is not None and gap > 400:
                stale[concept] = {
                    "latest_period_end": latest_end,
                    "newest_fiscal_period_available": anchor,
                    "days_behind": gap,
                    "reason": ("The company appears to have stopped reporting the tag '"
                               + rows[-1]["tag"] + "' after " + latest_end
                               + ". Treat this concept as unavailable, not current."),
                }

    return {
        "ticker": ident["ticker"],
        "cik": ident["cik"],
        "cik_padded": cikp,
        "company_name": ident["name"],
        "profile": profile,
        "annual": series,
        "shares_outstanding_latest": shares.as_dict() if shares else None,
        "latest_fiscal_period_end": anchor,
        "reorganization": reorg,
        "concepts_stale": stale,
        "concepts_stale_note": (
            "These tags exist in the filings but have not been updated in over ~13 months "
            "relative to the newest fiscal period. Their most recent value is NOT current "
            "and must not be used as a latest-year figure."
        ),
        "concepts_unavailable": unavailable,
        "concepts_unavailable_note": (
            "These US-GAAP tags were not found in this company's filings. That is often "
            "legitimate - banks report no gross profit or capex, asset-light firms report "
            "no inventory. Downstream code must render these as '"
            + config.MISSING + "', never as zero."
        ),
        "_provenance": prov.to_dict(),
        "_source_urls": {
            "companyfacts": config.SEC_BASE + "/api/xbrl/companyfacts/CIK" + cikp + ".json",
            "submissions": config.SEC_BASE + "/submissions/CIK" + cikp + ".json",
            "edgar_browse": (config.SEC_WWW + "/cgi-bin/browse-edgar?action=getcompany&CIK="
                             + cikp + "&type=10-K&dateb=&owner=include&count=40"),
        },
    }


# --------------------------------------------------------------------------------------
# Corporate reorganizations: finding a company's history under a predecessor CIK
# --------------------------------------------------------------------------------------
# When a company reorganizes into a holding-company structure, the ticker is reassigned to
# a BRAND NEW CIK with no filing history, while decades of financials stay under the
# predecessor entity - which usually loses its ticker and therefore vanishes from
# company_tickers.json entirely.
#
# ExxonMobil is the live example: XOM maps to CIK 0002115436 ("ExxonMobil Holdings Corp",
# registered 2026, no annual periods), while $332B of FY2025 revenue sits under CIK
# 0000034088 ("EXXON MOBIL CORP"). A naive lookup silently drops Exxon from every screen,
# or worse, analyses the empty shell.
#
# The SEC publishes a complete NAME:CIK index covering entities with no ticker, which is
# what makes recovery possible.

CIK_LOOKUP_URL = config.SEC_WWW + "/Archives/edgar/cik-lookup-data.txt"

_CIK_LOOKUP: Optional[list[tuple[str, str]]] = None

_CORP_SUFFIXES = [
    "HOLDINGS", "HOLDING", "HLDGS", "CORPORATION", "CORP", "INCORPORATED", "INC",
    "COMPANY", "CO", "LTD", "LIMITED", "LLC", "LP", "PLC", "GROUP", "NEW", "THE",
]


def _normalize_company_name(name: str) -> str:
    """Strip punctuation and corporate suffixes so 'ExxonMobil Holdings Corp' ~ 'EXXON MOBIL CORP'."""
    n = re.sub(r"[^A-Za-z0-9 ]", " ", (name or "").upper())
    words = [w for w in n.split() if w and w not in _CORP_SUFFIXES]
    return "".join(words)


def load_cik_lookup(refresh: bool = False, verbose: bool = True) -> list[tuple[str, str]]:
    """The SEC's complete NAME:CIK index, including entities that have no ticker.

    ~38MB, cached for a week. Only downloaded when a predecessor search is actually needed.
    """
    global _CIK_LOOKUP
    if _CIK_LOOKUP is not None and not refresh:
        return _CIK_LOOKUP
    if verbose:
        print("    [sec] downloading the full SEC CIK index (~38MB, cached 7 days)...")
    text, _prov = fetch(
        CIK_LOOKUP_URL, cache_dir=config.SEC_CACHE,
        ttl_hours=config.CACHE_TTL_HOURS["sec_tickers"],
        headers=config.SEC_HEADERS, rate_key="sec",
        rate=config.SEC_MAX_REQUESTS_PER_SECOND, timeout=120,
        max_retries=config.SEC_MAX_RETRIES, refresh=refresh, verbose=verbose,
        source_name="SEC CIK lookup index", basis="actual",
    )
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.endswith(":"):
            continue
        parts = line.rstrip(":").rsplit(":", 1)
        if len(parts) == 2 and parts[1].isdigit():
            rows.append((parts[0], parts[1].zfill(10)))
    _CIK_LOOKUP = rows
    return rows


def find_predecessor(company_name: str, sic: Optional[str], exclude_cik: str,
                     min_annual_periods: int = 2, refresh: bool = False,
                     verbose: bool = True) -> Optional[dict]:
    """Locate an older entity that holds this company's financial history.

    Match requires BOTH a normalized-name match AND the same SIC industry code, then the
    candidate must actually carry annual revenue history. Returns None if nothing
    qualifies - a wrong match would be far worse than no match.
    """
    target = _normalize_company_name(company_name)
    if not target:
        return None

    candidates: list[tuple[str, str]] = []
    for name, cik in load_cik_lookup(refresh=refresh, verbose=verbose):
        if cik == exclude_cik:
            continue
        norm = _normalize_company_name(name)
        if norm == target or (len(target) >= 8 and (norm.startswith(target)
                                                    or target.startswith(norm))):
            candidates.append((name, cik))

    seen: set[str] = set()
    for name, cik in candidates:
        if cik in seen:
            continue
        seen.add(cik)
        try:
            profile = company_profile(cik, refresh=refresh, verbose=verbose)
            if sic and str(profile.get("sic")) != str(sic):
                continue
            facts, _ = get_company_facts(cik, refresh=refresh, verbose=verbose)
            rev = annual_series(facts, "revenue", years=0)
            if len(rev) >= min_annual_periods:
                return {
                    "cik_padded": cik,
                    "name": profile.get("name"),
                    "sic": profile.get("sic"),
                    "annual_periods": len(rev),
                    "latest_period": rev[-1].period_end,
                    "why": ("Ticker resolves to '" + company_name + "' (CIK " + exclude_cik
                            + "), which has fewer than " + str(min_annual_periods)
                            + " annual periods. Financial history was located under the "
                            "predecessor entity '" + str(profile.get("name")) + "' (CIK "
                            + cik + "), matched on normalized name and SIC "
                            + str(profile.get("sic")) + "."),
                }
        except Exception:
            continue
    return None

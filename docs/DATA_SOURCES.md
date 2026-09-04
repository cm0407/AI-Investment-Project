# Data Sources

Every number this system produces traces back to one of the three sources below. Nothing
is typed in by hand, and nothing is estimated to fill a gap.

CLAUDE.md sets the priority order. This document records exactly which source answers
which question, what it costs, what its limits are, and where it can mislead you.

---

## Priority order (from CLAUDE.md)

| Rank | Source | Used here for |
|---|---|---|
| 1 | SEC EDGAR filings & company IR | **All fundamentals** — revenue, margins, cash flow, debt, share count |
| 2 | Earnings releases | Reachable via EDGAR 8-K exhibits (`fetch_sec.py --filings`) |
| 3 | Official transcripts | Not automated — read manually from the company's IR site |
| 4 | Government/regulatory data | **FRED** — rates, inflation, employment, credit spreads |
| 5 | Reputable data providers | **yfinance/Yahoo** — market prices only |
| 6 | Quality financial journalism | Not automated — analyst reads it and cites it in the thesis |
| 7 | Analyst opinions | Captured but quarantined as `vendor_estimate`; never used as value |

---

## 1. SEC EDGAR — `data.sec.gov`

**What it is:** the U.S. Securities and Exchange Commission's own filing database. When a
public company reports revenue, this is where that number legally lives. Everything else
in finance is a copy of it.

**Cost:** free. **API key:** none. **Registration:** none.

**Endpoints used**

| Endpoint | Purpose |
|---|---|
| `https://www.sec.gov/files/company_tickers.json` | Official ticker → CIK map (~10,000 companies) |
| `https://data.sec.gov/submissions/CIK##########.json` | Filing history, SIC industry code, exchange, fiscal year end |
| `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | Every XBRL fact the company has ever filed |
| `https://data.sec.gov/api/xbrl/companyconcept/CIK.../us-gaap/<tag>.json` | One tag's full history |
| `https://www.sec.gov/Archives/edgar/data/<cik>/<accession>/` | Individual filed documents, incl. Form 4 XML |

**Compliance with SEC rules** — [their fair-access policy](https://www.sec.gov/os/webmaster-faq#developers)
requires a declared User-Agent with a real contact address, and caps traffic at 10
requests/second.

- User-Agent sent: `INVEST-Research/1.0 (your-email@example.com)`
- Rate limit applied: **5 requests/second** — deliberately half the ceiling
- Configured in [invest/config.py](../invest/config.py); override the address with the
  `SEC_CONTACT_EMAIL` environment variable
- Responses are cached for 24h so re-running a script does not re-hammer a public service

**Known limitations — read these before trusting a figure**

1. **Tag inconsistency.** US-GAAP lets companies tag the same concept differently. Revenue
   might be `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, or
   `SalesRevenueNet`. The system tries a prioritised list per concept.
2. **Abandoned tags.** A company can stop using a tag without deleting its history.
   Caterpillar last filed `NetIncomeLoss` in **2010**; JPMorgan last filed
   `LongTermDebt` in **2013** and `CashAndCashEquivalentsAtCarryingValue` in **2018**.
   Naively taking "the latest value" of those tags returns a decade-old number and
   presents it as current. The system picks tags by **currency first, priority second**,
   and separately flags any concept more than ~13 months behind the newest fiscal period.
3. **Industry gaps are real, not errors.** Banks file no `GrossProfit` and no capital
   expenditure. Asset-light firms file no inventory. These render as
   `DATA UNAVAILABLE OR UNVERIFIED`, never as `0`.
4. **Restatements.** Where a period was restated, the most recently *filed* version wins.
5. **As-reported only.** No adjustment is made for one-off items, and management's
   preferred "adjusted" non-GAAP figures are deliberately ignored.
6. **Foreign issuers** file 20-F/40-F on different schedules; some file no XBRL at all.
7. **XBRL is machine-tagged by the filer.** Tagging errors do occur. A figure that looks
   extraordinary should be checked against the actual filed document before it is used —
   every fact carries its accession number so you can go read the original.

---

## 2. FRED — Federal Reserve Bank of St. Louis

**What it is:** the standard public repository for U.S. economic statistics.

**Cost:** free. **API key:** optional.

- **Without a key (the default):** the public CSV endpoint
  `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>` — no registration at all.
- **With a key:** set `FRED_API_KEY` and the JSON API is used instead. Free key at
  <https://fredaccount.stlouisfed.org/apikeys>.

**Series tracked by default**

| Series | What it is |
|---|---|
| `DGS10`, `DGS2` | 10-year and 2-year Treasury yields — the rates valuations discount against |
| `T10Y2Y` | 10y minus 2y spread; sustained inversion has preceded past recessions |
| `FEDFUNDS` | The Fed's policy rate |
| `CPIAUCSL` | Headline consumer price index |
| `UNRATE`, `PAYEMS` | Unemployment rate, nonfarm payrolls |
| `GDPC1`, `INDPRO` | Real GDP, industrial production |
| `UMCSENT` | Consumer sentiment |
| `BAMLH0A0HYM2` | High-yield credit spread — stress shows up here before earnings |
| `MORTGAGE30US` | 30-year mortgage rate |

**Limitations:** series lag at different speeds (Treasury yields daily, CPI monthly, GDP
quarterly) — "latest" means *latest published*, not today. Figures get revised, sometimes
substantially. Macro data sets context; it does not pick stocks.

---

## 3. Yahoo Finance via `yfinance`

**What it is:** an unofficial Python client for Yahoo Finance. Used for **market prices
only**.

**Cost:** free. **API key:** none. **Stability:** no guarantees — it is unofficial, it
breaks when Yahoo changes something, and it can rate-limit without warning.

**What it is allowed to supply**

| Field group | `basis` tag | Trust level |
|---|---|---|
| Prices, volume, returns, volatility | `market` | Observed market data — reliable |
| Sector/industry labels, share counts, vendor multiples | `vendor_reported` | Cross-check only |
| Forward P/E, PEG, target prices, consensus growth | `vendor_estimate` | **Opinions.** Never valuation inputs |

**The boundary that matters:** fundamentals never come from here. Yahoo is an unaudited
aggregator; the SEC filing is the original. Where both exist, the filing wins, and Yahoo's
version is kept only so a disagreement becomes visible.

**On analyst price targets:** CLAUDE.md is explicit that an analyst target is never
intrinsic value. They are captured under `vendor_estimates` so a thesis can note what
consensus thinks, and they are structurally barred from entering any DCF or fair-value
calculation.

---

## Provenance: what is attached to every figure

Each dataset written under `data/` carries a `_meta` block:

```json
{
  "_meta": {
    "generated_at_utc": "2026-09-04T06:22:10Z",
    "provenance": [{
      "source": "SEC EDGAR XBRL companyfacts",
      "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
      "retrieved_at_utc": "2026-09-04T06:22:10Z",
      "basis": "actual",
      "from_cache": false
    }],
    "assumptions": ["..."]
  }
}
```

And each individual SEC fact carries its own `tag`, `form`, `filed` date, `accession`
number and `period_end`, so any number can be traced to the exact filing that reported it.

### The `basis` vocabulary

| `basis` | Meaning |
|---|---|
| `actual` | A figure a company actually reported in a filing |
| `market` | An observed market price or volume |
| `official_stat` | A government statistical release |
| `vendor_estimate` | **A third party's forecast. An opinion.** |
| `derived` | Computed by us from the above; the formula is recorded |
| `projected` | A forward number **we** made up under stated assumptions (DCF output) |

---

## Caching and refreshing

| Data | Cached for | Why |
|---|---|---|
| SEC companyfacts | 24 h | Only changes when the company files |
| SEC submissions | 12 h | |
| SEC ticker map | 7 days | Changes slowly |
| An individual filed document | 30 days | A filed document never changes |
| Prices | 4 h | |
| FRED | 12 h | |

Pass `--refresh` to any script to bypass the cache. If a live fetch fails and a stale
cache exists, the stale copy is used **and loudly labelled** — the alternative is
inventing a number, which is worse.

**Never hand-edit a file under `data/`.** It is all regenerable:
`python scripts/refresh_all.py --force`. A hand-typed number has no source, no timestamp
and no way to be verified.

---

## What this system deliberately does NOT have

Being explicit about the blind spots matters as much as documenting the sources.

- **No consensus earnings estimates** (beyond Yahoo's, quarantined as vendor opinion)
- **No 13F institutional ownership history** — the SEC publishes 13Fs, but assembling a
  reliable ownership-change series from them is a project in itself and is not built here.
  CLAUDE.md lists institutional ownership shifts as a screening input; **this system
  cannot currently supply that**, and no screen should claim it does.
- **No short interest data**
- **No credit ratings**
- **No intraday or real-time quotes** — prices are delayed closes
- **No options data**
- **No paid terminal data** of any kind

Where a CLAUDE.md requirement cannot be met from free sources, the honest answer is to say
so here rather than to approximate it and hope.

# INVEST

An investment research system that pulls real financial data from official sources, does
the arithmetic for you, and — this is the important part — **tells you when it doesn't
know something** instead of guessing.

> **This is research and education, not financial advice.** Claude is not a licensed
> financial advisor. Nothing here is a recommendation tailored to your finances, and no
> return is ever guaranteed. Individual stock picking should be a small *satellite* around
> a diversified core (like index funds), never a replacement for one.

---

## What this thing actually does

It answers questions like *"is this company growing?"*, *"does it make real cash?"*,
*"is it carrying dangerous debt?"* and *"is the price reasonable?"* — using numbers taken
directly from the company's legal filings with the U.S. government, not from a website
that might be out of date.

It **does not** tell you what to buy. It gathers evidence and does the maths. The judgment
stays with a person.

### The three places the data comes from

| Source | What it gives us | Cost |
|---|---|---|
| **SEC EDGAR** (`data.sec.gov`) | Company financials, straight from official filings | Free, no signup |
| **FRED** (St. Louis Fed) | Interest rates, inflation, jobs — the economic backdrop | Free, no signup |
| **Yahoo Finance** | Current share prices | Free, no signup |

Full details, limitations and the exact endpoints: **[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)**

---

## Setup (once)

You need Python 3.10 or newer.

```bash
cd "path/to/INVEST"
python -m pip install -r requirements.txt
python scripts/selftest.py
```

If the last command ends with **"All data sources are live"**, you are done. No API keys,
no accounts, no configuration.

<details>
<summary>Optional: a FRED API key</summary>

Not needed. The system uses FRED's public CSV endpoint by default. If you want the richer
JSON API, get a free key at <https://fredaccount.stlouisfed.org/apikeys> and set
`FRED_API_KEY` in your environment.
</details>

---

## Before anything gets recommended

Open **`notes/my_investing_preferences.md`** and fill it in — how much risk you can
stomach, how long you'll hold, what you refuse to own.

The system **blocks itself** from issuing BUY/WATCH/AVOID calls until you do. That is
deliberate: advice given without knowing your situation is worthless at best. Claude did
not guess your answers, because inventing your risk tolerance would be exactly the kind of
made-up input this project is built to avoid.

---

## The scripts, in the order you'd use them

Every one is run the same way: `python scripts/NAME.py`. Add `--help` to any of them.

### 1. Check everything works

```bash
python scripts/selftest.py
```

Tests all three data sources on five real companies and verifies the honesty guarantees.
Run it after any upgrade.

### 2. Look at one company

```bash
python scripts/fetch_sec.py AAPL                  # financials from SEC filings
python scripts/fetch_sec.py AAPL --insider        # + who's buying/selling internally
python scripts/fetch_prices.py AAPL --history     # share price and volatility
```

### 3. Analyse and score one company

```bash
python scripts/score_stock.py AAPL --dcf --insider
```

The main event. Prints the multi-year financials, every derived metric, the valuation
(including a *reverse DCF* — "what growth is the current price already assuming?"), and
the scoring rubric.

**It will give you a partial score and say so.** A script can score growth, valuation,
financial strength and cash flow — that's 50 of the 100 points. The other 50 (moat,
catalysts, management, risk/reward) need a person. See
**[docs/SCORING.md](docs/SCORING.md)**.

### 4. Search many companies at once

```bash
python scripts/build_universe.py                  # build the list (184 companies)
python scripts/screen_stocks.py --top 20          # rank them
python scripts/screen_stocks.py --min-revenue-growth 8 --max-pe 25 --min-roic 12
python scripts/build_universe.py --full           # ~10,000 companies, no curation
```

The 184-name starter list is a convenience and it is **biased** toward big familiar
companies. For a genuinely broad search, use `--full`.

### 5. The economic backdrop

```bash
python scripts/fetch_fred.py
```

Interest rates, inflation, unemployment, credit stress. This doesn't pick stocks — it
tells you what world the stocks are living in.

### 6. Write down predictions, then grade them

```bash
python scripts/track_predictions.py add --ticker AAPL --entry 328.21 --target 395 \
    --horizon 12 --prob-positive 0.62 --prob-20pct 0.38 --prob-loss 0.30 \
    --conviction 74 --notes "why you think this"

python scripts/track_predictions.py list
python scripts/track_predictions.py review     # mark to market against live prices
python scripts/track_predictions.py stats      # were the odds honest?
```

**This is the part that makes the system improve.** Predictions are append-only — once
written, a row is never edited. `review` adds a dated snapshot to a separate file. You
cannot quietly rewrite history to look smarter, which is the only way calibration ever
means anything.

The `add` command refuses incoherent input: probabilities that sum past 1.0, a
"chance of +20%" higher than the "chance of any gain", or a prediction with no thesis.

### 7. Write the session digest

```bash
python scripts/make_digest.py --tickers AAPL JNJ --macro
```

Creates `reports/daily/digest_YYYY-MM-DD.md` with all the verifiable facts filled in and
every judgment left as a `TODO` for a human.

### 8. Refresh everything

```bash
python scripts/refresh_all.py --force
```

**Never hand-edit a file under `data/`.** It's all rebuildable. A number typed in by hand
has no source and no timestamp, which makes it unverifiable.

---

## What the folders are for

```
INVEST/
├── CLAUDE.md          The rules the research process must follow
├── README.md          This file
├── requirements.txt   Python packages needed
│
├── invest/            The engine (importable Python package)
│   ├── config.py         All settings and file paths
│   ├── sec_edgar.py      SEC filings client
│   ├── prices.py         Market prices
│   ├── fred.py           Economic data
│   ├── metrics.py        Turns raw filings into ratios
│   ├── valuation.py      DCF, reverse DCF, bear/base/bull
│   ├── scoring.py        The 0-100 rubric
│   └── universe.py       The list of stocks to search
│
├── scripts/           The commands you actually run
├── memory/            ** The long-term brain - append-only **
│   ├── research_state.md        Where things stand
│   ├── predictions.csv          Every prediction ever made
│   ├── prediction_reviews.csv   Dated mark-to-market snapshots
│   ├── lessons_learned.md       Rules earned from mistakes
│   ├── rejected_stocks.md       What was passed over, and why
│   └── decisions_and_reasoning.md
│
├── notes/             GLOSSARY.md · my_investing_preferences.md
├── docs/              DATA_SOURCES.md · ASSUMPTIONS.md · SCORING.md
│                      GIT_FOR_BEGINNERS.md
├── research/theses/   Full write-ups, one per company
├── reports/daily/     The digests
├── portfolio/         investment_log.csv
└── data/              Everything downloaded (rebuildable; cache is gitignored)
```

---

## The honesty rules, and how they're enforced in code

This is the part that makes the system worth using. Each rule below is a real mechanism,
verified by `selftest.py` on every run.

**1. Missing data is never zero.**
It renders as `DATA UNAVAILABLE OR UNVERIFIED`. Banks file no "gross profit" — that's a
fact about banks, not a 0% margin. A fabricated zero would flow straight into a score.

**2. Abandoned data is never treated as current.**
Companies stop using accounting tags without deleting the history. Caterpillar last filed
`NetIncomeLoss` in **2010**; JPMorgan last filed `LongTermDebt` in **2013**. Taking "the
latest value" of those returns a decade-old number. The system picks tags by *currency
first*, and flags anything more than ~13 months stale.

**3. A total with a missing part is not published.**
When JPMorgan's long-term debt went stale, "total debt" became `None` rather than a sum of
what was left — which would have hidden hundreds of billions of dollars and produced a
~70% return-on-capital figure for a bank. You get "unavailable" instead of a wrong number
that looks right.

**4. Banks aren't graded like factories.**
A bank borrowing 10× its equity is doing banking, not dying. Metrics that don't transfer
across industries are suppressed by SIC code, and the affected pillars go *unscored*
rather than scoring badly. JPMorgan is scored out of 30 available points, and the output
says so.

**5. The score refuses to complete itself.**
No `--judgment` file means no verdict band. The script will not pretend to have assessed a
moat.

**6. Analyst price targets are quarantined.**
Tagged `vendor_estimate` and structurally barred from any valuation calculation. An
analyst's target is an opinion, not a company's intrinsic value.

**7. Every number carries its source.**
Each figure records the exact XBRL tag, filing form, accession number, period and
retrieval timestamp. You can trace any number back to the filing that reported it.

**8. History can't be rewritten.**
`predictions.csv` is append-only. Reviews go to a separate file. Preserving mistakes is
the entire point — calibration is impossible otherwise.

---

## What this system cannot do

Worth knowing before you rely on it:

- It **cannot read** a 10-K's narrative — risk factors, competition, management's tone.
  That's still reading.
- It has **no institutional-ownership tracking**, even though CLAUDE.md lists it as a
  screening input.
- It has no consensus estimates, short interest, credit ratings, or options data.
- Its financial-sector coverage is **weak**: it correctly refuses to apply the wrong
  metrics, but doesn't yet compute the right ones (net interest margin, ROTCE, FFO).
- It cannot judge whether management is honest.
- **It cannot tell you what will happen.** Every forward number is a projection under
  assumptions listed in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md).

---

## Confused by a word?

**[notes/GLOSSARY.md](notes/GLOSSARY.md)** explains every term in plain English. If
something isn't there, ask Claude: *"explain that like I'm new to investing."*

New to git? **[docs/GIT_FOR_BEGINNERS.md](docs/GIT_FOR_BEGINNERS.md)** covers the nine
commands that do almost everything, and why this project keeps a history at all.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | `python -m pip install -r requirements.txt` |
| SEC returns 403 | Your User-Agent lacks a contact email. Check `SEC_CONTACT_EMAIL`. |
| Yahoo prices fail | It's an unofficial API. Wait a minute, or `python -m pip install -U yfinance` |
| A number looks wrong | Open the JSON in `data/` — every figure names the filing it came from |
| Data seems old | `python scripts/refresh_all.py --force` |

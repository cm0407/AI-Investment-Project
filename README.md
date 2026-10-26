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

copy .env.example .env          # Windows   (Mac/Linux: cp .env.example .env)
                                # then open .env and put your email in SEC_CONTACT_EMAIL

python scripts/selftest.py
```

If the last command ends with **"All data sources are live"**, you are done. No API keys
and no accounts — but the SEC does require a real contact address in `.env`, and the
self-test will fail until you set one. `.env` is gitignored, so your address stays on your
machine.

To use the system for real, also copy the two private templates:

```bash
copy notes\my_investing_preferences.example.md notes\my_investing_preferences.md
copy portfolio\investment_log.example.csv portfolio\investment_log.csv
```

Both are gitignored. They are where your risk tolerance and actual holdings live, so they
deliberately never enter version control — the `.example` files show the structure without
exposing anyone's finances.

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

### 8. Email the digest to yourself

```bash
python scripts/send_digest.py --setup      # one-time: how to get a Gmail App Password
python scripts/send_digest.py --dry-run    # preview WITHOUT sending anything
python scripts/send_digest.py              # send the most recent digest
```

`--dry-run` renders the full email and writes an HTML preview to `logs/` without contacting
a mail server, so you can check how it looks before any credentials are involved.

**Gmail will not accept your normal password.** You need an *App Password* - a 16-digit code
Google issues for one program, which you can revoke at any time without changing your real
password. It requires 2-Step Verification to be on first. `--setup` walks through it.

The password goes in `.env`, which is gitignored. **Never put it in a `.py` file** - this
repository is public, and a secret that reaches git history stays there even after the file
is deleted.

### 9. Refresh everything

```bash
python scripts/refresh_all.py --force
```

**Never hand-edit a file under `data/`.** It's all rebuildable. A number typed in by hand
has no source and no timestamp, which makes it unverifiable.

---

### 10. Let the model write the judgment half of a score

```bash
python scripts/score_stock.py INTU --judge
```

Half the 100-point score is arithmetic over SEC filings. The other half — business quality,
competitive advantage, catalysts, risk/reward, management — is judgement, and `--judge` hands
that part to a language model.

The model is given figures the Python has already worked out and asked to argue. **It never
touches a number itself.** Its answer is then checked seven ways and thrown away if any check
fails; the most important one rejects any figure in its reasoning that is not in the evidence it
was given. If it fails, you get the same PARTIAL score the system has always produced without
judgment — a model that cannot answer degrades the output, it never invents one.

A judgment you write yourself always wins:

```bash
python scripts/score_stock.py INTU --judgment research/judgments/INTU.json
```

You can overrule the model. The model can never overwrite you. The full split is written up in
`CLAUDE.md` under **The model in the loop**.

To see how the model compares with judgments written by hand:

```bash
python scripts/backtest_judge.py                      # all of them
python scripts/backtest_judge.py --tickers ADBE --repeat 3   # same evidence, three times
```

---

### 11. Look at it all in a browser

```bash
cd web
npm install        # first time only
npm run dev
```

Open **http://localhost:3000**. That's it — no second server.

The website reads JSON files in `web/public/data/`, not a live API. After you change anything
in the research record, regenerate them:

```bash
python scripts/export_site_data.py
```

Then refresh the browser. If a page says *No data file* with a filename in it, that's the
message telling you to run exactly that command.

**Why files and not a server.** This research changes a handful of times a month. A live API
would mean a server to host, pay for and keep awake, and a website that breaks whenever it
isn't. Reading frozen files means the whole site compiles to plain HTML that GitHub hosts for
free and that cannot fail at request time. The honest cost is printed in the footer of every
page: **the data is a snapshot, not live prices.**

The API still exists and is still the source of those files — `scripts/export_site_data.py`
calls the same functions the endpoints call, so the site can't drift from the API's answers.
Run it when you want to poke at the raw data:

```bash
python -m uvicorn api.main:app --port 8000     # then http://localhost:8000/docs
```

---

### 12. Put it on the internet

The site is published at **https://cm0407.github.io/AI-Investment-Project/** by GitHub Actions.
Two workflows do it, and neither costs anything:

| Workflow | Runs when | What it does |
|---|---|---|
| `.github/workflows/publish.yml` | every push to `master` | Rebuilds and republishes the site. |
| `.github/workflows/refresh.yml` | Saturdays 06:20 UTC, or on demand | Refreshes prices, macro, predictions and the screen, commits the result, then republishes. |

**So after a research session you just push.** The site updates itself two or three minutes
later. You never have to deploy by hand.

**What the schedule does NOT do:** it never runs the model. The judgment pillars, the digests
and the theses are written in a session, not on a timer. `claude -p` uses a Claude Code login
that lives on your laptop, not on a GitHub server — running it in the cloud would need an
Anthropic API key, which bills per call and is a separate product from Claude Code. That
boundary is deliberate: **the numbers keep themselves current, the judgement stays
human-initiated.**

#### One-time setup

1. **Settings → Pages → Source: GitHub Actions.**
2. **Settings → Secrets and variables → Actions → New repository secret**
   Name `SEC_CONTACT_EMAIL`, value your email. SEC asks for a real contact address in every
   request; the workflow refuses to run without it rather than hammering them anonymously.
3. Push. Watch it under the **Actions** tab.

To run the weekly refresh immediately: **Actions → Refresh data and publish site → Run
workflow.**

#### What is public, and what is not

The repository is public, so assume anything committed can be read by anyone. These are
gitignored and stay on your machine:

- `notes/my_investing_preferences.md` — your risk tolerance and goals
- `portfolio/investment_log.csv` — what you actually own
- `.env` — the SEC contact address and the email password

The published site shows the research: scores, theses, predictions and their outcomes. It does
not show your positions. Before adding anything new to the site, check which side of that line
it falls on.

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
│   ├── judge.py          ** The only file that calls a model **
│   └── universe.py       The list of stocks to search
│
├── api/               Read-only HTTP API over everything above (FastAPI)
├── web/               The browser interface (Next.js + TypeScript)
│   └── public/data/     Exported JSON the site reads - generated, never hand-edited
├── .github/workflows/ Scheduled refresh and site publishing (free, no model calls)
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
│                      GIT_FOR_BEGINNERS.md · MODEL_IN_THE_LOOP.md
│                      FRONTEND_SPEC.md · PLATFORM_ROADMAP.md · BUILD_PLAN.md
├── LOG.md             What was planned, and what changed as it was built
├── research/theses/     Full write-ups, one per company
├── research/judgments/  The five judgment pillars, per company
│   ├── _rejected/         Model answers that failed validation, kept on purpose
│   └── _backtest/         Model answers compared against hand-written ones
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

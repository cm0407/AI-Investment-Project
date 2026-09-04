"""Create the Beginner Digest skeleton for a session, pre-filled with verified data.

USAGE
    python scripts/make_digest.py
    python scripts/make_digest.py --tickers AAPL JNJ --macro

WHAT IT DOES AND DOES NOT DO
    It fills in everything that can be VERIFIED: today's date, live prices, the macro
    backdrop, the computed metrics, and the boilerplate structure CLAUDE.md specifies.

    It leaves every JUDGMENT as an explicit TODO: the plain-English upside case, the
    downside, the probabilities, the score, the BUY/WATCH/AVOID call. Those are the parts
    that require an analyst to have actually done Phases 2-5, and a script that filled
    them in with placeholder optimism would be manufacturing exactly the false confidence
    this project is built to avoid.

    The digest is a container for reasoning, not a substitute for it.
"""

from __future__ import annotations

import argparse
from datetime import date

import _bootstrap  # noqa: F401
from invest import config, fred, metrics, prices
from invest import sec_edgar as sec


def preferences_ready() -> tuple[bool, str]:
    """CLAUDE.md forbids recommending anything before the user's preferences are known."""
    if not config.PREFERENCES_FILE.exists():
        return False, "notes/my_investing_preferences.md does not exist"
    text = config.PREFERENCES_FILE.read_text(encoding="utf-8")
    unset = text.count("<UNSET>")
    if unset:
        return False, (str(unset) + " field(s) still marked <UNSET> in "
                       "notes/my_investing_preferences.md")
    return True, "preferences on file"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the daily digest skeleton.")
    ap.add_argument("--tickers", nargs="*", default=[], help="ideas to pre-fill with data")
    ap.add_argument("--macro", action="store_true", help="include the FRED macro backdrop")
    ap.add_argument("--date", default=None)
    args = ap.parse_args()

    config.ensure_dirs()
    today = args.date or date.today().isoformat()
    out = config.DAILY_REPORTS_DIR / ("digest_" + today + ".md")

    ready, pref_msg = preferences_ready()

    L: list[str] = []
    L.append("# INVEST - Daily Digest - " + today)
    L.append("")
    L.append("**Reminder: these are researched ideas, not guarantees. Not financial "
             "advice.** Claude is not a licensed financial advisor. Individual stock "
             "picking is a small *satellite* around a diversified core (like index "
             "funds), never a replacement for one.")
    L.append("")

    if not ready:
        L.append("> ## ⛔ BLOCKED: no recommendations may be issued")
        L.append("> " + pref_msg + ".")
        L.append("> CLAUDE.md requires the user's risk tolerance, horizon and avoid-list to "
                 "be on file before any stock is recommended. Fill in "
                 "`notes/my_investing_preferences.md`, then re-run this script.")
        L.append("> Research and data below are still valid; the BUY/WATCH/AVOID calls are not.")
        L.append("")

    L.append("## The 30-second version")
    L.append("")
    L.append("_TODO (analyst): 2-3 plain sentences - market mood, how many stocks were "
             "reviewed, the single best idea, and how confident you are in plain words. "
             "Write this LAST, after the work below is done._")
    L.append("")

    if args.macro:
        print("Pulling macro backdrop from FRED...")
        dash = fred.dashboard(verbose=True)
        L.append("## The backdrop (what the economy is doing)")
        L.append("")
        L.append("| Indicator | Latest | As of | What it is |")
        L.append("|---|---|---|---|")
        for sid, data in dash["series"].items():
            latest = data.get("latest")
            if not latest:
                L.append("| " + sid + " | " + config.MISSING + " | - | "
                         + data.get("description", "") + " |")
                continue
            L.append("| `" + sid + "` | " + format(latest["value"], ".2f") + " | "
                     + latest["date"] + " | " + data.get("description", "") + " |")
        L.append("")
        L.append("_Source: FRED (Federal Reserve Bank of St. Louis), official statistics. "
                 "Some series lag by weeks or months - 'latest' means latest published._")
        L.append("")
        L.append("_TODO (analyst): in one or two sentences, what does this backdrop mean "
                 "for the ideas below? Name any thesis that quietly depends on rates "
                 "falling or the consumer holding up._")
        L.append("")

    if args.tickers:
        L.append("## Ideas")
        L.append("")
        for i, tk in enumerate(args.tickers, 1):
            tk = tk.upper()
            print("Pulling data for " + tk + " ...")
            try:
                fund = sec.fundamentals(tk, years=6, verbose=False)
                q = prices.quote(tk, period="2y", verbose=False)
                m = metrics.compute(fund, price=q["price"])
            except Exception as exc:
                L.append("### Idea #" + str(i) + " - " + tk)
                L.append("")
                L.append("**DATA PULL FAILED:** " + str(exc)[:200])
                L.append("")
                continue

            L.append("### Idea #" + str(i) + " - " + str(fund["company_name"])
                     + " (ticker: " + tk + ")")
            L.append("")
            L.append("- **In one sentence:** _TODO (analyst): what the company does + the "
                     "core reason it is interesting._")
            L.append("- **Why it might rise 20%+:** _TODO (analyst): the plain-English "
                     "upside case, built on the numbers below - not on a story._")
            L.append("- **What could go wrong:** _TODO (analyst): the honest downside. "
                     "CLAUDE.md Phase 5 - never skip this, never soften it._")
            L.append("- **My honest read:** If it goes well -> ~+X%. If it goes badly -> "
                     "~-Y%. Chance of a positive return: ~A%. Chance of hitting +20%: ~B%. "
                     "_TODO (analyst): these must come from written bear/base/bull cases, "
                     "not from a feeling._")
            L.append("- **Score:** _TODO_ /100 · **Suggested action:** _TODO: BUY / WATCH / "
                     "AVOID_"
                     + ("" if ready else "  ← **cannot be issued until preferences are on file**"))
            L.append("")
            L.append("**Verified facts (auto-filled, sourced):**")
            L.append("")
            L.append("| Item | Value | Source |")
            L.append("|---|---|---|")

            def add(label, value, kind, source, dec=1):
                L.append("| " + label + " | " + metrics.format_metric(value, kind, dec)
                         + " | " + source + " |")

            sec_src = "SEC 10-K (FY ending " + str(m.get("revenue_period") or "?") + ")"
            add("Share price", q["price"], "usd", "Yahoo Finance, " + q["price_date"], 2)
            add("Market cap", m.get("market_cap"), "usd",
                "price x SEC-filed share count", 2)
            add("Revenue (latest FY)", m.get("revenue_latest"), "usd", sec_src, 2)
            add("Revenue growth (CAGR)", m.get("revenue_cagr_pct"), "pct", sec_src)
            add("Operating margin", m.get("operating_margin_pct"), "pct", sec_src)
            add("Net margin", m.get("net_margin_pct"), "pct", sec_src)
            add("Free cash flow", m.get("fcf_latest"), "usd", sec_src, 2)
            add("Return on invested capital", m.get("roic_pct"), "pct", sec_src)
            add("Debt / equity", m.get("debt_to_equity"), "x", sec_src, 2)
            add("P/E ratio", m.get("pe_ratio"), "x", "derived", 1)
            add("P/FCF ratio", m.get("pfcf_ratio"), "x", "derived", 1)
            add("FCF yield", m.get("fcf_yield_pct"), "pct", "derived")
            add("1-year price change", q["returns"]["1_year_pct"], "pct",
                "Yahoo Finance", 1)
            L.append("")

            sect = m.get("_sector", {})
            if sect.get("special"):
                L.append("> ⚠️ **" + str(sect.get("kind")).title() + " company.** "
                         + str(sect.get("note")))
                L.append("")
            if m.get("_fallback_tags_used") or m.get("_composites_suppressed"):
                L.append("> **Data caveats for this company:**")
                for c, e in (m.get("_fallback_tags_used") or {}).items():
                    L.append("> - `" + c + "` came from the fallback tag `"
                             + str(e.get("tag_used")) + "`, not `"
                             + str(e.get("preferred_tag")) + "`.")
                for s in (m.get("_composites_suppressed") or []):
                    L.append("> - " + s)
                L.append("")

            L.append("- **Jargon I used:** _TODO (analyst): define anything a newcomer "
                     "would not know, or point to `notes/GLOSSARY.md`._")
            L.append("")

    L.append("## Portfolio note")
    L.append("")
    L.append("_TODO (analyst): if more than one idea is listed, check for correlation and "
             "sector concentration, and size positions by conviction and risk. Never "
             "recommend putting all capital into one stock. Separate high-conviction ideas "
             "from speculative ones._")
    L.append("")
    L.append("## Housekeeping")
    L.append("")
    L.append("- [ ] Every prediction above appended to `memory/predictions.csv`")
    L.append("- [ ] Reasoning recorded in `memory/decisions_and_reasoning.md`")
    L.append("- [ ] Rejected ideas logged in `memory/rejected_stocks.md`")
    L.append("- [ ] `memory/research_state.md` updated")
    L.append("- [ ] New lessons appended to `memory/lessons_learned.md`")
    L.append("- [ ] Changes committed to git")
    L.append("")
    L.append("---")
    L.append("")
    L.append("_Generated by `scripts/make_digest.py` on " + today + ". Auto-filled figures "
             "come from SEC EDGAR filings and Yahoo Finance market data; every judgment is "
             "marked TODO because a script cannot make one._")

    out.write_text("\n".join(L), encoding="utf-8")
    print("\nWrote " + str(out.relative_to(config.ROOT)))
    print("\nPreferences check: " + ("OK - " if ready else "BLOCKED - ") + pref_msg)
    todos = "\n".join(L).count("TODO")
    print(str(todos) + " TODO(s) left for the analyst. The digest is a container for "
          "reasoning,\nnot a substitute for it - fill them in before showing this to anyone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

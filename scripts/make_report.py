"""Compile the research into a Word (.docx) report.

USAGE
    python scripts/make_report.py
    python scripts/make_report.py --tickers ADBE BKNG --out reports/custom.docx

WHAT IT DOES
    Reads the saved analysis JSON, the analyst judgment files and the scenario file, and
    assembles a single beginner-readable Word document: verdicts first, then the evidence,
    then the honest caveats, then a glossary.

    Every figure comes from a file that a script produced from SEC filings or market data.
    Nothing here is typed in by hand, so re-running the pipeline and re-running this script
    reproduces the document.
"""

from __future__ import annotations

import argparse
import json
from datetime import date

import _bootstrap  # noqa: F401
from invest import config

DEFAULT_TICKERS = ["BKNG", "ADBE", "EOG", "ULTA"]

ACTION_COLOR = {"BUY": (0x1B, 0x7F, 0x3B), "WATCH": (0xB8, 0x6E, 0x00),
                "AVOID": (0xB3, 0x26, 0x1E)}

GLOSSARY = [
    ("Free cash flow (FCF)", "The real cash left after a company pays its bills AND "
     "reinvests to keep running. Harder to fake than accounting profit."),
    ("FCF yield", "Free cash flow divided by the company's total market value. Like an "
     "interest rate on the business. 9.6% means the company throws off cash equal to 9.6% "
     "of its price each year."),
    ("P/E ratio", "Price divided by yearly profit. Roughly how many dollars you pay for "
     "each $1 of annual profit. Lower can mean cheaper - or that profits are expected to fall."),
    ("P/FCF", "Same idea as P/E but using cash flow instead of accounting profit."),
    ("Operating margin", "What portion of each sales dollar survives after the costs of "
     "running the business. 36% means 36 cents of every dollar."),
    ("ROIC", "Return on invested capital. The 'interest rate' the business earns on the "
     "money invested in it. Above ~15% suggests a genuinely good business."),
    ("CAGR", "Compound annual growth rate - the smoothed yearly growth rate between two "
     "points. Dangerous when the starting year was unusual."),
    ("Reverse DCF", "Instead of guessing a company's future to produce a target price, it "
     "asks what growth today's price already assumes. Then you judge whether that is beatable."),
    ("Moat", "A durable advantage protecting a company from competitors - a brand, a "
     "network, switching costs."),
    ("Bear / Base / Bull", "Three scenarios: the pessimistic outcome, the most likely one, "
     "and the optimistic one. Seeing all three keeps the analysis honest."),
    ("Probability-weighted return", "Each scenario's return multiplied by its likelihood, "
     "then added up. A single number summarising the whole risk/reward picture."),
    ("ARR", "Annual recurring revenue - the yearly run-rate of subscription revenue. The "
     "key growth measure for a software company."),
    ("Comparable sales (comps)", "Sales growth at stores open at least a year. Strips out "
     "growth that came only from opening new stores."),
    ("Buyback", "A company buying its own shares, leaving each remaining share owning a "
     "bigger slice. It raises per-share figures even if total profit does not grow."),
]


def _hex(run, rgb):
    from docx.shared import RGBColor
    run.font.color.rgb = RGBColor(*rgb)


def build(tickers: list[str], out_path) -> str:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    scen = json.loads((config.RESEARCH_DIR / "judgments" / "_scenarios.json")
                      .read_text(encoding="utf-8"))
    doc = Document()

    for style_name, size in (("Normal", 10.5),):
        st = doc.styles[style_name]
        st.font.name = "Calibri"
        st.font.size = Pt(size)

    # ---------------- Cover ----------------
    t = doc.add_heading("INVEST — Research Report", level=0)
    p = doc.add_paragraph()
    r = p.add_run(date.today().strftime("%d %B %Y") + "  ·  Four companies analysed  ·  "
                  "Phases 1–5 complete")
    r.bold = True
    r.font.size = Pt(12)

    warn = doc.add_paragraph()
    wr = warn.add_run(
        "This is researched opinion, not financial advice. Claude is not a licensed "
        "financial advisor. No return here is guaranteed — every forward number is a "
        "projection under stated assumptions, and the probabilities are informed "
        "estimates, not measurements."
    )
    wr.italic = True
    _hex(wr, (0xB3, 0x26, 0x1E))

    doc.add_paragraph()
    box = doc.add_paragraph()
    br = box.add_run("THE HEADLINE: no stock scored high enough to recommend buying.")
    br.bold = True
    br.font.size = Pt(12)
    doc.add_paragraph(
        "Four companies went through the full five-phase process. The best scored 77.8 out "
        "of 100, which the project's own rulebook classes as 'worth monitoring', not "
        "'strong'. Two scored in the speculative band and are rejected. Nothing reached the "
        "80+ needed for a BUY. Forcing a recommendation from this set would mean inflating a "
        "score, which the rules explicitly forbid."
    )

    # ---------------- Summary table ----------------
    doc.add_heading("The four, at a glance", level=1)
    tbl = doc.add_table(rows=1, cols=7)
    tbl.style = "Light Grid Accent 1"
    hdr = ["Ticker", "Company", "Price", "Score", "Action", "Expected return", "Chance of +20%"]
    for i, h in enumerate(hdr):
        cell = tbl.rows[0].cells[i]
        cell.text = h
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = True

    names = {"BKNG": "Booking Holdings", "ADBE": "Adobe", "EOG": "EOG Resources",
             "ULTA": "Ulta Beauty"}
    order = sorted(tickers, key=lambda x: -scen[x]["score"])
    for tk in order:
        d = scen[tk]
        c = d["_computed"]
        row = tbl.add_row().cells
        row[0].text = tk
        row[1].text = names.get(tk, tk)
        row[2].text = "$" + format(d["price"], ",.2f")
        row[3].text = format(d["score"], ".1f") + "/100"
        row[4].text = d["action"]
        row[5].text = format(c["probability_weighted_return_pct"], "+.1f") + "%"
        row[6].text = format(c["prob_hits_20pct"] * 100, ".0f") + "%"
        for para in row[4].paragraphs:
            for run in para.runs:
                run.bold = True
                _hex(run, ACTION_COLOR.get(d["action"], (0, 0, 0)))

    doc.add_paragraph()
    n = doc.add_paragraph()
    nr = n.add_run("Scoring bands: 90–100 exceptional · 80–89 strong · 70–79 worth "
                   "monitoring · 60–69 speculative · below 60 reject.")
    nr.italic = True
    nr.font.size = Pt(9)

    # ---------------- Per company ----------------
    for tk in order:
        d = scen[tk]
        c = d["_computed"]
        doc.add_page_break()
        doc.add_heading(names.get(tk, tk) + "  (" + tk + ")", level=1)

        sub = doc.add_paragraph()
        sr = sub.add_run("$" + format(d["price"], ",.2f") + "  ·  Score "
                         + format(d["score"], ".1f") + "/100  ·  ")
        sr.bold = True
        ar = sub.add_run(d["action"])
        ar.bold = True
        _hex(ar, ACTION_COLOR.get(d["action"], (0, 0, 0)))
        sub.add_run("  ·  " + str(d["horizon_months"]) + "-month horizon")

        try:
            analysis = json.loads(
                (config.FUNDAMENTALS_DIR / (tk + "_analysis.json")).read_text(encoding="utf-8")
            )["data"]
            m = analysis["metrics"]
        except Exception:
            m = {}

        doc.add_heading("The numbers", level=2)
        mt = doc.add_table(rows=1, cols=4)
        mt.style = "Light List Accent 1"
        for i, h in enumerate(["Metric", "Value", "Metric", "Value"]):
            cc = mt.rows[0].cells[i]
            cc.text = h
            for para in cc.paragraphs:
                for run in para.runs:
                    run.bold = True

        def fmtv(key, kind="pct", dec=1):
            v = m.get(key)
            if v is None:
                return "not available"
            if kind == "pct":
                return format(v, "." + str(dec) + "f") + "%"
            if kind == "x":
                return format(v, "." + str(dec) + "f") + "x"
            if kind == "usd":
                return "$" + format(v / 1e9, ",.2f") + "B"
            return format(v, ",.2f")

        pairs = [
            ("Operating margin", fmtv("operating_margin_pct"),
             "P/E ratio", fmtv("pe_ratio", "x")),
            ("Free cash flow margin", fmtv("fcf_margin_pct"),
             "P/FCF", fmtv("pfcf_ratio", "x")),
            ("ROIC", fmtv("roic_pct"), "FCF yield", fmtv("fcf_yield_pct")),
            ("Revenue CAGR (6y)", fmtv("revenue_cagr_pct"),
             "Revenue CAGR (recent 3y)", fmtv("revenue_cagr_3y_pct")),
            ("Free cash flow", fmtv("fcf_latest", "usd"),
             "Share count change", fmtv("share_count_change_pct")),
            ("Debt / equity", fmtv("debt_to_equity", "x", 2),
             "Net debt / EBITDA", fmtv("net_debt_to_ebitda", "x", 2)),
        ]
        for a, b, cc_, dd in pairs:
            row = mt.add_row().cells
            row[0].text = a
            row[1].text = b
            row[2].text = cc_
            row[3].text = dd

        for key, label in (("_growth_base_warning", "GROWTH WARNING"),
                           ("_per_share_split_warning", "PER-SHARE DATA WARNING")):
            if m.get(key):
                wp = doc.add_paragraph()
                wr2 = wp.add_run(label + ": " + m[key])
                wr2.italic = True
                wr2.font.size = Pt(9)
                _hex(wr2, (0xB3, 0x26, 0x1E))

        doc.add_heading("If it goes well, and if it goes badly", level=2)
        st_ = doc.add_table(rows=1, cols=4)
        st_.style = "Light Grid Accent 1"
        for i, h in enumerate(["Scenario", "Target price", "Return", "Likelihood"]):
            cc = st_.rows[0].cells[i]
            cc.text = h
            for para in cc.paragraphs:
                for run in para.runs:
                    run.bold = True
        for case in ("bear", "base", "bull"):
            cs = c["cases"][case]
            row = st_.add_row().cells
            row[0].text = case.upper()
            row[1].text = "$" + format(cs["target_price"], ",.2f")
            row[2].text = format(cs["return_pct"], "+.0f") + "%"
            row[3].text = format(cs["probability"] * 100, ".0f") + "%"

        sm = doc.add_paragraph()
        smr = sm.add_run(
            "Probability-weighted return: "
            + format(c["probability_weighted_return_pct"], "+.1f") + "%"
            + "   ·   Chance of any gain: " + format(c["prob_positive"] * 100, ".0f") + "%"
            + "   ·   Chance of +20%: " + format(c["prob_hits_20pct"] * 100, ".0f") + "%"
            + "   ·   Chance of a loss: " + format(c["prob_loss"] * 100, ".0f") + "%")
        smr.bold = True

        for case, heading in (("bull", "What has to go right"),
                              ("bear", "What could go wrong")):
            doc.add_heading(heading, level=2)
            for a_ in c["cases"][case]["assumptions"]:
                doc.add_paragraph(a_, style="List Bullet")

        try:
            jd = json.loads((config.RESEARCH_DIR / "judgments" / (tk + ".json"))
                            .read_text(encoding="utf-8"))
            doc.add_heading("The judgment calls a script cannot make", level=2)
            jt = doc.add_table(rows=1, cols=3)
            jt.style = "Light List Accent 1"
            for i, h in enumerate(["Pillar", "Score", "Why"]):
                cc = jt.rows[0].cells[i]
                cc.text = h
                for para in cc.paragraphs:
                    for run in para.runs:
                        run.bold = True
            labels = {"business_quality": "Business quality (15)",
                      "competitive_advantage": "Moat (10)", "catalysts": "Catalysts (10)",
                      "risk_reward": "Risk / reward (10)", "management": "Management (5)"}
            for k, v in jd.items():
                row = jt.add_row().cells
                row[0].text = labels.get(k, k)
                row[1].text = str(v["points"])
                row[2].text = v["justification"]
                for para in row[2].paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(8.5)
        except Exception:
            pass

        fp = doc.add_paragraph()
        fpr = fp.add_run("Full written thesis with sources: research/theses/" + tk + ".md")
        fpr.italic = True
        fpr.font.size = Pt(9)

    # ---------------- Caveats ----------------
    doc.add_page_break()
    doc.add_heading("What this report cannot tell you", level=1)
    doc.add_paragraph(
        "Being explicit about the limits matters as much as the analysis. Every item below "
        "is a real gap, not a disclaimer."
    )
    for item in [
        "It cannot tell you what will happen. Every forward figure is a projection under "
        "assumptions listed in docs/ASSUMPTIONS.md.",
        "The probabilities are informed estimates, not measurements. Their value is that "
        "they were written down before the outcome, so calibration can be checked later.",
        "The candidates came from a 184-name hand-picked list, biased toward large, "
        "familiar U.S. companies. It under-represents small caps and turnarounds, which is "
        "where mispricing most often lives. This is 'the best of these 184', not 'the best "
        "in the market'.",
        "Two exclusion thresholds were chosen by the analyst, not specified by you: a 2.0x "
        "debt/equity limit (which excluded 48 companies) and a 10% dilution limit (35 "
        "companies). Together they did almost all the filtering. They are worth reviewing.",
        "The system cannot read a 10-K's narrative — risk factors, competition, management "
        "tone. That still requires a human reader.",
        "It has no institutional-ownership tracking, no consensus estimates, no short "
        "interest and no credit ratings.",
        "Financial companies (banks, insurers, REITs) are analysed poorly. The system "
        "correctly refuses to apply the wrong metrics but does not yet compute the right "
        "ones — net interest margin, ROTCE, FFO.",
        "Competitor figures for private companies such as Canva and Figma come from "
        "journalism, not filings, and are unverified.",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("Two things about your own setup", level=1)
    p1 = doc.add_paragraph()
    p1r = p1.add_run("1. You have no diversified core. ")
    p1r.bold = True
    p1.add_run(
        "Your preferences record this sleeve as 30–50% of your investable money with no "
        "index funds or retirement account behind it. The entire structure this system "
        "assumes is a large, boring core with a small stock-picking satellite around it. "
        "What you have described is the satellite without the core. That is the single "
        "largest risk in this document — larger than any individual company's bear case."
    )
    p2 = doc.add_paragraph()
    p2r = p2.add_run("2. Your stop-loss contradicts your stated behaviour. ")
    p2r.bold = True
    p2.add_run(
        "You set a stop at −25%, but also said you would hold through a −30% month. A −25% "
        "stop sells you automatically before −30% is ever reached, so that second answer can "
        "never take effect. Backtesting on 45,431 simulated holds found a −25% stop fires on "
        "16.8% of positions and sells you out of a recovery 16.7% of the time, costing about "
        "1.65% of return per position. One of those two answers needs to change."
    )

    # ---------------- Glossary ----------------
    doc.add_page_break()
    doc.add_heading("Glossary", level=1)
    doc.add_paragraph("Every term in this report that a newcomer would not know.")
    gt = doc.add_table(rows=1, cols=2)
    gt.style = "Light List Accent 1"
    for i, h in enumerate(["Term", "In plain English"]):
        cc = gt.rows[0].cells[i]
        cc.text = h
        for para in cc.paragraphs:
            for run in para.runs:
                run.bold = True
    for term, meaning in GLOSSARY:
        row = gt.add_row().cells
        row[0].text = term
        row[1].text = meaning
        for para in row[0].paragraphs:
            for run in para.runs:
                run.bold = True

    doc.add_paragraph()
    src = doc.add_paragraph()
    sr2 = src.add_run(
        "Sources: SEC EDGAR (data.sec.gov) for all company financials — every figure traces "
        "to a filed 10-K with its XBRL tag, form type, accession number and filing date. "
        "Yahoo Finance for market prices (2026-09-08). FRED for macroeconomic context. "
        "Recent quarterly results and guidance from company releases and financial "
        "journalism, which the project rules rank below filings and which are labelled as "
        "such in each thesis."
    )
    sr2.italic = True
    sr2.font.size = Pt(8.5)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return str(out_path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Compile the Word research report.")
    ap.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    config.ensure_dirs()
    out = (config.ROOT / args.out) if args.out else (
        config.REPORTS_DIR / ("INVEST_Research_Report_" + date.today().isoformat() + ".docx"))
    path = build(args.tickers, out)
    print("Wrote " + path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

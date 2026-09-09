# Decisions and Reasoning

The "why" behind every recommendation, in the analyst's own words, recorded at the moment of the
decision — before the outcome is known. `predictions.csv` stores the numbers; this file stores the
reasoning that produced them. Together they make calibration possible.

**Append only.** Never revise an entry after the fact. If the view changes, write a new entry that
says so and links back.

Format:

```
### YYYY-MM-DD — TICKER — ACTION (BUY / WATCH / AVOID)
**The thesis in one sentence:**
**What I believe that the market seems not to:**
**The three numbers the thesis rests on:**
**What would prove me wrong (thesis-breaking risk):**
**Why this size / why this conviction score:**
**What I could not verify:**
**Links:** research/theses/TICKER.md · predictions.csv row date
```

---

*No decisions recorded yet — system built 2026-09-03, no research conducted.*

### 2026-09-09 — ADBE — WATCH
**The thesis in one sentence:** An exceptionally profitable software franchise (36.6% operating
margin, 63.2% ROIC, 41.4% FCF margin) is priced at 14.3x earnings because the market believes
AI will destroy it, and that belief may be overdone.
**What I believe that the market seems not to:** that the enterprise and professional core is
far more defensible than the prosumer flank being lost to Canva and Figma, and that a reverse
DCF implying 1–2% perpetual FCF growth is too pessimistic for a business compounding at 13%.
**The three numbers the thesis rests on:** ARR growth of ~10.9% (must stabilise, not decay);
free cash flow of $9.85B against a $102.3B market cap (9.6% yield); and undistorted revenue
growth of +23/+12/+10/+11/+11% — the only clean series among the four candidates.
**What would prove me wrong (thesis-breaking risk):** two consecutive quarters of ARR growth
below 8%, or falling net revenue retention in the enterprise segment. Either means the erosion
has reached the core, and the position should be abandoned rather than averaged down.
**Why this size / why this conviction score:** 72.7 is "worth monitoring", not "strong". The
bear case is structural rather than cyclical, so a 25% chance of +20% does not justify size.
**What I could not verify:** Canva and Figma ARR growth rates come from journalism, not
filings — they are private companies. Adobe's segment-level ARR detail was not read from the
10-K narrative.
**Links:** research/theses/ADBE.md · predictions.csv row 2026-09-09

### 2026-09-09 — BKNG — WATCH
**The thesis in one sentence:** The best business of the four and the highest score, but priced
at 25x earnings into management-guided deceleration, which leaves no margin of safety.
**What I believe that the market seems not to:** nothing material. This is a fairly-priced
quality company, which is precisely why it is a WATCH rather than a BUY — I found no
mispricing to exploit.
**The three numbers the thesis rests on:** $9.09B free cash flow; a 20.7% reduction in share
count; and Q3 guidance of just 3–5% room-night growth.
**What would prove me wrong (thesis-breaking risk):** two consecutive quarters of negative
room-night growth, or marketing spend rising as a share of gross bookings just to hold volume
flat — which would mean the network effect is being rented, not owned.
**Why this size / why this conviction score:** 77.8 is the top score but the probability-
weighted return is only +8.4% against a −33% bear. The score flatters it: the growth pillar
earned 13.1/15 on CAGRs inflated by the 2020 covid trough.
**What I could not verify:** whether the 55 insider sales against zero purchases were all
pre-scheduled 10b5-1 plans. Footnotes not read.
**Links:** research/theses/BKNG.md · predictions.csv row 2026-09-09

### 2026-09-09 — EOG — AVOID
**The thesis in one sentence:** A good operator whose return is a disguised oil-price bet I
cannot responsibly make.
**What I believe that the market seems not to:** nothing. I have no edge on the oil price, and
saying so is the honest position.
**The three numbers the thesis rests on:** 12.5% FCF yield; −4.2% recent three-year revenue
CAGR; and the 2026 plan's ~$4.5B FCF target at strip pricing.
**What would prove me wrong:** if oil rallies materially I will look wrong, and that will be
luck rather than analysis. Recording this now so the outcome is judged on process.
**Why this conviction score:** 67.6, and even that is generous — the growth pillar earned
12.0/15 on a CAGR that inverts the truth about a shrinking business.
**What I could not verify:** reserve quality, per-barrel breakeven costs, hedging positions.
**Links:** research/theses/EOG.md · predictions.csv row 2026-09-09

### 2026-09-09 — ULTA — AVOID
**The thesis in one sentence:** A good business whose profits are shrinking while its stock is
priced as though they are growing, with buybacks obscuring the decline.
**What I believe that the market seems not to:** that the raised August guidance is a weaker
signal than it appears, because ~12% guided EPS growth sits on a ~5% annual share-count
reduction and three straight years of falling operating income.
**The three numbers the thesis rests on:** operating income $1.68B → $1.56B → $1.53B; diluted
shares 50M → 45M; and a +1.6% probability-weighted return.
**What would prove me wrong (thesis-breaking risk):** one quarter of year-over-year operating
margin EXPANSION. That would mean the compression was cyclical and I misread it as structural.
**Why this conviction score:** 66.2, the lowest of the four, driven by the weakest risk/reward
(4/10) of any candidate.
**What I could not verify:** the mix between promotional discounting and cost inflation as the
cause of margin compression — that requires reading the MD&A section of the 10-K.
**Links:** research/theses/ULTA.md · predictions.csv row 2026-09-09

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

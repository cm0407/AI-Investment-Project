# Judgment files

Half of this system's 100-point score is arithmetic over SEC filings. The other half is
judgement, and it lives here: five pillars per company — business quality (15), competitive
advantage (10), catalysts (10), risk/reward (10), management (5) — each with a written argument.

## How to tell who wrote one

```json
"_model_run": { "source": "model", "attempts": 1, "checks_passed": [...] }
```

**If a file has a `_model_run` key, a model wrote it.** If it does not, a person did.

A hand-written file is never overwritten by the model: `judge()` returns the existing judgment
untouched when it finds no `_model_run` key, and `score_stock.py --judgment <file>` beats
`--judge` outright. The override runs one way only.

## The subdirectories

| | |
|---|---|
| `_backtest/` | Model output from the 2026-10-25 experiment, kept as evidence. |
| `_rejected/` | Model answers that **failed validation**, kept on purpose. |
| `_scenarios*.json` | Bear/base/bull inputs — unrelated to the judgment pillars. |

### `_backtest/` — the experiment

The 14 files in this directory that a person wrote are the **control group**. On 2026-10-25 the
model scored the same companies from the same evidence; its answers went to `_backtest/`
(`TICKER_runN.json`) and the originals were restored byte-for-byte afterwards.

Result: mean absolute deviation **3.38 points out of 50**, with four of five pillars agreeing to
within half a point. The whole gap is the catalysts pillar at **-2.77**, which is a defect in the
evidence rather than the model — catalysts are dated future events and the evidence pack is built
from SEC filings, which do not contain them. Repeat runs of the same evidence spread by **0.7
points on average**. Full write-up in `LOG.md` and `docs/MODEL_IN_THE_LOOP.md`.

To reproduce:

```bash
python scripts/backtest_judge.py                              # all of them
python scripts/backtest_judge.py --tickers ADBE --repeat 3    # determinism
```

### `_rejected/` — the failures, kept

A verdict is discarded unless it passes seven checks. Rejections are written here with the
failing check named, tagged `recovered_on_retry` or `abandoned`, **whether or not a later attempt
succeeded** — because a rejection rate that only counts total failures reads 0% while the
validators are busy firing, which is exactly what happened the first time this was measured.

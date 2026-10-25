"""Does the model agree with the human? Backtest `judge.py` against hand-written judgments.

USAGE
    python scripts/backtest_judge.py                 # all analyst-written judgments
    python scripts/backtest_judge.py --tickers INTU PTC
    python scripts/backtest_judge.py --repeat 3      # also measure run-to-run spread

WHY THIS EXISTS
    `research/judgments/*.json` holds judgments written by Claude IN CONVERSATION and saved by
    hand. That is a free, pre-existing test set for the in-pipeline model: same companies, same
    pillars, same schema, scored by a model that had full context and could search the web.

    Running `judge.py` over the same companies gives a direct read on three things the artifact
    needs to report honestly:

      1. AGREEMENT     - mean absolute deviation per pillar. Systematic gaps matter more than
                         the average: a model consistently kinder on moats is a finding.
      2. REJECTION     - what fraction fail validation, and which of the seven checks fires.
      3. DETERMINISM   - same evidence, repeated. If scores swing several points the output
                         should be reported as a range, not a point estimate.

    Model judgments are written to `research/judgments/_backtest/` so the hand-written
    originals are never overwritten - they are the control group.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import _bootstrap  # noqa: F401
from invest import config, judge, metrics, prices
from invest import sec_edgar as sec

OUT_DIR = config.RESEARCH_DIR / "judgments" / "_backtest"


def analyst_judgments() -> dict[str, dict]:
    """Hand-written judgments: no `_model_run` key means a human wrote it."""
    out = {}
    for p in sorted((config.RESEARCH_DIR / "judgments").glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if "_model_run" in d:
            continue
        if all(k in d for k in judge.PILLAR_CAPS):
            # Keep the raw bytes, not just the parsed dict. Restoring via json.dumps
            # round-trips the file and loses the trailing newline, which shows up as a
            # one-byte diff on all 14 control files. The hand-written judgments are the
            # control group for this experiment; they must come back byte-identical.
            out[p.stem] = {"data": d, "raw": p.read_bytes()}
    return out


def evidence_for(ticker: str):
    """Rebuild the same inputs the scorer would use."""
    fund = sec.fundamentals(ticker, years=6, verbose=False)
    try:
        q = prices.quote(ticker, period="2y", verbose=False)
        px, vol = q["price"], q["annualized_volatility_pct"]
    except Exception:
        px, vol = None, None
    m = metrics.compute(fund, price=px)
    m["annual_volatility_pct"] = vol
    return m, fund


def main() -> int:
    ap = argparse.ArgumentParser(description="Backtest model judgments against human ones.")
    ap.add_argument("--tickers", nargs="*", default=None)
    ap.add_argument("--repeat", type=int, default=1,
                    help="runs per company, to measure determinism")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    config.ensure_dirs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    human = analyst_judgments()
    tickers = args.tickers or sorted(human)
    if args.limit:
        tickers = tickers[:args.limit]

    print("BACKTEST - model judgments vs hand-written judgments")
    print("Control group: " + str(len(human)) + " analyst-written files")
    print("Testing: " + ", ".join(tickers))
    print("Runs per company: " + str(args.repeat))
    print()

    rows: list[dict] = []
    rejected: list[dict] = []
    started = time.time()
    RETRIES = 1                      # judge() default: one try plus one retry
    tally = {"calls": 0, "rejected": 0, "recovered": 0, "abandoned": 0, "checks": {}}

    for i, tk in enumerate(tickers, 1):
        print("[" + str(i) + "/" + str(len(tickers)) + "] " + tk)
        try:
            m, fund = evidence_for(tk)
        except Exception as exc:
            print("    data failed: " + str(exc)[:110])
            continue

        runs = []
        for r in range(args.repeat):
            verdict = judge.judge(tk, m, fund, refresh=True, verbose=True)
            if verdict is None:
                # every attempt failed; judge() fell back to the PARTIAL score
                tally["abandoned"] += 1
                tally["calls"] += RETRIES + 1
                tally["rejected"] += RETRIES + 1
                rejected.append({"ticker": tk, "run": r + 1})
                continue

            # Count the calls THIS invocation made. Reading _backtest/ off disk mixes in
            # files left by earlier runs, which is how the first version of this report
            # claimed 21 model calls for a 9-call run.
            meta = verdict.get("_model_run") or {}
            n = int(meta.get("attempts") or 1)
            tally["calls"] += n
            tally["rejected"] += n - 1
            if n > 1:
                tally["recovered"] += 1
                rejected.append({"ticker": tk, "run": r + 1, "note": "retried then accepted"})
            for name in meta.get("checks_failed_before_acceptance", []):
                tally["checks"][name] = tally["checks"].get(name, 0) + 1

            runs.append({p: verdict[p]["points"] for p in judge.PILLAR_CAPS})
            # keep the model's output; never clobber the human original
            (OUT_DIR / (tk + "_run" + str(r + 1) + ".json")).write_text(
                json.dumps(verdict, indent=2), encoding="utf-8")

        if not runs:
            continue

        h = (human.get(tk) or {}).get("data")
        row = {"ticker": tk, "runs": runs,
               "model_total": statistics.mean(sum(r.values()) for r in runs),
               "human_total": sum(h[p]["points"] for p in judge.PILLAR_CAPS) if h else None}
        if args.repeat > 1:
            totals = [sum(r.values()) for r in runs]
            row["spread"] = max(totals) - min(totals)
        rows.append(row)

    # restore: the backtest used refresh=True which rewrote the live files
    for tk, original in human.items():
        p = config.RESEARCH_DIR / "judgments" / (tk + ".json")
        if p.exists():
            cur = json.loads(p.read_text(encoding="utf-8"))
            if "_model_run" in cur:
                p.write_bytes(original["raw"])
    print("\n(restored hand-written judgments; model output kept in _backtest/)")

    if not rows:
        print("No comparable results.")
        return 1

    # ---------------- 1. agreement ----------------
    print("\n" + "=" * 76)
    print("1. AGREEMENT - model vs human, per company")
    print("=" * 76)
    print("  TICKER   HUMAN   MODEL    DIFF" + ("   SPREAD" if args.repeat > 1 else ""))
    print("  " + "-" * 50)
    diffs = []
    for r in sorted(rows, key=lambda x: x["ticker"]):
        if r["human_total"] is None:
            continue
        d = r["model_total"] - r["human_total"]
        diffs.append(d)
        line = ("  " + r["ticker"].ljust(8) + format(r["human_total"], "5.0f") + "   "
                + format(r["model_total"], "5.1f") + "  " + format(d, "+6.1f"))
        if args.repeat > 1:
            line += "   " + format(r.get("spread", 0), "5.0f")
        print(line)
    if diffs:
        print("  " + "-" * 50)
        print("  mean difference      " + format(statistics.mean(diffs), "+6.2f") + " points")
        print("  mean ABSOLUTE diff   " + format(statistics.mean(abs(d) for d in diffs), "6.2f"))
        print("  model scored lower in " + str(sum(1 for d in diffs if d < 0))
              + " of " + str(len(diffs)))

    # ---------------- per pillar ----------------
    print("\n  PER PILLAR (positive = model scores HIGHER than the human)")
    print("  " + "-" * 56)
    for pillar, cap in judge.PILLAR_CAPS.items():
        ds = []
        for r in rows:
            h = human.get(r["ticker"])
            if not h:
                continue
            mp = statistics.mean(run[pillar] for run in r["runs"])
            ds.append(mp - h[pillar]["points"])
        if ds:
            mean = statistics.mean(ds)
            flag = "  <-- systematic" if abs(mean) >= 1.5 else ""
            print("  " + pillar.ljust(24) + "/" + str(cap).ljust(3)
                  + format(mean, "+6.2f") + flag)

    # ---------------- 2. rejection ----------------
    print("\n" + "=" * 76)
    print("2. REJECTION RATE")
    print("=" * 76)
    attempted = len(tickers) * args.repeat
    calls = tally["calls"]
    rejected_calls = tally["rejected"]

    # Count MODEL CALLS, not companies, and count only the ones this invocation made.
    # A verdict rejected once and accepted on retry is one rejected call and one accepted
    # call - reporting only the companies that ended with nothing hides every time a
    # validator did its job. (The first backtest reported 0% while 2 of 15 calls had been
    # rejected, then a second version read the whole _backtest/ directory and claimed 21
    # calls for a 9-call run. See LOG.md 2026-10-25.)
    print("  companies attempted : " + str(attempted))
    print("  model calls made    : " + str(calls))
    print("  calls rejected      : " + str(rejected_calls)
          + ("" if not calls else "   ("
             + format(100.0 * rejected_calls / calls, ".1f") + "% of calls)"))
    print("  recovered on retry  : " + str(tally["recovered"])
          + "   (rejected once, valid on the next attempt)")
    print("  abandoned entirely  : " + str(tally["abandoned"])
          + "   (fell back to the PARTIAL score)")
    if tally["checks"]:
        print("  which checks fired THIS RUN:")
        for k, v in sorted(tally["checks"].items(), key=lambda kv: -kv[1]):
            print("    " + str(v).rjust(3) + "  " + k)
    elif rejected_calls == 0:
        print("  no validation failure this run")
    rej_dir = config.RESEARCH_DIR / "judgments" / "_rejected"
    if rej_dir.exists():
        checks: dict[str, int] = {}
        for p in rej_dir.glob("*.json"):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for a in d.get("attempts", []):
                for e in a.get("errors", []):
                    key = e.split(":")[0]
                    checks[key] = checks.get(key, 0) + 1
        if checks:
            print("  which checks fired (all time):")
            for k, v in sorted(checks.items(), key=lambda kv: -kv[1]):
                print("    " + str(v).rjust(3) + "  " + k)
        else:
            print("  no validation failures recorded")

    # ---------------- 3. determinism ----------------
    if args.repeat > 1:
        print("\n" + "=" * 76)
        print("3. DETERMINISM - same evidence, " + str(args.repeat) + " runs")
        print("=" * 76)
        spreads = [r["spread"] for r in rows if "spread" in r]
        if spreads:
            print("  mean total spread : " + format(statistics.mean(spreads), ".1f") + " points")
            print("  max total spread  : " + str(max(spreads)) + " points")
            if max(spreads) > 5:
                print("  -> report judgment scores as a RANGE, not a point estimate")

    print("\nelapsed " + format(time.time() - started, ".0f") + "s"
          + "   model output: " + str(OUT_DIR.relative_to(config.ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

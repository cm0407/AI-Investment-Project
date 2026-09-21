"""Record predictions and score them later. This is what makes the system improve.

USAGE
    # Log a new prediction (all fields validated before anything is written)
    python scripts/track_predictions.py add --ticker AAPL --entry 328.21 --target 395 \
        --horizon 12 --prob-positive 0.62 --prob-20pct 0.38 --prob-loss 0.30 \
        --conviction 74 --notes "thesis summary"

    python scripts/track_predictions.py list          # show every open prediction
    python scripts/track_predictions.py review        # mark to market against live prices
    python scripts/track_predictions.py stats         # calibration: are the odds honest?

THE APPEND-ONLY RULE
    CLAUDE.md is explicit: append, never overwrite, and never edit the record to make past
    predictions look better. So this script NEVER modifies a row in predictions.csv once
    written. `review` appends a dated snapshot to memory/prediction_reviews.csv instead.
    The original prediction, including its mistakes, stays exactly as it was made - which
    is the only way calibration can ever be checked.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, date
from pathlib import Path

import _bootstrap  # noqa: F401
from invest import config, prices

PREDICTION_FIELDS = [
    "date", "ticker", "entry_price", "target_price", "horizon_months", "expected_return",
    "prob_positive", "prob_20pct", "prob_loss", "conviction_score", "thesis_status", "notes",
]
REVIEW_FIELDS = [
    "review_date", "original_prediction_date", "ticker", "entry_price", "price_at_review",
    "pct_move_since_entry", "target_price", "pct_to_target", "days_elapsed",
    "horizon_months", "pct_of_horizon_elapsed", "thesis_status", "assumptions_held",
    "assumptions_broken", "reviewer_notes",
]
VALID_STATUS = ["open", "on_track", "at_risk", "thesis_broken", "target_hit",
                "closed_win", "closed_loss", "expired"]


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _append(path: Path, fields: list[str], row: dict) -> None:
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow(row)


def cmd_add(args) -> int:
    problems: list[str] = []
    for name, val in [("prob_positive", args.prob_positive),
                      ("prob_20pct", args.prob_20pct), ("prob_loss", args.prob_loss)]:
        if val is not None and not (0.0 <= val <= 1.0):
            problems.append(name + " must be between 0 and 1 (got " + str(val) + ")")
    if args.prob_positive is not None and args.prob_loss is not None:
        total = args.prob_positive + args.prob_loss
        if total > 1.01:
            problems.append("prob_positive + prob_loss = " + format(total, ".2f")
                            + ", which exceeds 1.0. They are mutually exclusive outcomes.")
    if (args.prob_20pct is not None and args.prob_positive is not None
            and args.prob_20pct > args.prob_positive + 1e-9):
        problems.append("prob_20pct (" + str(args.prob_20pct) + ") cannot exceed "
                        "prob_positive (" + str(args.prob_positive)
                        + ") - hitting +20% is a subset of finishing positive.")
    if args.conviction is not None and not (0 <= args.conviction <= 100):
        problems.append("conviction_score must be 0-100")
    if args.entry <= 0 or args.target <= 0:
        problems.append("prices must be positive")
    if args.horizon <= 0:
        problems.append("horizon_months must be positive")
    if not args.notes or len(args.notes.strip()) < 10:
        problems.append("notes must contain a real thesis summary (at least 10 characters) "
                        "- an unexplained prediction cannot be learned from later")
    if problems:
        print("REFUSED - fix these first:")
        for p in problems:
            print("  - " + p)
        return 1

    expected = (args.target / args.entry - 1.0) * 100.0
    if args.conviction is not None and args.conviction < 60:
        print("NOTE: conviction " + str(args.conviction) + " is below 60, which CLAUDE.md "
              "classifies as reject/speculative. Logging it anyway - a recorded rejection "
              "is useful data - but this should not be presented as a recommendation.")

    row = {
        "date": args.date or date.today().isoformat(),
        "ticker": args.ticker.upper(),
        "entry_price": format(args.entry, ".2f"),
        "target_price": format(args.target, ".2f"),
        "horizon_months": args.horizon,
        "expected_return": format(expected, ".1f"),
        "prob_positive": args.prob_positive if args.prob_positive is not None else "",
        "prob_20pct": args.prob_20pct if args.prob_20pct is not None else "",
        "prob_loss": args.prob_loss if args.prob_loss is not None else "",
        "conviction_score": args.conviction if args.conviction is not None else "",
        "thesis_status": args.status,
        "notes": args.notes.replace("\n", " ").strip(),
    }
    _append(config.PREDICTIONS_CSV, PREDICTION_FIELDS, row)
    print("Appended to " + str(config.PREDICTIONS_CSV.relative_to(config.ROOT)) + ":")
    for k, v in row.items():
        print("  " + k.ljust(18) + str(v))
    print("\nImplied return: " + format(expected, "+.1f") + "% over "
          + str(args.horizon) + " months.")
    print("This row is now permanent. It will not be edited later, only reviewed.")
    return 0


def cmd_list(args) -> int:
    rows = _read(config.PREDICTIONS_CSV)
    if not rows:
        print("No predictions recorded yet.")
        print("File: " + str(config.PREDICTIONS_CSV.relative_to(config.ROOT)))
        return 0
    print(str(len(rows)) + " prediction(s) on record\n")
    print("  DATE        TICKER  ENTRY     TARGET    EXP%     HORIZON  CONV  STATUS")
    print("  " + "-" * 76)
    for r in rows:
        print("  " + r["date"].ljust(12) + r["ticker"].ljust(8)
              + str(r["entry_price"]).rjust(8) + "  " + str(r["target_price"]).rjust(8)
              + "  " + str(r["expected_return"]).rjust(6) + "  "
              + str(r["horizon_months"]).rjust(7) + "  "
              + str(r["conviction_score"]).rjust(4) + "  " + str(r["thesis_status"]))
    return 0


def cmd_review(args) -> int:
    """Mark every prediction to market and APPEND a review snapshot. Never edits history."""
    rows = _read(config.PREDICTIONS_CSV)
    if not rows:
        print("No predictions to review.")
        return 0

    targets = [r for r in rows if (not args.ticker or r["ticker"] == args.ticker.upper())]
    print("Reviewing " + str(len(targets)) + " prediction(s) against live prices...\n")

    tickers = sorted({r["ticker"] for r in targets})
    live = prices.batch_prices(tickers, verbose=True)

    print("  TICKER  ENTRY     NOW       MOVE      TO TARGET   HORIZON USED")
    print("  " + "-" * 68)
    written = 0
    for r in targets:
        tk = r["ticker"]
        now = live.get(tk)
        entry = float(r["entry_price"])
        target = float(r["target_price"])
        pred_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
        days = (date.today() - pred_date).days
        horizon_days = int(r["horizon_months"]) * 30.44
        pct_horizon = (days / horizon_days * 100.0) if horizon_days else None

        if now is None:
            print("  " + tk.ljust(8) + format(entry, "8.2f") + "  " + config.MISSING)
            continue

        move = (now / entry - 1.0) * 100.0
        to_target = (target / now - 1.0) * 100.0
        print("  " + tk.ljust(8) + format(entry, "8.2f") + "  " + format(now, "8.2f")
              + "  " + format(move, "+7.1f") + "%  " + format(to_target, "+8.1f") + "%   "
              + format(pct_horizon or 0, "5.1f") + "%")

        _append(config.PREDICTION_REVIEWS_CSV, REVIEW_FIELDS, {
            "review_date": date.today().isoformat(),
            "original_prediction_date": r["date"],
            "ticker": tk,
            "entry_price": entry,
            "price_at_review": format(now, ".2f"),
            "pct_move_since_entry": format(move, ".1f"),
            "target_price": target,
            "pct_to_target": format(to_target, ".1f"),
            "days_elapsed": days,
            "horizon_months": r["horizon_months"],
            "pct_of_horizon_elapsed": format(pct_horizon or 0, ".1f"),
            "thesis_status": args.status or r["thesis_status"],
            "assumptions_held": args.held or "",
            "assumptions_broken": args.broken or "",
            "reviewer_notes": args.notes or "automated mark-to-market; no analyst review",
        })
        written += 1

    print("\nAppended " + str(written) + " review row(s) to "
          + str(config.PREDICTION_REVIEWS_CSV.relative_to(config.ROOT)))
    print("predictions.csv was NOT modified - the original forecasts stay as they were made.")
    print("\nA mark-to-market is not a verdict. Judging whether a thesis is intact needs a "
          "human\nreading of what actually happened; pass --held / --broken / --notes to "
          "record that.")
    return 0


def cmd_stats(args) -> int:
    """Calibration: when the system said 60%, did it happen about 60% of the time?"""
    preds = _read(config.PREDICTIONS_CSV)
    reviews = _read(config.PREDICTION_REVIEWS_CSV)
    print("PREDICTION CALIBRATION")
    print("=" * 60)
    print("  predictions recorded : " + str(len(preds)))
    print("  review snapshots     : " + str(len(reviews)))

    if not preds:
        print("\nNothing to calibrate yet. Calibration needs predictions that have had time "
              "to\nplay out - typically at least a full horizon, and enough of them that the "
              "result\nis not just luck. Fewer than ~20 resolved predictions tells you very "
              "little.")
        return 0

    resolved = [p for p in preds if p["thesis_status"] in
                ("closed_win", "closed_loss", "target_hit", "expired", "thesis_broken")]
    print("  resolved             : " + str(len(resolved)))

    if len(resolved) < 20:
        print("\nOnly " + str(len(resolved)) + " resolved prediction(s). Reporting a hit "
              "rate from this few\nwould be noise dressed up as evidence. The honest answer "
              "right now is: not enough\ndata to judge calibration.")

    latest: dict[str, dict] = {}
    for r in reviews:
        key = r["ticker"] + "|" + r["original_prediction_date"]
        if key not in latest or r["review_date"] > latest[key]["review_date"]:
            latest[key] = r
    if latest:
        moves = [float(r["pct_move_since_entry"]) for r in latest.values()]
        winners = [x for x in moves if x > 0]
        hit20 = [x for x in moves if x >= 20]
        print("\n  --- open positions, marked to market (NOT final outcomes) ---")
        print("  positions tracked    : " + str(len(moves)))
        print("  currently positive   : " + str(len(winners)) + " ("
              + format(len(winners) / len(moves) * 100, ".0f") + "%)")
        print("  currently >= +20%    : " + str(len(hit20)) + " ("
              + format(len(hit20) / len(moves) * 100, ".0f") + "%)")
        print("  average move         : " + format(sum(moves) / len(moves), "+.1f") + "%")
        stated = [float(p["prob_positive"]) for p in preds if p.get("prob_positive")]
        if stated:
            print("  avg stated P(positive): "
                  + format(sum(stated) / len(stated) * 100, ".0f") + "%")
            print("\n  Compare those last two lines. If the system routinely says 70% and "
                  "delivers 40%,\n  it is overconfident, and that belongs in "
                  "memory/lessons_learned.md.")
        print("\n  CAUTION: an unrealised move is not an outcome. A position up 15% two "
              "months into\n  a 12-month thesis has told you almost nothing yet.")
    return 0


def cmd_benchmark(args) -> int:
    """Compare every pick against the S&P 500 over that pick's OWN holding window.

    A raw return is close to meaningless on its own. "My picks are down 1.3%" reads as
    failure and "up 8%" reads as skill, when in both cases the honest question is what the
    market did over the same days. A pick that falls 2% while the index falls 5% is doing
    its job; one that rises 3% while the index rises 9% is not.

    Each prediction is measured from ITS OWN start date, because they were made on
    different days and a single shared window would misattribute market moves.
    """
    preds = _read(config.PREDICTIONS_CSV)
    if not preds:
        print("No predictions recorded yet.")
        return 0

    try:
        hist = prices.price_history(args.benchmark, period="1y", verbose=False)
        closes = hist["Close"]
    except Exception as exc:
        print("Could not load benchmark " + args.benchmark + ": " + str(exc)[:120])
        return 1

    def bench_on(day: str):
        stamps = [i for i in closes.index if i.strftime("%Y-%m-%d") <= day]
        return float(closes.loc[stamps[-1]]) if stamps else None

    bench_now = float(closes.iloc[-1])
    live = prices.batch_prices(sorted({p_["ticker"] for p_ in preds}), verbose=True)

    print()
    print("PICK vs " + args.benchmark + " OVER EACH PREDICTION'S OWN WINDOW")
    print("TICKER  FROM        DAYS   MY PICK    " + args.benchmark.ljust(9) + "RELATIVE")
    print("-" * 62)

    rel_total = pick_total = bench_total = 0.0
    counted = beat = 0
    for r in preds:
        now = live.get(r["ticker"])
        start = bench_on(r["date"])
        if now is None or start is None:
            print("  " + r["ticker"].ljust(6) + r["date"] + "  " + config.MISSING)
            continue
        entry = float(r["entry_price"])
        days = (date.today() - datetime.strptime(r["date"], "%Y-%m-%d").date()).days
        pick = (now / entry - 1.0) * 100.0
        mkt = (bench_now / start - 1.0) * 100.0
        rel = pick - mkt
        counted += 1
        beat += 1 if rel > 0 else 0
        pick_total += pick
        bench_total += mkt
        rel_total += rel
        print("  " + r["ticker"].ljust(6) + r["date"] + "  " + str(days).rjust(4) + "  "
              + format(pick, "+7.1f") + "%  " + format(mkt, "+7.1f") + "%  "
              + format(rel, "+8.1f") + " pts")

    if not counted:
        print("No comparable prices.")
        return 1

    print("-" * 62)
    print("  AVERAGE".ljust(24) + format(pick_total / counted, "+7.1f") + "%  "
          + format(bench_total / counted, "+7.1f") + "%  "
          + format(rel_total / counted, "+8.1f") + " pts")
    print("  beat the index: " + str(beat) + " of " + str(counted))

    oldest = min((datetime.strptime(p_["date"], "%Y-%m-%d").date() for p_ in preds))
    elapsed = (date.today() - oldest).days
    print()
    print("  Oldest prediction is " + str(elapsed) + " days old.")
    if elapsed < 180:
        print("  THIS IS NOT A TRACK RECORD. Relative performance over weeks is noise;")
        print("  the horizons here are 12-18 months. Reported because it is the correct")
        print("  way to measure, not because it yet means anything.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Record and score predictions.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="append a new prediction")
    a.add_argument("--ticker", required=True)
    a.add_argument("--entry", type=float, required=True, help="entry price")
    a.add_argument("--target", type=float, required=True, help="target price")
    a.add_argument("--horizon", type=int, required=True, help="horizon in months")
    a.add_argument("--prob-positive", type=float, default=None, help="0-1")
    a.add_argument("--prob-20pct", type=float, default=None, help="0-1")
    a.add_argument("--prob-loss", type=float, default=None, help="0-1")
    a.add_argument("--conviction", type=float, default=None, help="0-100 score")
    a.add_argument("--status", default="open", choices=VALID_STATUS)
    a.add_argument("--notes", required=True, help="the thesis, in one line")
    a.add_argument("--date", default=None, help="YYYY-MM-DD (defaults to today)")
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("list", help="show recorded predictions")
    l.set_defaults(func=cmd_list)

    r = sub.add_parser("review", help="mark to market and append review rows")
    r.add_argument("--ticker", default=None)
    r.add_argument("--status", default=None, choices=VALID_STATUS)
    r.add_argument("--held", default=None, help="which assumptions held")
    r.add_argument("--broken", default=None, help="which assumptions broke")
    r.add_argument("--notes", default=None)
    r.set_defaults(func=cmd_review)

    s = sub.add_parser("stats", help="calibration summary")
    s.set_defaults(func=cmd_stats)

    b = sub.add_parser("benchmark",
                       help="compare every pick against an index over its own window")
    b.add_argument("--benchmark", default="SPY", help="index ETF ticker (default SPY)")
    b.set_defaults(func=cmd_benchmark)

    args = ap.parse_args()
    config.ensure_dirs()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

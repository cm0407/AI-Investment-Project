"""Refresh every dataset by re-running the pipeline. Never hand-edit a data file.

USAGE
    python scripts/refresh_all.py                       # refresh macro + the watchlist
    python scripts/refresh_all.py --tickers AAPL JNJ    # refresh specific names
    python scripts/refresh_all.py --screen              # also re-run the full screen
    python scripts/refresh_all.py --force               # ignore caches entirely

WHY THIS EXISTS
    Every file under data/ is produced by a script and can be thrown away and rebuilt.
    Nothing in this system should ever be updated by opening a CSV and typing in it: a
    hand-edited number has no source, no timestamp and no way to be checked, which makes
    it exactly the kind of figure CLAUDE.md forbids. If a number is wrong, fix the code
    that produced it and re-run.

    Files under memory/, research/ and reports/ are the opposite: they are the written
    record, they are append-only, and this script does not touch them.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401
from invest import config

PY = sys.executable
SCRIPTS = Path(__file__).resolve().parent


def run(label: str, argv: list[str]) -> bool:
    print("\n" + "=" * 78)
    print(">>> " + label)
    print("    " + " ".join(argv[1:]))
    print("=" * 78)
    started = time.time()
    proc = subprocess.run([PY] + argv, cwd=str(config.ROOT))
    ok = proc.returncode == 0
    print("    " + ("done" if ok else "FAILED (exit " + str(proc.returncode) + ")")
          + " in " + format(time.time() - started, ".1f") + "s")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild every dataset from its source.")
    ap.add_argument("--tickers", nargs="*", default=["AAPL", "JNJ", "JPM", "PG", "CAT"],
                    help="watchlist to refresh (default: the 5 pipeline test companies)")
    ap.add_argument("--screen", action="store_true", help="also re-run the full screen")
    ap.add_argument("--universe", action="store_true", help="also rebuild the universe file")
    ap.add_argument("--force", action="store_true", help="bypass all caches")
    args = ap.parse_args()

    config.ensure_dirs()
    refresh = ["--refresh"] if args.force else []
    steps: list[tuple[str, list[str]]] = []

    if args.universe:
        steps.append(("Rebuild the screening universe",
                      [str(SCRIPTS / "build_universe.py")]))

    steps.append(("Macro backdrop from FRED",
                  [str(SCRIPTS / "fetch_fred.py")] + refresh))
    steps.append(("SEC EDGAR fundamentals",
                  [str(SCRIPTS / "fetch_sec.py")] + args.tickers + refresh))
    steps.append(("Market prices",
                  [str(SCRIPTS / "fetch_prices.py")] + args.tickers + ["--vendor"]))

    if args.screen:
        steps.append(("Full screen of the starter universe",
                      [str(SCRIPTS / "screen_stocks.py"), "--top", "30"] + refresh))

    print("INVEST - refreshing " + str(len(steps)) + " dataset group(s)")
    print("Caches: " + ("BYPASSED (--force)" if args.force else "used where still fresh"))

    failures = [label for label, argv in steps if not run(label, argv)]

    print("\n" + "=" * 78)
    if failures:
        print("FINISHED WITH FAILURES: " + ", ".join(failures))
        print("A failed pull leaves the previous data in place. Do not assume a stale file "
              "is current - check the retrieved_at_utc field inside it.")
        return 1
    print("All datasets refreshed. Every file carries its own source URL and retrieval "
          "timestamp\nin its _meta block; check there before trusting any figure.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

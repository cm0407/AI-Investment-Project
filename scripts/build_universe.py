"""Build the pool of stocks the screener searches.

USAGE
    python scripts/build_universe.py                # write the ~150-name starter universe
    python scripts/build_universe.py --full         # write the ~10,000-name SEC universe
    python scripts/build_universe.py --show         # print what is currently on file

WHY TWO UNIVERSES
    The starter list is fast and works immediately, but it is hand-picked and therefore
    biased toward big, familiar companies. The full list comes straight from the SEC's own
    ticker registry and has no curation at all - it is what a genuinely broad Phase 1 scan
    needs. Screening it takes much longer, so start small and go wide when it matters.
"""

from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from invest import config, universe


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the screening universe.")
    ap.add_argument("--full", action="store_true",
                    help="build the complete SEC-registered universe (~10,000 tickers)")
    ap.add_argument("--show", action="store_true", help="show the current universe files")
    ap.add_argument("--refresh", action="store_true", help="re-download the SEC ticker map")
    args = ap.parse_args()

    config.ensure_dirs()

    if args.show:
        for label, path in (("starter", config.STARTER_UNIVERSE),
                            ("full SEC", config.FULL_UNIVERSE)):
            if path.exists():
                rows = universe.load(path)
                print(label + ": " + str(len(rows)) + " tickers -> "
                      + str(path.relative_to(config.ROOT)))
                counts = universe.sector_counts(rows)
                if len(counts) > 1:
                    for sector, n in sorted(counts.items(), key=lambda kv: -kv[1]):
                        print("    " + sector.ljust(26) + str(n))
            else:
                print(label + ": not built yet")
        return 0

    if args.full:
        print("Downloading the SEC's official ticker registry...")
        n, path = universe.write_full(refresh=args.refresh)
        print("Wrote " + str(n) + " tickers -> " + path)
        print("\nNOTE: this list includes every SEC-registered ticker - operating "
              "companies, trusts, funds, shells and delisted names alike. The screener "
              "filters out anything without usable financial data as it goes.")
        return 0

    n, path = universe.write_starter()
    rows = universe.load()
    print("Wrote " + str(n) + " tickers -> " + path + "\n")
    print("Sector spread:")
    for sector, count in sorted(universe.sector_counts(rows).items(), key=lambda kv: -kv[1]):
        print("  " + sector.ljust(26) + str(count))
    print("\n" + universe.STARTER_BIAS_WARNING)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

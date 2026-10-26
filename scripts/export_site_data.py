"""Freeze everything the API serves into JSON files the static site reads at build time.

WHY THIS EXISTS

The website used to call a running FastAPI server. That server has to live somewhere, and
"somewhere" means a host, an account and a thing that can be down. This project's data only
changes when a research session runs - a few times a month - so a live API was the wrong
shape for it. Writing the same JSON to disk and building a static site removes the server
entirely: GitHub Pages can host it for nothing and it cannot break at 3am.

ONE SOURCE OF TRUTH

This script does NOT reimplement the API. It imports `api.main` and calls the same functions
the endpoints call, so the JSON on the website is produced by exactly the code the tests
cover. If `split_metrics` learns about a new unavailable-reason tomorrow, the static site
gets it for free.

    python scripts/export_site_data.py
    python scripts/export_site_data.py --out some/other/dir
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import main as api                                    # noqa: E402
from invest import config                                      # noqa: E402

DEFAULT_OUT = ROOT / "web" / "public" / "data"


def write(path: Path, payload: object) -> int:
    """Write one JSON file, returning its size in bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, default=str)
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="directory to write into (default: web/public/data)")
    ap.add_argument("--keep", action="store_true",
                    help="do not clear the output directory first")
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists() and not args.keep:
        # A stale company file left behind after a ticker is dropped would keep appearing
        # on the site with no way to notice. Clear, then rewrite.
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    total = 0
    files = 0
    problems: list[str] = []

    def emit(rel: str, payload: object) -> None:
        nonlocal total, files
        total += write(out / rel, payload)
        files += 1

    # ---- the index pages -------------------------------------------------------------
    companies = api.list_companies()
    emit("companies.json", companies)
    emit("predictions.json", api.get_predictions())
    emit("macro.json", api.get_macro())
    # Pass limit explicitly: called directly, FastAPI's Query(...) default arrives as a
    # Query object rather than an int.
    emit("screens-latest.json", api.latest_screen(limit=500))

    digests = api.list_digests()
    emit("digests.json", digests)

    # ---- one file per company --------------------------------------------------------
    for co in companies:
        tk = co["ticker"]
        try:
            emit("company-" + tk + ".json", api.get_company(tk))
        except Exception as exc:                                # noqa: BLE001
            problems.append(tk + " company: " + str(exc)[:80])
            continue
        try:
            emit("thesis-" + tk + ".json", api.get_thesis(tk))
        except Exception as exc:                                # noqa: BLE001
            # Not every analysed company has been scored. That is a real state, not an
            # error - the page renders without a thesis block.
            problems.append(tk + " thesis: " + str(exc)[:80])

    # ---- one file per digest ---------------------------------------------------------
    for d in digests:
        try:
            emit("digest-" + d["date"] + ".json", api.get_digest(d["date"]))
        except Exception as exc:                                # noqa: BLE001
            problems.append(d["date"] + " digest: " + str(exc)[:80])

    # ---- a manifest, so the build can assert it got what it expected -----------------
    emit("manifest.json", {
        "generatedAt": api.datetime.now().isoformat(timespec="seconds"),
        "companies": [c["ticker"] for c in companies],
        "digests": [d["date"] for d in digests],
        "counts": {"companies": len(companies), "digests": len(digests), "files": files + 1},
        "note": ("Written by scripts/export_site_data.py from the same functions the API "
                 "serves. Figures are as of the last time the research scripts ran, not "
                 "live market data."),
    })

    print("wrote " + str(files + 1) + " files, "
          + format(total / 1024.0, ".0f") + " KB -> " + str(out.relative_to(ROOT)))
    if problems:
        print("\nnot exported (" + str(len(problems)) + "):")
        for p in problems:
            print("  " + p)

    # A company with no thesis is normal. Zero companies is not.
    if not companies:
        print("\nERROR: no companies found - did the analysis scripts ever run?")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

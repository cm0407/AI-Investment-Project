"""Lets scripts/ import the invest package without any install step.

Every script starts with `import _bootstrap` so that `python scripts/whatever.py` works
from anywhere, on any OS, with no PYTHONPATH fiddling and no `pip install -e .`.

It also makes console output safe on Windows. The default Windows console codepage is
cp1252, which cannot encode the emoji and typographic characters the digests use - printing
a title containing an emoji raised UnicodeEncodeError and killed the script outright. The
file content was never the problem (everything is written as UTF-8); only the terminal.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Make stdout/stderr tolerant of characters the console cannot render. `errors="replace"`
# substitutes an unrenderable character instead of raising, so a decorative emoji can never
# crash a research script.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass  # already suitable, or redirected to something that cannot be reconfigured

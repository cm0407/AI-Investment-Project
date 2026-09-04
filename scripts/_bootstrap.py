"""Lets scripts/ import the invest package without any install step.

Every script starts with `import _bootstrap` so that `python scripts/whatever.py` works
from anywhere, on any OS, with no PYTHONPATH fiddling and no `pip install -e .`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

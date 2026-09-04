"""INVEST - autonomous investment research toolkit.

A small, dependency-light package that pulls verifiable data from free, authoritative
sources and refuses to guess when data is missing.

Data sources, in the priority order set by CLAUDE.md:
  1. SEC EDGAR (data.sec.gov)  -> fundamentals, filings, insider transactions  [authoritative]
  2. FRED (St. Louis Fed)      -> macroeconomic series                         [authoritative]
  3. yfinance / Yahoo Finance  -> market prices, vendor estimates              [third-party]

Every number this package returns carries provenance: where it came from, when it was
retrieved, what period it covers, and whether it is an actual reported figure, a vendor
estimate, or a projection made by us.
"""

__version__ = "1.0.0"

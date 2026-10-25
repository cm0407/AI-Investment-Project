"""The one module that calls a model. Scores the five judgment pillars.

WHY THIS EXISTS
---------------
`docs/SCORING.md` has said since 2026-09-03 that only four of the nine scoring pillars can be
scored honestly by a script, and that the other five - business quality, competitive
advantage, catalysts, risk/reward, management - "require judgment a program does not have".
Until now a human filled that hole by hand. This module fills it from inside the pipeline.

THE SPLIT, STATED PLAINLY
-------------------------
    Deterministic code  ->  fetch filings, pick XBRL tags, compute 72 metrics, detect stale
                            and fallback data, score 4 pillars on fixed thresholds
    THE MODEL           ->  read an evidence pack; return 5 integers and 5 justifications
    Deterministic code  ->  validate that output against 7 rules, clamp, assemble, band

The model's surface is deliberately tiny: five integers and five paragraphs. It does not pick
stocks, fetch data, compute anything, set price targets, or decide BUY/WATCH/AVOID. That
narrowness is the point - when a score looks wrong you can tell whether the model or the code
produced it, because they touch different things.

THE MODEL IS AN UNTRUSTED EXTERNAL SERVICE
------------------------------------------
Nothing it returns is used until it passes `validate()`. The check that matters most is
GROUNDEDNESS: every figure cited in a justification must appear in the evidence pack the model
was given. A justification claiming "ROIC of 28%" when the evidence says 16.2% is a
hallucination, and this project's entire premise is that numbers are never invented.

COST AND LATENCY
----------------
Runs through `claude -p` (Claude Code access), not the billed Anthropic API. A call costs
10-30s, so judgments are cached against a hash of the evidence - re-running a script with
unchanged fundamentals makes no call at all.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import config

JUDGMENTS_DIR = config.RESEARCH_DIR / "judgments"
REJECTED_DIR = JUDGMENTS_DIR / "_rejected"

PILLAR_CAPS = {
    "business_quality": 15,
    "competitive_advantage": 10,
    "catalysts": 10,
    "risk_reward": 10,
    "management": 5,
}

MIN_JUSTIFICATION_CHARS = 120

# The project bans implying certainty. These are rejected outright.
FORBIDDEN_PHRASES = [
    "guaranteed", "will definitely", "risk-free", "riskless", "cannot lose",
    "sure thing", "certain to", "no downside",
]

# Free-cash-flow language in a bank's judgment means the model ignored the sector note.
FCF_LANGUAGE = ["free cash flow", "fcf", "cash conversion", "ocf"]


# --------------------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------------------
def build_evidence(metrics: dict, fund: dict, insider: Optional[dict] = None) -> dict:
    """Assemble the facts the model is allowed to reason from.

    Everything here is public SEC data or a ratio computed from it. Nothing personal, no
    credentials, nothing from .env or the user's preferences file.
    """
    from . import scoring

    profile = fund.get("profile") or {}
    sector = metrics.get("_sector") or {}

    annual = {}
    for key in ("revenue", "operating_income", "net_income"):
        rows = (fund.get("annual") or {}).get(key) or []
        annual[key] = [{"period_end": r["period_end"], "value": r["value"]} for r in rows[-5:]]

    # Valuation context. The first live run scored catalysts 2/10 and risk_reward 3/10 with
    # the model stating plainly that "the evidence has no share price, market value,
    # valuation multiple, or bear/base/bull cases". It was right - the pack was incomplete,
    # and it behaved correctly by scoring low rather than inventing an assessment. Risk and
    # reward cannot be judged without knowing what is being paid.
    valuation = {k: metrics.get(k) for k in (
        "price", "market_cap", "pe_ratio", "pfcf_ratio", "ev_ebitda", "ps_ratio",
        "fcf_yield_pct", "earnings_yield_pct", "peg_ratio", "annual_volatility_pct",
    )}

    # What the price already assumes, against what the company has delivered. This is the
    # single most decision-relevant comparison the system computes.
    reverse_dcf = None
    try:
        from . import valuation as val
        shares = metrics.get("shares_outstanding")
        fcf = metrics.get("fcf_latest")
        price = metrics.get("price")
        if price and shares and fcf and fcf > 0:
            rd = val.reverse_dcf(price, shares, fcf, metrics.get("net_cash_position") or 0.0)
            reverse_dcf = {
                "implied_fcf_growth_pct_the_price_requires": rd.get("implied_growth_pct"),
                "fcf_growth_pct_actually_delivered": metrics.get("fcf_cagr_pct"),
                "note": "If the required rate far exceeds the delivered rate, the price "
                        "already assumes an improvement the company has not demonstrated.",
            }
    except Exception:
        reverse_dcf = None

    # Dated events the company has actually filed. A catalyst needs a date.
    filings = []
    try:
        from . import sec_edgar as _sec
        for f_ in _sec.recent_filings(fund["cik_padded"], forms=("10-K", "10-Q", "8-K"),
                                      limit=8, verbose=False):
            filings.append({"date": f_.get("filingDate"), "form": f_.get("form")})
    except Exception:
        pass

    return {
        "ticker": fund.get("ticker"),
        "company_name": fund.get("company_name"),
        "industry": str(profile.get("sic")) + " - " + str(profile.get("sic_description")),
        "sector_special": sector.get("kind"),
        "sector_unreliable_metrics": sector.get("unreliable_metrics") or [],
        "annual_financials": annual,
        "valuation": valuation,
        "reverse_dcf": reverse_dcf,
        "recent_filings": filings,
        "share_count_change_pct": metrics.get("share_count_change_pct"),
        "pillars": scoring.judgment_evidence(metrics, fund, insider),
        "data_caveats": {
            "fallback_tags": {k: v.get("tag_used")
                              for k, v in (metrics.get("_fallback_tags_used") or {}).items()},
            "stale_excluded": metrics.get("_stale_inputs_excluded") or [],
            "composites_suppressed": metrics.get("_composites_suppressed") or [],
            "growth_base_warning": metrics.get("_growth_base_warning"),
            "share_count_warning": metrics.get("_share_count_warning"),
        },
    }


def evidence_hash(evidence: dict) -> str:
    """Stable hash. Same facts -> same cached judgment -> no second model call."""
    blob = json.dumps(evidence, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------------------
PROMPT_TEMPLATE = """You are scoring five judgment pillars for an equity research system.

Score ONLY from the EVIDENCE below. You have no other information about this company, and you
must not use any you happen to recall - if a figure is not in the evidence, you may not cite it.

PILLARS AND THEIR MAXIMUM POINTS
  business_quality        15   Is this a good business, independent of its price?
  competitive_advantage   10   Is there a moat, and is it widening or narrowing?
  catalysts               10   What specific, DATED events could re-rate this stock?
  risk_reward             10   Is the upside big enough for the realistic downside?
  management               5   Do they allocate capital well and tell the truth?

RULES
1. Every figure you cite in a justification MUST appear in the EVIDENCE. Citing a number that
   is not there is the single worst failure you can make here.
2. Justify every score in at least 150 characters, referencing specific evidence.
3. Never imply certainty. Do not write "guaranteed", "will definitely", or "risk-free".
4. A catalyst needs a DATE and a MECHANISM. "The sector should recover" is not a catalyst.
5. If the evidence lists metrics as unreliable for this company's sector, do not reason from
   them - they are meaningless for this industry.
6. Score what the evidence supports. An unremarkable company should score unremarkably; do not
   inflate to make the idea look better.
7. Note deterioration as readily as strength. Revenue rising while profit falls is a warning.

OUTPUT
Return ONLY a JSON object, no prose before or after, exactly this shape:

{{"business_quality": {{"points": <int>, "justification": "<text>"}},
 "competitive_advantage": {{"points": <int>, "justification": "<text>"}},
 "catalysts": {{"points": <int>, "justification": "<text>"}},
 "risk_reward": {{"points": <int>, "justification": "<text>"}},
 "management": {{"points": <int>, "justification": "<text>"}}}}

EVIDENCE
{evidence}
"""


def render_prompt(evidence: dict) -> str:
    return PROMPT_TEMPLATE.format(evidence=json.dumps(evidence, indent=2, default=str))


# --------------------------------------------------------------------------------------
# The model call
# --------------------------------------------------------------------------------------
class ModelCallError(RuntimeError):
    pass


def call_model(prompt: str, timeout: int = 180, verbose: bool = True) -> str:
    """Run `claude -p` headless. Argument list only - never shell=True.

    The prompt goes in on stdin rather than as an argument so that evidence content can never
    be interpreted as a command.
    """
    if verbose:
        print("    [judge] calling model (" + str(len(prompt)) + " chars of prompt)...")
    try:
        proc = subprocess.run(
            ["claude", "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        raise ModelCallError("model call timed out after " + str(timeout) + "s")
    except FileNotFoundError:
        raise ModelCallError("`claude` CLI not found on PATH - cannot run the judgment step")
    if proc.returncode != 0:
        raise ModelCallError("claude exited " + str(proc.returncode) + ": "
                             + (proc.stderr or "")[:200])
    return proc.stdout or ""


def extract_json(raw: str) -> Optional[dict]:
    """Pull the outermost JSON object out of the model's reply."""
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if fence:
        raw = fence.group(1)
    start, depth = raw.find("{"), 0
    if start == -1:
        return None
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


# --------------------------------------------------------------------------------------
# Validation - the model is untrusted until this passes
# --------------------------------------------------------------------------------------
def _evidence_numbers(evidence: dict) -> set[float]:
    """Every number anywhere in the evidence, rounded to 1dp, for the groundedness check."""
    found: set[float] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            f = float(node)
            found.add(round(f, 1))
            found.add(round(f, 0))
            for scale in (1e3, 1e6, 1e9):          # $21,450,000,000 cited as "21.45B"
                if abs(f) >= scale:
                    found.add(round(f / scale, 1))
                    found.add(round(f / scale, 0))
        elif isinstance(node, str):
            for m in re.findall(r"-?\d+\.?\d*", node):
                try:
                    f = float(m)
                    found.add(round(f, 1))
                    found.add(round(f, 0))
                except ValueError:
                    pass

    walk(evidence)
    return found


def _cited_numbers(text: str) -> list[float]:
    """Figures a justification asserts. Years and small counts are not claims about data."""
    out = []
    for raw in re.findall(r"-?\$?\d[\d,]*\.?\d*", text):
        try:
            f = float(raw.replace("$", "").replace(",", ""))
        except ValueError:
            continue
        if 1900 <= f <= 2100 and float(f).is_integer():
            continue                       # a year
        if abs(f) <= 20 and float(f).is_integer():
            continue                       # point scores, counts, "5 of 16"
        out.append(f)
    return out


def validate(verdict: Optional[dict], evidence: dict) -> tuple[Optional[dict], list[str]]:
    """Seven checks. Returns (verdict, errors). A non-empty error list means reject."""
    errors: list[str] = []

    # 1. parses
    if verdict is None:
        return None, ["check1_json: model output did not contain parseable JSON"]

    # 2. exactly the five pillars
    missing = [p for p in PILLAR_CAPS if p not in verdict]
    extra = [p for p in verdict if p not in PILLAR_CAPS]
    if missing:
        errors.append("check2_pillars: missing " + ", ".join(missing))
    if extra:
        errors.append("check2_pillars: unexpected " + ", ".join(extra))
    if missing:
        return None, errors

    sector = evidence.get("sector_special")
    unreliable = [u.lower() for u in (evidence.get("sector_unreliable_metrics") or [])]
    ev_numbers = _evidence_numbers(evidence)

    for pillar, cap in PILLAR_CAPS.items():
        entry = verdict.get(pillar) or {}
        pts = entry.get("points")
        just = (entry.get("justification") or "").strip()

        # 3. integer within the cap - rejected, never silently clamped
        if not isinstance(pts, int) or isinstance(pts, bool):
            errors.append("check3_points: " + pillar + " points is not an integer (" + repr(pts) + ")")
        elif not (0 <= pts <= cap):
            errors.append("check3_points: " + pillar + " scored " + str(pts) + ", cap is " + str(cap))

        # 4. a number with no argument is exactly what SCORING.md forbids
        if len(just) < MIN_JUSTIFICATION_CHARS:
            errors.append("check4_justification: " + pillar + " justification is "
                          + str(len(just)) + " chars, minimum " + str(MIN_JUSTIFICATION_CHARS))

        # 5. GROUNDEDNESS - the check that matters most
        for cited in _cited_numbers(just):
            if round(cited, 1) not in ev_numbers and round(cited, 0) not in ev_numbers:
                errors.append("check5_groundedness: " + pillar + " cites " + str(cited)
                              + " which does not appear in the evidence pack")

        # 6. certainty language
        low = just.lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in low:
                errors.append("check6_certainty: " + pillar + " uses forbidden phrase '"
                              + phrase + "'")

        # 7. sector sanity
        if sector in ("banking/credit", "insurance", "brokerage/exchanges"):
            if any(t in low for t in FCF_LANGUAGE) and any("fcf" in u for u in unreliable):
                errors.append("check7_sector: " + pillar + " reasons from free cash flow, which "
                              "is declared meaningless for a " + str(sector) + " company")

    return (None if errors else verdict), errors


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------
def _record_rejections(ticker: str, ehash: str, attempts: list[dict], outcome: str) -> None:
    """Persist every rejected attempt, whether or not a later one succeeded.

    Originally this only ran when ALL attempts failed, which made the validators look
    like they never fired: a verdict rejected on attempt 1 and accepted on attempt 2 left
    nothing on disk, so the first backtest reported a 0% rejection rate while two of
    thirteen calls had in fact been rejected. An instrument that reads zero when the real
    figure is 15% is worse than no instrument, so rejections are now always kept.

    `outcome` is "recovered_on_retry" or "abandoned" - the difference between a model that
    self-corrects and one that cannot produce a valid verdict at all.
    """
    if not attempts:
        return
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (REJECTED_DIR / (ticker.upper() + "_" + stamp + ".json")).write_text(
        json.dumps({"ticker": ticker.upper(), "evidence_hash": ehash,
                    "outcome": outcome, "attempts": attempts}, indent=2),
        encoding="utf-8")


def judge(ticker: str, metrics: dict, fund: dict, insider: Optional[dict] = None,
          refresh: bool = False, retries: int = 1, verbose: bool = True) -> Optional[dict]:
    """Produce a validated judgment, or None.

    None is not a failure mode to paper over - it means the system falls back to the PARTIAL
    score it has always produced without analyst judgment. A model outage degrades this
    system; it does not break it.
    """
    JUDGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)

    evidence = build_evidence(metrics, fund, insider)
    ehash = evidence_hash(evidence)
    path = JUDGMENTS_DIR / (ticker.upper() + ".json")

    if path.exists() and not refresh:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            meta = cached.get("_model_run") or {}
            if meta.get("evidence_hash") == ehash:
                if verbose:
                    print("    [judge] cached judgment is current (evidence unchanged)")
                return cached
            if not meta:
                if verbose:
                    print("    [judge] existing ANALYST-written judgment found; not overwriting")
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    prompt = render_prompt(evidence)
    attempts: list[dict] = []

    for attempt in range(retries + 1):
        try:
            raw = call_model(prompt, verbose=verbose)
        except ModelCallError as exc:
            attempts.append({"attempt": attempt + 1, "errors": ["call_failed: " + str(exc)]})
            if verbose:
                print("    [judge] " + str(exc))
            continue

        verdict, errors = validate(extract_json(raw), evidence)
        if not errors:
            verdict["_model_run"] = {
                "source": "model",
                "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "evidence_hash": ehash,
                "attempts": attempt + 1,
                "checks_passed": ["check1_json", "check2_pillars", "check3_points",
                                  "check4_justification", "check5_groundedness",
                                  "check6_certainty", "check7_sector"],
                # Which checks fired on the way to this answer. Without this, a verdict
                # rejected once and accepted on retry is indistinguishable from one that
                # passed first time, and the measured rejection rate reads 0% while the
                # validators are in fact firing. See LOG.md 2026-10-25.
                "checks_failed_before_acceptance": [
                    e.split(":")[0] for a in attempts for e in a.get("errors", [])
                ],
                "model_cli": "claude -p",
            }
            if attempts:
                _record_rejections(ticker, ehash, attempts, "recovered_on_retry")
            path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
            if verbose:
                total = sum(verdict[p]["points"] for p in PILLAR_CAPS)
                print("    [judge] accepted: " + str(total) + "/50 (attempt "
                      + str(attempt + 1) + ")")
            return verdict

        attempts.append({"attempt": attempt + 1, "errors": errors, "raw": raw[:4000]})
        if verbose:
            print("    [judge] REJECTED on attempt " + str(attempt + 1) + ":")
            for e in errors[:5]:
                print("            - " + e)

    _record_rejections(ticker, ehash, attempts, "abandoned")
    if verbose:
        print("    [judge] all attempts rejected; falling back to PARTIAL score")
    return None

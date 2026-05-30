"""LLM trace-judge for the specify slice.

The deterministic structural reward (reward.py) can confirm a spec has the right SECTIONS
and FR ids — but not whether each requirement is genuinely *testable*, whether the spec
*covers the brief*, or whether success criteria are *outcome-level*. Those are semantic and
need a model. This judge reads (brief, spec) and scores them 0..1.

It's the "judge tokens << rollout tokens" layer: one ~0.5k-token call per rollout that
writes a full spec. Uses the same claude backend as the rollout (chat_target).
"""

from __future__ import annotations

import json
import re
from typing import Any

from skillopt.model import chat_target

JUDGE_SYSTEM = """You are a strict, fair specification reviewer. You are given a feature
BRIEF and a candidate SPEC. Judge ONLY semantic quality that structure cannot reveal.

Score each 0.0–1.0:
- testable:  are the functional requirements genuinely verifiable — each states an
             observable, checkable behavior (not vague, not an implementation detail)?
- coverage:  does the spec cover the core behavior the brief asks for (no major gap)?
- outcome:   are the success criteria outcome-level and measurable (not restating steps)?

Then overall = your holistic 0.0–1.0 (you may weight as you see fit).
Respond with ONLY a JSON object, no prose:
{"testable": <f>, "coverage": <f>, "outcome": <f>, "overall": <f>, "notes": "<one line: the single biggest weakness>"}"""


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
    except Exception:
        return {}
    out: dict[str, Any] = {}
    for k in ("testable", "coverage", "outcome", "overall"):
        try:
            out[k] = max(0.0, min(1.0, float(d.get(k))))
        except (TypeError, ValueError):
            out[k] = 0.0
    out["notes"] = str(d.get("notes", ""))[:300]
    return out


def llm_judge(brief: str, spec_md: str, max_completion_tokens: int = 1024, timeout: int = 120) -> dict:
    """Return {testable, coverage, outcome, overall, notes, error}. overall=0.0 on failure."""
    user = f"BRIEF:\n{brief}\n\nSPEC:\n{spec_md[:8000]}\n\nScore it."
    try:
        text, _ = chat_target(
            system=JUDGE_SYSTEM, user=user, max_completion_tokens=max_completion_tokens, timeout=timeout
        )
    except Exception as exc:  # judge failure -> conservative 0, surfaced as error
        return {
            "testable": 0.0,
            "coverage": 0.0,
            "outcome": 0.0,
            "overall": 0.0,
            "notes": "",
            "error": f"{type(exc).__name__}: {exc}",
        }
    parsed = _parse(text)
    if not parsed:
        return {
            "testable": 0.0,
            "coverage": 0.0,
            "outcome": 0.0,
            "overall": 0.0,
            "notes": "",
            "error": "unparseable judge output",
        }
    parsed["error"] = ""
    return parsed


# ── Reference-ANCHORED judge (FR-017) ──────────────────────────────────────────
# Coverage is not a judge gestalt: the judge marks each `expected` behavior present/absent,
# and coverage = fraction present (deterministic aggregation over concrete items). This is
# more reliable than reference-free absolute scoring, which "purely depends on the judge".

JUDGE_REF_SYSTEM = """You are a strict, fair specification reviewer. You are given a feature
BRIEF, a list of EXPECTED core behaviors the spec must cover, and a candidate SPEC.

For EACH expected behavior, decide whether the SPEC actually covers it (true/false).
Also score 0.0–1.0:
- testable: are the requirements genuinely verifiable (observable, checkable; not vague)?
- outcome:  are success criteria outcome-level and measurable (not restating steps)?

Respond with ONLY a JSON object, no prose. `covered` MUST be a list of booleans, one per
expected behavior, in the SAME order:
{"covered": [true, false, ...], "testable": <f>, "outcome": <f>, "notes": "<one line: biggest gap>"}"""


def _parse_ref(text: str, n_expected: int) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
    except Exception:
        return {}
    covered = d.get("covered")
    if not isinstance(covered, list):
        return {}
    flags = [bool(x) for x in covered][:n_expected]
    flags += [False] * (n_expected - len(flags))  # pad if judge returned too few
    out: dict[str, Any] = {"covered": flags}
    out["coverage"] = round(sum(flags) / n_expected, 4) if n_expected else 0.0
    for k in ("testable", "outcome"):
        try:
            out[k] = max(0.0, min(1.0, float(d.get(k))))
        except (TypeError, ValueError):
            out[k] = 0.0
    out["notes"] = str(d.get("notes", ""))[:300]
    return out


def llm_judge_ref(
    brief: str, spec_md: str, expected: list[str], max_completion_tokens: int = 1024, timeout: int = 120
) -> dict:
    """Reference-anchored judge. coverage = fraction of `expected` behaviors marked present.

    Returns {testable, coverage, outcome, overall, covered, notes, error}.
    overall = mean(testable, coverage, outcome).
    """
    fail = {
        "testable": 0.0,
        "coverage": 0.0,
        "outcome": 0.0,
        "overall": 0.0,
        "covered": [False] * len(expected),
        "notes": "",
    }
    expected_block = "\n".join(f"{i + 1}. {b}" for i, b in enumerate(expected))
    user = f"BRIEF:\n{brief}\n\nEXPECTED behaviors:\n{expected_block}\n\nSPEC:\n{spec_md[:8000]}\n\nScore it."
    try:
        text, _ = chat_target(
            system=JUDGE_REF_SYSTEM, user=user, max_completion_tokens=max_completion_tokens, timeout=timeout
        )
    except Exception as exc:  # judge failure -> conservative 0, surfaced as error
        return {**fail, "error": f"{type(exc).__name__}: {exc}"}
    parsed = _parse_ref(text, len(expected))
    if not parsed:
        return {**fail, "error": "unparseable judge output"}
    parsed["overall"] = round((parsed["testable"] + parsed["coverage"] + parsed["outcome"]) / 3, 4)
    parsed["error"] = ""
    return parsed

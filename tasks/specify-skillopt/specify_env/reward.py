"""Deterministic structural reward for the `specify` SkillOpt target.

reward(brief, spec_md) -> dict with:
  hard : 0/1  — all CRITICAL structural checks pass
  soft : 0..1 — fraction of weighted checks passed (the gradient signal)
  checks      — per-check booleans (reflect uses failing checks to patch the skill)
  needs_judge — aspects this DETERMINISTIC checker cannot verify; routed to the LLM
                trace-judge (the layer that earns its keep here, since judge tokens
                are cheap relative to a long rollout).

This is the key contrast with the `reviewer` target: structure is checkable by code,
but *whether each requirement is genuinely testable* is semantic and needs a judge.
"""

from __future__ import annotations

import re

CRITICAL = {
    "has_user_scenarios",
    "has_functional_requirements",
    "has_success_criteria",
    "fr_ids_present",
}

# section weights sum to 1.0
WEIGHTS = {
    "has_user_scenarios": 0.12,
    "has_priorities": 0.08,
    "has_functional_requirements": 0.12,
    "fr_ids_present": 0.15,
    "fr_use_must": 0.12,
    "has_success_criteria": 0.12,
    "success_measurable": 0.13,
    "has_assumptions": 0.06,
    "no_impl_leakage": 0.10,
}


def _requirements_block(md: str) -> str:
    m = re.search(r"###\s*Functional Requirements(.*?)(\n##\s|\Z)", md, re.S | re.I)
    return m.group(1) if m else ""


def _success_block(md: str) -> str:
    m = re.search(r"##\s*Success Criteria(.*?)(\n##\s|\Z)", md, re.S | re.I)
    return m.group(1) if m else ""


def evaluate(spec_md: str) -> dict:
    md = spec_md or ""
    req = _requirements_block(md)
    succ = _success_block(md)
    fr_ids = re.findall(r"\*\*FR-?\d+\*\*|\bFR-\d+\b", md)

    checks = {
        "has_user_scenarios": bool(re.search(r"##\s*User Scenarios", md, re.I)),
        "has_priorities": bool(re.search(r"\(Priority:\s*P\d\)", md, re.I)),
        "has_functional_requirements": bool(re.search(r"###\s*Functional Requirements", md, re.I)),
        "fr_ids_present": len(fr_ids) >= 3,
        "fr_use_must": len(re.findall(r"\bMUST\b", req)) >= 3,
        "has_success_criteria": bool(re.search(r"##\s*Success Criteria", md, re.I)),
        # measurable = stable SC ids OR explicit numeric thresholds / bound phrasing
        "success_measurable": (
            len(re.findall(r"\bSC-?\d+\b", succ)) >= 3
            or bool(
                re.search(
                    r"(at least|under|within|fewer than|less than|no more than|"
                    r"[≥<>]=?\s*\d|\d+\s*(%|ms|second|minute|x\b|/))",
                    succ,
                    re.I,
                )
            )
        ),
        "has_assumptions": bool(re.search(r"##\s*Assumptions", md, re.I)),
        # impl leakage: code fences inside the requirements block = spec is too low-level
        "no_impl_leakage": "```" not in req,
    }
    return checks


def reward(brief: str, spec_md: str) -> dict:
    _ = brief  # part of the task interface; semantic use is the LLM trace-judge's job
    checks = evaluate(spec_md)
    soft = sum(WEIGHTS[k] for k, ok in checks.items() if ok)
    hard = int(all(checks[k] for k in CRITICAL))
    failed = [k for k, ok in checks.items() if not ok]
    return {
        "hard": hard,
        "soft": round(soft, 4),
        "checks": checks,
        "failed": failed,
        "needs_judge": [
            # semantic aspects no regex can confirm — sent to the LLM trace-judge
            "each FR is genuinely testable (measurable accept criteria, not just FR-id-shaped)",
            "requirements actually cover the brief (no missing core behavior)",
            "success criteria are outcome-level, not implementation steps",
        ],
    }

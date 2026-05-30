"""Analysis helpers for the SkillOpt task-slice notebooks (reviewer / specify).

Loaders over a saved ``jobs/<run>/`` artifact. These live here — not inlined in notebook
cells — per the notebook skill: a loop / parse / repo-walk / reusable helper belongs in an
importable module and is *imported* into the cell.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path) -> Any:
    with open(path) as f:
        return json.load(f)


def load_jsonl(path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def mean(rows: list[dict], key: str) -> float:
    rows = list(rows)
    return round(sum(r[key] for r in rows) / len(rows), 4) if rows else 0.0


def case_dir(repo: Path, slug: str) -> Path:
    return repo / "tasks" / slug


def job_dir(repo: Path, name: str) -> Path:
    return repo / "jobs" / name


# --- specify slice: structural ⊕ trace-judge analysis (SC-006) -------------

_JUDGE_DIMS = ("judge_testable", "judge_coverage", "judge_outcome")


def sc006_evidence(rows: list[dict]) -> list[dict]:
    """Rows where the *structural* reward saturated (structural_soft >= 1.0) but the
    *judge* still down-scored at least one dimension (< 1.0).

    Each such row is a concrete witness for SC-006: the deterministic checker saw
    nothing wrong, yet the LLM trace-judge found a real testability/coverage/outcome
    gap. Sorted by ``judge_overall`` ascending so the strongest witness is first.
    """
    witnesses = [
        r for r in rows if r.get("structural_soft", 0) >= 1.0 and min(r.get(d, 1.0) for d in _JUDGE_DIMS) < 1.0
    ]
    return sorted(witnesses, key=lambda r: r.get("judge_overall", 1.0))

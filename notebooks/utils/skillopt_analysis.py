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

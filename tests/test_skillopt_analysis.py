"""Unit tests for the specify-slice analysis helper (SC-006 witness selection).

The notebook ``notebooks/specify_skillopt.ipynb`` leans on ``sc006_evidence``
returning *only* witnesses, *deterministically* ordered (it reads ``witnesses[0]``).
These tests pin both properties so the SC-006 demonstration can't silently drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

# the helper lives under notebooks/utils (a notebook-support package, not src/) —
# make it importable the same way the notebook's bootstrap cell does.
_NOTEBOOKS = Path(__file__).resolve().parent.parent / "notebooks"
if str(_NOTEBOOKS) not in sys.path:
    sys.path.insert(0, str(_NOTEBOOKS))

from utils.skillopt_analysis import sc006_evidence  # noqa: E402


def _row(id: str, struct: float, overall: float, testable: float, coverage: float, outcome: float) -> dict:
    return {
        "id": id,
        "structural_soft": struct,
        "judge_overall": overall,
        "judge_testable": testable,
        "judge_coverage": coverage,
        "judge_outcome": outcome,
    }


def test_keeps_only_structural_pass_with_judge_drop_sorted_ascending() -> None:
    rows = [
        _row("a", 1.0, 0.88, 0.90, 0.95, 0.85),  # witness (outcome dropped)
        _row("b", 1.0, 1.00, 1.00, 1.00, 1.00),  # not a witness (judge perfect)
        _row("c", 0.80, 0.50, 0.50, 0.50, 0.50),  # not a witness (structural failed)
        _row("d", 1.0, 0.80, 0.70, 0.90, 0.85),  # witness, lowest overall -> first
    ]
    out = sc006_evidence(rows)
    assert [r["id"] for r in out] == ["d", "a"]


def test_missing_judge_dims_is_not_a_witness() -> None:
    # structural passed but no judge dimensions present: min() defaults to 1.0 -> excluded.
    rows = [{"id": "x", "structural_soft": 1.0, "judge_overall": 0.5}]
    assert sc006_evidence(rows) == []


def test_empty_input() -> None:
    assert sc006_evidence([]) == []

"""T042/T043 — both optimizers integrate via the substrate, no optimizer-specific
substrate code (SC-003), and the loop invariants hold (C-5/C-6/FR-006/FR-008).

Both GEPA and SkillOpt are *engine-mode* adapters (design A): the library owns its
loop and the adapter maps its output onto Session entities. These tests are offline —
GEPA's construction needs the `gepa` lib; SkillOpt's disk-mapping runs against a real
run-directory fixture captured from an actual live run (tests/fixtures/skillopt_run).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentbook.adapters.skillopt_adapter import SkillOptOptimizer
from agentbook.session import Session

FIXTURE = Path(__file__).parent / "fixtures" / "skillopt_run"
REPO = Path(__file__).resolve().parent.parent


def _session(seed: object, slice_kind: str) -> Session:
    return Session(eval_set=["q"], model_client=lambda *_a, **_k: None, slice_kind=slice_kind, seed_artifact=seed)


def test_skillopt_maps_real_run_into_session() -> None:
    """SC-003: a real on-disk SkillOpt run maps onto the same Session entities."""
    seed_skill = (FIXTURE / "skills" / "skill_v0000.md").read_text()
    session = _session(seed_skill, "skill_document")
    opt = SkillOptOptimizer(session, skillopt_root="/unused-for-disk-mapping")

    summary = opt.sync_from_disk(FIXTURE)

    assert summary["version"].startswith("skillopt")
    # best skill became a candidate (child of the seed), with the test score attached
    assert len(session.candidates) == 2
    best = session.candidates[-1]
    assert best.parent_id == session.candidates[0].candidate_id
    assert "test_hard" in best.scores
    # one Iteration recorded per training step from history.json
    assert len(session.iterations) >= 1


def test_skillopt_reflect_reads_logged_trajectories() -> None:
    """C-5/FR-006: the optimizer operates on logged trajectory objects (the same
    conversation.json files SkillOpt's reflect parses), not a fresh re-parse path."""
    trajectories = SkillOptOptimizer.load_trajectories(FIXTURE)
    assert trajectories, "expected real logged trajectories in the fixture"
    row = trajectories[0]
    assert row["item_id"].startswith("squad-val-")
    assert row["n_turns"] >= 1 and isinstance(row["roles"], list)

    results = SkillOptOptimizer.load_results(FIXTURE)
    assert results and all("id" in r and "phase" in r for r in results)


def test_skillopt_sync_does_not_write_substrate() -> None:
    """C-6/FR-008: mapping a run into the session must not write to the codebase."""

    def snapshot() -> dict[str, float]:
        files: dict[str, float] = {}
        for root in (REPO / "src" / "agentbook", REPO / "notebooks"):
            for p in root.rglob("*"):
                if p.is_file():
                    files[str(p)] = p.stat().st_mtime
        return files

    before = snapshot()
    session = _session("seed skill", "skill_document")
    SkillOptOptimizer(session, skillopt_root="/unused").sync_from_disk(FIXTURE)
    assert snapshot() == before


def test_gepa_adapter_integrates_with_no_substrate_changes() -> None:
    """SC-003: the GEPA (engine-mode) adapter wires to a Session the same way —
    only the slice and state shape differ. Construction needs the gepa lib."""
    pytest.importorskip("gepa")  # optional extra: pip install .[gepa]
    from agentbook.adapters.gepa_adapter import GepaOptimizer

    session = _session({"system_prompt": "Solve it."}, "system_prompt")
    opt = GepaOptimizer(session, task_lm="bedrock/x", reflection_lm="bedrock/y")
    assert opt.seed_candidate == {"system_prompt": "Solve it."}
    # same substrate (Session) hosts both optimizers; no optimizer-specific substrate code
    assert opt.session is session

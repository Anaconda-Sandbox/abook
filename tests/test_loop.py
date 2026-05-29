"""Deterministic substrate-driver tests using a FakeOptimizer (no gepa, no kernel).

Covers the parts of T022 / T032 / T043 that need no external library or live
kernel: stable PID and load-once (SC-001), in-memory failed-trace introspection
(FR-004), and the no-self-rewrite invariant (C-6/FR-008). The live-kernel halves
of those tasks run in the GEPA/SkillOpt notebook phases.
"""

from __future__ import annotations

from pathlib import Path

from agentbook.contract import Optimizer, Reflection, Trace
from agentbook.loop import run_iteration
from agentbook.session import Session

REPO = Path(__file__).resolve().parent.parent


class FakeOptimizer:
    """Evolves a system-prompt string; longer prompt scores higher, so each
    reflection is accepted by the gate. ``reflect`` calls the model client."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.last_traces: list[Trace] = []

    def rollout(self, candidate: str, eval_set: object) -> list[Trace]:
        traces = []
        for i, ex in enumerate(self.session.eval_set.examples):
            # Example 0 always fails (score 0) so we can assert failed-trace introspection.
            score = 0.0 if i == 0 else min(1.0, len(candidate) / 60.0)
            traces.append(Trace(candidate_id=candidate, eval_id=str(i), inputs=ex, output=candidate, score=score))
        self.last_traces = traces
        return traces

    def evaluate(self, traces: list[Trace]) -> dict[str, float]:
        return {t.eval_id: (t.score or 0.0) for t in traces}

    def reflect(self, candidate: str, traces: list[Trace]) -> Reflection:
        self.session.model_client("propose an edit")  # inner-LLM call
        return Reflection(from_candidate_id=candidate, proposed_artifact=candidate + " Think step by step.")

    def edit(self, reflection: Reflection) -> str:
        return str(reflection.proposed_artifact)

    def gate(self, parent: object, child: object) -> bool:
        return bool(child.mean_score >= parent.mean_score)  # type: ignore[attr-defined]


def _make_session() -> Session:
    return Session(
        eval_set=["q1", "q2", "q3"],
        model_client=lambda _p: "ok",
        slice_kind="system_prompt",
        seed_artifact="Solve it.",
    )


def test_fake_optimizer_satisfies_protocol() -> None:
    opt = FakeOptimizer(_make_session())
    assert isinstance(opt, Optimizer)  # structural conformance (contract C-1)


def test_stable_pid_and_load_once() -> None:
    session = _make_session()
    opt = FakeOptimizer(session)
    pid = session.kernel_pid
    eval_set_id = id(session.eval_set)
    client_id = id(session.model_client)
    for _ in range(10):
        run_iteration(opt, session)
    assert session.kernel_pid == pid  # SC-001: PID stable
    assert id(session.eval_set) == eval_set_id  # eval set loaded once
    assert id(session.model_client) == client_id  # client loaded once
    assert len(session.iterations) == 10


def test_failed_trace_is_queryable_in_memory() -> None:
    session = _make_session()
    opt = FakeOptimizer(session)
    run_iteration(opt, session)
    failed = [t for t in opt.last_traces if t.failed]
    assert failed and failed[0].eval_id == "0"  # FR-004: in-memory, queryable


def test_host_outcome_accessors() -> None:
    """T030 / FR-009: the host can read best score, frontier, and the latest diff."""
    session = _make_session()
    opt = FakeOptimizer(session)
    for _ in range(3):
        run_iteration(opt, session)
    assert session.best_score() > 0.0
    assert session.best_candidate().candidate_id in session.frontier_snapshot()
    diff = session.latest_diff()
    assert "Think step by step." in diff  # the accepted edit shows in the unified diff


def test_no_self_rewrite_of_notebook_or_codebase() -> None:
    """C-6 / FR-008: running iterations must not create/modify notebooks or src."""

    def snapshot() -> dict[str, float]:
        files: dict[str, float] = {}
        for root in (REPO / "src" / "agentbook", REPO / "notebooks"):
            for p in root.rglob("*"):
                if p.is_file():
                    files[str(p)] = p.stat().st_mtime
        return files

    before = snapshot()
    session = _make_session()
    opt = FakeOptimizer(session)
    for _ in range(5):
        run_iteration(opt, session)
    assert snapshot() == before  # no files written

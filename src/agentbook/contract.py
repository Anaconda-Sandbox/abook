"""The loop contract — the one interface every optimizer adapter satisfies.

This is the substrate-level surface for ``rollout → evaluate → reflect → edit``
(plus a ``gate``). It is *structural*: an adapter satisfies :class:`Optimizer`
by shape, without inheriting a base class, so optimizers stay decoupled from the
substrate and from each other.

The driver in :mod:`agentbook.loop` is written once against this Protocol and is
identical for GEPA (kernel-resident state) and SkillOpt (on-disk state).

See ``specs/agentbook_thesis/contracts/loop-contract.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Trace:
    """Inputs, output, and signals from one rollout of one candidate over one
    eval example. A Trace MUST stay a queryable in-memory object for the next
    loop step — never a file to re-parse (FR-004)."""

    candidate_id: Any
    eval_id: str
    inputs: Any
    output: Any
    score: float | None = None
    signals: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        """A trace counts as failed when its score is falsy (0.0 or None)."""
        return not self.score


@dataclass
class Reflection:
    """An inner-LLM-proposed edit to a candidate, informed by recent traces."""

    from_candidate_id: Any
    proposed_artifact: Any
    rationale: str = ""
    llm_calls: int = 0


@runtime_checkable
class Optimizer(Protocol):
    """The four loop arrows plus a gate. State lives wherever the adapter keeps
    it — the substrate never assumes kernel-resident vs. on-disk."""

    def rollout(self, candidate: Any, eval_set: Any) -> list[Trace]:
        """Run ``candidate`` over ``eval_set``; one Trace per example. Reads the
        warm model client and already-loaded eval set from kernel memory."""
        ...

    def evaluate(self, traces: list[Trace]) -> dict[str, float]:
        """Score the traces. Returns ``{eval_id: score}``. Failed traces remain
        queryable in-memory objects (FR-004)."""
        ...

    def reflect(self, candidate: Any, traces: list[Trace]) -> Reflection:
        """Inner LLM proposes an edit, informed by ``traces``."""
        ...

    def edit(self, reflection: Reflection) -> Any:
        """Apply the reflection, producing a new candidate artifact. Operates on
        the same in-memory objects as :meth:`evaluate` — one vocabulary (FR-006)."""
        ...

    def gate(self, parent: Any, child: Any) -> bool:
        """Accept or reject the child candidate (e.g. Pareto dominance).
        Returning ``False`` drops the iteration without adding a candidate."""
        ...

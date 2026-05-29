"""Session — the warm kernel state held across iterations.

Loaded once per session (FR-003): the eval set, the model client, and the
candidate population. The inner loop never mutates session *config* (eval-set
identity, slice kind) — those are host-set at setup and changed only between
sessions (Constitution II, FR-008). Drift in the eval set is surfaced loudly,
never silently (research Decision 5).

See ``specs/agentbook_thesis/data-model.md``.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import warnings
from dataclasses import dataclass, field
from typing import Any

from agentbook.contract import Trace


def _hash_examples(examples: Any) -> str:
    """Stable content hash of an eval set, for drift detection."""
    try:
        payload = json.dumps(examples, sort_keys=True, default=repr)
    except TypeError:
        payload = repr(examples)
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class EvalSet:
    """The examples candidates are scored against; pinned by content hash."""

    examples: list[Any]
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = _hash_examples(self.examples)

    def __len__(self) -> int:
        return len(self.examples)

    def drifted(self) -> bool:
        return _hash_examples(self.examples) != self.content_hash


@dataclass
class Candidate:
    """A version of the harness slice under evolution, with attached scores."""

    candidate_id: int
    artifact: Any
    scores: dict[str, float] = field(default_factory=dict)
    parent_id: int | None = None

    @property
    def mean_score(self) -> float:
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0.0


@dataclass
class Iteration:
    """One full rollout → evaluate → reflect → edit cycle (see run_log.json)."""

    index: int
    selected_candidate_id: int
    new_candidate_id: int | None
    subsample_ids: list[str]
    scores: list[float]
    partial: bool = False


class Session:
    """One live kernel hosting state across iterations.

    Args:
        eval_set: examples to score against (or a raw list, wrapped in EvalSet).
        model_client: the inner-loop model client (any callable).
        slice_kind: the one declared harness slice under evolution this run
            (e.g. ``"system_prompt"``); immutable for the run (Constitution II.2).
        seed_artifact: the starting artifact for the seed candidate.
    """

    def __init__(
        self,
        eval_set: EvalSet | list[Any],
        model_client: Any,
        slice_kind: str,
        seed_artifact: Any,
    ) -> None:
        self.eval_set = eval_set if isinstance(eval_set, EvalSet) else EvalSet(eval_set)
        self.model_client = model_client
        self.slice_kind = slice_kind
        self.kernel_pid = os.getpid()
        self._next_id = 0
        self.candidates: list[Candidate] = []
        self.iterations: list[Iteration] = []
        self.add_candidate(seed_artifact, parent=None)

    # --- candidate lifecycle -------------------------------------------------

    def add_candidate(self, artifact: Any, parent: Candidate | None) -> Candidate:
        cand = Candidate(
            candidate_id=self._next_id, artifact=artifact, parent_id=parent.candidate_id if parent else None
        )
        self._next_id += 1
        self.candidates.append(cand)
        return cand

    def select_parent(self) -> Candidate:
        """Frontier-driven parent selection. The substrate's default is
        best-by-mean-score; an optimizer with a richer frontier (e.g. GEPA's
        Pareto set) can override selection in its adapter."""
        return max(self.candidates, key=lambda c: c.mean_score)

    def record(
        self,
        parent: Candidate,
        child: Candidate | None,
        traces: list[Trace],
        partial: bool = False,
    ) -> Iteration:
        """Append an Iteration record. The driver attaches candidate scores
        before calling this; ``record`` only logs the cycle."""
        it = Iteration(
            index=len(self.iterations),
            selected_candidate_id=parent.candidate_id,
            new_candidate_id=child.candidate_id if child else None,
            subsample_ids=[t.eval_id for t in traces],
            scores=[t.score for t in traces if t.score is not None],
            partial=partial,
        )
        self.iterations.append(it)
        return it

    # --- host-facing outcome accessors (T030, FR-009) ------------------------

    def best_candidate(self) -> Candidate:
        return max(self.candidates, key=lambda c: c.mean_score)

    def best_score(self) -> float:
        return self.best_candidate().mean_score

    def frontier_snapshot(self) -> list[int]:
        """Non-dominated candidate ids by mean score (substrate default)."""
        if not self.candidates:
            return []
        top = self.best_score()
        return [c.candidate_id for c in self.candidates if c.mean_score >= top]

    def latest_diff(self) -> str:
        """Unified diff between the most recent candidate and its parent, when
        both artifacts are strings; otherwise an empty string."""
        if len(self.candidates) < 2:
            return ""
        child = self.candidates[-1]
        if child.parent_id is None:
            return ""
        parent = next((c for c in self.candidates if c.candidate_id == child.parent_id), None)
        if parent is None or not isinstance(child.artifact, str) or not isinstance(parent.artifact, str):
            return ""
        return "".join(
            difflib.unified_diff(
                parent.artifact.splitlines(keepends=True),
                child.artifact.splitlines(keepends=True),
                fromfile=f"candidate_{parent.candidate_id}",
                tofile=f"candidate_{child.candidate_id}",
            )
        )

    # --- eval-set integrity (research Decision 5) ----------------------------

    def check_eval_set_drift(self) -> None:
        if self.eval_set.drifted():
            warnings.warn(
                "eval set changed since session setup — cross-iteration scores are no "
                "longer comparable. Re-pin intentionally if this is a new experiment.",
                stacklevel=2,
            )

"""GEPA adapter — engine mode (see contracts/loop-contract.md, design A).

GEPA owns its own optimization loop (``gepa.optimize`` runs rollout → evaluate →
reflect → edit internally and reports progress through a ``GEPACallback``). This
adapter does not drive GEPA arrow-by-arrow; it runs the real engine and **maps
GEPA's callback events and result onto the substrate's Session entities** so the
run renders inline (FR-005).

State is kernel-resident: GEPA's candidate population lives as Python objects in
the live kernel for the whole run (FR-003, SC-001).
"""

from __future__ import annotations

from typing import Any

from gepa.core.callbacks import GEPACallback

from agentbook.session import Candidate, Session


class _SessionCallback(GEPACallback):
    """Mirrors GEPA progress into an event log and the substrate Session."""

    def __init__(self, session: Session, events: list[dict[str, Any]]) -> None:
        self.session = session
        self.events = events

    def on_optimization_start(self, event: Any) -> None:
        self.events.append({"phase": "start", "trainset": event["trainset_size"], "valset": event["valset_size"]})

    def on_iteration_start(self, event: Any) -> None:
        state = event["state"]
        self.events.append(
            {
                "phase": "iter_start",
                "iteration": event["iteration"],
                "total_evals": state.total_num_evals,
                "num_candidates": len(state.program_candidates),
            }
        )

    def on_evaluation_end(self, event: Any) -> None:
        if event.get("is_seed_candidate") and event.get("candidate_idx") is None:
            return
        scores = event.get("scores") or []
        self.events.append(
            {
                "phase": "eval_end",
                "iteration": event.get("iteration"),
                "candidate_idx": event.get("candidate_idx"),
                "minibatch_score": sum(scores),
                "batch_size": len(scores),
            }
        )

    def on_candidate_accepted(self, event: Any) -> None:
        self.events.append({"phase": "accepted", "iteration": event.get("iteration")})

    def on_candidate_rejected(self, event: Any) -> None:
        self.events.append({"phase": "rejected", "iteration": event.get("iteration")})

    def on_optimization_end(self, event: Any) -> None:
        self.events.append(
            {
                "phase": "end",
                "best_idx": event["best_candidate_idx"],
                "total_iterations": event["total_iterations"],
                "total_metric_calls": event["total_metric_calls"],
            }
        )


class GepaOptimizer:
    """Engine-mode adapter for GEPA (system-prompt slice, kernel-resident state).

    Args:
        session: the live substrate session (holds the seed candidate).
        task_lm: litellm model string for the task model (e.g. a Bedrock model).
        reflection_lm: litellm model string for GEPA's reflection model.
    """

    def __init__(self, session: Session, task_lm: str, reflection_lm: str) -> None:
        self.session = session
        self.task_lm = task_lm
        self.reflection_lm = reflection_lm
        self.events: list[dict[str, Any]] = []
        self.result: Any = None

    @property
    def seed_candidate(self) -> dict[str, str]:
        """GEPA seed = the session's seed artifact, which must be a component dict."""
        artifact = self.session.candidates[0].artifact
        if not isinstance(artifact, dict):
            raise TypeError("GEPA seed_artifact must be a dict of named text components, e.g. {'system_prompt': ...}")
        return artifact

    def optimize(
        self,
        trainset: list[Any],
        valset: list[Any],
        max_metric_calls: int,
        reflection_minibatch_size: int = 3,
        seed: int = 0,
    ) -> Any:
        """Run the real GEPA engine in this kernel and sync results into the session."""
        import gepa

        # GEPACallback's other on_* hooks have empty bodies (mypy reads them as abstract);
        # we intentionally override only the events we capture, so this instantiation is safe.
        cb = _SessionCallback(self.session, self.events)  # type: ignore[abstract]
        self.result = gepa.optimize(
            seed_candidate=self.seed_candidate,
            trainset=trainset,
            valset=valset,
            task_lm=self.task_lm,
            reflection_lm=self.reflection_lm,
            max_metric_calls=max_metric_calls,
            reflection_minibatch_size=reflection_minibatch_size,
            skip_perfect_score=False,
            callbacks=[cb],
            display_progress_bar=False,
            seed=seed,
        )
        self._sync_session(self.result)
        return self.result

    def _sync_session(self, result: Any) -> None:
        """Map GEPA's result onto Session entities."""
        # Record the best discovered candidate so Session.best_candidate / latest_diff work.
        seed = self.session.candidates[0]
        best = result.best_candidate
        scores = {"valset": float(_mean(getattr(result, "val_aggregate_subscores", []) or [0.0]))}
        child = self.session.add_candidate(best, parent=seed)
        child.scores.update(scores)
        # Record one Iteration per GEPA iteration observed.
        for ev in (e for e in self.events if e["phase"] == "iter_start"):
            self.session.iterations.append(
                _iteration(index=ev["iteration"], parent=seed, child=child, n=ev["num_candidates"])
            )

    def event_frame(self) -> Any:
        """Return the captured events as a pandas DataFrame for inline display."""
        import pandas as pd

        return pd.DataFrame(self.events)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _iteration(index: int, parent: Candidate, child: Candidate, n: int) -> Any:
    from agentbook.session import Iteration

    return Iteration(
        index=index,
        selected_candidate_id=parent.candidate_id,
        new_candidate_id=child.candidate_id,
        subsample_ids=[],
        scores=[],
    )

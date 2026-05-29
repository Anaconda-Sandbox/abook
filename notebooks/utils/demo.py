"""Python entry points the demo notebooks call, so notebook cells stay thin and the
heavy rollout→evaluate→reflect→edit loop runs as importable, reusable python — driven
live in the warm kernel (the notebook just calls these)."""

from __future__ import annotations

import os
import time
from typing import Any


def build_gepa(trainset: Any, seed_artifact: dict[str, str], task_lm: str,
               reflection_lm: str) -> tuple[Any, Any]:
    """Wire a Session + GepaOptimizer over the system-prompt slice."""
    from agentbook.adapters.gepa_adapter import GepaOptimizer
    from agentbook.session import Session

    # engine-mode placeholder: gepa calls the LLM itself via litellm
    session = Session(eval_set=trainset, model_client=lambda *_a, **_k: None,
                      slice_kind="system_prompt", seed_artifact=seed_artifact)
    opt = GepaOptimizer(session, task_lm=task_lm, reflection_lm=reflection_lm)
    return session, opt


def run_gepa(opt: Any, trainset: Any, valset: Any, *, max_metric_calls: int,
             reflection_minibatch_size: int, seed: int) -> Any:
    """Run one engine-mode GEPA optimization (the inner loop) in the current kernel."""
    return opt.optimize(trainset=trainset, valset=valset,
                        max_metric_calls=max_metric_calls,
                        reflection_minibatch_size=reflection_minibatch_size, seed=seed)


def steer_next_experiment(session: Any) -> tuple[int, dict[str, Any]]:
    """Outer-loop step (US2/SC-002): read the live outcome and decide the next knob.

    Returns (next_reflection_minibatch_size, outcome) and the host-side transit latency
    inside `outcome["host_latency_s"]` — the time to read live state + decide + issue,
    which must stay under 1s (it is substrate transit, not cold start or file I/O).
    """
    t0 = time.perf_counter()
    best = session.best_score()
    frontier = session.frontier_snapshot()
    diff_lines = session.latest_diff().count("\n")
    next_minibatch = 2 if len(frontier) >= 1 else 3
    host_latency = time.perf_counter() - t0
    return next_minibatch, {
        "best_score": best, "frontier": frontier, "diff_lines": diff_lines,
        "host_latency_s": host_latency,
    }


def run_gepa_demo(trainset: Any, valset: Any, seed_artifact: dict[str, str], *,
                  task_lm: str, reflection_lm: str, max_metric_calls: int = 30,
                  reflection_minibatch_size: int = 3) -> dict[str, Any]:
    """Full demo: run #1, host steers one knob from live state, run #2 — same kernel.

    Returns a results dict with both runs, the SC-002 host→next-experiment latency, and
    the SC-001 PID-stability check. The notebook calls this and renders the result inline.
    """
    pid = os.getpid()
    session, opt = build_gepa(trainset, seed_artifact, task_lm, reflection_lm)

    r1 = run_gepa(opt, trainset, valset, max_metric_calls=max_metric_calls,
                  reflection_minibatch_size=reflection_minibatch_size, seed=0)

    next_minibatch, outcome = steer_next_experiment(session)  # US2 + SC-002
    r2 = run_gepa(opt, trainset, valset, max_metric_calls=max_metric_calls,
                  reflection_minibatch_size=next_minibatch, seed=1)

    return {
        "kernel_pid": pid,
        "pid_stable": os.getpid() == pid,                      # SC-001
        "run1": {"candidates": r1.num_candidates, "best_idx": r1.best_idx,
                 "metric_calls": r1.total_metric_calls},
        "steer": outcome,                                      # incl. host_latency_s (SC-002)
        "next_reflection_minibatch_size": next_minibatch,
        "run2": {"candidates": r2.num_candidates, "best_idx": r2.best_idx,
                 "metric_calls": r2.total_metric_calls},
        "best_score": session.best_score(),
        "frontier": session.frontier_snapshot(),
        "session": session, "opt": opt,
    }

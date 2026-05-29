"""The loop driver — ``rollout → evaluate → reflect → edit`` in one function.

Written once against the :class:`agentbook.contract.Optimizer` Protocol and
identical for every optimizer (FR-010, SC-003). One call is one inner-loop
iteration; it runs entirely on state already resident in the kernel (FR-001,
FR-003).
"""

from __future__ import annotations

from agentbook.contract import Optimizer
from agentbook.session import Iteration, Session


def run_iteration(opt: Optimizer, session: Session) -> Iteration:
    """Run one rollout → evaluate → reflect → edit cycle.

    The parent is scored, an edit is reflected and applied to make a child, the
    child is scored, and the optimizer's gate accepts or rejects it. A rejected
    child is dropped from the population.
    """
    session.check_eval_set_drift()
    parent = session.select_parent()

    # rollout + evaluate the parent over the (warm, in-memory) eval set
    traces = opt.rollout(parent.artifact, session.eval_set)
    scores = opt.evaluate(traces)
    for t in traces:
        if t.score is None and t.eval_id in scores:
            t.score = scores[t.eval_id]
    parent.scores.update(scores)

    # reflect (inner LLM) → edit → child candidate
    reflection = opt.reflect(parent.artifact, traces)
    child = session.add_candidate(opt.edit(reflection), parent)

    # score the child over the same eval set
    child_traces = opt.rollout(child.artifact, session.eval_set)
    child_scores = opt.evaluate(child_traces)
    for t in child_traces:
        if t.score is None and t.eval_id in child_scores:
            t.score = child_scores[t.eval_id]
    child.scores.update(child_scores)

    if opt.gate(parent, child):
        return session.record(parent, child, child_traces)
    session.candidates.remove(child)
    return session.record(parent, None, traces)

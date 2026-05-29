"""T014 / T032 — the budget chokepoint halts cleanly, never silently overruns."""

from __future__ import annotations

import pytest

from agentbook.budget import Budget, BudgetedClient, BudgetExhausted


def _echo(x: object) -> object:
    return x


def test_counts_each_call() -> None:
    client = BudgetedClient(_echo, Budget(max_calls=3))
    client("a")
    client("b")
    assert client.budget.calls_used == 2
    assert client.budget.state == "active"


def test_raises_exactly_at_cap() -> None:
    budget = Budget(max_calls=2)
    client = BudgetedClient(_echo, budget)
    client("first")
    client("second")
    assert budget.exhausted
    with pytest.raises(BudgetExhausted):
        client("third")
    # The offending call was NOT made — budget never silently exceeded (FR-007).
    assert budget.calls_used == 2


def test_spend_cap_enforced() -> None:
    budget = Budget(max_calls=100, max_spend=1.0)
    client = BudgetedClient(_echo, budget, cost=lambda _resp: 0.6)
    client("one")  # spend 0.6
    assert not budget.exhausted
    client("two")  # spend 1.2 -> now exhausted
    assert budget.exhausted
    with pytest.raises(BudgetExhausted):
        client("three")


def test_remaining_calls() -> None:
    budget = Budget(max_calls=5)
    client = BudgetedClient(_echo, budget)
    client("x")
    assert budget.remaining_calls() == 4

"""Inner-loop LLM budget — the single chokepoint that bounds spend.

Every inner-loop model call passes through :class:`BudgetedClient`, which
counts calls (and optionally spend) against a :class:`Budget`. Reaching the cap
raises :class:`BudgetExhausted` *before* the offending call is made — the run
halts cleanly with a partial result and never silently exceeds the budget
(FR-007, SC-006).

See ``specs/agentbook_thesis/research.md`` (Decision 4).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class BudgetExhausted(RuntimeError):
    """Raised when an LLM call would exceed the host-declared budget.

    The loop driver catches this and returns the best-so-far candidate with the
    run marked partial — it is control flow, not an error condition.
    """


@dataclass
class Budget:
    """A host-declared bound on inner-loop LLM usage.

    ``max_spend`` is optional and only enforced when the wrapped client reports
    a per-call cost (passed to :class:`BudgetedClient` via its ``cost`` hook).
    """

    max_calls: int
    max_spend: float | None = None
    calls_used: int = 0
    spend_used: float = 0.0

    @property
    def exhausted(self) -> bool:
        if self.calls_used >= self.max_calls:
            return True
        return self.max_spend is not None and self.spend_used >= self.max_spend

    @property
    def state(self) -> str:
        return "exhausted" if self.exhausted else "active"

    def remaining_calls(self) -> int:
        return max(0, self.max_calls - self.calls_used)


class BudgetedClient:
    """Wraps a callable model client so every call is counted against a Budget.

    Args:
        client: the underlying model client — any callable
            (``client(*args, **kwargs) -> response``).
        budget: the :class:`Budget` to enforce.
        cost: optional ``(response) -> float`` hook; if given, its return value
            is added to ``budget.spend_used`` after each successful call.

    Raises:
        BudgetExhausted: at call time, if the budget is already exhausted. The
            offending call is NOT made, so the budget is never silently exceeded.
    """

    def __init__(
        self,
        client: Callable[..., Any],
        budget: Budget,
        cost: Callable[[Any], float] | None = None,
    ) -> None:
        self._client = client
        self.budget = budget
        self._cost = cost

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if self.budget.exhausted:
            raise BudgetExhausted(f"budget exhausted: {self.budget.calls_used}/{self.budget.max_calls} calls used")
        self.budget.calls_used += 1
        response = self._client(*args, **kwargs)
        if self._cost is not None:
            self.budget.spend_used += self._cost(response)
        return response

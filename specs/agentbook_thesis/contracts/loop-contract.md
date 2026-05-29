# Contract: the loop — rollout → evaluate → reflect → edit

**Feature**: agentbook_thesis
**Status**: Phase 1 design contract

This is the single substrate-level interface every optimizer adapter must satisfy
(FR-010, SC-003). It is structural — adapters satisfy it by shape, not by inheriting a
base class (research Decision 2). The substrate code that drives the loop is written
once against this Protocol and is identical for GEPA and SkillOpt.

## Python Protocol

```python
from __future__ import annotations
from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class Optimizer(Protocol):
    """The four loop arrows plus a gate. State lives wherever the adapter
    keeps it (kernel-resident or on-disk) — the substrate never assumes."""

    def rollout(self, candidate: Any, eval_set: Any) -> list["Trace"]:
        """Run `candidate` over `eval_set`, producing one Trace per example.
        Reads the warm model client and the already-loaded eval set from
        kernel memory — pays no cold-start cost (FR-001, FR-003)."""

    def evaluate(self, traces: list["Trace"]) -> dict[str, float]:
        """Score the traces. Returns {eval_id -> score}. A failed trace MUST
        remain a queryable in-memory object for the next step (FR-004)."""

    def reflect(self, candidate: Any, traces: list["Trace"]) -> "Reflection":
        """Inner LLM proposes an edit to `candidate`, informed by `traces`."""

    def edit(self, reflection: "Reflection") -> Any:
        """Apply the reflection, producing a new candidate. Written in the
        same language / against the same objects as `evaluate` — one
        vocabulary, not a hand-off between codebases (FR-006)."""

    def gate(self, parent: Any, child: Any) -> bool:
        """Accept or reject the child candidate (e.g., Pareto dominance).
        Returning False drops the iteration without adding a candidate."""
```

## Two integration modes (design A — revised 2026-05-28)

Implementation revealed that mature optimizer libraries own their own engine. The substrate
supports **two** integration modes against the same loop *concept*:

1. **Driver mode** — the optimizer exposes the four arrows; the substrate's written-once
   `run_iteration` (below) orchestrates them. Best for simple/custom optimizers. The Phase-2
   tests exercise this mode with a `FakeOptimizer`. `ClaudeAgentOptimizer`
   (`src/agentbook/adapters/claude_agent_adapter.py`) is the first real (non-fake) driver-mode
   adapter: its rollout is a multi-turn tool-using agent invoked via `claude -p`, validating
   the driver-mode path end-to-end.
2. **Engine mode** — the optimizer owns its loop (e.g. `gepa.optimize(...)`), running
   rollout→evaluate→reflect→edit *internally*. The adapter does not drive it; instead it
   **maps the library's progress events (callbacks) onto the substrate entities**
   (`Candidate`/`Trace`/`Iteration`/`Frontier`) so they render inline.
   GEPA and SkillOpt both integrate this way.

What generalizes across both (and what SC-003 actually asserts) is the **substrate**: the live
kernel, the MCP cell-op surface, and the shared entity/observation model — *not* a single loop
driver. The adapter is thin in both modes, but in engine mode it calls the library's own optimizer
rather than the substrate's `run_iteration`.

## Driver contract (substrate-owned, written once — driver mode)

```python
def run_iteration(opt: Optimizer, session: Session) -> Iteration:
    """One inner-loop iteration. Identical code for every optimizer."""
    cand = session.select_parent()                      # frontier-driven
    traces = opt.rollout(cand, session.eval_set)        # ← persistent state
    scores = opt.evaluate(traces)                       # ← coupled introspection
    reflection = opt.reflect(cand, traces)              # ← inner LLM
    child = opt.edit(reflection)                        # ← one vocabulary
    accepted = opt.gate(cand, child)
    return session.record(cand, child if accepted else None, traces, scores)
```

## Substrate operations (MCP tool surface — A-001, FR-002)

The host drives the session through these `mcp__runt__*` calls; each returns its result
in the same response (no file round-trip):

| Operation | MCP tool | Loop role |
|-----------|----------|-----------|
| Create a cell | `create_cell` | Stage setup / experiment code |
| Execute a cell | `execute_cell` | Run any of the four arrows; output returns inline (FR-005) |
| Read results | `get_results` / `get_cell` | Host reads score/frontier/diff to pick the next experiment (FR-009) |
| Persist | `save_notebook` | Snapshot the session artifact |
| Dependencies | `manage_dependencies` | Install optimizer libs into the warm kernel |

## Contract obligations

| # | Obligation | Verifies |
|---|------------|----------|
| C-1 | Both adapters integrate with **no optimizer-specific substrate code** — via driver mode (satisfy `Optimizer`) or engine mode (map callbacks onto substrate entities). The substrate (kernel, MCP ops, entity model) is unchanged per optimizer. | FR-010, SC-003 |
| C-2 | `rollout`/`evaluate` read state already resident in the kernel | FR-001, FR-003, SC-001 |
| C-3 | A failed trace returned by `evaluate` is an in-memory queryable object | FR-004 |
| C-4 | `edit` operates on the same in-memory objects as `evaluate` (no cross-codebase hand-off) | FR-006 |
| C-5 | No method mutates the notebook or the agentbook codebase | Constitution II.1, FR-008 |
| C-6 | Exactly one `HarnessSlice` is mutable for the run | Constitution II.2, FR-008 |

*(C-4 renumbered from C-5/C-6/C-7 — former C-4 budget obligation removed)*

# Implementation Plan: agentbook — notebook for a self-evolving agent harness

**Branch**: `agentbook_thesis` | **Date**: 2026-05-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/agentbook_thesis/spec.md`

## Summary

Build a thin Python substrate (`src/agentbook`) plus MCP-driven demo notebooks that host
the full rollout → evaluate → reflect → edit loop inside one live kernel session, with no
process restart between arrows. The substrate defines a single structural loop contract (a
Python `Protocol` + a written-once driver); two thin adapters wire GEPA (system-prompt
slice, kernel-resident state) and SkillOpt (skill-document slice, on-disk state) into that
one contract, proving the substrate generalizes across both harness slice and state shape.
The host (Claude Code) drives every cell over `mcp__runt__*`, reads live outcomes to pick
the next experiment, and edits agentbook itself between sessions — which is what makes the
harness genuinely self-evolving. A graduation-criteria doc names the measurable thresholds
at which the hot path leaves the kernel for a compiled service.

## Technical Context

**Language/Version**: Python ≥3.10,<3.14 (ruff target py310; mypy baseline 3.10)
**Primary Dependencies**: `matplotlib`, `numpy`, `ruff` (runtime); `gepa`, `SkillOpt` (optimizer adapters, installed into the kernel); `runt` MCP server (substrate, session-side)
**Storage**: In-kernel Python objects (session state, FR-003); on-disk only where an adapter's library requires it (SkillOpt) or for run snapshots (`save_notebook`, `_gepa_run_*` artifacts). No database.
**Testing**: `pytest` (+ `pytest-asyncio`, `pytest-cov`); unit tests may mock, CLI/E2E hits real services with real credentials (Constitution IV)
**Target Platform**: Local dev kernel driven live over MCP (single-tenant, interactive)
**Project Type**: Single project — installable library + MCP-driven notebooks
**Performance Goals**: ≥10 iterations, stable kernel PID (SC-001); host→next-experiment latency <1s on a warm kernel (SC-002)
**Constraints**: Inner loop never self-rewrites the notebook/codebase (II.1); one declared slice per run (II.2); substrate-first, no batch-wrapping (II.3); real data only (I)
**Scale/Scope**: Single-tenant interactive iteration. Multi-tenant serving and headless batch are explicitly out of scope (A-006); FR-011 governs when to leave the kernel.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Real Data Only | ✅ Pass | Eval sets are real (e.g. AIME, per `_gepa_run_07/candidates.json`); demo notebooks read real sources and carry a Data sources section. No fabricated scores/traces. |
| II.1 Inner loop never self-rewrites | ✅ Pass | Loop contract C-6 forbids any method mutating the notebook/codebase; agentbook edits are outer-loop, between sessions (FR-009). |
| II.2 One declared slice per run | ✅ Pass | `Session.slice_kind` is set at setup and immutable for the run (data-model invariant); contract C-7. |
| II.3 Substrate-first; don't batch-wrap | ✅ Pass | Research Decision 1 rejects papermill/nbclient; graduation thresholds documented (FR-011, SC-005). |
| III. Code Quality | ✅ Pass | Adapters/loop are small typed modules; ruff + mypy gate them; `agentbook-fix` already repairs LLM-edited notebooks post-`edit`. |
| IV. Testing Standards | ✅ Pass | Adapter conformance + loop driver get unit tests; one full optimizer run validated E2E against real LLM credentials (SC-004). |
| V. Thin Harness, Fat Skills | ✅ Pass | Substrate stays boring (Protocol + driver); intelligence is the inner reflection LLM and the outer host. |
| VI. Explicit Over Implicit | ✅ Pass | Slice and eval set are declared at setup; eval-set drift is surfaced loudly (research Decision 5), never silent. |

**Gate result**: PASS — no violations. Proceeded to Phase 0.

### Post-Design Re-check (after Phase 1)

Re-evaluated every principle against research.md, data-model.md, and contracts/loop-contract.md.
No new violations emerged. The state-agnostic contract (Decision 3) strengthens II and VI rather
than straining them. **Gate result: PASS.**

## Project Structure

### Documentation (this feature)

```text
specs/agentbook_thesis/
├── plan.md              # This file
├── research.md          # Phase 0: 6 technology decisions
├── data-model.md        # Phase 1: 9 entities + relationships + state-location table
├── quickstart.md        # Phase 1: run one GEPA inner loop over MCP
├── contracts/
│   └── loop-contract.md # Phase 1: the Optimizer Protocol + driver + MCP surface
├── checklists/
│   └── requirements.md  # Spec quality gate
└── tasks.md             # Phase 2 output (/specify tasks)
```

### Source Code (repository root)

```text
src/agentbook/
├── __init__.py
├── loop.py              # run_iteration driver — reference driver for "driver mode" optimizers (NEW)
├── contract.py          # the Optimizer Protocol + Trace/Reflection types (NEW)
├── session.py           # Session: warm state, frontier, eval-set pin/hash, kernel_pid (NEW)
├── adapters/
│   ├── __init__.py      # (NEW)
│   ├── gepa_adapter.py  # GEPA → Optimizer; kernel-resident state (NEW)
│   └── skillopt_adapter.py  # SkillOpt → Optimizer; on-disk state (NEW)
└── notebook_fix.py      # EXISTING — post-edit hygiene (repair_notebook + agentbook-fix CLI)

notebooks/
├── gepa_demo.ipynb      # MCP-driven system-prompt evolution demo (NEW, rebuilt)
└── skillopt_demo.ipynb  # MCP-driven skill-document evolution demo (NEW, rebuilt)

docs/
└── graduation.md        # Measurable thresholds for leaving the kernel (FR-011, SC-005) (NEW)

tests/
├── test_smoke.py        # EXISTING — package importability
├── test_contract.py     # Both adapters satisfy Optimizer with no driver changes (NEW)
└── test_loop.py         # run_iteration honors gate; no self-rewrite (NEW)
```

**Structure Decision**: Single project. The substrate is a thin installable library
(`src/agentbook`); the notebooks are the live deliverables driven over MCP; `docs/` holds
the graduation criteria. This matches the existing layout (the `agentbook-fix` CLI already
lives in `src/agentbook`) and keeps the harness legible to the agent improving it.

## Design Patterns

> Matched from `~/.claude/skills/specify/patterns/` based on spec triggers.

| Pattern | Applies Because | Key Implication |
| --- | --- | --- |
| [tentative-internals](~/.claude/skills/specify/patterns/tentative-internals.md) | Always applicable | Only the **loop contract** (`contracts/loop-contract.md`) is the stable surface; `loop.py`/`session.py`/adapter internals are free to change. Don't let adapters depend on each other's internals. |
| [empirical-validation](~/.claude/skills/specify/patterns/empirical-validation.md) | Spec sets measurable thresholds (graduation memory/latency/concurrency; eval gates) | The graduation thresholds (FR-011) and any score gate MUST be validated against real run data (e.g. `_gepa_run_07/`), not asserted — reinforces Constitution I. |
| llm-verification (weak match) | "LLM / model client / reflection" appear | Noted but **not load-bearing**: the inner LLM *reflects/proposes*, it does not classify weak signals. Treated as guidance, not a design driver. |

## Complexity Tracking

No violations. All constitution principles satisfied (both gate passes). This section
intentionally left without exceptions.

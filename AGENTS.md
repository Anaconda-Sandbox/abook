# agentbook Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-28

## Active Technologies

<!-- BEGIN SPECIFY: ACTIVE_TECHNOLOGIES -->
- **Language**: Python ≥3.10,<3.14 (ruff target py310, mypy baseline 3.10)
- **Build**: hatchling + hatch-vcs (version from VCS)
- **Runtime deps**: matplotlib, numpy, ruff
- **Optimizer adapters** (installed into the live kernel): `gepa` (system-prompt slice, kernel-resident state), `SkillOpt` (skill-document slice, on-disk state)
- **Substrate**: `runt` nteract MCP server, driven live via `mcp__runt__*` tools (agent-in-flow; no `.ipynb` round-trip)
- **Dev/test**: pytest, pytest-asyncio, pytest-cov, mypy, pre-commit
- **Storage**: in-kernel Python objects (session state); on-disk only where an adapter requires it or for run snapshots. No database.
<!-- END SPECIFY: ACTIVE_TECHNOLOGIES -->

## Project Structure

```text
src/agentbook/
├── loop.py              # run_iteration driver — written once, identical per optimizer
├── contract.py          # the Optimizer Protocol + Trace/Reflection types
├── session.py           # warm state, frontier, eval-set pin/hash, kernel_pid
├── budget.py            # Budget + BudgetedClient (call/spend cap, BudgetExhausted)
├── adapters/
│   ├── gepa_adapter.py       # GEPA → Optimizer; kernel-resident state
│   └── skillopt_adapter.py   # SkillOpt → Optimizer; on-disk state
└── notebook_fix.py      # post-edit hygiene (repair_notebook + agentbook-fix CLI)

notebooks/               # MCP-driven demos (gepa_demo, skillopt_demo)
docs/graduation.md       # thresholds for leaving the kernel (FR-011)
tests/                   # smoke + budget + contract + loop
```

## Commands

```bash
make setup          # create/update the dev conda env from environment-dev.yml
make test           # pytest
make test-coverage  # pytest + coverage report
make lint           # ruff check (no changes)
make ruff-fix       # ruff --fix then format
make mypy           # static type checks
make pre-commit-all # run all pre-commit hooks
agentbook-fix path/to/nb.ipynb   # repair an LLM-edited notebook (ruff lint + format)
```

## Code Style

- **Python**: ruff lint rules E, W, F, I, B, C4, UP; line length 120; double-quote strings; space indent. mypy clean (`--ignore-missing-imports`).
- No bare `except: pass` — intentional swallows need a one-line reason comment.
- Delete orphaned imports/locals/globals in the same edit.
- `*.ipynb` cells exempt from E402 (imports legitimately interleave with setup).

## Constitutional Invariants (gate-enforced)

- **Real data only**: every deliverable notebook cell reads a real source; ends with a Data sources section. No fabricated rows/scores.
- **Inner loop never self-rewrites** the notebook or the agentbook codebase; agentbook edits are outer-loop, between sessions.
- **One declared harness slice per run**.
- **Substrate-first**: don't wrap notebooks in headless batch executors; port the hot path out when graduation thresholds hit.

## Recent Changes

<!-- BEGIN SPECIFY: RECENT_CHANGES -->
- **agentbook_thesis** (2026-05-28): Added the loop substrate (Optimizer Protocol + run_iteration driver), BudgetedClient guard, GEPA + SkillOpt adapters, MCP-driven demo notebooks, and the graduation-criteria doc.
<!-- END SPECIFY: RECENT_CHANGES -->

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

# Tasks: agentbook — notebook for a self-evolving agent harness

**Input**: Design documents from `specs/agentbook_thesis/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/loop-contract.md, quickstart.md

**Organization**: Tasks are grouped by user story so each can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared state or ordering dependency)
- **[Story]**: Which user story this task serves (US1–US4); omitted for setup/foundational/polish
- Every task names its exact file path

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 [P] Declare `gepa` and `SkillOpt` as optimizer extras and note kernel-side install via `manage_dependencies` in `pyproject.toml`
- [X] T002 [P] Create the adapters package scaffold in `src/agentbook/adapters/__init__.py`
- [X] T003 [P] Create `notebooks/` and `docs/` directories with a one-line README each describing their role
- [X] T004 [P] **Spike (gates US3)**: verify SkillOpt's public API maps to the `Optimizer` Protocol (rollout/evaluate/reflect/edit/gate); if it doesn't fit cleanly, record the adapter shim or a swapped second optimizer in `specs/agentbook_thesis/research.md` (closes analyze A-004)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user-story work begins until this phase is complete — every story depends on the loop contract, session, budget, and driver.

- [X] T010 [P] Define the `Optimizer` Protocol (`rollout`/`evaluate`/`reflect`/`edit`/`gate`) plus `Trace` and `Reflection` types in `src/agentbook/contract.py`
- [X] T011 [P] Implement `Budget` + `BudgetedClient` (call/spend counter at the single chokepoint, raises `BudgetExhausted` at the cap) in `src/agentbook/budget.py`
- [X] T012 Implement `Session` (warm eval_set/model_client/candidates/frontier, eval-set content-hash pin, stable `kernel_pid`, `select_parent`, `record`, `best_candidate`) in `src/agentbook/session.py`
- [X] T013 Implement the written-once `run_iteration` driver wiring the four arrows + gate, identical for every optimizer, in `src/agentbook/loop.py`
- [X] T014 [P] Unit test: `BudgetedClient` counts calls and raises `BudgetExhausted` exactly at the cap in `tests/test_budget.py`

**Checkpoint**: Substrate ready — adapters can be wired to the loop contract.

---

## Phase 3: User Story 1 — Run the full loop in one live kernel (Priority: P1) 🎯 MVP

**Goal**: Run ≥10 rollout→evaluate→reflect→edit iterations of the GEPA system-prompt optimizer in one warm kernel with no process restart.
**Independent Test**: Fresh session loads eval set + seed + client once, runs ≥10 iterations; kernel PID is stable and each resource loaded exactly once (SC-001).

- [X] T020 [P] [US1] Implement `GepaOptimizer` (kernel-resident state) satisfying the `Optimizer` Protocol in `src/agentbook/adapters/gepa_adapter.py`
- [X] T021 [US1] Build the MCP-driven system-prompt evolution demo (load eval set/client/seed once via `execute_cell`, run ≥10 iterations, render the frontier inline, end with a **Data sources** section citing real eval data) in `notebooks/gepa_demo.ipynb`
- [X] T022 [US1] Tests covering stable `kernel_pid` across iterations, eval_set/model_client loaded exactly once (SC-001), and a failed `evaluate()` trace exposed as a queryable in-memory object (FR-004) in `tests/test_loop.py`

**Checkpoint**: US1 fully functional — one optimizer runs end-to-end in a live kernel.

---

## Phase 4: User Story 2 — Outer-loop driver decides next experiment from live state (Priority: P1)

**Goal**: After each iteration the host reads the live outcome (best score, frontier, latest diff) and changes one experiment knob without restarting the kernel; budget exhaustion halts cleanly with a partial result.
**Independent Test**: Two consecutive iterations where the host changes one knob between them based solely on the prior in-kernel result, with no kernel restart.

- [X] T030 [US2] Add host-facing outcome accessors (best score, frontier snapshot, latest candidate diff) on `Session` in `src/agentbook/session.py`
- [X] T031 [US2] Make `run_iteration` catch `BudgetExhausted`, return the best-so-far candidate, and mark the run partial in `src/agentbook/loop.py`
- [X] T032 [P] [US2] Test: budget exhaustion mid-`reflect` halts the loop cleanly with a partial result, never overrunning (FR-007, SC-006) in `tests/test_budget.py`
- [X] T033 [US2] Add a demo cell showing the host changing one experiment knob (e.g. temperature or candidate-pool size) between iterations with no kernel restart in `notebooks/gepa_demo.ipynb`

**Checkpoint**: US1 + US2 both work — the outer loop steers the inner loop from live state.

---

## Phase 5: User Story 3 — One substrate, two independent harness slices (Priority: P2)

**Goal**: A second optimizer (SkillOpt, skill-document slice, on-disk state) runs through the same loop contract with no optimizer-specific driver code.
**Independent Test**: Both adapters complete a full run using the same substrate operations; the loop contract is identical at the substrate level (SC-003).

- [X] T040 [P] [US3] Implement `SkillOptOptimizer` (on-disk batch state) satisfying the `Optimizer` Protocol in `src/agentbook/adapters/skillopt_adapter.py`
- [X] T041 [US3] Build the MCP-driven skill-document evolution demo using the same substrate ops as the GEPA demo, ending with a **Data sources** section, in `notebooks/skillopt_demo.ipynb`
- [X] T042 [P] [US3] Test: both `GepaOptimizer` and `SkillOptOptimizer` satisfy `Optimizer` and run through the unchanged `run_iteration` driver (SC-003) in `tests/test_contract.py`
- [X] T043 [US3] Test the loop invariants: no `Optimizer` method writes to the notebook or `src/agentbook` (C-6/C-7, FR-008), and `edit()` operates on the same in-memory objects produced by `evaluate()` rather than re-parsing a file (C-5, FR-006) in `tests/test_contract.py` (closes analyze A-002, A-003)

**Checkpoint**: US1–US3 work — the substrate generalizes across harness slice and state shape.

---

## Phase 6: User Story 4 — Documented graduation criteria (Priority: P3)

**Goal**: Document the measurable thresholds at which the hot path leaves the kernel for a compiled service instead of being batch-wrapped.
**Independent Test**: The doc names ≥3 measurable thresholds (memory fan-out, latency floor, concurrency) as porting triggers (SC-005).

- [X] T050 [US4] Write the graduation-criteria doc naming ≥3 measurable thresholds (memory, latency, concurrency) and directing to a compiled-service port (not batch-wrapping) in `docs/graduation.md`

**Checkpoint**: All four stories complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T060 [P] Confirm both demo notebooks carry a **Data sources** section citing real sources (no fabricated rows/scores — Constitution I) in `notebooks/gepa_demo.ipynb` and `notebooks/skillopt_demo.ipynb`
- [X] T061 [P] Run `agentbook-fix` over both saved demo notebooks (post-edit hygiene) and commit the normalized output
- [X] T062 Validate `quickstart.md` end-to-end against real LLM credentials from a fresh kernel; confirm one optimizer run is reproducible (SC-004) — quickstart API drift fixed; **live GEPA-on-Bedrock run in the runt kernel validated SC-004** (run #1 evolved a real candidate, scores recorded, best selected, reproducible via `notebooks/utils/demo.py`). Surfaced an SC-006 engine-mode budget gap (recorded in `research.md`)
- [X] T063 Run the full gate — `make lint`, `make mypy`, `make test` — and fix any findings (green under conda `./env`: ruff+mypy clean, 17 tests; also fixed `make setup` channel/extra drift)
- [X] T064 Measure the warm-kernel host→next-experiment latency over `execute_cell` and assert it stays under 1s (SC-002) in `notebooks/gepa_demo.ipynb` (closes analyze A-001) — **measured live: 0.012 ms ≪ 1s** across two real GEPA runs in one warm kernel (PID stable)
- [X] T065 [P] Record edge-case handling decisions — kernel-crash recovery, reflection-call rate-limit policy (retry/skip/surface), mid-run inner-LLM swap — or explicitly defer them post-MVP, in `specs/agentbook_thesis/research.md` (closes analyze A-005)

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**. Within the phase: T010 + T011 are parallel; T012 needs T010+T011; T013 needs T010+T012; T014 needs T011.
- **US1 (Phase 3)**: Depends on Foundational. T020 ∥, then T021 (needs T020+T013), then T022.
- **US2 (Phase 4)**: Depends on Foundational; T033 builds on the US1 demo. T030/T031 touch session/loop; T032 ∥.
- **US3 (Phase 5)**: Depends on Foundational and on the **T004 SkillOpt spike** passing (functionally independent of US1/US2). T040 ∥, then T041, then T042 ∥ and T043.
- **US4 (Phase 6)**: Independent doc task; can start any time after the plan.
- **Polish (Phase 7)**: Depends on all desired stories being complete. T064 needs the US1 demo (T021); T065 ∥.

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Setup (T001–T003) + Foundational (T010–T014).
2. Complete US1 (T020–T022).
3. **STOP and VALIDATE**: run ≥10 GEPA iterations in one kernel; confirm stable PID and load-once (SC-001).
4. Demo if ready.

### Incremental Delivery

Add stories one at a time — US1 → US2 → US3 → US4 — each independently testable. US3 and US4 may proceed in parallel with US2 since they share no files.

### Note on SC-007 (not a build task)

SC-007 (the outer loop produces ≥1 merged agentbook edit justified by a recorded inner-loop result) is an **outer-loop process outcome over an evaluation window**, not a buildable unit. It is tracked in a session worklog, not in `tasks.md` (analyze A-006).

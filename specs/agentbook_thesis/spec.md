# Feature Specification: agentbook — notebook for a self-evolving agent harness

**Feature Branch**: `agentbook_thesis`
**Created**: 2026-05-28
**Status**: Draft
**Input**: User description: "agentbook — notebook for self-evolving agent harness; evaluation + improvement in one loop, driven live over nteract MCP. Evaluation and improvement are one loop: eval without improvement has no value, improvement without eval has no measurement. The agent harness (system prompt, scaffolding code, tool wiring, model config, on-demand skill documents, and agentbook itself) is the thing under evolution. One notebook hosts the eval set, the trace history, and the best-so-far artifact, and the same notebook hosts the agent doing the next improvement. The loop is rollout → evaluate → reflect → edit, each arrow happening without a process restart, in the same memory. Two timescales: an inner loop (in-cell thin LLM editing one declared harness slice inside a live kernel) and an outer loop (Claude Code, heavy intelligence, editing the experiment and agentbook itself between sessions). Two reference instances: GEPA (evolves the system-prompt slice, kernel-resident state) and SkillOpt (evolves the skill-document slice, on-disk state). Substrate: nteract's MCP (runt), driven live — agent fires execute_cell, the cell runs in a live kernel, output returns in the same tool response. When the workload outgrows interactive iteration, port the hot path to a compiled service rather than wrapping notebooks in headless batch executors."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Run the full loop in one live kernel, no restart (Priority: P1)

An agent engineer wants to improve one slice of an agent harness with a reflective optimizer. They open a single session, load the eval set, the model client, and the starting artifact once, then run rollout → evaluate → reflect → edit repeatedly inside that one session. The process is never restarted between iterations; each arrow operates on objects the previous arrow left in memory.

**Why this priority**: This is the whole thesis. If the loop pays a cold-start tax every iteration, or if reflect/edit live in a separate codebase from rollout/evaluate, the notebook supplies no coupling and the project has no reason to exist.

**Independent Test**: Open a fresh session, load eval set + starting artifact + model client, run ≥10 iterations of one optimizer, and confirm the kernel process never restarted and that the eval set, model client, and best-so-far artifact were each loaded exactly once.

**Acceptance Scenarios**:

1. **Given** a fresh session with eval set, model client, and starting artifact loaded, **When** the host runs N iterations of the loop, **Then** the eval set and model client are loaded once and reused across all N iterations and the kernel process ID is stable.
2. **Given** a candidate that failed evaluation in iteration k, **When** the host inspects that failed trace in iteration k+1, **Then** the trace is available as an in-memory, queryable object — not a file on disk to re-parse with a separate script.
3. **Given** an iteration completes, **When** the host requests the current score frontier or a candidate diff, **Then** the artifact renders inline in the session response, with no separate dashboard stood up.
4. **Given** the reflect step proposes an edit, **When** the edit is applied, **Then** it is expressed in the same language and against the same in-memory objects (eval set, traces, model client) as the evaluate step — one vocabulary, one cell-by-cell flow, not a hand-off between two codebases.

---

### User Story 2 — Outer-loop driver decides the next experiment from live state (Priority: P1)

A host agent (heavy intelligence) sits outside the inner loop. After each iteration it reads the inner loop's outcome from the live session — best score, frontier, latest diff — and decides what to change next: a different candidate population, a different optimizer config, a different eval slice, or a different optimizer library. Across sessions, the host also edits agentbook itself (library code, skill documents, optimizer wiring), because agentbook is part of the harness it is improving.

**Why this priority**: Without the outer loop, the substrate is a fancy script and "two intelligences at two timescales" collapses to one. The outer loop is also what makes the harness *genuinely* self-evolving: it edits parts of the harness — including agentbook — that the inner loop is forbidden to touch.

**Independent Test**: Run two consecutive inner-loop iterations where the host changes exactly one experiment knob (temperature, candidate-pool size, eval subset) between them, the change justified strictly by the previous iteration's in-kernel result, and confirm the change took effect without restarting the kernel.

**Acceptance Scenarios**:

1. **Given** iteration k has completed and reported a score, **When** the host reads that score and the latest trace from the live session, **Then** it can issue the next experiment's setup in the same session with no process restart.
2. **Given** the inner loop is mid-run, **When** the host's declared LLM-call budget is exhausted, **Then** the inner loop halts cleanly with a partial result rather than silently continuing past the budget.
3. **Given** a session has completed, **When** the host edits agentbook itself (library code, skill document, or optimizer wiring) based on the session's recorded outcome, **Then** the edit happens between sessions — never inside a live inner-loop kernel.

---

### User Story 3 — One substrate, two independent harness slices (Priority: P2)

The substrate hosts one optimizer that evolves the system-prompt slice (reference: GEPA) and one that evolves the skill-document slice (reference: SkillOpt), under the same rollout → evaluate → reflect → edit contract. The two also differ in where optimizer state lives — one kernel-resident (Python objects, in-memory frontier), one on-disk (batch-trainer style) — so the substrate must host both state shapes without bespoke harness code per optimizer.

**Why this priority**: One instance proves the substrate exists; two prove it generalizes — across both harness slice *and* state shape. This is the load-bearing claim that makes agentbook a substrate rather than a one-off integration.

**Independent Test**: Run one full optimization with the system-prompt optimizer and one with the skill-document optimizer using the same substrate operations (cell create / execute / read), and confirm the loop contract — candidate, evaluation, reflection, edit, gate — is identical at the substrate level.

**Acceptance Scenarios**:

1. **Given** the substrate's loop contract, **When** a system-prompt optimizer is loaded into a session, **Then** the four loop arrows are wired with no optimizer-specific harness.
2. **Given** the same substrate, **When** a skill-document optimizer is loaded, **Then** the four arrows are wired the same way; the only differences are where state lives and which harness slice is mutated.

---

### User Story 4 — Documented graduation criteria for leaving the kernel (Priority: P3)

When the workload outgrows interactive iteration — memory fan-out across many candidates, sub-100ms per-call latency, multi-tenant serving — the project does not wrap notebooks in headless batch executors. The documented path is to port the hot path to a compiled service and let the notebook stay a notebook.

**Why this priority**: Long-term hygiene, not blocking for the first runs. But the rule must exist before someone reflexively batch-wraps the moment the kernel starts hurting.

**Independent Test**: Open the project documentation and confirm at least three named, measurable thresholds (memory, latency, concurrency) are documented as triggers for porting out of the kernel.

**Acceptance Scenarios**:

1. **Given** a contributor proposes wrapping the substrate in a headless batch executor, **When** they consult the documented criteria, **Then** the criteria name specific thresholds and direct them to a compiled-service port instead.

---

### Edge Cases

- The kernel crashes mid-iteration — what state is recoverable, and from where?
- The host's LLM-call budget is exhausted mid-rollout — does the run halt with a partial result, or abort entirely?
- A cell redefines the eval set mid-run — does the substrate freeze/detect the eval set, or accept silent drift that invalidates cross-iteration scores?
- Two host agents drive the same session concurrently — allowed, blocked, or undefined?
- An LLM provider rate-limits a reflection call — is the iteration retried, skipped, or surfaced to the host?
- An optimizer wants to swap its own inner LLM mid-run — substrate concern, or strictly optimizer-internal?
- The outer loop's edits to agentbook land while a session is still running — is the in-flight session pinned to the version it started with, or does it pick up the change?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The substrate MUST host the full rollout → evaluate → reflect → edit cycle inside a single live kernel session, with no process restart between phases.
- **FR-002**: The host agent MUST be able to create cells, execute cells, and read cell results in the live session through the substrate's tool surface, with each operation returning its result in the same response — no file round-trip or separate harvest step required.
- **FR-003**: The eval set, model client, and best-so-far artifact MUST remain resident in kernel memory across iterations once loaded, so each is loaded exactly once per session.
- **FR-004**: When a candidate fails evaluation, its trace MUST be exposed as an in-memory, queryable structure within the same session, reachable by the next step without re-parsing a file.
- **FR-005**: Evolution artifacts (candidate diffs, score frontiers, plots) MUST render inline in the session so the human in the loop can review them without a separate dashboard.
- **FR-006**: The reflect and edit steps MUST operate in the same language and against the same in-memory objects as the evaluate step, so a mutation is one continuous cell-by-cell flow rather than a hand-off between two codebases.
- **FR-007**: Inner-loop LLM calls MUST be bounded by an explicit budget set by the host; reaching the budget MUST halt the inner loop cleanly with a partial result, never silently exceeding it.
- **FR-008**: The inner loop MUST mutate only the single declared harness slice under evolution (e.g., a system prompt, a skill document, a scaffolding routine, a tool config). The notebook and the agentbook codebase MUST NOT be self-rewriting within an inner-loop iteration.
- **FR-009**: After each iteration the host MUST be able to read the iteration's outcome (best score, frontier, latest diff) from the live session and use it to decide the next experiment; edits to agentbook itself MUST happen between sessions, justified by a recorded inner-loop result.
- **FR-010**: The substrate MUST support at least two independent optimizer libraries under the same loop contract, each targeting a different harness slice (reference slices: system prompt, skill document), and MUST accommodate both kernel-resident and on-disk optimizer state without bespoke harness code per optimizer.
- **FR-011**: The project MUST document the measurable conditions (memory fan-out, latency floor, concurrency level) under which the hot path is to be ported out of the kernel to a compiled service rather than wrapped in batch executors.

### Key Entities *(include if feature involves data)*

- **Agent Harness**: the full scaffolding around an LLM call — system prompt, loop/control flow, tool definitions, context-management policy, hooks, model config, on-demand skill documents, and the agentbook codebase itself when the agent is using agentbook to improve its harness. The harness is the **target of evolution**; everything else serves evolving it.
- **Harness Slice**: a single declared piece of the harness under evolution in one run — system prompt (GEPA), skill document (SkillOpt), scaffolding routine, or tool config. An optimizer may mutate exactly one slice per run.
- **Candidate**: a version of the harness slice under evolution, with attached scores from one or more rollouts.
- **Trace**: the inputs, outputs, and intermediate signals captured from one rollout of one candidate over the eval set.
- **Eval Set**: the examples or scenarios against which candidates are scored.
- **Reflection / Patch**: an LLM-proposed edit to a candidate, informed by recent traces.
- **Frontier**: the set of currently non-dominated candidates under the optimizer's scoring (e.g., a Pareto frontier).
- **Iteration**: one full rollout → evaluate → reflect → edit cycle (inner loop).
- **Session**: one live kernel holding state — eval set, model client, candidate population, frontier — across iterations.
- **Host**: the outer-loop agent (heavy intelligence) that drives the session, inspects outcomes, picks the next experiment, and edits agentbook between sessions.
- **Inner LLM**: the LLM running inside the optimizer (reflection / analyst) — thin intelligence, bounded by the host's budget.

## Assumptions *(mandatory)*

- **A-001**: The notebook substrate exposes its operations (create / execute / read cells, save, dependency management) as tool calls reachable by the host agent, one connection per session.
- **A-002**: The host agent has authority to choose which optimizer library is loaded into a session and to set the inner loop's LLM-call budget.
- **A-003**: LLM API credentials and per-run spend caps are provisioned in the kernel environment before the session starts.
- **A-004**: The optimizer libraries adhere to a candidate / patch / gate contract expressible as rollout → evaluate → reflect → edit. Optimizers that do not fit this framing are out of scope.
- **A-005**: "Agent harness" is a broad umbrella covering system prompts, scaffolding code, tool wiring, model config, skill documents, and the agentbook codebase itself. Each run mutates exactly one declared slice. Genuine self-evolution comes from the outer loop editing agentbook (a piece of its own harness) between sessions — not from any in-kernel self-rewrite during an iteration.
- **A-006**: Explicitly out of scope: multi-tenant serving of the optimizer, headless batch execution of saved notebook files, and inner-loop self-mutation of the notebook or the agentbook codebase. FR-011 governs when to leave the kernel substrate behind.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An engineer can run at least 10 inner-loop iterations of one optimizer in a single kernel session with zero process restarts (kernel PID stable across all iterations).
- **SC-002**: The latency between "inner loop reports a candidate score" and "host issues the next experiment in the same session" is under 1 second on a warm kernel — dominated by tool-call transit, not file I/O or cold start.
- **SC-003**: Two independent optimizer libraries — each targeting a different harness slice and differing in state shape (kernel-resident vs. on-disk) — each complete a full optimization run on the substrate using the same set of substrate operations, with no optimizer-specific harness code.
- **SC-004**: For at least one optimizer, a complete reflective run (≥1 evolved generation, scores recorded, best candidate selected) is reproducible end-to-end from a fresh kernel using only substrate tool calls.
- **SC-005**: The graduation-criteria document names at least three measurable thresholds (memory, latency, concurrency) that would trigger porting the hot path out of the kernel.
- **SC-006**: For every run, total inner-loop LLM spend stays within the host-declared budget; over-budget runs halt cleanly with a partial result rather than silently exceeding it.
- **SC-007**: Within a documented evaluation window, the outer loop produces at least one merged edit to agentbook itself (library code, skill document, or optimizer wiring) justified by a recorded inner-loop result — demonstrating the harness genuinely self-evolves rather than merely hosting an optimizer.

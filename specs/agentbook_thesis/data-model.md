# Data Model: agentbook — notebook for a self-evolving agent harness

**Date**: 2026-05-28
**Feature**: agentbook_thesis

These entities live primarily as **in-kernel Python objects** within a live session
(FR-003). Some optimizers (SkillOpt) additionally persist a subset to disk; the substrate
treats persistence as adapter-owned (research Decision 3). Field types below are the
substrate's view of each entity — the minimal shape the loop contract depends on.

## Entity: HarnessSlice

The single declared piece of the harness under evolution in one run (FR-008, Constitution II.2).

| Field | Type | Constraints |
|-------|------|-------------|
| `slice_kind` | enum: `system_prompt` \| `skill_document` \| `scaffolding` \| `tool_config` | Required; declared at setup, immutable for the run |
| `artifact` | str (the editable text) \| structured config | Required; this is what the inner loop mutates |
| `target_id` | str | Identifies which harness component this slice maps to |

**Invariant**: exactly one `HarnessSlice` is mutable per run. The notebook and the
agentbook codebase are never a `HarnessSlice` of an inner-loop run (Constitution II.1).

## Entity: Candidate

A version of the harness slice, with attached scores (spec Key Entities).

| Field | Type | Constraints |
|-------|------|-------------|
| `candidate_id` | int / str | Unique within a session |
| `artifact` | same type as `HarnessSlice.artifact` | Required |
| `scores` | dict[eval_id → float] | Populated by `evaluate`; empty until evaluated |
| `parent_id` | int / str \| None | The candidate this was reflected from (None for the seed) |

**Relationship**: N Candidates : 1 HarnessSlice (all candidates are versions of the same slice).
**Real reference**: `_gepa_run_07/candidates.json` is exactly a list of `Candidate.artifact`
values (evolved system prompts).

## Entity: EvalSet

The examples/scenarios candidates are scored against (FR-003).

| Field | Type | Constraints |
|-------|------|-------------|
| `examples` | list[Example] | Required; loaded once per session |
| `content_hash` | str | Recorded at setup; checked before each evaluate (research Decision 5) |
| `frozen_at` | session timestamp | Pin marker; re-pinning is an explicit host action |

**Invariant**: loaded exactly once per session; a hash change between iterations raises a
loud warning, never silent drift (Constitution VI).

## Entity: Trace

Inputs, outputs, and intermediate signals from one rollout of one candidate over the eval set.

| Field | Type | Constraints |
|-------|------|-------------|
| `candidate_id` | int / str | FK → Candidate |
| `eval_id` | str | FK → EvalSet example |
| `inputs` | structured | The example fed to the rollout |
| `output` | structured | What the candidate produced |
| `score` | float | The evaluate step's verdict for this (candidate, example) |
| `signals` | dict | Intermediate signals the reflect step reads |

**Invariant**: a Trace MUST be a queryable in-memory object within the session — not a
file to re-parse (FR-004). N Traces : 1 Candidate.

## Entity: Reflection / Patch

An LLM-proposed edit to a candidate, informed by recent traces (spec Key Entities).

| Field | Type | Constraints |
|-------|------|-------------|
| `from_candidate_id` | int / str | FK → Candidate |
| `proposed_artifact` | same type as artifact | The edited slice |
| `rationale` | str | Why the inner LLM proposed this |
| `llm_calls` | int | Counts against the Budget |

**Relationship**: a Reflection produces a new Candidate (`parent_id = from_candidate_id`).

## Entity: Frontier

The set of currently non-dominated candidates under the optimizer's scoring (spec Key Entities).

| Field | Type | Constraints |
|-------|------|-------------|
| `members` | list[candidate_id] | Non-dominated set (e.g., Pareto for GEPA) |
| `objective_keys` | list[str] | What dimensions dominance is computed over |

**Relationship**: subset of all Candidates; recomputed after each evaluate step.

## Entity: Budget

The host-declared bound on inner-loop LLM calls/spend (FR-007, SC-006).

| Field | Type | Constraints |
|-------|------|-------------|
| `max_calls` | int | Required; the hard cap |
| `max_spend` | float \| None | Optional spend cap where the provider exposes cost |
| `calls_used` | int | Monotonic; incremented at the client chokepoint |
| `state` | enum: `active` \| `exhausted` | `exhausted` halts the inner loop with a partial result |

**Invariant**: reaching the cap raises `BudgetExhausted`; the run halts cleanly with the
best-so-far Candidate. Never silently exceeded.

## Entity: Iteration

One full rollout → evaluate → reflect → edit cycle (spec Key Entities).

| Field | Type | Constraints |
|-------|------|-------------|
| `index` | int | Monotonic within a session |
| `selected_candidate_id` | int / str | The candidate this iteration evolved from |
| `new_candidate_id` | int / str \| None | Produced candidate (None if the iteration was rejected by the gate) |
| `subsample_ids` | list[str] | Which eval examples this iteration scored against |
| `scores` | list[float] | Per-example scores |

**Real reference**: `_gepa_run_07/run_log.json` is a list of exactly these Iteration records.

## Entity: Session

One live kernel holding state across iterations (spec Key Entities).

| Field | Type | Constraints |
|-------|------|-------------|
| `kernel_pid` | int | MUST be stable across all iterations (SC-001) |
| `eval_set` | EvalSet | Loaded once |
| `model_client` | BudgetedClient | Loaded once; warm across iterations |
| `candidates` | list[Candidate] | Grows as the loop runs |
| `frontier` | Frontier | Current non-dominated set |
| `budget` | Budget | The active bound |
| `slice` | HarnessSlice | The one slice under evolution this run |

**Invariant**: the inner loop never mutates `Session` config (eval_set identity, slice
kind, budget) — those are host-set at setup and changed only between sessions (Constitution II).

## Relationship Summary

```
Session 1──1 EvalSet 1──N Example
Session 1──1 HarnessSlice 1──N Candidate
Candidate 1──N Trace N──1 Example
Candidate 1──N Reflection ──produces──► Candidate (parent_id)
Session 1──1 Frontier ⊆ Candidates
Session 1──1 Budget ──guards──► every inner LLM call
Session 1──N Iteration
```

## State location (per research Decision 3)

| Entity | GEPA (kernel-resident) | SkillOpt (on-disk batch) |
|--------|------------------------|--------------------------|
| Candidate | live Python objects | written to disk by the trainer |
| Trace | in-memory | in-memory during a batch, persisted between batches |
| Frontier | live Pareto set | recomputed from disk state |

The substrate's loop contract is identical in both; only the adapter's load/save differs.

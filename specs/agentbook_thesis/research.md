# Research: agentbook — notebook for a self-evolving agent harness

**Date**: 2026-05-28
**Feature**: agentbook_thesis

Phase 0 technology decisions. Each is assessed against the constitution
(`specs/constitution.md`) — especially Principle II (loop invariants),
Principle I (real data only), and the Execution Ladder / Simplicity philosophy.

## Decision 1: The live substrate

**Context**: The loop's four arrows (rollout → evaluate → reflect → edit) must run
without a process restart, in shared memory, with the host agent driving cells and
reading results in the same tool response (FR-001, FR-002).

**Decision**: nteract's `runt` MCP server, driven live via `mcp__runt__*` tools.

| Option | Pros | Cons | Constitution Fit |
|--------|------|------|-----------------|
| **runt MCP, driven live** | Agent-in-flow: `execute_cell` returns output in the same response; one warm kernel across iterations; inline rich outputs | Requires the runt MCP server registered in-session; one connection per session | ✅ Matches FR-001/002/005; honors Simplicity (no harvest layer) |
| Headless papermill / nbclient | Reproducible batch runs | Cold-start per run; `.ipynb` round-trip + harvest step; no live introspection | ❌ Violates FR-001 (restart tax) and the substrate-first invariant (II.3) |
| Raw `jupyter_client` | Full control of the kernel protocol | Reimplements what runt already exposes as tools; more scaffolding | ❌ Against Simplicity / Generalizability |

**Rationale**: The thesis *is* coupling without restart. Only the live-MCP option
delivers it; the other two reintroduce the cold-start tax the project exists to remove.
**Rejected alternatives**: papermill/nbclient are explicitly the anti-pattern named in
FR-011 — they belong *after* graduation, not as the substrate.

## Decision 2: The loop contract (one substrate, two optimizers)

**Context**: GEPA and SkillOpt must wire into the same rollout → evaluate → reflect →
edit contract with no optimizer-specific harness code (FR-010, SC-003).

**Decision**: A minimal Python `Protocol` (the four arrows + a `gate`) plus one thin
adapter per optimizer. The substrate owns the contract; each adapter owns its library's
specifics and its state shape.

| Option | Pros | Cons | Constitution Fit |
|--------|------|------|-----------------|
| **Protocol + per-optimizer adapter** | Substrate code is identical across optimizers; adapters are small and obvious | Two adapter files to maintain | ✅ Generalizability + Simplicity; satisfies SC-003 |
| Shared base class with hooks | Less boilerplate | Inheritance couples optimizers to a framework; "framework gravity" | ❌ Tension with Simplicity / agent-autonomy |
| Bespoke harness per optimizer | Fastest to write the first one | Fails the load-bearing claim — substrate doesn't generalize | ❌ Directly violates FR-010 |

**Rationale**: A `Protocol` is structural typing — adapters satisfy it without importing
a base class, keeping each optimizer decoupled. Two adapters prove generalization
(SC-003) without a framework.
**Rejected alternatives**: inheritance and bespoke harnesses both fail the "no
optimizer-specific harness code" requirement or add gravity the project doesn't need.

## Decision 3: Optimizer state — kernel-resident vs. on-disk

**Context**: GEPA keeps state as live Python objects (in-memory frontier); SkillOpt is a
batch trainer with on-disk state. The substrate must host both without special-casing
(FR-010, SC-003).

**Decision**: The substrate is **state-agnostic**. The loop contract passes opaque
candidate/trace objects; each adapter persists (or doesn't) however its library wants.
The substrate never assumes where state lives.

| Option | Pros | Cons | Constitution Fit |
|--------|------|------|-----------------|
| **State-agnostic contract** | Both shapes fit unchanged; substrate stays minimal | Adapters must each declare their own load/save | ✅ Generalizability; proves the SC-003 claim |
| Substrate-owned state store | Uniform persistence | Forces GEPA's in-memory objects through a disk layer they don't need | ❌ Violates Simplicity; cold-start tax creeps back |

**Rationale**: The real `_gepa_run_07/` artifacts (kernel-resident objects serialized to
`gepa_state.bin` only at the end) and a SkillOpt on-disk trainer differ precisely in
state shape — the substrate must not care. State-agnosticism is what makes the two
instances prove generalization rather than coincidence.

*(Decision 4 removed — budget abstraction dropped for simplicity)*

## Decision 5: Eval-set integrity across iterations

**Context**: An edge case: a cell redefines the eval set mid-run, silently invalidating
cross-iteration score comparisons (spec Edge Cases; Principle VI).

**Decision**: Pin the eval set at session setup by recording a content hash; the loop
driver checks the hash before each evaluate step and **warns loudly** (not silently
drifts) if it changed. Freezing is advisory, not enforced — the host may intentionally
re-pin for a new experiment.

**Rationale**: Explicit-over-Implicit (VI) forbids silent drift; agent-autonomy forbids
hard-locking a knob the host legitimately owns. A loud warning + recorded hash satisfies
both — the drift is surfaced, the host decides.
**Rejected alternatives**: hard-freeze (blocks legitimate re-pinning); ignore (silent
drift, the exact failure the edge case names).

## Decision 6: Inline artifact rendering

**Context**: Diffs, score frontiers, and plots must render inline so the human reviews
them without a dashboard (FR-005, SC requirement for visible artifacts).

**Decision**: Return rich representations through `execute_cell` — matplotlib figures
(already a dependency) as inline images, candidate diffs as rendered text/HTML, frontiers
as DataFrame/plot. No separate web app.

**Rationale**: `matplotlib` and `numpy` are already first-class dependencies; the runt
MCP surface returns rich outputs in the tool response. This is the zero-new-dependency
path and directly satisfies "no separate dashboard."

## Addendum: T004 SkillOpt conformance spike (2026-05-28) — RESOLVED, PASS

`microsoft/SkillOpt` (public) was cloned to `~/Documents/GitHub/SkillOpt-src` and installed
editable (`skillopt==0.1.0`). The spike confirms it maps onto the contract:

| Contract arrow | SkillOpt surface |
|---|---|
| rollout | `skillopt.envs.searchqa.rollout.process_one(item, out_root, skill_content, max_turns)` |
| reflect | `skillopt.gradient` (the "gradient" step; orchestrated internally) |
| edit | `skillopt.optimizer.apply_edit / rewrite / clip / slow_update / meta_skill` |
| gate | `skillopt.evaluation.gate.evaluate_gate → GateResult/GateAction` |
| **engine** | `skillopt.engine.trainer.ReflACTTrainer(cfg, adapter).train()` |

**Findings that shape the adapter:**
- SkillOpt is **engine mode** (design A): `ReflACTTrainer.train()` is the sanctioned entry; the
  reflect/edit/gate components are submodules wired internally, not clean standalone functions,
  so a driver-mode wiring would be fragile. The adapter wraps `train()` and maps the on-disk run
  output onto Session entities — mirroring the GepaOptimizer pattern. State is **on-disk**
  (trajectory dir under `out_root`), satisfying the "two state shapes" half of SC-003.
- Backend: `claude_chat` shells out to the local `claude` CLI (present at `~/.local/bin/claude`),
  which inherits `AWS_BEARER_TOKEN_BEDROCK` → routes through Bedrock. No extra key needed.
- Data: `data/searchqa_id_split` ships in the clone; the default config expects `train_size=400,
  batch_size=40` — a live run requires tiny overrides (small train/limit) to be affordable, and
  each rollout is a claude-CLI subprocess (slow, ~minutes).

**Conclusion**: SkillOpt fits (A-004 risk retired). US3 is unblocked. The remaining cost is the
live engine run (claude-CLI rollouts), materially heavier than US1's in-process litellm calls.

## Addendum: T065 edge-case handling decisions (2026-05-28) — RESOLVED

The spec's Edge Cases list seven situations. Two are already resolved by the Phase-0
decisions above — eval-set drift (Decision 5: pin-and-warn). The remaining edge cases are decided here, each against the
constitution (Simplicity, Explicit-over-Implicit VI, agent-autonomy). The theme is the same:
the substrate stays minimal and **surfaces** the condition to the host rather than hiding it
behind a recovery/retry layer that would reintroduce the cold-start tax the project removes.

**1. Kernel crash mid-iteration — recovery point.**
Decision: the substrate adds **no checkpoint layer**. Recovery is "restart the kernel and reload
from the optimizer's own last on-disk artifact." A crash loses the in-flight iteration's
in-memory state (e.g. GEPA's live frontier since its last serialize); the optimizer re-runs that
iteration. GEPA serializes to `gepa_state.bin`; SkillOpt writes its trajectory dir continuously,
so its recovery point is the last completed rollout. Rationale: a substrate-owned checkpoint
store is exactly the disk layer Decision 3 rejected — it forces kernel-resident state through a
persistence path it doesn't need. Crash recovery is the optimizer's concern via its own artifact.
*Post-MVP option*: an optional periodic frontier snapshot, opt-in per adapter, if a long GEPA run
makes lost iterations expensive.

**2. Reflection call rate-limited by the provider — retry / skip / surface.**
Decision: **surface to the host.** The substrate does not add its own retry loop. A provider
rate-limit (or any reflection-call error) is caught by the loop driver and exposed as a failed
trace — the same queryable in-memory failure object as a failed `evaluate()` (FR-004) — and the
host decides retry vs. skip vs. re-pace. Rationale: Explicit-over-Implicit
(VI) — a hidden substrate retry would distort the trace history,
and silently skipping would drop a data point from cross-iteration comparison. Bounded
retry-with-backoff *inside* the optimizer library is fine and remains optimizer-internal; the
substrate just doesn't add a second, invisible one.

**3. Optimizer swaps its own inner LLM mid-run — substrate or optimizer concern.**
Decision: **strictly optimizer-internal.** The substrate passes an opaque model client; an
optimizer that wants to change its inner LLM does so within its own adapter state. This mirrors
the state-agnostic contract (Decision 3) — the substrate does not track or constrain what model an
optimizer runs internally.

**Two remaining edge cases — explicitly scoped, not engineered for MVP:**
- **Concurrent host agents on one session**: out of scope for MVP — the project is single-tenant
  interactive iteration (A-006). One driver per session; concurrent drivers are undefined and
  should be treated as unsupported. Multi-tenant serving is a graduation trigger, not a substrate
  feature (see `docs/graduation.md`).
- **Outer-loop edits to agentbook land while a session runs**: the in-flight session is **pinned to
  the code it imported at session start** — already-imported Python modules stay resident in the
  kernel; picking up an outer-loop edit requires a kernel restart / re-import. This is the natural
  behavior, documented rather than worked around: a running experiment is reproducible against the
  version it began with.

## Addendum: T062/T064 live e2e finding (2026-05-28)

A real GEPA run on Bedrock (haiku task / sonnet-4-6 reflection, AIME eval, `max_metric_calls=6`,
two runs in one warm kernel) validated the substrate claims: **SC-001** PID stable across both
runs; **SC-002** host→next-experiment latency **0.012 ms** (≪1s); **SC-004** run #1 evolved a
real candidate (genuine reflective prompt rewrite), scores recorded, best selected, reproducible
from a fresh kernel via `notebooks/utils/demo.py`.

## Addendum: Agentic rollout — driver-mode, `claude -p` (2026-05-28)

**Context**: US5 (`ClaudeAgentOptimizer`) is the first adapter to use `run_iteration`
in driver mode with a real (non-fake) optimizer. The rollout is a genuine multi-turn
tool-using agent rather than single-turn Q&A; the adapter shells out to
`claude -p --output-format stream-json --allowedTools Bash` and parses the resulting
NDJSON stream into a `Trace`.

**Decision: parse `--output-format stream-json` into Traces.**

| Option | Pros | Cons | Selected? |
|--------|------|------|-----------|
| `--output-format stream-json` + `parse_stream_json` | Full fidelity: `tool_use`/`tool_result` pairs, `num_turns`, cost, and tokens all present in the stream | Parser must handle NDJSON incrementally | ✅ Yes |
| `--output-format json` (final summary only) | Single JSON blob, simpler to parse | `tool_use`/`tool_result` pairs stripped; no per-turn detail; `num_turns` not directly available | ❌ Loses trajectory |
| Scrape plain text | Zero extra parsing | Tool calls not structured; reflect step gets text globs, not queryable call/result pairs | ❌ Too lossy |

**Rationale**: The `Trace.signals` field must carry the full tool-call trajectory so the
reflect step can target specific failing tool calls in the rewritten system prompt. The
stream-json format is the only CLI option that preserves `tool_use`/`tool_result` pairing,
turn count, and cost in one pass. Scraping text or using the final-summary JSON both lose
structure that the reflect step needs.

**Driver mode vs. engine mode**: GEPA and SkillOpt are engine-mode adapters — they own
their own loop and bypass `run_iteration`. `ClaudeAgentOptimizer` is the **first driver-mode
adapter backed by a real optimizer**: it exposes the four arrows individually and lets the
substrate's written-once `run_iteration` orchestrate them. This validates the driver-mode
path end-to-end (beyond the `FakeOptimizer` used in the Phase-2 tests).

**Cost trade-off**: Each rollout is a real `claude -p` Bedrock call. With the CLI's own
system prompt overhead, a single episode costs roughly $0.20. The eval set is therefore kept
intentionally tiny (tool-forcing tasks with deterministic gold answers such as `sha256("foo")`
and `17 * 23 = 391`) to keep a demo run affordable. Larger eval sets are possible but should
be budgeted explicitly before running.

## Summary

| Decision | Selected | Key Reason |
|----------|----------|-----------|
| Live substrate | runt MCP, driven live | Coupling-without-restart is the thesis; batch executors are the named anti-pattern |
| Loop contract | Protocol + per-optimizer adapter | Identical substrate code across optimizers proves generalization (SC-003) |
| Optimizer state | State-agnostic contract | Hosts kernel-resident (GEPA) and on-disk (SkillOpt) shapes unchanged |
| Eval-set integrity | Pin-and-warn on hash change | Surfaces drift (VI) without locking a host-owned knob (agent-autonomy) |
| Inline artifacts | Rich repr via execute_cell | Zero new dependencies; satisfies "no dashboard" |
| Agentic rollout transcript | `--output-format stream-json` + `parse_stream_json` | Only format that preserves tool-call pairs, turn count, and cost for the reflect step |

*(Decision 4 / Budget row removed — budget abstraction dropped for simplicity)*

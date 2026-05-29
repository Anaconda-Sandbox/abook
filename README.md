# agentbook — notebook for self-evolving agent harness
### evaluation + improvement in one loop, driven live over nteract MCP

> **Evaluation and improvement are one loop.**
> Eval without improvement has no value. Improvement without eval has no measurement.

## The thesis

The **agent harness** — system prompt, scaffolding code, tool wiring,
model config, the skill documents the agent loads on demand, **and
agentbook itself** — is the thing under evolution. A notebook hosts
the eval set, the trace history, and the best-so-far artifact, and
the same notebook hosts the agent doing the next improvement.

Because agentbook is part of the harness it improves, the harness
genuinely **self-evolves**. Not by the notebook rewriting itself
mid-iteration (it doesn't), but by the outer loop editing pieces of
the harness — including agentbook — between sessions, justified by
what the inner loop just measured.

## The loop

```
    rollout ──► evaluate ──► reflect ──► edit
                   ▲                       │
                   └───────────────────────┘
```

None of those operations is notebook-native by itself. What a
notebook supplies is **coupling**: each arrow above happens without a
process restart, in the same memory.

## What "agent harness" means here

Anything around the LLM call that the agent reads at runtime:

- the **system prompt**
- **scaffolding code** — the loop, context management, hooks
- **tool definitions** and wiring
- **model config** — temperature, sampling, budget caps
- **skill documents** the agent loads on demand
- **agentbook itself**, when the agent is using agentbook to improve its harness

Each optimization run mutates exactly **one declared slice**. Crossing
slices is an outer-loop decision, not an inner-loop privilege.

## Two timescales

| Loop | Who | What it edits | Where |
|---|---|---|---|
| **Inner** | the in-cell LLM (thin intelligence) | a single harness slice | inside a live kernel session |
| **Outer** | Claude Code (heavy intelligence) | the experiment, and agentbook itself | between sessions |

The inner loop never rewrites the notebook or the agentbook codebase.
The outer loop does — that's where the genuine self-evolution lives.

## Two real instances of the loop

Both target a different harness slice, both run the full cycle, both
fit the same substrate.

| Library | Harness slice it evolves | Optimizer state |
|---|---|---|
| [`gepa`](https://github.com/gepa-ai/gepa) — Genetic-Pareto reflective prompt optimization (ICLR 2026 Oral) | **system prompt** | kernel-resident (Python objects) |
| [`SkillOpt`](https://github.com/microsoft/SkillOpt) — natural-language skill document as trainable artifact (Microsoft Research) | **skill document** | on-disk (batch trainer) |

One instance proves the substrate exists; two prove it generalizes —
across both harness slice and state shape.

## Two intelligences cooperate

The notebook isn't dumb. Its cells call LLM APIs directly — GEPA's
`reflection_lm`, SkillOpt's analyst — bounded by the budget the host
sets. That's **thin intelligence**. Claude Code is **heavy
intelligence**: it drives the session, picks the next experiment, and
edits agentbook itself between runs.

| Layer | Role | Contributes |
|---|---|---|
| **Claude Code** | heavy intelligence (outer loop) | drives the session, picks the next experiment, calls `mcp__runt__*` tools, edits agentbook between sessions |
| **Notebook cells** | thin intelligence (inner loop) | reflection / analyst LLM inside the optimizer; bounded by `max_metric_calls` |
| **nteract MCP (`runt`)** | substrate | live kernel, persistent state, inline outputs, MCP tool surface |
| **GEPA / SkillOpt** | optimizer library | structures `rollout → evaluate → reflect → edit`; defines the candidate / patch / gate contract |

## Why each step wants a notebook

One ergonomic property per arrow.

1. **`rollout`** wants **persistent state**. Eval set already loaded,
   model client already warm, best-so-far candidate already in scope.
   A subprocess loop pays the cold-start tax every iteration; a
   kernel pays it once.

2. **`evaluate`** wants **coupled introspection**. When a candidate
   fails, the failed trace is a DataFrame slice away — not a JSON
   file to re-parse with another script. The next step reads the same
   object this step produced.

3. **`reflect`** wants **visible artifacts**. The thing under
   evolution — a prompt diff, an SVG, a Pareto frontier — renders
   inline. The human in the loop glances at it between rounds without
   standing up a dashboard.

4. **`edit`** wants **one vocabulary**. The mutation is written in
   the same Python as the evaluator, against the same DataFrames,
   calling the same model client. What's conventionally two codebases
   collapses into one cell-by-cell flow.

## The substrate — `nteract`'s MCP, driven live

The cleanest version of this loop is **agent-in-flow**. An agent
fires `execute_cell` over MCP; the cell runs in a live kernel; the
output comes back in the same tool response. No `.ipynb` round-trip,
no harvest step, no scraps file. Evaluate and edit become adjacent
tool calls, not adjacent subprocess invocations.

[`nteract/nteract`](https://github.com/nteract/nteract) provides the
substrate — desktop + kernel built on React, plus the `runt` MCP
server that exposes notebook operations as tool calls. The demo
notebooks here are built and driven against exactly that MCP, every
cell created and read through `mcp__runt__*` tools by an agent inside
Claude Code. The eval notebook isn't a file handed to a subprocess;
it's a kernel session the agent is *inside*.

### When the loop outgrows the kernel

If the workload hits real scale — memory fan-out across many
candidates, sub-100ms per-call latency, multi-tenant serving — don't
wrap notebooks in headless batch executors. Port the hot path to a
compiled service (Rust, Go) and let the notebook stay being a
notebook. Notebooks are for iteration; the moment they stop being
interactive, the substrate stops earning its keep.

## Status

Early. The thesis is staked; the substrate is named; the loop runs
on two real optimizers. What it becomes from here is what gets
evolved next — including agentbook itself.

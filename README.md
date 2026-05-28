# abook — a self-evolving notebook
### evaluation + improvement in one loop, driven live over nteract MCP

> **Evaluation and improvement are one loop.**
> Eval without improvement has no value. Improvement without eval has no measurement.

A notebook hosts the agent's eval set, trace history, and best-so-far
artifact — and the same notebook hosts the agent doing the next
improvement. *Self-evolving* doesn't mean the notebook edits itself; it
means the **thing it operates on** — prompt, skill document, code,
config — gets edited from what just got measured, in cells one tab
apart.

## The loop

```
    rollout ──► evaluate ──► reflect ──► edit
                   ▲                       │
                   └───────────────────────┘
```

None of those operations is notebook-native by itself. What a notebook
supplies is **coupling**: each arrow above happens without a process
restart, in the same memory.

## Two real instances of the loop

| Library | What gets evolved |
|---|---|
| [`gepa`](https://github.com/gepa-ai/gepa) — Genetic-Pareto reflective prompt optimization (ICLR 2026 Oral) | a system prompt |
| [`SkillOpt`](https://github.com/microsoft/SkillOpt) — natural-language skill document as trainable artifact (Microsoft Research) | a skill markdown |

Both are independent. Both run the full rollout–reflect–edit–gate
loop. GEPA is kernel-native by design (optimizer state in Python);
SkillOpt is batch-trainer-native (state on disk) but still earns its
keep from kernel-resident config composition and post-hoc trajectory
EDA.

## Layers — what does what

**Two intelligences cooperate, at different scales.** The notebook
isn't dumb — its cells call LLM APIs directly (GEPA's
`reflection_lm`, SkillOpt's analyst). That's **thin intelligence**,
bounded by the budget the host sets. Claude Code is **heavy
intelligence**: it drives the session itself, decides what to run
next, and may rewrite the optimizer between iterations.

| Layer | Role | What it contributes |
|---|---|---|
| **Claude Code** | heavy intelligence (host) | drives the session, decides which experiment to run, calls `mcp__runt__*` tools, inspects results between iterations |
| **Notebook cells** | thin intelligence (inner) | LLM calls *inside the optimizer* — GEPA's `reflection_lm`, SkillOpt's analyst LLM; bounded by `max_metric_calls` |
| **nteract MCP (`runt`)** | substrate | live kernel, persistent state, inline outputs, MCP tool surface |
| **GEPA / SkillOpt** | optimizer library | structures `rollout → evaluate → reflect → edit`; defines the candidate / patch / gate contract |

The 4-step loop above is the **inner loop**, run by thin intelligence
inside the notebook. The **outer loop** is Claude Code itself —
observing each inner-loop outcome and deciding what to change for the
next run. Both halves are eval-and-improve, just at different scales:
the inner mutates an artifact, the outer mutates the experiment.

## Why each step wants a notebook

One ergonomic property per arrow in the loop above.

1. **`rollout`** wants **persistent state**. Eval set already loaded,
   model client already warm, best-so-far artifact already in scope.
   A subprocess loop pays the cold-start tax every iteration; a kernel
   pays it once.

2. **`evaluate`** wants **coupled introspection**. When a candidate
   fails, the failed trace is a DataFrame slice away — not a JSON
   file to re-parse with another script. The next step reads the same
   object this step produced.

3. **`reflect`** wants **visible artifacts**. The thing under
   evolution — a prompt diff, an SVG, a Pareto frontier — renders
   inline. The human in the loop glances at it between rounds without
   standing up a dashboard.

4. **`edit`** wants **one vocabulary**. The mutation is written in the
   same Python as the evaluator, against the same DataFrames, calling
   the same model client. What's conventionally two codebases collapses
   into one cell-by-cell flow.

## The substrate — `nteract`'s MCP, driven live

The cleanest version of this loop is **agent-in-flow**. An agent
fires `execute_cell` over MCP; the cell runs in a live kernel; the
output comes back in the same tool response. No `.ipynb` round-trip,
no harvest step, no scraps file. Evaluate and edit become adjacent
tool calls, not adjacent subprocess invocations.

[`nteract/nteract`](https://github.com/nteract/nteract) provides the
substrate — desktop + kernel built on React, plus the `runt` MCP
server that exposes notebook operations as tool calls. The
work-in-progress demo notebooks here are built and driven against
exactly that MCP, every cell created and read through `mcp__runt__*`
tools by an agent inside Claude Code. The eval notebook isn't a file
handed to a subprocess; it's a kernel session the agent is *inside*.

### When the loop outgrows the kernel

If the loop hits real scale — memory-constrained fan-out, sub-100ms
latency, multi-tenant serving — don't wrap notebooks in headless
batch executors. Port the hot path to a compiled service (Rust, Go)
and let the notebook stay being a notebook. Notebooks are for
iteration; the moment they stop being interactive, the substrate
stops earning its keep.

## Status

Early. The thesis is staked; the substrate is named; the loop runs on
two real optimizers. What it becomes from here is what gets evolved
next.

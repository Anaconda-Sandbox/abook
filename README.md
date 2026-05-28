# abook — a self-evolving notebook: evaluation + improvement in one loop

> **Evaluation and improvement are one loop.**
> Eval without improvement has no value. Improvement without eval has no measurement.

A notebook hosts the state of an agent's behavior — its eval set, its
trace history, its best-so-far artifact — and that same notebook hosts
the agent doing the next improvement. The two halves of the loop live
in the same kernel namespace. That's what "self-evolving" means here:
not that the notebook edits itself, but that the *thing it operates
on* — prompt, skill document, code, agent architecture, config —
gets edited based on what just got measured, in cells one tab apart.

## The loop

```
    rollout ──► score ──► reflect ──► edit ──► re-evaluate
        ▲                                              │
        └──────────────────────────────────────────────┘
```

Four operations, none of them notebook-native by themselves. What a
notebook supplies is **coupling**: rollout outputs land in DataFrames
the reflect step slices; the edit step writes a new artifact the
re-evaluate step picks up without a process restart; convergence plots
update inline while the loop is alive.

## Two real instances of the loop

| Library | What gets evolved |
|---|---|
| [`gepa`](https://github.com/gepa-ai/gepa) — Genetic-Pareto reflective prompt optimization (ICLR 2026 Oral) | a system prompt |
| [`SkillOpt`](https://github.com/microsoft/SkillOpt) — natural-language skill document as trainable artifact (Microsoft Research) | a skill markdown |

Both libraries are independent. Both run their full
rollout–reflect–edit–gate loop. GEPA is kernel-native by design (the
optimizer object holds state in Python); SkillOpt is batch-trainer-
native (state lives on disk) but still benefits from kernel-resident
config composition and post-hoc trajectory EDA.

## Why the loop wants a notebook

1. **Persistent state.** The eval set loads once. The best-so-far
   artifact stays in scope. The reflection LM's API client stays
   warm. A subprocess loop pays this tax every iteration; a kernel
   loop pays it once.

2. **Coupled introspection.** When the optimizer fails to improve,
   the failed trace is a DataFrame slice away — not a JSON file to
   re-parse with another script. The improvement step reads the same
   object the eval step produced.

3. **Visible artifacts.** The thing under evolution — a prompt diff,
   an SVG, a Pareto frontier — renders inline. The human in the loop
   glances at the artifact between rounds without standing up a
   dashboard.

4. **One vocabulary.** Eval and improvement use the same Python, the
   same DataFrame library, the same model client. A notebook collapses
   what is conventionally two separate codebases into one cell-by-cell
   flow.

## The substrate — `nteract`'s MCP, driven live

The cleanest version of this loop is **agent-in-flow**. An agent fires
`execute_cell` over MCP, the cell runs in a live kernel, and the
cell's outputs come back in the *same* tool response — no `.ipynb`
round-trip, no separate "harvest" step, no scraps file to re-parse.
Eval and improvement become adjacent tool calls, not adjacent
subprocess invocations.

That's what [`nteract/nteract`](https://github.com/nteract/nteract)
gives you: a desktop + kernel substrate built around React and rich
programmatic execution, paired with an MCP server (`runt`) that
exposes notebook operations as tool calls. The demo notebooks in
this repo (still a work in progress) are being built and driven
against exactly that MCP — every cell created, executed, and re-read
through `mcp__runt__*` tools by an agent inside Claude Code. The eval
notebook isn't a file you hand to a subprocess; it's a kernel session
the agent is *inside*.

### When the loop outgrows the kernel

If the loop eventually hits real scale — memory-constrained fan-out,
sub-100ms per-run latency, multi-tenant serving — the honest move
isn't to keep wrapping notebooks in headless batch executors. It's to
port the hot path to a compiled service (Rust, Go) and let the
notebook stay being a notebook. Notebooks are for iteration; the
moment they stop being interactive, the substrate stops earning its
keep.

## Status

Early. The thesis is staked; the substrate is named; the loop runs on
two real optimizers. What it becomes from here is what gets evolved
next.

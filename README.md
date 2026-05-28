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

## The nteract substrate — three repos that make the loop tractable

The notebook half of the story is not one program. The
[`nteract`](https://github.com/nteract) organization ships a modular
suite of libraries built around React and programmatic execution.
Three of them, together, are how an eval ↔ improve loop is wired in
practice:

### 1. [`nteract/nteract`](https://github.com/nteract/nteract) — the core repo

A monolithic repository containing the nteract desktop application
(Electron + React) and a large collection of SDK packages. Unlike
JupyterLab — which runs in the browser via a Python server — nteract
provides a native desktop experience focused on UX, rich data
visualization, and dropping the complexity of managing hidden kernel
state. This is the substrate the *live* loop runs on when a human is
watching: the cell that just produced a score is one click away from
the cell that proposes the next mutation.

### 2. [`nteract/papermill`](https://github.com/nteract/papermill) — the automation engine

A tool for parameterizing and executing Jupyter notebooks
programmatically. **The most critical repo in the org for an
eval-improve loop.** Instead of an agent manually "typing" into a live
notebook cell, papermill treats the notebook like an API: pass a JSON
payload of the eval dataset in as parameters, papermill executes the
notebook headlessly in the background, and outputs a new notebook
containing the scores and trace logs. The loop becomes:
*propose mutation → papermill executes the eval notebook with the
mutation → harvest scores → reflect → propose next mutation.* The
notebook is both the experiment definition and the eval harness.

### 3. [`nteract/scrapbook`](https://github.com/nteract/scrapbook) — structured outputs

A library for recording and reading data ("scraps") from Jupyter
notebooks. When papermill finishes running an evaluation notebook,
the improvement step uses scrapbook to extract visual charts (e.g. a
matplotlib of token efficiency) or pandas DataFrames **without
parsing the raw `.ipynb` JSON by hand**. That is what closes the loop
mechanically: the eval notebook records `glue("score", 0.73)` and the
improvement notebook reads `nb.scraps["score"]` — a typed channel
between the two halves.

Together: **nteract** is where the live loop lives, **papermill** is
how you run N copies of it in batch, **scrapbook** is how the next
round reads what the last one produced. Each one is independently
useful; together they collapse the eval-improve split that scripts
usually enforce.

## Status

Early. The thesis is staked; the substrate is named; the loop runs on
two real optimizers. What it becomes from here is what gets evolved
next.

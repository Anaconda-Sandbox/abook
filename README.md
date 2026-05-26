# abook

**Does a notebook substrate lift a coding agent?** An evaluation.

A coding agent works with `Bash`, `Read`, `Edit`, `Write`. A notebook adds two
things on top of that: a **persistent stateful REPL** and a **visual feedback
channel**. This repo measures whether either one *lifts* the agent — improves
task success, lowers cost, or keeps a human able to supervise it.

## The two questions

A notebook, stripped to what is not just files, is *a REPL whose outputs render
into a visual channel*. So the eval tests exactly two things — nothing else.

### Q1 — Does the persistent REPL lift the agent? (statefulness)

Does a live stateful kernel — variables, imports, loaded models surviving across
calls — measurably lift a coding agent over a stateless `Bash`/`Read`/`Edit`
baseline? Measured on stateful-compute tasks, with a negative-control tier to
falsify a universal-lift claim.

### Q2 — Does visual feedback lift the loop? (rich display)

Does rendered output — plots, images, tables — lift the work, for two audiences:

- **(2a) the AI** — rendered output forwarded into the model's vision channel,
  closing a see-then-act loop.
- **(2b) the human in the loop — primary** — a notebook is a shared visual
  surface. A terminal agent emits walls of text and the human falls out of the
  loop; a notebook emits artifacts a human can glance at, stay oriented, and
  intervene. This is an oversight/adoption value, measured with a human-facing
  metric (review time, intervention rate, stated trust), not a task score.

## Decided architecture (settled, not under test)

For an agent, a notebook = a **filesystem companion** + a **kernel CLI**:

- **Document plane** — the notebook is a directory of flat cell files
  (`cells/0002.py`); the agent edits it with native `Read`/`Edit`/`Write`/`ls`.
  ~12 of nteract's 20 MCP tools just duplicate the filesystem; they are dropped.
- **Kernel plane** — a thin CLI (~6 process verbs: `exec`, `results`, `run-all`,
  `status`, `interrupt`, `restart`) drives the live kernel.

Only the *kernel* and the *visual feedback* are irreducibly "notebook"; the
document plane is the filesystem. The eval spends its budget only on what is
genuinely under test.

## Eval design

`harbor` harness, three arms, stateful-compute task set with a negative control:

| Arm | Substrate |
|---|---|
| Stateless baseline | coding agent, default tools, no kernel |
| nteract | imperative + stateful Jupyter kernel |
| marimo | reactive notebook — deterministic DAG, no hidden-state hazard |

Lead with **cost-normalized success** (success per dollar). Report 95% CIs —
N is small. Use a human-facing measure for Q2b.

## Status

Bootstrapping. Next: wire the filesystem-companion baseline + kernel CLI into a
harbor trial; build the Q2 task set + human-supervision protocol; verify image
passthrough into the vision channel.

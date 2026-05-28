# GEPA inside an nteract MCP kernel

One half of the self-evolving-notebook dogfood (see the [top-level README](../../README.md) for the thesis). [GEPA](https://github.com/gepa-ai/gepa) (Genetic-Pareto, ICLR 2026 Oral) is an evolutionary prompt optimizer — its `rollout → score → reflect → edit → re-evaluate` loop is exactly the loop this repo argues belongs in a kernel.

Each notebook in this folder isolates **one** kernel-native ergonomic edge from `~/Documents/GitHub/_docs/notebook/use-cases/01-gepa.md` and exercises it against real GEPA code from `~/Documents/GitHub/gepa`.

## Sources

- **GEPA library:** `~/Documents/GitHub/gepa` (cloned from `github.com/gepa-ai/gepa`)
- **Use-case framing:** `~/Documents/GitHub/_docs/notebook/use-cases/01-gepa.md`
- **Ranking context:** `~/Documents/GitHub/_docs/notebook/use-cases/README.md` (this is rank #1)

## Model wiring

All live runs route through AWS Bedrock via `litellm`. Credentials are loaded from `../../.env` (gitignored).

- `task_lm = "bedrock/converse/us.anthropic.claude-haiku-4-5-20251001-v1:0"` (cheap, fast — for rollouts)
- `reflection_lm = "bedrock/converse/us.anthropic.claude-sonnet-4-5-20250929-v1:0"` (stronger — for trace reflection)

Budgets are kept small (`max_metric_calls` ≤ 15, dataset slice ≤ 5–10 examples) so total run cost is bounded.

## Notebooks

| # | Notebook | Ergonomic edge it isolates |
|---|----------|----------------------------|
| 00 | `00-quickstart.ipynb` | Install `gepa` mid-session (`manage_dependencies`); first 5-line run |
| 01 | `01-architecture-tour.ipynb` | `inspect.getsource` walk of the optimizer in the same kernel that runs it |
| 02 | `02-default-adapter-deep-dive.ipynb` | Per-example traces as pandas DataFrames — `traces[traces.score == 0]` |
| 03 | `03-aime-mini-live.ipynb` | Convergence curve plotted **while** the optimizer runs |
| 04 | `04-pareto-frontier-viz.ipynb` | Pareto frontier as a heatmap; result lives in kernel namespace |
| 05 | `05-custom-adapter.ipynb` | Iterate `GEPAAdapter` subclass without restarting Python |
| 06 | `06-optimize-anything-svg.ipynb` | Evolved artifact rendered inline at every accepted mutation |
| 07 | `07-kernel-restart-survival.ipynb` | Checkpoint best-so-far so a kernel restart doesn't wipe a multi-hour run |
| 08 | `08-vs-script-baseline.ipynb` | Same config, in-kernel vs subprocess — wall-clock + ergonomics |

## How they were built

Every cell was created and executed by Claude Code via the `mcp__runt__*` tools (`runt mcp`). Outputs you see are real responses from Bedrock against real eval data. No synthetic rows, no mocked traces — per the project's "No Fabricated Data" rule.

## Reproducing

```bash
# from repo root
.venv/bin/python -m pip install gepa litellm boto3 python-dotenv
# .env must contain AWS_BEARER_TOKEN_BEDROCK + AWS_REGION
.venv/bin/jupyter lab notebooks/gepa/
```

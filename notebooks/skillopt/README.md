# SkillOpt inside an nteract MCP kernel

The second half of the self-evolving-notebook dogfood (see the [top-level README](../../README.md) for the thesis). [SkillOpt](https://github.com/microsoft/SkillOpt) (Microsoft Research, "agentic skill optimization via reflective training loops") runs the same `rollout → reflect → edit → gate` loop as GEPA, just with the artifact under evolution being a natural-language *skill document* instead of a single prompt.

Companion to `notebooks/gepa/`. Honest framing: SkillOpt is a **batch trainer** with on-disk trajectory state — *not* kernel-resident like GEPA. The notebook adds value in three places: code archaeology, config composition, and post-hoc trajectory-log EDA. The training loop itself is the same shape in or out of a notebook. This collection makes that distinction concrete so the contrast with GEPA's kernel-native loop is honest, not selling.

## Sources

- **SkillOpt library:** `~/Documents/GitHub/SkillOpt` (cloned from `github.com/microsoft/SkillOpt`)
- **Use-case framing:** `~/Documents/GitHub/_docs/notebook/use-cases/02-skillopt.md`
- **Comparator entry:** `~/Documents/GitHub/_docs/notebook/use-cases/04-skillopt-vs-gepa.md`
- **Ranking context:** rank #2 in `_docs/notebook/use-cases/README.md`

## Model wiring

SkillOpt supports four backends: `azure_openai`, `openai_chat`, `claude_chat`, `qwen_chat`. The simplest path for this repo is **`claude_chat`** — it shells out to the local `claude` CLI binary, which inherits the parent process's environment. With `AWS_BEARER_TOKEN_BEDROCK` already in `../../.env` (set up for the GEPA notebooks), every claude-CLI subprocess routes through Bedrock automatically. **No separate Anthropic API key is needed.**

If you want to use a direct Anthropic key instead, export `ANTHROPIC_API_KEY` and SkillOpt's claude backend uses that path automatically.

## Notebooks

| # | Notebook | Needs LLM? | Slice it isolates |
|---|----------|---|----|
| 01 | `01-architecture-tour.ipynb` | No | `skillopt/` package tree, engine/gradient/optimizer/scheduler/evaluation source walk |
| 02 | `02-gradient-deep-dive.ipynb` | No | What a "gradient" is in SkillOpt — reflection + edit-proposal structure |
| 03 | `03-optimizer-types.ipynb` | No | clip / slow_update / meta_skill — side-by-side acceptance logic |
| 04 | `04-scheduler-and-budget.ipynb` | No | Textual learning rate + edit budget across epochs — simulation |
| 05 | `05-config-yaml.ipynb` | No | Anatomy of `configs/searchqa/default.yaml`, composing custom configs in Python |
| 06 | `06-quickstart-and-train.ipynb` | **Yes** (claude-CLI → Bedrock) | Smallest possible live training run on a tiny dataset slice |
| 07 | `07-trajectory-log-eda.ipynb` | No (post-hoc) | Parse the run output from 06 into pandas, surface decisions |
| 08 | `08-custom-benchmark-env.ipynb` | Optional | Sketch a tiny custom `BenchmarkEnv` against the protocol |

## Honest caveat

Per `02-skillopt.md`: SkillOpt's design center is `scripts/train.py` plus the `skillopt_webui` dashboard. The optimizer is not built to be driven cell-by-cell; trajectory history is on-disk; the final deliverable is `best_skill.md` on disk. **This notebook collection does not pretend otherwise.** What it adds is (a) interactive code archaeology with `inspect.getsource`, (b) declarative config composition without YAML editing, (c) post-hoc EDA of the trajectory log as DataFrames, and (d) a reproducible smoke training run for sanity-checking the install.

## Reproducing

```bash
# from repo root
.venv/bin/python -m pip install -e ~/Documents/GitHub/SkillOpt
.venv/bin/jupyter lab notebooks/skillopt/
```

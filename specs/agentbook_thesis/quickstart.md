# Quickstart: agentbook — run one inner loop in a live kernel

**Feature**: agentbook_thesis
**Date**: 2026-05-28

## Overview

Drive a full rollout → evaluate → reflect → edit iteration of the GEPA (system-prompt)
optimizer inside one live kernel session, over the `runt` MCP surface — no process
restart, no `.ipynb` round-trip. This is the P1 path (User Story 1).

## Prerequisites

- The dev env created: `make setup` (creates the conda prefix env `./env` from
  `environment-dev.yml` and `pip install -e ".[gepa]"` — this installs `gepa`, `litellm`,
  `boto3`, `pandas`, `datasets`, `python-dotenv`). Activate with `conda activate ./env`.
- The `runt` MCP server registered in your Claude Code session (`mcp__runt__*` tools visible).
- LLM credentials in the kernel environment — this demo routes through AWS Bedrock via
  `AWS_BEARER_TOKEN_BEDROCK` + `AWS_REGION` (loaded from the repo `.env` by `notebooks/utils.bootstrap()`).
- GEPA's `max_metric_calls` parameter controls the optimizer's own call cap.
- If you drive the demo in the **runt** kernel rather than `./env`, install the optimizer
  deps into that kernel first (`manage_dependencies` / a `pip install` cell): `gepa`, `litellm`.

## Implementation Steps

> **Note**: this mirrors the working `notebooks/gepa_demo.ipynb`. The `agentbook` types
> (`Session`, the adapters) are the substrate; GEPA is engine-mode, so the inner loop runs
> via `opt.optimize(...)` rather than a manual `run_iteration` loop (the `run_iteration`
> driver is for driver-mode optimizers — see `src/agentbook/loop.py`).

### Step 1: Open a session and load state once

A setup cell loads the eval set, the model client, and the seed candidate — each loaded
exactly once (FR-003). `notebooks/utils.bootstrap()` finds the repo root, loads `.env`,
and puts `src/` on the path (no hardcoded path).

```python
# cell 1 — setup (executed via mcp__runt__execute_cell)
import os, time
from utils import bootstrap
REPO = bootstrap()

from gepa.examples.aime import init_dataset
from agentbook.adapters.gepa_adapter import GepaOptimizer
from agentbook.session import Session

TASK_LM       = "bedrock/converse/us.anthropic.claude-haiku-4-5-20251001-v1:0"
REFLECTION_LM = "bedrock/converse/us.anthropic.claude-sonnet-4-6"
KERNEL_PID    = os.getpid()                          # record for SC-001 stability check

trainset_full, valset_full, _ = init_dataset()       # real AIME eval data, loaded once
trainset, valset = trainset_full[:4], valset_full[:4]
seed_artifact = {"system_prompt": "Solve the math problem step by step and finish with '### <number>'."}

# engine-mode placeholder; gepa calls Bedrock itself via litellm
client  = lambda *a, **k: None
session = Session(eval_set=trainset, model_client=client,
                  slice_kind="system_prompt", seed_artifact=seed_artifact)
print("kernel PID:", session.kernel_pid, "| eval hash:", session.eval_set.content_hash[:16], "(pinned)")
```

### Step 2: Wire the GEPA adapter

```python
# cell 2
opt = GepaOptimizer(session, task_lm=TASK_LM, reflection_lm=REFLECTION_LM)
```

### Step 3: Run the inner loop in the same kernel

```python
# cell 3 — engine-mode: gepa drives rollout->evaluate->reflect->edit internally, no restart
result = opt.optimize(trainset=trainset, valset=valset,
                      max_metric_calls=30, reflection_minibatch_size=3, seed=0)
print("candidates:", result.num_candidates, "| best_idx:", result.best_idx,
      "| metric_calls:", result.total_metric_calls,
      "| PID stable:", os.getpid() == KERNEL_PID)     # SC-001
```

### Step 4: Read the result and render it inline

```python
# cell 4 — host reads outcome to decide the next experiment (FR-009, FR-005)
import matplotlib.pyplot as plt
ev = opt.event_frame()                                # per-iteration events as a DataFrame
ev[ev.phase == "eval_end"].plot(x="iteration", y="minibatch_score", marker="o")
plt.show()                                            # renders inline, no dashboard
print(session.best_candidate().artifact["system_prompt"][:200])   # the evolved system prompt
print("best_score:", session.best_score(), "| frontier:", session.frontier_snapshot())
```

### Step 5: Verify the run

```bash
# kernel PID was printed once in Step 1 and never changed → SC-001
make test          # adapter + loop unit tests
```

## Expected Results

### Stable kernel across iterations (SC-001)

```json
{"kernel_pid": 48213, "iterations": 10, "pid_changed": false, "loads": {"eval_set": 1, "model_client": 1}}
```

## Troubleshooting

### `mcp__runt__*` tools not available

**Cause**: the runt MCP server is not registered in this session.
**Fix**: register it (`runt mcp`) and reconnect; confirm the tools appear before driving cells.

### Kernel PID changes between iterations

**Cause**: a cell restarted the kernel (e.g. `restart_kernel`) or an unhandled crash.
**Fix**: this violates SC-001 — investigate the crashing cell; the loop must run in one warm kernel.


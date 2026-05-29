# Implementation Plan: SkillOpt optimizes the `reviewer` skill (full trainer)

**Spec**: [spec.md](spec.md) · **Created**: 2026-05-29 · governed by [constitution](../constitution.md)

## Phase 0 — Research (resolved)

All contracts confirmed against `../SkillOpt-src` (see [[entity/agentbook-skills-to-optimize]]):

- **No Docker / no Ray / no Azure.** Rollout agent is the `claude` CLI via
  `claude_backend`; select with `TARGET_BACKEND=claude_chat`, `OPTIMIZER_BACKEND=claude_chat`,
  `TARGET_DEPLOYMENT=claude-sonnet-4-6`.
- **Adapter registry**: `scripts/train.py` `_ENV_REGISTRY`; add lazy import for
  `skillsbench` → `SkillsBenchReviewerAdapter`.
- **Adapter contract** (`skillopt/envs/base.py`): implement `setup`, `get_dataloader`,
  `requires_ray()->False`, `build_train_env`, `build_eval_env`, `rollout`, `reflect`,
  `get_task_types`.
- **rollout() returns** `list[dict]` each with `id`, `hard` (0/1), `soft` (0..1) + our
  diagnostics (`recall`,`precision`,`missed`,`lints`,`fail_reason`,`task_description`).
- **reflect()** delegates to `run_minibatch_reflect(results, skill, prediction_dir,
  patches_dir, ...)`; reads `prediction_dir/<id>/conversation.json` — rollout MUST write it.
- **Patches** apply via `apply_patch(skill, {"edits":[...]})`; trainer does selection +
  `_save_skill` → `best_skill.md`.
- **Trainer entry**: `python scripts/train.py --config configs/skillsbench/reviewer.yaml`;
  config uses `_base_: ../_base_/default.yaml` deep-merge.

## Phase 1 — Design

### Component map (single source of truth = the candidate seeds)

```
SkillOpt-src/
  skillopt/envs/skillsbench/
    __init__.py
    adapter.py        # SkillsBenchReviewerAdapter(EnvAdapter)
    dataloader.py     # loads instances from split_dir train/val/test; BatchSpec payload=list[instance]
    rollout.py        # per-instance: claude_backend.chat_target(skill, code) -> findings JSON
                      #   -> score via reward.py -> write prediction_dir/<id>/conversation.json
                      #   -> RolloutResult dict
    reward.py         # imported/adapted from agentbook candidates/reviewer/reward.py (vendored copy)
    skills/initial.md # == candidates/reviewer/seed_skill.md (weak seed)
  scripts/train.py    # + register "skillsbench"
  configs/skillsbench/reviewer.yaml   # smoke config (small)

agentbook/
  notebooks/skillopt_bench/
    candidates/reviewer/   # generator + reward + validate (already built, validated)
    data/reviewer_split/{train,val,test}/*.json   # generated, git-ignored
    reviewer_skillopt.ipynb                        # the deliverable notebook
```

### Data flow (one iteration)
1. dataloader → BatchSpec(payload = list of instance dicts) for train / val / test.
2. `rollout(instances, skill)`: for each instance, build system=skill+task-frame,
   user=code-under-review (GT NOT included — FR-004); call `chat_target`; parse findings
   JSON; `reward(instance, findings)` → soft/hard + lints; trace-lint zeroes degenerate
   rollouts (FR-005); write `conversation.json` trajectory for reflect.
3. `reflect(results, skill)` → `run_minibatch_reflect` → patches from missed-bug traces.
4. Trainer applies patches (`apply_patch`), gates on val (`evaluation.use_gate`),
   `_save_skill` → `best_skill.md`.
5. Eval on held-out **test** split each step (FR-006); record train vs test reward.

### Anti-cheat enforcement points (map to FRs)
- FR-004: `rollout.py` builds the user prompt from `instance["code"]` only; planted
  `instance["bugs"]` never serialized into the prompt or working dir.
- FR-005: `reward.py` trace-lints (`spam_findings`, `flags_nearly_every_line`) → `hard=0`.
- FR-006/007: notebook computes test-reward each step; flags train↑/test-flat.
- FR-011: every number from a real `chat_target` call; no synthetic fallbacks.

### Notebook responsibilities (orchestration only)
- `pip install -e ../SkillOpt-src` into `./env` (idempotent cell).
- Generate instances (`gen_instances.py`) → split train/val/test (disjoint, seeded).
- Set backend env vars; write `configs/skillsbench/reviewer.yaml` (smoke).
- Run trainer as subprocess (`scripts/train.py`) — captures real stdout.
- Load `out_root/best_skill.md` + per-step results; render seed→evolved diff +
  train/test reward curve inline. End with **Data sources** section (constitution).

### Risks / mitigations
- Trainer requires many config keys → inherit from `_base_/default.yaml`, override minimal.
- `chat_target` empty/garbled JSON → rollout returns soft=0, captured as failure trace (edge case).
- Token cost → smoke config first (SC-000) before SC-001.
- Vendoring reward.py into SkillOpt vs importing agentbook path → vendor a copy in the
  adapter (keeps SkillOpt self-contained); keep agentbook candidate as source of truth + a
  test asserting they match.

## Phase 1b — Slice 2: `specify` (structural ⊕ LLM trace-judge)

Same loop contract as reviewer; the only new piece is the **reward** (a model call augments the
deterministic check). No SkillOpt edits; `env.name: specify`, `ReflACTTrainer(cfg, adapter)` direct.

### Component map
```
tasks/specify-skillopt/
  seed_skill.md                 # weak: "write a spec"
  gen_instances.py              # feature briefs (the task input)
  make_split.py                 # 5/2/3 disjoint split
  run_smoke.py                  # trainer driver (env.name=specify)
  specify_env/
    adapter.py   dataloader.py  # mirror reviewer
    prompts.py                  # build_system(skill)+frame, build_user(brief) — brief only (FR-014)
    reward.py                   # deterministic STRUCTURAL score (sections, FR-/SC- ids, MUST, measurable)
    judge.py                    # LLM trace-judge: testable/coverage/outcome/overall (FR-015)
    rollout.py                  # write spec → score = 0.5·structural + 0.5·judge; trajectory carries both
```

### Reward flow (one rollout)
1. `chat_target(skill+frame, brief)` → spec text (~1.5k tok).
2. `structural_reward(brief, spec)` → {hard, soft, failed_checks}.
3. `llm_judge(brief, spec)` → {testable, coverage, outcome, overall, notes} (~0.5k tok).
4. `soft = 0.5·structural.soft + 0.5·judge.overall`; `hard = structural.hard==1 AND judge.overall≥0.7` (FR-016).
5. trajectory `[verification]` = failed structural checks **+** judge feedback → reflect learns both (FR-017).

### Why the judge here (not for reviewer)
Reviewer reward is fully objective (planted-bug match). A spec has no single right answer; structure is
checkable but *testability/coverage/outcome* are semantic — the judge supplies exactly that signal. Cost
is justified: judge tokens ≪ the spec-writing rollout tokens.

### Risks
- Judge non-determinism / unparseable output → `judge.py` returns conservative 0 + `error`; surfaced, not hidden.
- Judge could be gamed → held-out test split (FR-006/007) still guards; SC-006 checks the judge adds real signal.

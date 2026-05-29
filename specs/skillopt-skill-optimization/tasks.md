# Tasks: SkillOpt optimizes the `reviewer` skill (full trainer)

**Plan**: [plan.md](plan.md) · `[P]` = parallelizable · `[USn]` = user story

## Phase A — SkillOpt adapter (in ../SkillOpt-src) [US1]
- [ ] T001 [US1] Create `skillopt/envs/skillsbench/__init__.py`
- [ ] T002 [P][US1] Vendor `reward.py` into `skillopt/envs/skillsbench/` (copy of candidates/reviewer/reward.py)
- [ ] T003 [P][US1] Copy weak seed → `skillopt/envs/skillsbench/skills/initial.md` (== candidates/reviewer/seed_skill.md)
- [ ] T004 [US1] `dataloader.py`: load instances from `split_dir/{train,val,test}/*.json`; `build_train_batch`/`build_eval_batch` → BatchSpec(payload=list[instance])
- [ ] T005 [US1] `rollout.py`: per-instance claude_backend `chat_target` (system=skill+frame, user=code-only — FR-004) → parse findings JSON → `reward()` → write `prediction_dir/<id>/conversation.json` → RolloutResult dict (id/hard/soft/missed/lints/...)
- [ ] T006 [US1] `adapter.py`: `SkillsBenchReviewerAdapter(EnvAdapter)` — setup/get_dataloader/requires_ray=False/build_*_env/rollout/reflect(→run_minibatch_reflect)/get_task_types
- [ ] T007 [US1] Register `skillsbench` in `scripts/train.py` `_ENV_REGISTRY` (lazy import)
- [ ] T008 [US1] `configs/skillsbench/reviewer.yaml` (smoke): `_base_` merge, env.name=skillsbench, skill_init, split_dir, claude_chat backend, small batch/epochs

## Phase B — Anti-cheat contracts [US2]
- [ ] T009 [P][US2] FR-004 check: assert planted `bugs` never appear in built prompt (unit test on rollout prompt builder)
- [ ] T010 [P][US2] FR-005: trace-lints zero `hard` (already in reward.py) — add rollout test injecting spam findings → hard=0
- [ ] T011 [US2] FR-007: notebook helper that flags train↑/test-flat as suspected memorization

## Phase C — agentbook notebook orchestration [US1]
- [ ] T012 [US1] Instance gen + disjoint seeded split → `notebooks/skillopt_bench/data/reviewer_split/{train,val,test}` (gitignored)
- [ ] T013 [US1] `reviewer_skillopt.ipynb`: install SkillOpt (idempotent), set backend env, write config, run `scripts/train.py` subprocess (real stdout)
- [ ] T014 [US1] Notebook: load `best_skill.md` + per-step results → render seed→evolved diff + train/test reward curve inline
- [ ] T015 [US1] Notebook ends with **Data sources** section (constitution / FR-011)

## Phase D — Run + verify [US1/US2]
- [ ] T016 [US1] SC-000 smoke run: train≈8–12, 2 iters, test≈12 — completes end-to-end through real trainer
- [ ] T017 [US2] Report held-out test reward before/after + train↔test gap (real numbers)
- [ ] T018 Verify against spec SC-000/002/003/004/005; record result in notebook

## Phase E — second slice (deferred) [US3]
- [ ] T019 [US3] specify slice adapter variant + LLM trace-judge verifier (after reviewer green)

## Definition of done (smoke)
SC-000 + SC-002 + SC-003 pass; notebook reproducible from fresh kernel; skill diff
auditable to missed-bug categories (SC-005). Scale to SC-001 only on user go-ahead.

# Feature Specification: SkillOpt optimizes a real `~/.claude` skill, scored by a SkillsBench-style deterministic task

**Status**: draft · **Created**: 2026-05-28 · **Updated**: 2026-05-28
**Governed by**: [`specs/constitution.md`](../constitution.md)
**Related**: [[entity/agentbook-skills-to-optimize]] (target ranking) · `notebooks/skillopt_bench/candidates/` (validated seeds)

## Summary

Run SkillOpt (microsoft) — the optimizer that trains a `SKILL.md` via
rollout → reward → reflect → patch → select — against one **real** `~/.claude` skill,
measured by a SkillsBench-style task with a **deterministic reward**, entirely inside a
notebook (Docker-free, on SkillOpt's `claude_backend`). First slice: **`reviewer`**
(planted-bug recall). The experiment answers: *can SkillOpt measurably improve a real
skill on held-out tasks without reward hacking?*

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Optimize a real skill from a deterministic signal (Priority: P1)
A practitioner seeds SkillOpt with a deliberately-weak version of their real `reviewer`
skill, runs the loop on a train split of planted-bug instances, and reads a
**held-out test-reward** curve plus the seed→evolved skill diff.

**Independent Test**: From a fresh kernel, run the notebook end-to-end and confirm it
reports test-reward before vs after and renders the skill diff inline.

### User Story 2 — Reward hacking is detectable, not silent (Priority: P1)
The same practitioner can see, per iteration, whether gains are real learning or train
memorization, and whether any rollout cheated.

**Independent Test**: Inject a spam-findings rollout and confirm its reward is zeroed by
a trace-lint and logged; confirm a train-up/test-flat run is flagged as memorization.

### User Story 3 — One loop contract, second slice swappable (Priority: P3)
The same notebook loop accepts `specify` as a second slice that additionally turns on
the LLM trace-judge, with no change to the loop contract.

**Independent Test**: Point the loop at the `specify` seed and confirm it runs with the
judge layer enabled and the deterministic structural reward unchanged.

### Edge Cases
- Rollout returns malformed/no JSON findings → scored 0, captured as a failure trace.
- Reflect proposes a patch that doesn't apply cleanly → patch rejected, skill unchanged.
- All train instances already pass → reflect has no failures to learn from (honest null).
- Test split empty/too small → loop refuses to report a headline delta.

## Requirements *(mandatory)*

### Functional Requirements
- **FR-001**: The loop MUST run Docker-free and use SkillOpt's `claude_backend`
  (subprocess rollout, no Ray, no Azure dependency).
- **FR-002**: The loop MUST optimize exactly one declared harness slice — the
  `reviewer` `SKILL.md` — seeded from a deliberately-weak version with stripped headroom.
- **FR-003**: The primary reward MUST be the deterministic
  `candidates/reviewer/reward.py` (planted-bug F1); no LLM judge is required for the
  reviewer slice.
- **FR-004**: Ground truth (planted-bug locations/categories) MUST NOT appear in the
  agent's prompt or working input during rollout; only the source-under-review is given.
- **FR-005**: Degenerate rollouts MUST be caught by deterministic trace-lints
  (spam findings, flags-nearly-every-line) and have their reward zeroed and logged.
- **FR-006**: Instances MUST be split into disjoint **train** and **test** sets; the
  headline metric MUST be **held-out test reward**, and train reward MUST also be shown.
- **FR-007**: A run where train reward rises while held-out test reward stays flat MUST
  be explicitly flagged as suspected memorization / reward hacking.
- **FR-008**: The loop MUST run SkillOpt's real `ReflACTTrainer` via `scripts/train.py`
  driven by a custom `skillsbench` `EnvAdapter` (rollout + `run_minibatch_reflect` +
  `apply_patch` + selection are SkillOpt's own code, not reimplemented). The adapter
  MUST register under `env.name: skillsbench` and run with `requires_ray() == False`.
- **FR-009**: The notebook MUST surface the seed→evolved skill diff and the per-iteration
  train/test reward so a human can audit what was learned.
- **FR-010**: The loop contract MUST accept a second slice (`specify`) that additionally
  enables an **LLM trace-judge** verifier, without changing the contract.
- **FR-011** (Real Data, per constitution): every reported number MUST come from a real
  rollout / real subprocess execution / real reward computation — no fabricated curves.
- **FR-012**: The whole loop MUST run with all new code inside agentbook; the SkillOpt repo
  MUST NOT be modified (adapter subclasses `skillopt` as a library; trainer is constructed
  directly as `ReflACTTrainer(cfg, adapter)`).
- **FR-013** (prompt isolation): the rollout `claude` CLI MUST run with `CLAUDE_SETTING_SOURCES=""`
  so it cannot load this machine's user/project settings or CLAUDE.md. Without it the rollout
  agent behaves agentically and answers about its own session instead of reviewing the code
  (observed in the first run). This is the operational half of FR-004.

#### Slice 2 — `specify` (structural reward ⊕ LLM trace-judge)
- **FR-014**: The `specify` slice MUST optimize a deliberately-weak spec-writing `SKILL.md`;
  the rollout writes a full spec for a feature brief (the brief only — never a reference spec).
- **FR-015**: The reward MUST blend a **deterministic structural** score (required sections,
  `FR-`/`SC-` ids, `MUST` usage, measurable success criteria, no impl leakage) with an
  **LLM trace-judge** score covering what structure cannot see — whether each requirement is
  genuinely *testable*, whether the spec *covers the brief*, and whether success criteria are
  *outcome-level*. Blend: `soft = 0.5·structural + 0.5·judge_overall`.
- **FR-016**: The LLM trace-judge MUST run on **every** rollout (not a sample) — its tokens are
  small relative to the spec-writing rollout. A hard pass requires structural-hard AND
  `judge_overall ≥ 0.7`.
- **FR-017**: The judge MUST be reference-free (no gold spec); the held-out **test** split
  (FR-006/007) remains the anti-overfitting guard. The reflect trajectory MUST carry BOTH the
  failed structural checks AND the judge feedback, so the skill learns structure *and* testability.

### Key Entities
- **Slice**: the single skill under evolution (reviewer `SKILL.md`).
- **Instance**: a source file with planted bugs (train or test); GT held by the harness.
- **Rollout**: agent reviews one instance → structured findings → deterministic reward.
- **Trace**: the agent's findings + prompt, consumed by trace-lints, the trace-judge, and `run_minibatch_reflect`.
- **Patch**: SkillOpt reflect output applied to the skill via `apply_patch`.

## Assumptions *(mandatory)*
- **A-001**: `ANTHROPIC_API_KEY` (or the `claude_backend`'s configured creds) is present in the kernel.
- **A-002**: SkillOpt-src is importable (`pip install -e`) and its `run_minibatch_reflect` / `apply_patch` / `claude_backend` are stable.
- **A-003**: The reviewer reward + generator under `candidates/reviewer/` are the source of truth for the slice's task.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-000** (smoke): A first run completes a tiny real loop (train ≈8–12 instances,
  2 reflect iterations, test ≈12) end-to-end through the real trainer before any scale-up.
- **SC-001**: From a fresh kernel, the notebook completes ≥3 reflect iterations on a
  train split of ≥40 instances with no manual intervention.
- **SC-002**: The spam-findings cheat is caught by a trace-lint in **100%** of injected
  cases (reward forced to 0).
- **SC-003**: The notebook reports held-out **test** reward before and after, and the
  train↔test gap, as real measured numbers (per FR-011).
- **SC-004**: Either held-out test soft-reward improves by a stated margin over the seed
  skill, **or** the run is reported as an honest null / memorization-flagged result —
  both are acceptable outcomes; a silently train-only "win" is not.
- **SC-005**: The evolved skill diff is human-auditable and attributable to specific
  missed-bug categories from the train traces.
- **SC-006** (specify slice): The `specify` smoke runs end-to-end through the real trainer with
  the trace-judge enabled, and at least one rollout shows the **judge** down-scoring a spec on
  `testable`/`coverage`/`outcome` that the **structural** reward alone passed — demonstrating the
  judge adds signal the deterministic checker cannot (per FR-015/FR-016).

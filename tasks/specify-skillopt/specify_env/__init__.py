"""In-agentbook SkillsBench `specify` slice for SkillOpt (library use).

Optimizes a spec-writing SKILL.md. Reward = deterministic structural checks
(reward.py) BLENDED with an LLM **trace-judge** (judge.py) that scores the semantics
structure can't see — whether each requirement is genuinely testable, whether the spec
covers the brief, and whether success criteria are outcome-level. The judge runs on every
rollout; its token cost is small relative to the spec-writing rollout itself.

No SkillOpt repo edits — subclasses skillopt.envs.base.EnvAdapter at runtime.
"""

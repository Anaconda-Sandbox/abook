"""In-agentbook SkillsBench `reviewer` adapter for SkillOpt (used as a library).

Optimizes a code-review SKILL.md against planted-bug recall. Docker-free; the rollout
agent is the `claude` CLI via skillopt's claude_backend. NO file in the SkillOpt repo is
modified — this subclasses skillopt.envs.base.EnvAdapter at runtime and is driven by
constructing ReflACTTrainer(cfg, adapter) directly.
"""

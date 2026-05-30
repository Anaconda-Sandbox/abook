"""Smoke driver: optimize the specify SKILL.md via SkillOpt's real trainer, in-process.

Reward = deterministic structural ⊕ LLM trace-judge. No SkillOpt repo edits — constructs
ReflACTTrainer(cfg, adapter) directly. Run from agentbook's conda env with the claude_chat
backend env vars set (see the notebook's re-run cell), plus CLAUDE_SETTING_SOURCES="".
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from skillopt.config import flatten_config  # noqa: E402
from skillopt.engine.trainer import ReflACTTrainer  # noqa: E402
from specify_env.adapter import SpecifyAdapter  # noqa: E402

SPLIT_DIR = os.path.join(HERE, "data", "specify_split")
SEED_SKILL = os.path.join(HERE, "seed_skill.md")
OUT_ROOT = os.environ.get("SMOKE_OUT", "/tmp/skillopt_specify_smoke")


def build_cfg() -> dict:
    nested = {
        "model": {
            "optimizer_backend": "claude_chat",
            "target_backend": "claude_chat",
            "optimizer": "claude-sonnet-4-6",
            "target": "claude-sonnet-4-6",
            "reasoning_effort": "",
            "rewrite_reasoning_effort": "",
        },
        "train": {"num_epochs": 1, "train_size": 0, "batch_size": 5, "accumulation": 1, "seed": 42},
        "gradient": {
            "minibatch_size": 3,
            "merge_batch_size": 3,
            "analyst_workers": 2,
            "max_analyst_rounds": 2,
            "failure_only": False,
        },
        "optimizer": {
            "learning_rate": 3,
            "min_learning_rate": 2,
            "lr_scheduler": "constant",
            "lr_control_mode": "fixed",
            "skill_update_mode": "patch",
            "use_slow_update": False,
            "use_meta_skill": False,
        },
        "evaluation": {"use_gate": True, "sel_env_num": 0, "test_env_num": 0, "eval_test": True},
        "env": {
            "name": "specify",
            "skill_init": SEED_SKILL,
            "split_mode": "split_dir",
            "split_dir": SPLIT_DIR,
            "split_seed": 42,
            "exec_timeout": 180,
            "workers": 4,
            "out_root": OUT_ROOT,
        },
    }
    cfg: dict = flatten_config(nested)
    return cfg


def main() -> None:
    cfg = build_cfg()
    cfg["out_root"] = OUT_ROOT
    os.makedirs(OUT_ROOT, exist_ok=True)
    adapter = SpecifyAdapter(
        split_dir=SPLIT_DIR,
        split_mode="split_dir",
        workers=4,
        analyst_workers=2,
        minibatch_size=3,
        edit_budget=3,
        exec_timeout=180,
        max_completion_tokens=6000,
    )
    print(f"[specify smoke] out_root={OUT_ROOT}")
    summary = ReflACTTrainer(cfg, adapter).train()
    print("[specify smoke] DONE:", summary)


if __name__ == "__main__":
    main()

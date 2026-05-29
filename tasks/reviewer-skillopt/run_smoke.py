"""Smoke driver: optimize the reviewer SKILL.md via SkillOpt's real trainer, in-process.

No SkillOpt repo edits — constructs ReflACTTrainer(cfg, adapter) directly with our
agentbook-local adapter. Run from the agentbook conda env with the claude_chat backend
env vars set (see SETTINGS below). Writes everything under out_root.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from reviewer_env.adapter import SkillsBenchReviewerAdapter  # noqa: E402
from skillopt.config import flatten_config  # noqa: E402
from skillopt.engine.trainer import ReflACTTrainer  # noqa: E402

SPLIT_DIR = os.path.join(HERE, "data", "reviewer_split")
SEED_SKILL = os.path.join(HERE, "seed_skill.md")
OUT_ROOT = os.environ.get("SMOKE_OUT", "/tmp/skillopt_reviewer_smoke")


def build_cfg() -> dict:
    nested = {
        "model": {
            "optimizer_backend": "claude_chat",
            "target_backend": "claude_chat",
            "optimizer": "claude-sonnet-4-6",
            "target": "claude-sonnet-4-6",
            # claude CLI --thinking accepts enabled|adaptive|disabled (NOT medium/high);
            # empty -> flag omitted (plain completion). See claude_backend.py:257.
            "reasoning_effort": "",
            "rewrite_reasoning_effort": "",
        },
        "train": {"num_epochs": 1, "train_size": 0, "batch_size": 6, "accumulation": 1, "seed": 42},
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
            "name": "skillsbench",
            "skill_init": SEED_SKILL,
            "split_mode": "split_dir",
            "split_dir": SPLIT_DIR,
            "split_seed": 42,
            "exec_timeout": 120,
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
    adapter = SkillsBenchReviewerAdapter(
        split_dir=SPLIT_DIR,
        split_mode="split_dir",
        workers=4,
        analyst_workers=2,
        minibatch_size=3,
        edit_budget=3,
        exec_timeout=120,
    )
    print(f"[smoke] out_root={OUT_ROOT}")
    print(f"[smoke] cfg keys: {sorted(cfg.keys())}")
    trainer = ReflACTTrainer(cfg, adapter)
    summary = trainer.train()
    print("[smoke] DONE. summary:", summary)


if __name__ == "__main__":
    main()

"""SkillsBench `specify` adapter for SkillOpt (agentbook-local; library use).

Optimizes a spec-writing SKILL.md. Reward = deterministic structural ⊕ LLM trace-judge
(see rollout.py / judge.py). Reflect + patch + selection are SkillOpt's own code.
Driven by constructing `ReflACTTrainer(cfg, adapter)` directly — no SkillOpt repo edits.
"""

from __future__ import annotations

import json
import os

from skillopt.datasets.base import BatchSpec
from skillopt.envs.base import EnvAdapter
from skillopt.gradient.reflect import run_minibatch_reflect

from .dataloader import SpecifyDataLoader
from .rollout import run_specify_batch

TASK_TYPES = ["spec_writing"]


class SpecifyAdapter(EnvAdapter):
    """SkillsBench specify slice — structural reward + LLM trace-judge."""

    def __init__(
        self,
        split_dir: str = "",
        data_path: str = "",
        split_mode: str = "split_dir",
        split_ratio: str = "2:1:7",
        split_seed: int = 42,
        split_output_dir: str = "",
        exec_timeout: int = 180,
        workers: int = 4,
        analyst_workers: int = 4,
        failure_only: bool = False,
        minibatch_size: int = 3,
        edit_budget: int = 3,
        seed: int = 42,
        max_completion_tokens: int = 6000,
    ) -> None:
        self.exec_timeout = int(exec_timeout)
        self.workers = int(workers)
        self.analyst_workers = int(analyst_workers)
        self.failure_only = failure_only
        self.minibatch_size = int(minibatch_size)
        self.edit_budget = int(edit_budget)
        self.max_completion_tokens = int(max_completion_tokens)
        self.dataloader = SpecifyDataLoader(
            split_dir=split_dir,
            data_path=data_path,
            split_mode=split_mode,
            split_ratio=split_ratio,
            split_seed=split_seed,
            split_output_dir=split_output_dir,
            seed=seed,
        )

    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        self.dataloader.setup(cfg)

    def get_dataloader(self):
        return self.dataloader

    def requires_ray(self) -> bool:
        return False

    def get_task_types(self) -> list[str]:
        return list(TASK_TYPES)

    def build_env_from_batch(self, batch: BatchSpec, **kwargs):
        return list(batch.payload or [])

    def build_train_env(self, batch_size: int, seed: int, **kwargs):
        return self.build_env_from_batch(
            self.dataloader.build_train_batch(batch_size=batch_size, seed=seed, **kwargs), **kwargs
        )

    def build_eval_env(self, env_num: int, split: str, seed: int, **kwargs):
        return self.build_env_from_batch(
            self.dataloader.build_eval_batch(env_num=env_num, split=split, seed=seed, **kwargs), **kwargs
        )

    def rollout(self, env_manager, skill_content: str, out_dir: str, **kwargs) -> list[dict]:
        items = env_manager
        os.makedirs(out_dir, exist_ok=True)
        results_path = os.path.join(out_dir, "results.jsonl")
        if os.path.exists(results_path):
            existing = []
            with open(results_path) as f:
                for line in f:
                    try:
                        existing.append(json.loads(line))
                    except Exception:
                        pass  # best-effort: skip malformed resume lines
            if existing:
                return existing
        results = run_specify_batch(
            items=items,
            skill_content=skill_content,
            out_dir=out_dir,
            workers=self.workers,
            max_completion_tokens=self.max_completion_tokens,
            timeout=self.exec_timeout,
        )
        with open(results_path, "w") as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return results

    def reflect(self, results: list[dict], skill_content: str, out_dir: str, **kwargs) -> list[dict | None]:
        patches: list[dict | None] = run_minibatch_reflect(
            results=results,
            skill_content=skill_content,
            prediction_dir=kwargs.get("prediction_dir", os.path.join(out_dir, "predictions")),
            patches_dir=kwargs.get("patches_dir", os.path.join(out_dir, "patches")),
            workers=self.analyst_workers,
            failure_only=self.failure_only,
            minibatch_size=self.minibatch_size,
            edit_budget=self.edit_budget,
            random_seed=kwargs.get("random_seed"),
            step_buffer_context=kwargs.get("step_buffer_context", ""),
            meta_skill_context=kwargs.get("meta_skill_context", ""),
            update_mode=getattr(self, "_cfg", {}).get("skill_update_mode", "patch"),
        )
        return patches

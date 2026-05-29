"""SkillOpt adapter — engine mode, on-disk state (contracts/loop-contract.md, design A).

SkillOpt is a batch trainer: ``ReflACTTrainer.train()`` runs the
``rollout → reflect → aggregate → select → update → gate`` loop and persists
*everything* to disk — per-item trajectories (``predictions/<id>/conversation.json``),
a per-step ``history.json``, and skill snapshots (``skills/skill_v*.md``). Its
reflect step reads those trajectory files back from disk, so the on-disk log is
the interface between rollout and reflect.

This adapter therefore integrates at the **on-disk layer**: it drives SkillOpt's
own CLI (so we reuse its config machinery and backends, not reimplement them),
then maps the resulting run directory onto the substrate's Session entities. The
disk-mapping (:meth:`sync_from_disk`) needs no LLM and is unit-tested against a
real run directory.

This is the on-disk state shape that, paired with GEPA's kernel-resident shape,
satisfies SC-003 ("two optimizers, two slices, two state shapes, one substrate").

It does not implement the four-arrow ``Optimizer`` Protocol — SkillOpt owns its
loop (engine mode); forcing it through ``run_iteration`` would mean reimplementing
its trainer.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from agentbook.session import Iteration, Session


class SkillOptOptimizer:
    """Engine-mode adapter for SkillOpt (skill-document slice, on-disk state).

    Args:
        session: the live substrate session (its seed candidate's artifact is the
            seed skill document text).
        skillopt_root: path to the SkillOpt checkout (where ``scripts/train.py`` lives).
        config: config path, relative to ``skillopt_root`` (e.g. the searchqa default).
        backend: SkillOpt backend name. ``claude_chat`` shells to the local ``claude``
            CLI; the ``--thinking`` flag is dropped (``reasoning_effort=""``) to stay
            compatible with current CLI versions.
    """

    def __init__(
        self,
        session: Session,
        *,
        skillopt_root: str | Path,
        config: str = "configs/searchqa/default.yaml",
        backend: str = "claude_chat",
    ) -> None:
        self.session = session
        self.root = Path(skillopt_root)
        self.config = config
        self.backend = backend
        self.summary: dict[str, Any] | None = None

    def optimize(
        self,
        out_root: str | Path,
        *,
        split_dir: str | Path,
        train_size: int = 2,
        batch_size: int = 2,
        num_epochs: int = 1,
        minibatch_size: int = 2,
        workers: int = 2,
        timeout: int = 1200,
        extra_options: list[str] | None = None,
        python: str | None = None,
    ) -> dict[str, Any]:
        """Run SkillOpt's trainer live (subprocess) and map the result into the session.

        Returns the parsed ``summary.json``. Raises ``RuntimeError`` on a non-zero exit.
        """
        out_root = Path(out_root)
        options = [
            "model.backend=" + self.backend,
            "model.target_backend=" + self.backend,
            "model.optimizer_backend=" + self.backend,
            "model.reasoning_effort=",  # drop the stale --thinking CLI flag
            f"train.train_size={train_size}",
            f"train.batch_size={batch_size}",
            f"train.num_epochs={num_epochs}",
            f"gradient.minibatch_size={minibatch_size}",
            "env.split_mode=split_dir",
            f"env.split_dir={Path(split_dir)}",
            f"env.workers={workers}",
            f"env.out_root={out_root}",
            *(extra_options or []),
        ]
        cmd = [
            python or sys.executable,
            "scripts/train.py",
            "--config",
            self.config,
            "--backend",
            self.backend,
            "--cfg-options",
            *options,
        ]
        proc = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True, timeout=timeout, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"SkillOpt train.py failed ({proc.returncode}):\n{proc.stderr[-2000:]}")
        return self.sync_from_disk(out_root)

    def sync_from_disk(self, out_root: str | Path) -> dict[str, Any]:
        """Map a completed SkillOpt run directory onto the Session (no LLM needed).

        Adds the best skill document as a candidate (child of the seed), records one
        Iteration per training step from ``history.json``, and credits the budget with
        the run's call count from ``summary.json``.
        """
        out_root = Path(out_root)
        summary: dict[str, Any] = json.loads((out_root / "summary.json").read_text())
        self.summary = summary

        best_skill = self._best_skill_text(out_root, summary)
        seed = self.session.candidates[0]
        child = self.session.add_candidate(best_skill, parent=seed)
        child.scores["test_hard"] = float(summary.get("test_hard", 0.0) or 0.0)

        for step in self._history(out_root):
            self.session.iterations.append(
                Iteration(
                    index=int(step.get("step", len(self.session.iterations))),
                    selected_candidate_id=seed.candidate_id,
                    # an accepted step yields the child; a rejected/skipped step yields none
                    new_candidate_id=child.candidate_id if step.get("action") == "accept" else None,
                    subsample_ids=[],
                    scores=[float(step.get("rollout_hard", 0.0) or 0.0)],
                )
            )

        calls = 0
        token_summary = summary.get("token_summary") or {}
        if isinstance(token_summary, dict):
            calls = int(token_summary.get("calls", 0) or 0)
        self.session.budget.calls_used = calls
        return summary

    def _best_skill_text(self, out_root: Path, summary: dict[str, Any]) -> str:
        """The best skill document — prefer ``best_skill.md``, else the last snapshot."""
        best = out_root / "best_skill.md"
        if best.exists():
            return best.read_text()
        snaps = sorted((out_root / "skills").glob("skill_v*.md"))
        return snaps[-1].read_text() if snaps else str(self.session.candidates[0].artifact)

    @staticmethod
    def _history(out_root: Path) -> list[dict[str, Any]]:
        path = Path(out_root) / "history.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []

    # --- log EDA helpers (the notebook's value-add for a batch trainer) ----------

    @staticmethod
    def load_trajectories(out_root: str | Path) -> list[dict[str, Any]]:
        """Every logged trajectory: one row per ``predictions/<id>/conversation.json``.

        This is what SkillOpt's own reflect step parses — surfacing it as data is the
        notebook's value-add for an on-disk batch trainer ("use logs, not reruns")."""
        rows: list[dict[str, Any]] = []
        for conv in sorted(Path(out_root).rglob("predictions/*/conversation.json")):
            try:
                turns = json.loads(conv.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            rows.append(
                {
                    "phase": conv.relative_to(out_root).parts[0],
                    "item_id": conv.parent.name,
                    "n_turns": len(turns),
                    "roles": [t.get("role") for t in turns if isinstance(t, dict)],
                }
            )
        return rows

    @staticmethod
    def load_results(out_root: str | Path) -> list[dict[str, Any]]:
        """Every per-item result row across all ``results.jsonl`` files (for EDA)."""
        rows: list[dict[str, Any]] = []
        for rj in sorted(Path(out_root).rglob("results.jsonl")):
            phase = rj.relative_to(out_root).parts[0]
            for line in rj.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rec["phase"] = phase
                rows.append(rec)
        return rows

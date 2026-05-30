"""Rollout for the specify slice: write a spec, then score = structural ⊕ LLM-judge.

Per instance: system = skill + task frame; user = the feature brief only. The agent writes
a spec; we score it with the deterministic structural reward AND the LLM trace-judge, blend
them, and write a trajectory whose `[verification]` message carries BOTH signals (failed
structural checks + judge feedback) — so reflect learns structure *and* testability.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from skillopt.model import chat_target

from .judge import llm_judge
from .prompts import build_system, build_user
from .reward import reward as structural_reward

JUDGE_HARD_FLOOR = 0.7  # judge overall must clear this for a hard pass


def score(brief: str, spec: str) -> tuple[float, int, dict, dict]:
    s = structural_reward(brief, spec)
    j = llm_judge(brief, spec)
    soft = round(0.5 * s["soft"] + 0.5 * j["overall"], 4)
    hard = int(s["hard"] == 1 and j["overall"] >= JUDGE_HARD_FLOOR)
    return soft, hard, s, j


def _write_prediction(out_dir, tid, system, user, spec, s, j) -> None:
    pdir = os.path.join(out_dir, "predictions", tid)
    os.makedirs(pdir, exist_ok=True)
    verification = (
        f"STRUCTURAL soft={s['soft']} hard={s['hard']} failed_checks={s['failed']}. "
        f"JUDGE overall={j['overall']} testable={j['testable']} coverage={j['coverage']} "
        f"outcome={j['outcome']} notes={j['notes']!r}."
    )
    conversation = [
        {"role": "assistant", "content": spec},
        {"role": "system", "content": verification},
    ]
    with open(os.path.join(pdir, "conversation.json"), "w") as f:
        json.dump(conversation, f, ensure_ascii=False, indent=2)
    with open(os.path.join(pdir, "target_system_prompt.txt"), "w") as f:
        f.write(system)
    with open(os.path.join(pdir, "target_user_prompt.txt"), "w") as f:
        f.write(user)


def process_one(item, skill_content, out_dir, max_completion_tokens, timeout) -> dict:
    tid, brief = str(item["id"]), item["brief"]
    system, user = build_system(skill_content), build_user(brief)
    spec, error = "", ""
    try:
        spec, _ = chat_target(system=system, user=user, max_completion_tokens=max_completion_tokens, timeout=timeout)
    except Exception as exc:  # rollout failure -> scored as a failed spec
        error = f"{type(exc).__name__}: {exc}"

    soft, hard, s, j = score(brief, spec)
    _write_prediction(out_dir, tid, system, user, spec, s, j)

    weak_judge = [k for k in ("testable", "coverage", "outcome") if j.get(k, 0) < 0.7]
    fail_reason = ""
    if not hard:
        bits = []
        if error:
            bits.append(f"rollout error: {error}")
        if s["failed"]:
            bits.append(f"structural: {s['failed']}")
        if weak_judge:
            bits.append(f"judge weak: {weak_judge} ({j.get('notes', '')})")
        fail_reason = " | ".join(bits)

    return {
        "id": tid,
        "hard": hard,
        "soft": soft,
        "structural_soft": s["soft"],
        "structural_hard": s["hard"],
        "failed_checks": s["failed"],
        "judge_overall": j["overall"],
        "judge_testable": j["testable"],
        "judge_coverage": j["coverage"],
        "judge_outcome": j["outcome"],
        "judge_notes": j["notes"],
        "task_description": f"Write a feature specification for: {brief[:80]}",
        "task_type": "spec_writing",
        "fail_reason": fail_reason,
        "n_turns": 1,
        "error": error,
    }


def run_specify_batch(items, skill_content, out_dir, workers=4, max_completion_tokens=6000, timeout=180) -> list[dict]:
    os.makedirs(out_dir, exist_ok=True)
    results: list[dict] = [None] * len(items)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {
            ex.submit(process_one, it, skill_content, out_dir, max_completion_tokens, timeout): i
            for i, it in enumerate(items)
        }
        for fut in as_completed(futs):
            results[futs[fut]] = fut.result()
    return results

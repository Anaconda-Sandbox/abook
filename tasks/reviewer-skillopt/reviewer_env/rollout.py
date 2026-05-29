"""Rollout for the SkillsBench `reviewer` slice (agentbook-local).

For each instance: system prompt = skill + a fixed task frame; user prompt = ONLY the
line-numbered code under review. Planted bugs are NEVER serialized into either prompt
(FR-004) — they stay in the harness, used only to score and to build the post-hoc reflect
trajectory. Writes <out_dir>/predictions/<id>/{conversation.json, target_system_prompt.txt,
target_user_prompt.txt} for run_minibatch_reflect, and returns RolloutResult dicts.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from skillopt.model import chat_target

from .prompts import build_system, build_user, parse_findings
from .reward import reward


def _write_prediction(out_dir: str, tid: str, system: str, user: str,
                      assistant: str, rew: dict) -> None:
    # reflect reads <rollout_dir>/predictions/<id>/conversation.json
    pdir = os.path.join(out_dir, "predictions", tid)
    os.makedirs(pdir, exist_ok=True)
    verification = (
        f"Reward: soft={rew['soft']} hard={rew['hard']} "
        f"recall={rew['recall']} precision={rew['precision']}. "
        f"Caught {rew['caught']}/{rew['n_planted']} planted bugs."
    )
    if rew["missed"]:
        cats = sorted({m["category"] for m in rew["missed"]})
        verification += f" MISSED bug categories: {cats}."
    if rew["lints"]:
        verification += f" TRACE-LINT (degenerate, reward zeroed): {rew['lints']}."
    conversation = [
        {"role": "assistant", "content": assistant},
        {"role": "system", "content": verification},
    ]
    with open(os.path.join(pdir, "conversation.json"), "w") as f:
        json.dump(conversation, f, ensure_ascii=False, indent=2)
    with open(os.path.join(pdir, "target_system_prompt.txt"), "w") as f:
        f.write(system)
    with open(os.path.join(pdir, "target_user_prompt.txt"), "w") as f:
        f.write(user)


def process_one(item: dict, skill_content: str, out_dir: str,
                max_completion_tokens: int, timeout: int) -> dict:
    tid = str(item["id"])
    system = build_system(skill_content)
    user = build_user(item["code"])
    error = ""
    assistant = ""
    try:
        assistant, _usage = chat_target(
            system=system, user=user,
            max_completion_tokens=max_completion_tokens, timeout=timeout,
        )
    except Exception as exc:  # network/CLI failure -> scored as a failed rollout
        error = f"{type(exc).__name__}: {exc}"

    findings = parse_findings(assistant)
    rew = reward(item, findings)
    _write_prediction(out_dir, tid, system, user, assistant, rew)

    fail_reason = ""
    if not rew["hard"]:
        if error:
            fail_reason = f"rollout error: {error}"
        elif rew["lints"]:
            fail_reason = f"degenerate findings ({rew['lints']})"
        elif rew["missed"]:
            fail_reason = "missed categories: " + ", ".join(
                sorted({m["category"] for m in rew["missed"]})
            )
        else:
            fail_reason = f"precision below floor ({rew['precision']})"

    return {
        "id": tid,
        "hard": rew["hard"],
        "soft": rew["soft"],
        "recall": rew["recall"],
        "precision": rew["precision"],
        "caught": rew["caught"],
        "n_planted": rew["n_planted"],
        "n_findings": rew["n_findings"],
        "missed": rew["missed"],
        "lints": rew["lints"],
        "task_description": "Review a Python module and report every defect as JSON findings.",
        "task_type": "code_review",
        "fail_reason": fail_reason,
        "n_turns": 1,
        "error": error,
    }


def run_reviewer_batch(items: list[dict], skill_content: str, out_dir: str,
                       workers: int = 4, max_completion_tokens: int = 4096,
                       timeout: int = 120) -> list[dict]:
    os.makedirs(out_dir, exist_ok=True)
    results: list[dict] = [None] * len(items)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {
            ex.submit(process_one, it, skill_content, out_dir,
                      max_completion_tokens, timeout): i
            for i, it in enumerate(items)
        }
        for fut in as_completed(futs):
            results[futs[fut]] = fut.result()
    return results

"""Pure prompt builders for the specify slice (no skillopt/network dependency)."""

from __future__ import annotations

TASK_FRAME = (
    "\n\n---\n# Task\n"
    "Write a complete feature specification in Markdown for the brief below. "
    "Output ONLY the spec (Markdown), no preamble.\n"
)


def build_system(skill_content: str) -> str:
    return (skill_content or "").strip() + TASK_FRAME


def build_user(brief: str) -> str:
    return f"# Feature brief\n\n{brief}\n"

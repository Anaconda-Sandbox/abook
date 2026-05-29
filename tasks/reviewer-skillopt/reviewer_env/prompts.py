"""Pure prompt builders + findings parser for the reviewer slice.

No skillopt / network dependency — importable standalone (e.g. by the FR-004 contract
test) so the GT-free-prompt guarantee can be checked without installing skillopt.
"""
from __future__ import annotations

import json
import re

TASK_FRAME = (
    "\n\n---\n# Task\n"
    "You are reviewing the Python module below for defects. Report every real bug.\n"
    "Respond with ONLY a JSON array, no prose:\n"
    '[{"line": <int>, "category": "<short_snake_case_label>"}]\n'
    "`line` is the 1-based line number shown in the listing. Report a finding only when "
    "you are confident it is a real bug.\n"
)


def build_system(skill_content: str) -> str:
    return (skill_content or "").strip() + TASK_FRAME


def build_user(code: str) -> str:
    numbered = "\n".join(
        f"{i:>4}  {line}" for i, line in enumerate(code.splitlines(), start=1)
    )
    return "# Module under review (line-numbered)\n```python\n" + numbered + "\n```\n"


def parse_findings(text: str) -> list[dict]:
    """Extract a JSON array of {line, category} from the model response, robustly."""
    if not text:
        return []
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    blob = fenced.group(1) if fenced else None
    if blob is None:
        start, end = text.find("["), text.rfind("]")
        blob = text[start : end + 1] if (start != -1 and end > start) else ""
    try:
        data = json.loads(blob)
    except Exception:
        return []
    out: list[dict] = []
    if isinstance(data, list):
        for d in data:
            if isinstance(d, dict) and isinstance(d.get("line"), int):
                out.append({"line": d["line"], "category": str(d.get("category", ""))})
    return out

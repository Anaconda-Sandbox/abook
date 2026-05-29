# Code Review Skill (seed — deliberately weak)

## Overview
Review the given Python source and report the defects you find.

## Output
Return a JSON array of findings. Each finding is an object:

```json
[{"line": <int>, "category": "<short_snake_case_label>"}]
```

- `line` — 1-based line number where the defect is.
- `category` — a short label naming the defect kind.

Report a defect only when you are confident it is a real bug. Do not report style
preferences. Be precise about the line number.

<!--
HEADROOM (intentionally omitted from this seed; SkillOpt should re-derive it from
missed-bug traces): a checklist of bug categories to scan for — mutable_default_arg,
bare_except, off_by_one, sql_injection, resource_leak, is_none_comparison,
unhandled_keyerror, integer_division, shadowed_builtin, missing_return,
division_by_zero, type_confusion — and the canonical line each maps to.
-->

"""Deterministic reward + trace-lints for the `reviewer` SkillOpt target.

reward(instance, findings) -> dict with:
  hard : 0/1  — all planted bugs caught AND precision >= PRECISION_FLOOR AND no lint
  soft : 0..1 — F1 over planted-bug detection (the gradient signal)
  plus diagnostics consumed by SkillOpt's reflect (recall/precision/missed/lints).

A planted bug is "caught" by a finding when the finding's line is within LINE_TOL of
the planted line AND the categories match (exact, or via SYNONYMS). One finding can
match at most one planted bug; one planted bug is caught at most once.

Anti-cheat:
  - Precision is in the score (F1), so spraying findings does not maximize reward.
  - Trace-lints zero out `hard` on degenerate strategies (spam, every-line). These are
    the *deterministic* anti-cheat layer; an LLM trace-judge is layered on top in the
    notebook for subtle cases.
"""
from __future__ import annotations

LINE_TOL = 2
PRECISION_FLOOR = 0.5
SPAM_RATIO = 3.0  # findings > SPAM_RATIO * planted -> spam lint

SYNONYMS = {
    "mutable_default_arg": {"mutable_default", "default_arg", "mutable_argument"},
    "bare_except": {"broad_except", "bare_except_pass", "silent_except"},
    "off_by_one": {"index_out_of_range", "off_by_one_error", "indexerror"},
    "sql_injection": {"injection", "sqli", "string_formatted_query"},
    "resource_leak": {"file_not_closed", "unclosed_file", "leak"},
    "is_none_comparison": {"none_equality", "eq_none", "none_compare"},
    "unhandled_keyerror": {"keyerror", "missing_key", "unchecked_key"},
    "integer_division": {"floor_division", "int_div", "truncation"},
    "shadowed_builtin": {"builtin_shadow", "shadow", "name_shadowing"},
    "missing_return": {"no_return", "implicit_none_return"},
    "division_by_zero": {"zero_division", "div_zero"},
    "type_confusion": {"type_error", "wrong_type", "type_mismatch"},
}


def _norm(cat: str) -> str:
    return (cat or "").strip().lower().replace("-", "_").replace(" ", "_")


def _cat_match(planted: str, found: str) -> bool:
    p, f = _norm(planted), _norm(found)
    if p == f:
        return True
    return f in SYNONYMS.get(p, set()) or p in SYNONYMS.get(f, set())


def _trace_lints(instance: dict, findings: list[dict]) -> list[str]:
    lints: list[str] = []
    n_planted = max(1, len(instance.get("bugs", [])))
    if len(findings) > SPAM_RATIO * n_planted:
        lints.append("spam_findings")
    n_lines = instance.get("code", "").count("\n") + 1
    flagged = {f.get("line") for f in findings if isinstance(f.get("line"), int)}
    if n_lines and len(flagged) >= 0.8 * n_lines:
        lints.append("flags_nearly_every_line")
    return lints


def reward(instance: dict, findings: list[dict]) -> dict:
    planted = list(instance.get("bugs", []))
    findings = [f for f in (findings or []) if isinstance(f.get("line"), int)]

    matched_planted: set[int] = set()
    matched_findings: set[int] = set()
    for pi, p in enumerate(planted):
        for fi, f in enumerate(findings):
            if fi in matched_findings:
                continue
            if abs(f["line"] - p["line"]) <= LINE_TOL and _cat_match(
                p["category"], f.get("category", "")
            ):
                matched_planted.add(pi)
                matched_findings.add(fi)
                break

    caught = len(matched_planted)
    recall = caught / len(planted) if planted else 0.0
    precision = caught / len(findings) if findings else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    lints = _trace_lints(instance, findings)
    hard = int(
        recall >= 1.0 and precision >= PRECISION_FLOOR and not lints
    )
    missed = [planted[i] for i in range(len(planted)) if i not in matched_planted]

    return {
        "hard": hard,
        "soft": round(f1, 4),
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "caught": caught,
        "n_planted": len(planted),
        "n_findings": len(findings),
        "missed": missed,            # what reflect uses to patch the skill
        "lints": lints,
    }

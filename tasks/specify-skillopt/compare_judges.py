"""Dual-judge the specs produced by a specify run: reference-free vs reference-anchored.

Loads each produced spec (from a run's predictions) + its brief/expected (from instances),
scores it with BOTH judges, and writes a comparison JSON. This isolates the *judge* (same
specs, two judges) so the notebook can show what the anchor changes — the point being that
reference-free judging "purely depends on the judge", while the anchored judge grounds
coverage in concrete expected behaviors.

    TARGET_BACKEND=claude_chat CLAUDE_SETTING_SOURCES="" \
      ./env/bin/python tasks/specify-skillopt/compare_judges.py \
        --run jobs/specify-skillopt-2026-05-29 --out jobs/specify-judge-compare-2026-05-29.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from glob import glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from specify_env.judge import llm_judge, llm_judge_ref  # noqa: E402


def load_expected(instances_dir: str) -> dict[str, dict]:
    out = {}
    for f in glob(os.path.join(instances_dir, "spec_*.json")):
        inst = json.loads(open(f).read())
        out[inst["id"]] = inst
    return out


def collect_specs(run_dir: str) -> dict[str, str]:
    """id -> produced spec text (first occurrence found across the run's predictions)."""
    specs: dict[str, str] = {}
    for conv in sorted(glob(os.path.join(run_dir, "**", "predictions", "*", "conversation.json"), recursive=True)):
        tid = os.path.basename(os.path.dirname(conv))
        if tid in specs:
            continue
        convo = json.loads(open(conv).read())
        spec = next((m["content"] for m in convo if m.get("role") == "assistant"), "")
        if spec:
            specs[tid] = spec
    return specs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="a specify run dir under jobs/")
    ap.add_argument("--instances", default=os.path.join(HERE, "instances"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=6, help="max specs to dual-judge (cost control)")
    args = ap.parse_args()

    expected = load_expected(args.instances)
    specs = collect_specs(args.run)
    ids = [i for i in specs if i in expected][: args.limit]
    if not ids:
        raise SystemExit(f"no specs with matching expected found in {args.run}")

    rows = []
    for tid in ids:
        brief = expected[tid]["brief"]
        exp = expected[tid]["expected"]
        spec = specs[tid]
        free = llm_judge(brief, spec)
        ref = llm_judge_ref(brief, spec, exp)
        rows.append(
            {
                "id": tid,
                "brief": brief,
                "expected": exp,
                "free": {k: free[k] for k in ("overall", "testable", "coverage", "outcome", "notes", "error")},
                "ref": {k: ref[k] for k in ("overall", "testable", "coverage", "outcome", "covered", "notes", "error")},
            }
        )
        print(
            f"{tid}: free.overall={free['overall']} ref.overall={ref['overall']} "
            f"free.cov={free['coverage']} ref.cov={ref['coverage']} covered={ref['covered']}"
        )

    with open(args.out, "w") as f:
        json.dump({"run": args.run, "n": len(rows), "rows": rows}, f, indent=2)
    print(f"\nwrote {len(rows)} dual-judged specs to {args.out}")


if __name__ == "__main__":
    main()

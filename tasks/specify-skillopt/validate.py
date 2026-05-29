"""No-LLM validation that the specify structural reward DISCRIMINATES — on REAL data.

Scores three specs against reward.py:
  good     : a real, well-formed spec from this repo (specs/agentbook_thesis/spec.md)
  degraded : the same spec with sections + FR ids stripped (simulates a weak skill)
  empty    : a bare prose blob (no structure)

Expect good >> degraded >= empty. Also prints the `needs_judge` aspects the
deterministic checker explicitly cannot cover (the LLM trace-judge's job).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from specify_env.reward import reward  # noqa: E402

REPO = Path(__file__).resolve().parents[2]  # tasks/specify-skillopt/ -> repo root
REAL_SPEC = REPO / "specs" / "agentbook_thesis" / "spec.md"


def degrade(md: str) -> str:
    # strip FR ids, MUST, and section headers -> what a weak skill tends to produce
    md = re.sub(r"\*\*FR-?\d+\*\*", "It", md)
    md = re.sub(r"\bMUST\b", "should", md)
    md = re.sub(r"^#{2,3}\s.*$", "", md, flags=re.M)
    return md


def main() -> None:
    if not REAL_SPEC.exists():
        sys.exit(f"real spec not found: {REAL_SPEC}")
    good_md = REAL_SPEC.read_text()
    cases = {
        "good": good_md,
        "degraded": degrade(good_md),
        "empty": "This feature lets users do the thing. It will be good and fast.",
    }
    print(f"scoring against real spec: {REAL_SPEC.relative_to(REPO)}\n")
    print(f"{'spec':10} {'soft':>6} {'hard':>5}  failed_checks")
    results = {}
    for name, md in cases.items():
        r = reward("", md)
        results[name] = r
        print(f"{name:10} {r['soft']:>6} {r['hard']:>5}  {r['failed']}")

    print("\nneeds_judge (deterministic checker CANNOT verify these):")
    for item in results["good"]["needs_judge"]:
        print(f"  - {item}")

    ok = (
        results["good"]["soft"] > 0.9
        and results["good"]["hard"] == 1
        and results["degraded"]["soft"] < results["good"]["soft"]
        and results["empty"]["soft"] < 0.3
    )
    print("\nDISCRIMINATES:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

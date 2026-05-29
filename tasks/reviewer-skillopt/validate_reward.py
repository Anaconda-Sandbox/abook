"""No-LLM validation that the reviewer reward DISCRIMINATES and resists the spam cheat.

This does NOT run any agent — it feeds three deterministic synthetic reviewers into
reward.py to prove the signal separates good/weak/cheat behavior. (Validating the
checker, not reporting optimization results.)

    oracle : reports exactly the planted bugs           -> expect soft=1.0, hard=1
    weak   : reports only ~half (misses some categories) -> expect mid soft, hard=0
    spam   : reports every line as a bug                  -> expect lint-flagged, hard=0
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from reviewer_env.reward import reward  # noqa: E402


def oracle(inst: dict) -> list[dict]:
    return [dict(b) for b in inst["bugs"]]


def weak(inst: dict) -> list[dict]:
    bugs = inst["bugs"]
    keep = bugs[: max(1, len(bugs) // 2)]  # catches roughly half
    return [dict(b) for b in keep]


def spam(inst: dict) -> list[dict]:
    n_lines = inst["code"].count("\n") + 1
    return [{"line": i, "category": "bug"} for i in range(1, n_lines + 1)]


def main() -> None:
    inst_dir = Path(__file__).parent / "instances"
    files = sorted(inst_dir.glob("rev_*.json"))
    if not files:
        sys.exit("no instances — run: python gen_instances.py --out instances --n 60")
    agg: dict[str, list] = {"oracle": [], "weak": [], "spam": []}
    spam_lints = 0
    for f in files:
        inst = json.loads(f.read_text())
        agg["oracle"].append(reward(inst, oracle(inst)))
        agg["weak"].append(reward(inst, weak(inst)))
        sp = reward(inst, spam(inst))
        agg["spam"].append(sp)
        if sp["lints"]:
            spam_lints += 1

    def mean(rs, k):
        return round(sum(r[k] for r in rs) / len(rs), 3)

    print(f"instances: {len(files)}\n")
    print(f"{'reviewer':8} {'soft':>6} {'recall':>7} {'prec':>6} {'hard%':>6}")
    for name, rs in agg.items():
        hard_pct = round(100 * sum(r["hard"] for r in rs) / len(rs))
        print(f"{name:8} {mean(rs, 'soft'):>6} {mean(rs, 'recall'):>7} {mean(rs, 'precision'):>6} {hard_pct:>5}%")
    print(f"\nspam runs caught by trace-lint: {spam_lints}/{len(files)}")

    ok = (
        mean(agg["oracle"], "soft") > 0.95
        and mean(agg["weak"], "soft") < mean(agg["oracle"], "soft")
        and spam_lints == len(files)
    )
    print("\nDISCRIMINATES + ANTI-CHEAT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

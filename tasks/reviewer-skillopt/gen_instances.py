"""Procedural instance generator for the `reviewer` SkillOpt target.

An instance is a Python source file with a known set of *planted* bugs, each at a
known line with a known category. The agent (guided by the reviewer skill) reviews
the file and reports findings; reward = planted-bug recall (F1, see reward.py).

Bugs come from a hand-written catalog of REAL buggy functions (legitimate test
fixtures — the bug is genuinely present). The generator stitches k snippets into one
file and recomputes each planted bug's absolute line. No fabricated data: the source
is real Python and the bugs are real defects.

Usage:
    python gen_instances.py --out instances --n 60 --seed 42
"""
from __future__ import annotations

import argparse
import json
import os
import random

# Each snippet: real buggy function. `bug_line` is 1-based within `src`.
CATALOG: list[dict] = [
    {
        "category": "mutable_default_arg",
        "bug_line": 1,
        "src": (
            "def collect(item, acc=[]):\n"
            "    acc.append(item)\n"
            "    return acc\n"
        ),
    },
    {
        "category": "bare_except",
        "bug_line": 3,
        "src": (
            "def load(path):\n"
            "    try:\n"
            "        return open(path).read()\n"
            "    except:\n"
            "        return None\n"
        ),
    },
    {
        "category": "off_by_one",
        "bug_line": 3,
        "src": (
            "def last_pairs(xs):\n"
            "    out = []\n"
            "    for i in range(len(xs)):\n"
            "        out.append((xs[i], xs[i + 1]))\n"
            "    return out\n"
        ),
    },
    {
        "category": "sql_injection",
        "bug_line": 2,
        "src": (
            "def find_user(cur, name):\n"
            "    cur.execute(\"SELECT * FROM users WHERE name = '%s'\" % name)\n"
            "    return cur.fetchone()\n"
        ),
    },
    {
        "category": "resource_leak",
        "bug_line": 2,
        "src": (
            "def count_lines(path):\n"
            "    f = open(path)\n"
            "    n = sum(1 for _ in f)\n"
            "    return n\n"
        ),
    },
    {
        "category": "is_none_comparison",
        "bug_line": 2,
        "src": (
            "def is_empty(x):\n"
            "    if x == None:\n"
            "        return True\n"
            "    return len(x) == 0\n"
        ),
    },
    {
        "category": "unhandled_keyerror",
        "bug_line": 2,
        "src": (
            "def greet(cfg):\n"
            "    return 'hello ' + cfg['username']\n"
        ),
    },
    {
        "category": "integer_division",
        "bug_line": 2,
        "src": (
            "def mean(xs):\n"
            "    return sum(xs) // len(xs)\n"
        ),
    },
    {
        "category": "shadowed_builtin",
        "bug_line": 1,
        "src": (
            "def tally(list):\n"
            "    total = 0\n"
            "    for x in list:\n"
            "        total += x\n"
            "    return total\n"
        ),
    },
    {
        "category": "missing_return",
        "bug_line": 1,
        "src": (
            "def double_all(xs):\n"
            "    result = [x * 2 for x in xs]\n"
        ),
    },
    {
        "category": "division_by_zero",
        "bug_line": 2,
        "src": (
            "def ratio(a, b):\n"
            "    return a / b\n"
        ),
    },
    {
        "category": "type_confusion",
        "bug_line": 2,
        "src": (
            "def add_id(record, new_id):\n"
            "    record['ids'] += new_id\n"
            "    return record\n"
        ),
    },
]

HEADER = "# module under review — find and report every defect\n\n"


def build_instance(rng: random.Random, k: int) -> dict:
    picks = rng.sample(CATALOG, k)
    lines: list[str] = HEADER.splitlines(keepends=True)
    planted: list[dict] = []
    for snip in picks:
        offset = len(lines)  # snippet's first line is at absolute index offset+1
        lines.extend(snip["src"].splitlines(keepends=True))
        planted.append(
            {"line": offset + snip["bug_line"], "category": snip["category"]}
        )
        lines.append("\n")  # blank separator
    return {"code": "".join(lines), "bugs": planted}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="instances")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-bugs", type=int, default=1)
    ap.add_argument("--max-bugs", type=int, default=3)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(args.seed)
    for i in range(args.n):
        k = rng.randint(args.min_bugs, min(args.max_bugs, len(CATALOG)))
        inst = build_instance(rng, k)
        inst["id"] = f"rev_{i:04d}"
        with open(os.path.join(args.out, f"{inst['id']}.json"), "w") as fh:
            json.dump(inst, fh, indent=2)
    print(f"wrote {args.n} instances to {args.out}/ (seed={args.seed})")


if __name__ == "__main__":
    main()

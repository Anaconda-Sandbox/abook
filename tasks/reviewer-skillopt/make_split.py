"""Materialize a disjoint train/val/test split for the reviewer slice.

Reads a pool of per-instance JSON files (each {"id","code","bugs"}) produced by
candidates/reviewer/gen_instances.py and writes each split as a single JSON array to
``<out>/{train,val,test}/items.json`` — the layout SkillOpt's SplitDataLoader expects in
``split_mode=split_dir``.

    python make_reviewer_split.py --pool /tmp/_revpool --out data/reviewer_split \
        --train 12 --val 6 --test 12 --seed 7
"""
from __future__ import annotations

import argparse
import json
import os
import random
from glob import glob


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, help="dir of rev_*.json instances")
    ap.add_argument("--out", required=True, help="split_dir root to write")
    ap.add_argument("--train", type=int, default=12)
    ap.add_argument("--val", type=int, default=6)
    ap.add_argument("--test", type=int, default=12)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    files = sorted(glob(os.path.join(args.pool, "rev_*.json")))
    pool = [json.loads(open(f).read()) for f in files]
    need = args.train + args.val + args.test
    if len(pool) < need:
        raise SystemExit(f"pool has {len(pool)} instances, need {need}")

    rng = random.Random(args.seed)
    rng.shuffle(pool)
    splits = {
        "train": pool[: args.train],
        "val": pool[args.train : args.train + args.val],
        "test": pool[args.train + args.val : args.train + args.val + args.test],
    }

    ids = {name: {i["id"] for i in items} for name, items in splits.items()}
    assert not (ids["train"] & ids["val"]), "train/val overlap"
    assert not (ids["train"] & ids["test"]), "train/test overlap"
    assert not (ids["val"] & ids["test"]), "val/test overlap"

    for name, items in splits.items():
        d = os.path.join(args.out, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "items.json"), "w") as f:
            json.dump(items, f, indent=2)
    counts = {k: len(v) for k, v in splits.items()}
    print(f"wrote split to {args.out}: {counts} (disjoint, seed={args.seed})")


if __name__ == "__main__":
    main()

"""Materialize a disjoint train/val/test split for the specify slice.

Reads per-instance JSON files (each {"id","brief"}) from a pool dir and writes each split
as a single JSON array to <out>/{train,val,test}/items.json (SplitDataLoader split_dir mode).

    python make_split.py --pool ./instances --out data/specify_split --train 5 --val 2 --test 3 --seed 7
"""

from __future__ import annotations

import argparse
import json
import os
import random
from glob import glob


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--train", type=int, default=5)
    ap.add_argument("--val", type=int, default=2)
    ap.add_argument("--test", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    pool = [json.loads(open(f).read()) for f in sorted(glob(os.path.join(args.pool, "spec_*.json")))]
    need = args.train + args.val + args.test
    if len(pool) < need:
        raise SystemExit(f"pool has {len(pool)} instances, need {need}")
    rng = random.Random(args.seed)
    rng.shuffle(pool)
    splits = {
        "train": pool[: args.train],
        "val": pool[args.train : args.train + args.val],
        "test": pool[args.train + args.val : need],
    }
    ids = {k: {i["id"] for i in v} for k, v in splits.items()}
    assert not (ids["train"] & ids["val"]) and not (ids["train"] & ids["test"]) and not (ids["val"] & ids["test"]), (
        "split overlap"
    )
    for name, items in splits.items():
        d = os.path.join(args.out, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "items.json"), "w") as f:
            json.dump(items, f, indent=2)
    counts = {k: len(v) for k, v in splits.items()}
    print(f"wrote split to {args.out}: {counts} (disjoint, seed={args.seed})")


if __name__ == "__main__":
    main()

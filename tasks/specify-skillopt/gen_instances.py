"""Procedural instance generator for the `specify` SkillOpt target.

An instance is a feature BRIEF plus an `expected` checklist of core behaviors the spec
must cover. The brief is the task input (the agent never sees `expected`); `expected` is
the **reference anchor** the trace-judge scores coverage against (see specify_env/judge.py).
Reference-anchored judging is more reliable than reference-free absolute scoring, which
"purely depends on the judge".

Briefs + expected behaviors are real, hand-authored task definitions — not fabricated results.

Usage:
    python gen_instances.py --out instances --n 10 --seed 7
"""

from __future__ import annotations

import argparse
import json
import os
import random

# (brief, expected core behaviors). `expected` anchors the judge's coverage score.
BRIEFS: list[dict] = [
    {
        "brief": "A CLI that watches a directory and re-runs the test suite whenever a "
        "tracked file changes, debouncing rapid saves.",
        "expected": [
            "watches a directory recursively for file changes",
            "re-runs the test suite on a relevant change",
            "debounces rapid successive saves into one run",
            "lets the user scope which files/paths are tracked",
        ],
    },
    {
        "brief": "A service that accepts a webhook from GitHub and posts a formatted summary "
        "of the PR diff to a Slack channel.",
        "expected": [
            "receives and verifies a GitHub webhook",
            "extracts/summarizes the PR diff",
            "posts a formatted message to a Slack channel",
            "handles webhook delivery failures/retries",
        ],
    },
    {
        "brief": "A feature that lets users export their saved articles as a single EPUB "
        "file, preserving images and reading order.",
        "expected": [
            "selects the user's saved articles",
            "produces a single valid EPUB file",
            "embeds images inline",
            "preserves the original reading order",
        ],
    },
    {
        "brief": "An API rate limiter that allows bursts but enforces a sustained per-key "
        "ceiling, shared across multiple app instances.",
        "expected": [
            "enforces a sustained per-key request ceiling",
            "allows short bursts above the steady rate",
            "shares limit state across multiple instances",
            "returns a clear limit-exceeded response",
        ],
    },
    {
        "brief": "A nightly job that detects duplicate customer records and merges them, "
        "keeping an audit trail of every merge.",
        "expected": [
            "detects duplicate customer records",
            "merges duplicates into one canonical record",
            "writes an audit trail of every merge",
            "runs on a nightly schedule",
        ],
    },
    {
        "brief": "A search box that returns results as the user types, ranking recent and "
        "frequently opened items higher.",
        "expected": [
            "returns results incrementally as the user types",
            "ranks recently opened items higher",
            "ranks frequently opened items higher",
            "stays responsive under fast typing",
        ],
    },
    {
        "brief": "A permissions layer where workspace owners can grant scoped, time-boxed access to external auditors.",
        "expected": [
            "owners grant access to external auditors",
            "access is scoped to specific resources",
            "access is time-boxed and auto-expires",
            "grants are revocable and audited",
        ],
    },
    {
        "brief": "A migration tool that moves a project's issues from one tracker to another "
        "without losing comments or attachments.",
        "expected": [
            "moves issues from a source tracker to a target",
            "preserves comments on each issue",
            "preserves attachments",
            "reports/handles partial-failure during migration",
        ],
    },
    {
        "brief": "A dashboard widget that shows live deployment status across environments "
        "and alerts when a rollout stalls.",
        "expected": [
            "shows deployment status per environment",
            "updates status live",
            "detects when a rollout stalls",
            "raises an alert on a stalled rollout",
        ],
    },
    {
        "brief": "A feature that lets a user schedule a message to send later and edit or "
        "cancel it before it goes out.",
        "expected": [
            "schedules a message to send at a future time",
            "lets the user edit a scheduled message before send",
            "lets the user cancel before send",
            "sends exactly once at the scheduled time",
        ],
    },
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="instances")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(args.seed)
    for i in range(args.n):
        spec = BRIEFS[i % len(BRIEFS)] if i < len(BRIEFS) else rng.choice(BRIEFS)
        inst = {"id": f"spec_{i:04d}", "brief": spec["brief"], "expected": spec["expected"]}
        with open(os.path.join(args.out, f"{inst['id']}.json"), "w") as fh:
            json.dump(inst, fh, indent=2)
    n = min(args.n, len(BRIEFS)) if args.n <= len(BRIEFS) else args.n
    print(f"wrote {n} instances (with expected-behavior anchors) to {args.out}/ (seed={args.seed})")


if __name__ == "__main__":
    main()

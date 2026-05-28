"""Repair an LLM-generated Jupyter notebook.

The eval-improve loop's edit step often hands back a `.ipynb` that is
*syntactically* valid but messy in the small ways ruff catches: dangling
imports, single-char loop variables, lambdas where a `def` would do,
missing `strict=` on `zip`. This module exposes a single function that
normalizes such a notebook in place, plus a `abook-fix` CLI for the
same.

Designed to be called as the **post-edit hygiene step** of the loop:
``rollout → score → reflect → edit → repair_notebook(...) → re-evaluate``.

The repair is non-semantic — it never changes what the notebook
computes, only how it reads.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class RepairReport:
    """What `repair_notebook` did to one notebook."""

    path: str
    json_valid: bool
    ruff_lint_succeeded: bool
    ruff_format_succeeded: bool
    bytes_before: int
    bytes_after: int
    json_error: str | None = None

    @property
    def changed(self) -> bool:
        return self.bytes_before != self.bytes_after


def _ruff_argv() -> list[str]:
    """Resolve how to invoke ruff. Prefers the in-process Python's ruff
    package; falls back to importable in case PATH lookup is unreliable
    (e.g. when invoked from a CLI installed in the same venv)."""
    if importlib.util.find_spec("ruff") is None:
        raise FileNotFoundError(
            "`ruff` is not importable from the current Python. "
            "Install with `pip install ruff` into the same environment."
        )
    return [sys.executable, "-m", "ruff"]


def repair_notebook(path: str | Path) -> RepairReport:
    """Repair a single notebook in place (ruff lint --fix + ruff format).

    Args:
        path: Path to the `.ipynb` file. Must exist.

    Returns:
        A :class:`RepairReport` summarizing what changed.

    Raises:
        FileNotFoundError: if ``path`` is missing or ``ruff`` is not
            importable from the current Python environment.
    """
    nb_path = Path(path)
    if not nb_path.exists():
        raise FileNotFoundError(nb_path)

    ruff_argv = _ruff_argv()
    before_bytes = nb_path.stat().st_size

    # 1. Validate JSON. If the notebook is broken, ruff will also fail,
    #    but a clear error here saves the user a debugging trip.
    try:
        json.loads(nb_path.read_text())
        json_valid = True
        json_error: str | None = None
    except json.JSONDecodeError as e:
        json_valid = False
        json_error = str(e)

    # 2. Lint with auto-fix. Tolerate non-zero exit (means unfixable
    #    issues remain), but flag the call as "didn't succeed."
    lint_proc = subprocess.run(
        [*ruff_argv, "check", "--fix", str(nb_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    ruff_lint_succeeded = lint_proc.returncode == 0

    # 3. Format. Same tolerance: format may rewrite cells; non-zero exit
    #    only means the formatter found issues (e.g. parse errors).
    fmt_proc = subprocess.run(
        [*ruff_argv, "format", str(nb_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    ruff_format_succeeded = fmt_proc.returncode == 0

    after_bytes = nb_path.stat().st_size

    return RepairReport(
        path=str(nb_path),
        json_valid=json_valid,
        ruff_lint_succeeded=ruff_lint_succeeded,
        ruff_format_succeeded=ruff_format_succeeded,
        bytes_before=before_bytes,
        bytes_after=after_bytes,
        json_error=json_error,
    )


def main(argv: list[str] | None = None) -> int:
    """`abook-fix` CLI entry point. Returns process exit code."""
    parser = argparse.ArgumentParser(
        prog="abook-fix",
        description="Repair LLM-generated Jupyter notebooks (ruff lint + format).",
    )
    parser.add_argument(
        "paths",
        type=Path,
        nargs="+",
        help="One or more `.ipynb` paths to repair in place.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object per path instead of a human-readable summary.",
    )
    args = parser.parse_args(argv)

    any_invalid = False
    for path in args.paths:
        report = repair_notebook(path)
        if args.json:
            print(json.dumps(asdict(report)))
        else:
            status = "ok" if report.json_valid else "JSON INVALID"
            changed = "changed" if report.changed else "unchanged"
            print(
                f"{report.path}: {status} | "
                f"lint={'pass' if report.ruff_lint_succeeded else 'fail'} | "
                f"format={'pass' if report.ruff_format_succeeded else 'fail'} | "
                f"{report.bytes_before:>7}B → {report.bytes_after:>7}B ({changed})"
            )
        if not report.json_valid:
            any_invalid = True

    return 1 if any_invalid else 0


if __name__ == "__main__":
    sys.exit(main())

"""Shared setup helpers for the agentbook demo notebooks.

Notebooks run with their working directory set to ``notebooks/``, so the repo
root is found by walking up for a marker file rather than hardcoding a path.
"""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root(marker: str = "pyproject.toml") -> Path:
    """Return the repo root by ascending from cwd until ``marker`` is found."""
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / marker).exists():
            return d
    raise FileNotFoundError(f"could not locate {marker} above {here}")


def bootstrap(load_env: bool = True) -> Path:
    """Make the local ``agentbook`` package importable and load ``.env``.

    Returns the repo root. Idempotent — safe to call from every notebook.
    """
    root = repo_root()
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    if load_env:
        try:
            from dotenv import load_dotenv

            load_dotenv(root / ".env")
        except ImportError:
            # best-effort: python-dotenv is optional; the kernel env may already be set
            pass
    return root

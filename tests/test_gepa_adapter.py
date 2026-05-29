"""Offline tests for the GEPA adapter (no LLM calls, no network).

The live end-to-end run lives in notebooks/gepa_demo.ipynb (real Bedrock). Here
we only check the adapter's substrate-facing contract: construction and the seed
type guard. gepa must be importable (it is an extra: `pip install .[gepa]`).
"""

from __future__ import annotations

import pytest

pytest.importorskip("gepa")  # optional extra: pip install .[gepa]

from agentbook.adapters.gepa_adapter import GepaOptimizer  # noqa: E402
from agentbook.session import Session  # noqa: E402


def _session(seed_artifact: object) -> Session:
    return Session(
        eval_set=["x"], model_client=lambda *_a, **_k: None, slice_kind="system_prompt", seed_artifact=seed_artifact
    )


def test_seed_candidate_requires_component_dict() -> None:
    opt = GepaOptimizer(_session({"system_prompt": "hi"}), task_lm="t", reflection_lm="r")
    assert opt.seed_candidate == {"system_prompt": "hi"}


def test_seed_candidate_rejects_non_dict() -> None:
    opt = GepaOptimizer(_session("a bare string"), task_lm="t", reflection_lm="r")
    with pytest.raises(TypeError):
        _ = opt.seed_candidate

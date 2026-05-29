"""Offline tests for the Claude-agent (driver-mode) adapter.

The live rollout shells out to the `claude` CLI; here we only exercise the pure
stream-json parser, the answer scorer, and Protocol conformance — no subprocess,
no network. The transcript below is a *minimal synthetic* stream-json sample
covering the event types the parser cares about (assistant tool_use, user
tool_result, final result). It is deliberately tiny and carries no real session
data — unlike a captured `claude -p` log, whose init event leaks the full
environment.
"""

from __future__ import annotations

import json

from agentbook.adapters.claude_agent_adapter import ClaudeAgentOptimizer, parse_stream_json
from agentbook.contract import Optimizer, Trace
from agentbook.session import Session

# A 2-turn agent episode: think → Bash tool_use → tool_result → text answer → result.
TRANSCRIPT = "\n".join(
    json.dumps(e)
    for e in [
        {"type": "system", "subtype": "init", "session_id": "test"},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "echo $((17 * 23))"}}
                ],
            },
        },
        {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}},  # ignored
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"tool_use_id": "t1", "type": "tool_result", "content": "391", "is_error": False}],
            },
        },
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "391"}]}},
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "num_turns": 2,
            "result": "391",
            "total_cost_usd": 0.01,
            "usage": {"input_tokens": 1200, "output_tokens": 8},
        },
    ]
)


def _session() -> Session:
    return Session(
        eval_set=[],
        model_client=lambda *_a, **_k: None,
        slice_kind="system_prompt",
        seed_artifact="You are a helpful agent.",
    )


def test_parse_stream_json_pairs_tools_and_answer() -> None:
    res = parse_stream_json(TRANSCRIPT)
    assert res.answer == "391"
    assert res.num_turns == 2
    assert not res.is_error
    assert [tc.name for tc in res.tool_calls] == ["Bash"]
    assert res.tool_calls[0].input["command"] == "echo $((17 * 23))"
    assert res.tool_calls[0].result == "391" and not res.tool_calls[0].is_error
    assert res.cost_usd == 0.01 and res.output_tokens == 8


def test_parse_ignores_unknown_and_malformed_lines() -> None:
    res = parse_stream_json('not json\n{"type":"result","result":"ok","num_turns":1}\n')
    assert res.answer == "ok" and res.num_turns == 1


def test_optimizer_satisfies_protocol() -> None:
    assert isinstance(ClaudeAgentOptimizer(_session()), Optimizer)


def test_evaluate_scores_gold_substring() -> None:
    opt = ClaudeAgentOptimizer(_session())
    traces = [
        Trace(candidate_id="c", eval_id="t1", inputs={"gold": "391"}, output="The answer is 391."),
        Trace(candidate_id="c", eval_id="t2", inputs={"gold": "42"}, output="I think it is 7."),
    ]
    assert opt.evaluate(traces) == {"t1": 1.0, "t2": 0.0}

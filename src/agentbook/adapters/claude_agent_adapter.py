"""Claude-agent adapter — a *driver-mode* optimizer over a real tool-using agent.

Unlike the engine-mode adapters (GEPA, SkillOpt), this one drives the loop arrow
by arrow through :func:`agentbook.loop.run_iteration`: each ``rollout`` runs a real
multi-turn ``claude -p`` agent (with a Bash tool) on a task, the stream-json events
are parsed into a :class:`~agentbook.contract.Trace` (capturing the tool calls and
the final answer), ``evaluate`` checks the answer against a gold value, and
``reflect``/``edit`` rewrite the **system prompt** under optimization.

The rollout is genuinely agentic — the model thinks, calls a tool, reads the result,
and answers (``num_turns`` > 1) — so the Traces carry real ``tool_use``/``tool_result``
pairs, not single-shot Q&A.

State is in-memory (the candidate system prompts live in the Session). The only
external dependency is the local ``claude`` CLI; nothing is imported at module load,
so this file is import-safe without it.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any

from agentbook.contract import Reflection, Trace
from agentbook.session import Session


@dataclass
class ToolCall:
    """One tool_use paired with its tool_result from a stream-json transcript."""

    name: str
    input: dict[str, Any]
    result: str = ""
    is_error: bool = False


@dataclass
class AgentResult:
    """Parsed outcome of one ``claude -p --output-format stream-json`` run."""

    answer: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    num_turns: int = 0
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    is_error: bool = False


def parse_stream_json(text: str) -> AgentResult:
    """Parse the JSONL emitted by ``claude -p --output-format stream-json``.

    Pairs each assistant ``tool_use`` block with the matching ``tool_result`` and
    pulls the final answer + usage from the terminating ``result`` event. Pure and
    offline — unknown/irrelevant event types (hooks, rate limits) are ignored.
    """
    tool_uses: dict[str, ToolCall] = {}
    order: list[str] = []
    answer = ""
    num_turns = 0
    cost_usd = 0.0
    in_tok = out_tok = 0
    is_error = False

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate the occasional non-JSON log line
        etype = ev.get("type")
        if etype == "assistant":
            for block in ev.get("message", {}).get("content", []) or []:
                if block.get("type") == "tool_use":
                    tid = block.get("id", "")
                    tool_uses[tid] = ToolCall(name=block.get("name", ""), input=block.get("input", {}) or {})
                    order.append(tid)
        elif etype == "user":
            for block in ev.get("message", {}).get("content", []) or []:
                if block.get("type") == "tool_result":
                    tid = block.get("tool_use_id", "")
                    if tid in tool_uses:
                        content = block.get("content", "")
                        if isinstance(content, list):  # content can be a list of blocks
                            content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
                        tool_uses[tid].result = str(content)
                        tool_uses[tid].is_error = bool(block.get("is_error", False))
        elif etype == "result":
            answer = str(ev.get("result", "") or "")
            num_turns = int(ev.get("num_turns", 0) or 0)
            cost_usd = float(ev.get("total_cost_usd", 0.0) or 0.0)
            usage = ev.get("usage", {}) or {}
            in_tok = int(usage.get("input_tokens", 0) or 0)
            out_tok = int(usage.get("output_tokens", 0) or 0)
            is_error = bool(ev.get("is_error", False))

    return AgentResult(
        answer=answer,
        tool_calls=[tool_uses[t] for t in order],
        num_turns=num_turns,
        cost_usd=cost_usd,
        input_tokens=in_tok,
        output_tokens=out_tok,
        is_error=is_error,
    )


def run_agent(
    task_prompt: str,
    *,
    system_prompt: str | None = None,
    model: str = "claude-sonnet-4-6",
    allowed_tools: tuple[str, ...] = ("Bash",),
    max_turns: int = 6,
    timeout: int = 120,
) -> AgentResult:
    """Run one real ``claude -p`` agent episode and parse its stream-json transcript."""
    cmd = [
        "claude",
        "-p",
        task_prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--allowedTools",
        ",".join(allowed_tools),
        "--permission-mode",
        "bypassPermissions",
        "--model",
        model,
        "--max-turns",
        str(max_turns),
    ]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return parse_stream_json(proc.stdout)


class ClaudeAgentOptimizer:
    """Driver-mode optimizer that evolves a system prompt for a tool-using agent.

    Args:
        session: the live substrate session (holds candidate system prompts).
        model: model for the task agent rollouts (default: cheap Haiku).
        reflect_model: model that proposes the improved system prompt.
    """

    def __init__(
        self, session: Session, *, model: str = "claude-sonnet-4-6", reflect_model: str = "claude-sonnet-4-6"
    ) -> None:
        self.session = session
        self.model = model
        self.reflect_model = reflect_model
        self.last_results: dict[str, AgentResult] = {}

    def rollout(self, candidate: Any, eval_set: Any) -> list[Trace]:
        """Run the agent (system_prompt=``candidate``) over each task in ``eval_set``.

        Each eval example is a dict ``{"id", "prompt", "gold"}``. The resulting Trace
        carries the answer plus the real tool calls / turns / cost as signals.
        """
        traces: list[Trace] = []
        for ex in eval_set:
            res = run_agent(ex["prompt"], system_prompt=str(candidate), model=self.model)
            self.last_results[ex["id"]] = res
            traces.append(
                Trace(
                    candidate_id=candidate,
                    eval_id=ex["id"],
                    inputs=ex,
                    output=res.answer,
                    signals={
                        "tool_calls": [tc.name for tc in res.tool_calls],
                        "num_turns": res.num_turns,
                        "cost_usd": res.cost_usd,
                        "tokens": {"in": res.input_tokens, "out": res.output_tokens},
                    },
                )
            )
        return traces

    def evaluate(self, traces: list[Trace]) -> dict[str, float]:
        """Score 1.0 when the agent's answer contains the task's gold value."""
        scores: dict[str, float] = {}
        for t in traces:
            gold = str(t.inputs.get("gold", "")).strip().lower()
            scores[t.eval_id] = 1.0 if gold and gold in t.output.strip().lower() else 0.0
        return scores

    def reflect(self, candidate: Any, traces: list[Trace]) -> Reflection:
        """Ask the reflect model to rewrite the system prompt, given the failures."""
        failures = [
            f"- task {t.eval_id}: asked {t.inputs['prompt']!r}, agent answered {t.output!r} "
            f"(tools: {t.signals.get('tool_calls')}), expected to contain {t.inputs['gold']!r}"
            for t in traces
            if t.failed
        ]
        if not failures:
            return Reflection(
                from_candidate_id=candidate,
                proposed_artifact=candidate,
                rationale="all tasks passed; no edit",
                llm_calls=0,
            )
        meta = (
            "You are improving the SYSTEM PROMPT given to a tool-using agent that answers "
            "questions by running shell commands via a Bash tool.\n\n"
            f"Current system prompt:\n---\n{candidate}\n---\n\n"
            "It failed these tasks:\n" + "\n".join(failures) + "\n\n"
            "Rewrite the system prompt so the agent uses the Bash tool correctly and returns "
            "ONLY the exact answer. Reply with the new system prompt text only, no preamble."
        )
        res = run_agent(meta, system_prompt=None, model=self.reflect_model, allowed_tools=())
        proposed = res.answer.strip() or str(candidate)
        return Reflection(
            from_candidate_id=candidate,
            proposed_artifact=proposed,
            rationale="rewrote system prompt from failure traces",
            llm_calls=1,
        )

    def edit(self, reflection: Reflection) -> Any:
        """The new candidate artifact is the proposed system prompt."""
        return reflection.proposed_artifact

    def gate(self, parent: Any, child: Any) -> bool:
        """Keep the child only if it scores at least as well as the parent."""
        return bool(child.mean_score >= parent.mean_score)

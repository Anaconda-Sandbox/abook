"""FR contract tests for the reviewer slice (run WITHOUT skillopt installed).

Imports only the skillopt-free modules (prompts.py, reward.py). Guards two anti-cheat
invariants from specs/skillopt-skill-optimization/spec.md:
  FR-004 — ground truth never enters the agent's prompt.
  FR-005 — degenerate (spam) findings are deterministically zeroed by a trace-lint.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts import build_system, build_user  # noqa: E402
from reward import reward  # noqa: E402

INSTANCE = {
    "id": "rev_test",
    "code": (
        "def collect(item, acc=[]):\n"
        "    acc.append(item)\n"
        "    return acc\n"
        "\n"
        "def ratio(a, b):\n"
        "    return a / b\n"
        "\n"
        "def is_empty(x):\n"
        "    if x == None:\n"
        "        return True\n"
        "    return len(x) == 0\n"
    ),
    "bugs": [
        {"line": 1, "category": "mutable_default_arg"},
        {"line": 9, "category": "is_none_comparison"},
    ],
}


def test_fr004_ground_truth_not_in_prompt():
    """The agent must never see the planted-bug answer key."""
    system = build_system("Review the module and report defects as JSON findings.")
    user = build_user(INSTANCE["code"])
    prompt = system + "\n" + user
    # the planted ANSWER must not leak: not the category labels, nor the serialized bug list
    for bug in INSTANCE["bugs"]:
        assert bug["category"] not in prompt, f"planted category {bug['category']!r} leaked"
    assert json.dumps(INSTANCE["bugs"]) not in prompt, "serialized planted-bug list leaked"
    assert "category" not in user, "answer-shaped 'category' field leaked into code prompt"


def test_fr005_spam_findings_zeroed():
    """Reporting every line as a bug (recall hack) is caught and reward-zeroed."""
    n_lines = INSTANCE["code"].count("\n") + 1
    spam = [{"line": i, "category": "bug"} for i in range(1, n_lines + 1)]
    rew = reward(INSTANCE, spam)
    assert rew["hard"] == 0, "spam should not earn a hard pass"
    assert "spam_findings" in rew["lints"], "spam_findings trace-lint should fire"


if __name__ == "__main__":
    test_fr004_ground_truth_not_in_prompt()
    test_fr005_spam_findings_zeroed()
    print("FR-004 + FR-005 contract tests PASS")

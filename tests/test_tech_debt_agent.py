"""
Tests for TechDebtAgent.

All tests use a mocked Ollama client — no real API calls.

Run: pytest tests/test_tech_debt_agent.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from agents.context import AgentContext
from agents.tech_debt_agent import TechDebtAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ollama_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.message.content = text
    return resp


def make_context(code: str = "def foo(): pass", review_issues: list = None) -> AgentContext:
    ctx = AgentContext(code=code, filename="test.py", language="python")
    ctx.review_issues = review_issues or []
    return ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTechDebtAgentParsing:

    def test_parses_debt_score_and_hotspots(self):
        """TechDebtAgent should write debt_score and debt_hotspots to context."""
        payload = {
            "debt_score": 72,
            "hotspots": [
                {"line": 10, "description": "Long function", "severity": "HIGH"},
                {"line": 25, "description": "Duplicate logic", "severity": "MEDIUM"},
            ],
            "rationale": "High complexity and duplication."
        }
        mock_resp = make_ollama_response(json.dumps(payload))

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_resp
            agent = TechDebtAgent()
            ctx = agent.run(make_context())

        assert ctx.debt_score == 72
        assert len(ctx.debt_hotspots) == 2
        assert ctx.debt_hotspots[0]["severity"] == "HIGH"

    def test_debt_score_is_always_integer(self):
        """debt_score must be cast to int even if LLM returns a float."""
        payload = {"debt_score": 45.9, "hotspots": [], "rationale": "Moderate debt."}
        mock_resp = make_ollama_response(json.dumps(payload))

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_resp
            agent = TechDebtAgent()
            ctx = agent.run(make_context())

        assert isinstance(ctx.debt_score, int)
        assert ctx.debt_score == 45

    def test_handles_clean_code_with_zero_hotspots(self):
        """TechDebtAgent should handle pristine code returning score <= 20 and empty hotspots."""
        payload = {"debt_score": 5, "hotspots": [], "rationale": "Very clean code."}
        mock_resp = make_ollama_response(json.dumps(payload))

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_resp
            agent = TechDebtAgent()
            ctx = agent.run(make_context())

        assert ctx.debt_score == 5
        assert ctx.debt_hotspots == []

    def test_strips_markdown_code_blocks(self):
        """TechDebtAgent should strip ```json fences from LLM response."""
        payload = {"debt_score": 30, "hotspots": [], "rationale": "Minor issues."}
        wrapped = f"```json\n{json.dumps(payload)}\n```"
        mock_resp = make_ollama_response(wrapped)

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_resp
            agent = TechDebtAgent()
            ctx = agent.run(make_context())

        assert ctx.debt_score == 30

    def test_invalid_json_appends_to_errors(self):
        """TechDebtAgent should not crash on bad JSON — logs to errors instead."""
        mock_resp = make_ollama_response("not json at all")

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_resp
            agent = TechDebtAgent()
            ctx = agent.run(make_context())

        assert len(ctx.errors) == 1
        assert "TechDebtAgent" in ctx.errors[0]
        assert ctx.debt_score is None

    def test_includes_review_issues_in_prompt(self):
        """TechDebtAgent should pass prior review issues to the LLM."""
        issues = [{"line": 3, "message": "SQL injection risk", "severity": "CRITICAL"}]
        payload = {"debt_score": 80, "hotspots": [], "rationale": "Critical issues found."}
        mock_resp = make_ollama_response(json.dumps(payload))

        with patch("ollama.Client") as MockClient:
            instance = MockClient.return_value
            instance.chat.return_value = mock_resp
            agent = TechDebtAgent()
            agent.run(make_context(review_issues=issues))

            call_kwargs = instance.chat.call_args.kwargs
            messages = call_kwargs.get("messages", [])
            user_content = next((m["content"] for m in messages if m["role"] == "user"), "")
            assert "SQL injection risk" in user_content


class TestTechDebtAgentValidation:

    def test_raises_if_code_is_empty(self):
        """TechDebtAgent should raise ValueError when code is not provided."""
        with patch("ollama.Client"):
            agent = TechDebtAgent()
        ctx = AgentContext(code="", filename="test.py", language="python")

        with pytest.raises(ValueError, match="code"):
            agent.run(ctx)

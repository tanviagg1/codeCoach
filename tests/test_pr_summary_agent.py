"""
Tests for PRSummaryAgent.

All tests use a mocked Ollama client — no real API calls.

Run: pytest tests/test_pr_summary_agent.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from agents.context import AgentContext
from agents.pr_summary_agent import PRSummaryAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ollama_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.message.content = text
    return resp


def make_context() -> AgentContext:
    ctx = AgentContext(code="def foo(): pass", filename="app.py", language="python")
    ctx.review_summary = "Two security issues found."
    ctx.explanation = "This module handles user authentication."
    ctx.debt_score = 65
    ctx.debt_hotspots = [{"line": 10, "description": "Long function", "severity": "HIGH"}]
    ctx.review_issues = [
        {"line": 5, "message": "No input validation", "severity": "HIGH"},
        {"line": 12, "message": "Hardcoded secret", "severity": "CRITICAL"},
    ]
    return ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPRSummaryAgentParsing:

    def test_parses_title_and_body(self):
        """PRSummaryAgent should write pr_title and pr_body to context."""
        payload = {
            "title": "fix(auth): removed hardcoded credentials and added validation",
            "body": "## Summary\n- Removed hardcoded secret\n- Added input validation"
        }
        mock_resp = make_ollama_response(json.dumps(payload))

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_resp
            agent = PRSummaryAgent()
            ctx = agent.run(make_context())

        assert ctx.pr_title == payload["title"]
        assert ctx.pr_body == payload["body"]

    def test_strips_markdown_code_blocks(self):
        """PRSummaryAgent should strip ```json fences from LLM response."""
        payload = {"title": "chore: cleanup", "body": "## Summary\n- Cleaned up code"}
        wrapped = f"```json\n{json.dumps(payload)}\n```"
        mock_resp = make_ollama_response(wrapped)

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_resp
            agent = PRSummaryAgent()
            ctx = agent.run(make_context())

        assert ctx.pr_title == "chore: cleanup"

    def test_invalid_json_appends_to_errors(self):
        """PRSummaryAgent should not crash on bad JSON — logs to errors instead."""
        mock_resp = make_ollama_response("not valid json")

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_resp
            agent = PRSummaryAgent()
            ctx = agent.run(make_context())

        assert len(ctx.errors) == 1
        assert "PRSummaryAgent" in ctx.errors[0]
        assert ctx.pr_title == ""
        assert ctx.pr_body == ""

    def test_handles_missing_upstream_data(self):
        """PRSummaryAgent should run even if prior agents produced no output."""
        payload = {"title": "chore: empty review", "body": "## Summary\n- No issues found"}
        mock_resp = make_ollama_response(json.dumps(payload))

        ctx = AgentContext(code="def foo(): pass", filename="app.py", language="python")
        # No review_summary, explanation, debt_score — all defaults

        with patch("ollama.Client") as MockClient:
            MockClient.return_value.chat.return_value = mock_resp
            agent = PRSummaryAgent()
            result = agent.run(ctx)

        assert result.pr_title == "chore: empty review"

    def test_upstream_context_included_in_prompt(self):
        """PRSummaryAgent should pass review summary and debt info to the LLM."""
        payload = {"title": "fix: security patches", "body": "## Summary\n- Fixed issues"}
        mock_resp = make_ollama_response(json.dumps(payload))

        with patch("ollama.Client") as MockClient:
            instance = MockClient.return_value
            instance.chat.return_value = mock_resp
            agent = PRSummaryAgent()
            agent.run(make_context())

            call_kwargs = instance.chat.call_args.kwargs
            messages = call_kwargs.get("messages", [])
            user_content = next((m["content"] for m in messages if m["role"] == "user"), "")
            assert "Two security issues found." in user_content
            assert "app.py" in user_content

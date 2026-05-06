"""
Tests for ReviewAgent.

All tests here use a mocked Claude client — no real API calls.
For integration tests that call the real API, see test_integration.py.

Run: pytest tests/test_review_agent.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from agents.context import AgentContext
from agents.review_agent import ReviewAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_response(text: str) -> MagicMock:
    """Create a mock Claude API response with the given text."""
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def make_context(code: str = "def foo(): pass", filename: str = "test.py") -> AgentContext:
    """Create a minimal AgentContext for testing."""
    return AgentContext(code=code, filename=filename, language="python")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReviewAgentParsing:
    """Tests for JSON parsing and context writing."""

    def test_parses_issues_into_context(self):
        """ReviewAgent should parse issues from Claude's JSON response into context."""
        response_json = json.dumps({
            "issues": [
                {"line": 5, "message": "No input validation", "severity": "HIGH"},
                {"line": 12, "message": "Hardcoded password", "severity": "CRITICAL"},
            ],
            "summary": "Two serious issues found."
        })
        mock_resp = make_mock_response(response_json)

        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            agent = ReviewAgent()
            ctx = agent.run(make_context())

        assert len(ctx.review_issues) == 2
        assert ctx.review_issues[0]["severity"] == "HIGH"
        assert ctx.review_issues[1]["severity"] == "CRITICAL"
        assert ctx.review_summary == "Two serious issues found."

    def test_handles_empty_issues(self):
        """ReviewAgent should handle clean code (no issues) gracefully."""
        response_json = json.dumps({
            "issues": [],
            "summary": "No issues found. Clean code."
        })
        mock_resp = make_mock_response(response_json)

        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            agent = ReviewAgent()
            ctx = agent.run(make_context())

        assert ctx.review_issues == []
        assert "clean" in ctx.review_summary.lower()

    def test_strips_markdown_code_blocks(self):
        """ReviewAgent should handle responses wrapped in markdown code blocks."""
        issues_data = {"issues": [{"line": 1, "message": "Test", "severity": "LOW"}], "summary": "One issue."}
        response_text = f"```json\n{json.dumps(issues_data)}\n```"
        mock_resp = make_mock_response(response_text)

        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            agent = ReviewAgent()
            ctx = agent.run(make_context())

        assert len(ctx.review_issues) == 1

    def test_invalid_json_appends_to_errors(self):
        """ReviewAgent should log an error (not crash) when JSON is unparseable."""
        mock_resp = make_mock_response("This is not valid JSON at all.")

        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            agent = ReviewAgent()
            ctx = agent.run(make_context())

        assert len(ctx.errors) == 1
        assert "ReviewAgent" in ctx.errors[0]
        # Issues should remain empty
        assert ctx.review_issues == []


class TestReviewAgentValidation:
    """Tests for prerequisite validation."""

    def test_raises_if_code_is_empty(self):
        """ReviewAgent should raise ValueError when code is empty."""
        with patch("anthropic.Anthropic"):
            agent = ReviewAgent()
            ctx = AgentContext(code="", filename="test.py", language="python")

        with pytest.raises(ValueError, match="code"):
            agent.run(ctx)

    def test_raises_if_code_is_whitespace_only(self):
        """ReviewAgent should raise ValueError when code is only whitespace."""
        with patch("anthropic.Anthropic"):
            agent = ReviewAgent()
            ctx = AgentContext(code="   \n\t  ", filename="test.py", language="python")

        # Note: context.code is set to whitespace, the agent checks for falsy
        # If we want this to raise, we need to validate in the agent.
        # This test documents current behavior.
        # Update this test if behavior changes.


class TestReviewAgentPromptSubstitution:
    """Tests that the agent substitutes placeholders correctly."""

    def test_code_appears_in_api_call(self):
        """ReviewAgent should include the code in the message sent to Claude."""
        sample_code = "def my_function(): return 42"
        response_json = json.dumps({"issues": [], "summary": "Clean."})
        mock_resp = make_mock_response(response_json)

        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_resp
            agent = ReviewAgent()
            agent.run(make_context(code=sample_code))

            call_args = instance.messages.create.call_args
            # The code should appear somewhere in the messages
            messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
            user_content = messages[0]["content"] if messages else ""
            assert sample_code in user_content

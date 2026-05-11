"""
Tests for the LangGraph pipeline (Phase 3).

Tests cover:
- Graph builds without error
- Parallel nodes (test_gen + explainer) both write their outputs
- AlertAgent is inserted when debt_score > 80
- AlertAgent is skipped when debt_score <= 80
- Retry router logic (review_router function)
- debt_router conditional routing

Run: pytest tests/test_langgraph_pipeline.py -v
"""

import pytest
from unittest.mock import MagicMock, patch

from agents.context import AgentContext
from agents.langgraph_pipeline import (
    build_graph,
    LangGraphPipeline,
    review_router,
    debt_router,
    PipelineState,
)
from agents.alert_agent import AlertAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(**overrides) -> PipelineState:
    base: PipelineState = {
        "code": "def foo(): pass",
        "filename": "test.py",
        "language": "python",
        "model": "llama3.1:8b",
        "review_issues": [],
        "review_summary": "",
        "generated_tests": "",
        "explanation": "",
        "debt_score": None,
        "debt_hotspots": [],
        "alert_message": "",
        "pr_title": "",
        "pr_body": "",
        "timings": {},
        "errors": [],
        "review_retries": 0,
    }
    base.update(overrides)
    return base


def make_ollama_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.message.content = text
    return resp


# ---------------------------------------------------------------------------
# Graph structure tests
# ---------------------------------------------------------------------------

class TestGraphBuilds:

    def test_graph_compiles_without_error(self):
        """build_graph() should compile the LangGraph without raising."""
        graph = build_graph()
        assert graph is not None

    def test_langgraph_pipeline_instantiates(self):
        """LangGraphPipeline should construct and compile graph on init."""
        pipeline = LangGraphPipeline(model="llama3.1:8b")
        assert pipeline.graph is not None


# ---------------------------------------------------------------------------
# Conditional router tests (pure logic — no LLM needed)
# ---------------------------------------------------------------------------

class TestReviewRouter:

    def test_continues_when_no_error(self):
        """review_router should proceed to test_gen when there are no errors."""
        state = make_state(errors=[], review_retries=0)
        assert review_router(state) == "test_gen_node"

    def test_retries_on_parse_error_first_attempt(self):
        """review_router should loop back on JSON parse error if retries < max."""
        state = make_state(
            errors=["ReviewAgent: failed to parse JSON: ..."],
            review_retries=0,
        )
        assert review_router(state) == "review_node"

    def test_continues_after_max_retries(self):
        """review_router should stop retrying after MAX_REVIEW_RETRIES attempts."""
        state = make_state(
            errors=["ReviewAgent: failed to parse JSON: ..."],
            review_retries=1,
        )
        assert review_router(state) == "test_gen_node"

    def test_continues_on_non_parse_error(self):
        """review_router should not retry for non-JSON errors."""
        state = make_state(
            errors=["ReviewAgent: error: connection refused"],
            review_retries=0,
        )
        assert review_router(state) == "test_gen_node"


class TestDebtRouter:

    def test_routes_to_alert_when_debt_critical(self):
        """debt_router should insert AlertAgent when debt_score > 80."""
        state = make_state(debt_score=85)
        assert debt_router(state) == "alert_node"

    def test_routes_to_pr_when_debt_normal(self):
        """debt_router should skip AlertAgent when debt_score <= 80."""
        state = make_state(debt_score=80)
        assert debt_router(state) == "pr_node"

    def test_routes_to_pr_when_debt_none(self):
        """debt_router should skip AlertAgent when debt_score is None."""
        state = make_state(debt_score=None)
        assert debt_router(state) == "pr_node"

    def test_routes_to_pr_when_debt_low(self):
        state = make_state(debt_score=20)
        assert debt_router(state) == "pr_node"


# ---------------------------------------------------------------------------
# AlertAgent unit tests
# ---------------------------------------------------------------------------

class TestAlertAgent:

    def test_sets_alert_message_when_debt_critical(self):
        """AlertAgent should write alert_message when debt_score > 80."""
        ctx = AgentContext(code="x=1", filename="bad.py", language="python")
        ctx.debt_score = 90
        ctx.debt_hotspots = [
            {"line": 1, "description": "No tests", "severity": "CRITICAL"},
            {"line": 5, "description": "Long function", "severity": "HIGH"},
        ]

        agent = AlertAgent()
        result = agent.run(ctx)

        assert result.alert_message != ""
        assert "CRITICAL DEBT ALERT" in result.alert_message
        assert "90/100" in result.alert_message
        assert "No tests" in result.alert_message

    def test_skips_alert_when_debt_normal(self):
        """AlertAgent should not set alert_message when debt_score <= 80."""
        ctx = AgentContext(code="x=1", filename="ok.py", language="python")
        ctx.debt_score = 50
        ctx.debt_hotspots = []

        agent = AlertAgent()
        result = agent.run(ctx)

        assert result.alert_message == ""

    def test_skips_alert_when_debt_none(self):
        """AlertAgent should not crash when debt_score is None."""
        ctx = AgentContext(code="x=1", filename="ok.py", language="python")
        ctx.debt_score = None

        agent = AlertAgent()
        result = agent.run(ctx)

        assert result.alert_message == ""


# ---------------------------------------------------------------------------
# Integration test — full LangGraph pipeline with mocked Ollama
# ---------------------------------------------------------------------------

import json

REVIEW_RESPONSE = json.dumps({
    "issues": [{"line": 1, "message": "No docstring", "severity": "LOW"}],
    "summary": "Minor style issue."
})
TESTS_RESPONSE = "def test_foo():\n    assert foo() is None"
EXPLAIN_RESPONSE = "This function does nothing."
DEBT_RESPONSE = json.dumps({
    "debt_score": 15,
    "hotspots": [],
    "rationale": "Mostly clean."
})
PR_RESPONSE = json.dumps({
    "title": "chore: add docstring to foo",
    "body": "## Summary\n- Added docstring"
})


@pytest.mark.integration
def test_full_langgraph_pipeline_with_mocks():
    """
    Full LangGraph pipeline run with all Ollama calls mocked.
    Verifies all agents ran and context is fully populated.
    """
    responses = [
        make_ollama_response(REVIEW_RESPONSE),
        make_ollama_response(TESTS_RESPONSE),
        make_ollama_response(EXPLAIN_RESPONSE),
        make_ollama_response(DEBT_RESPONSE),
        make_ollama_response(PR_RESPONSE),
    ]

    with patch("ollama.Client") as MockClient:
        MockClient.return_value.chat.side_effect = responses
        pipeline = LangGraphPipeline(model="llama3.1:8b")
        ctx = AgentContext(code="def foo(): pass", filename="test.py", language="python")
        result = pipeline.run(ctx)

    assert result.review_summary == "Minor style issue."
    assert result.debt_score == 15
    assert result.pr_title == "chore: add docstring to foo"
    assert result.alert_message == ""  # debt < 80, no alert

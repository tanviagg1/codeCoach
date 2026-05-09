"""
Integration tests — these call the real Ollama API (llama3.1:8b must be running).

Skip these in CI or when Ollama is not available:
    pytest tests/ -m "not integration"

Run only integration tests:
    pytest tests/test_integration.py -v
"""

import pytest

from agents.context import AgentContext
from agents.tech_debt_agent import TechDebtAgent
from agents.pr_summary_agent import PRSummaryAgent
from agents.pipeline import SequentialPipeline
from agents.review_agent import ReviewAgent


SAMPLE_CODE = """
import os

def get_user(user_id):
    password = "secret123"
    query = "SELECT * FROM users WHERE id = " + str(user_id)
    result = os.system(query)
    return result

def process(data):
    for i in range(len(data)):
        for j in range(len(data)):
            if data[i] == data[j]:
                print(data[i])
"""


@pytest.mark.integration
def test_tech_debt_agent_returns_valid_score():
    """TechDebtAgent must return an integer debt_score between 0 and 100."""
    ctx = AgentContext(code=SAMPLE_CODE, filename="bad.py", language="python")
    agent = TechDebtAgent()
    result = agent.run(ctx)

    assert result.debt_score is not None, f"Errors: {result.errors}"
    assert isinstance(result.debt_score, int)
    assert 0 <= result.debt_score <= 100


@pytest.mark.integration
def test_tech_debt_agent_finds_hotspots_in_bad_code():
    """TechDebtAgent should identify hotspots in obviously bad code."""
    ctx = AgentContext(code=SAMPLE_CODE, filename="bad.py", language="python")
    agent = TechDebtAgent()
    result = agent.run(ctx)

    assert result.debt_score is not None
    assert result.debt_score > 30, "Bad sample code should have moderate-to-high debt"


@pytest.mark.integration
def test_pr_summary_agent_generates_title_and_body():
    """PRSummaryAgent must produce a non-empty pr_title and pr_body."""
    ctx = AgentContext(code=SAMPLE_CODE, filename="bad.py", language="python")
    ctx.review_summary = "Found hardcoded password and SQL injection risk."
    ctx.explanation = "Queries a user database using raw SQL."
    ctx.debt_score = 80
    ctx.debt_hotspots = [{"line": 4, "description": "Hardcoded password", "severity": "CRITICAL"}]
    ctx.review_issues = [
        {"line": 4, "message": "Hardcoded password", "severity": "CRITICAL"},
        {"line": 5, "message": "SQL injection", "severity": "CRITICAL"},
    ]

    agent = PRSummaryAgent()
    result = agent.run(ctx)

    assert result.pr_title, f"pr_title is empty. Errors: {result.errors}"
    assert result.pr_body, f"pr_body is empty. Errors: {result.errors}"
    assert len(result.pr_title) <= 70, "PR title must be under 70 characters"


@pytest.mark.integration
def test_full_phase2_pipeline():
    """Full pipeline (review → debt → pr) should complete without fatal errors."""
    ctx = AgentContext(code=SAMPLE_CODE, filename="bad.py", language="python")
    pipeline = SequentialPipeline([
        ReviewAgent(),
        TechDebtAgent(),
        PRSummaryAgent(),
    ])
    result = pipeline.run(ctx)

    # No fatal errors
    fatal = [e for e in result.errors if "FATAL" in e]
    assert not fatal, f"Fatal errors: {fatal}"

    # All three agents should have produced output
    assert isinstance(result.debt_score, int)
    assert 0 <= result.debt_score <= 100
    assert result.pr_title

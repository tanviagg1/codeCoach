"""
Tests for SequentialPipeline.

Run: pytest tests/test_pipeline.py -v
"""

import pytest
from unittest.mock import MagicMock

from agents.base import BaseAgent
from agents.context import AgentContext
from agents.pipeline import SequentialPipeline


# ---------------------------------------------------------------------------
# Helpers — minimal agents for testing pipeline behavior
# ---------------------------------------------------------------------------

class WritesFieldA(BaseAgent):
    """Test agent that writes field_a to context."""
    def run(self, context: AgentContext) -> AgentContext:
        context.review_summary = "written by agent A"
        return context


class WritesFieldB(BaseAgent):
    """Test agent that reads field_a and writes field_b."""
    def run(self, context: AgentContext) -> AgentContext:
        # Should be able to see A's output since it runs after A
        context.explanation = f"seen A: {context.review_summary}"
        return context


class AlwaysFails(BaseAgent):
    """Test agent that always raises an exception."""
    def run(self, context: AgentContext) -> AgentContext:
        raise RuntimeError("Simulated agent failure")


class LogsAndPasses(BaseAgent):
    """Test agent that appends to errors but does not crash."""
    def run(self, context: AgentContext) -> AgentContext:
        context.errors.append("LogsAndPasses: non-fatal warning")
        return context


def make_context() -> AgentContext:
    return AgentContext(code="def foo(): pass", filename="test.py", language="python")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSequentialPipeline:

    def test_runs_agents_in_order(self):
        """Later agents should see output from earlier agents."""
        pipeline = SequentialPipeline([WritesFieldA(), WritesFieldB()])
        ctx = pipeline.run(make_context())

        assert ctx.review_summary == "written by agent A"
        assert "seen A: written by agent A" in ctx.explanation

    def test_tracks_timing_for_each_agent(self):
        """Pipeline should record timing for each agent that runs."""
        pipeline = SequentialPipeline([WritesFieldA(), WritesFieldB()])
        ctx = pipeline.run(make_context())

        assert "WritesFieldA" in ctx.timings
        assert "WritesFieldB" in ctx.timings
        assert ctx.timings["WritesFieldA"] >= 0
        assert ctx.timings["WritesFieldB"] >= 0

    def test_stops_on_fatal_error(self):
        """Pipeline should stop and log error if an agent raises."""
        pipeline = SequentialPipeline([AlwaysFails(), WritesFieldB()])
        ctx = pipeline.run(make_context())

        # WritesFieldB should NOT have run (pipeline stopped at AlwaysFails)
        assert ctx.explanation == ""
        # Error should be logged
        assert len(ctx.errors) == 1
        assert "AlwaysFails" in ctx.errors[0]
        assert "FATAL" in ctx.errors[0]

    def test_continues_on_non_fatal_errors(self):
        """Pipeline should continue if agent logs to errors but does not raise."""
        pipeline = SequentialPipeline([LogsAndPasses(), WritesFieldB()])
        ctx = pipeline.run(make_context())

        # WritesFieldB should still run
        assert ctx.explanation != ""
        # Non-fatal error should be in errors list
        assert len(ctx.errors) == 1
        assert "non-fatal warning" in ctx.errors[0]

    def test_raises_on_empty_agents_list(self):
        """Pipeline should not be created with zero agents."""
        with pytest.raises(ValueError, match="at least one agent"):
            SequentialPipeline([])

    def test_single_agent_pipeline(self):
        """Pipeline with one agent should work correctly."""
        pipeline = SequentialPipeline([WritesFieldA()])
        ctx = pipeline.run(make_context())
        assert ctx.review_summary == "written by agent A"
        assert len(ctx.timings) == 1

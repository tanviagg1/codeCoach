"""
LangGraph pipeline — Phase 3 replacement for SequentialPipeline.

Graph structure:
  START
    ↓
  review_node  (ReviewAgent, with retry on JSON parse failure)
    ↓ [conditional: retry if parse failed and retries < 1]
    ├── retry → review_node
    └── continue → test_gen_node + explainer_node (parallel)
                         ↓ (both must complete)
                     debt_node  (TechDebtAgent)
                         ↓ [conditional: debt_score > 80?]
                     ├── high debt → alert_node → pr_node → END
                     └── normal   → pr_node → END

Key LangGraph concepts demonstrated:
- Parallel node execution (ReviewAgent + ExplainerAgent run simultaneously)
- Conditional routing (AlertAgent inserted only when debt > 80)
- Retry logic via conditional edge loop (ReviewAgent retries on bad JSON)
- Reducer functions for merging parallel state updates (lists, dicts)
"""

import operator
import time
from typing import Optional, Annotated, Literal

from langgraph.graph import StateGraph, START, END

from agents.context import AgentContext
from agents.review_agent import ReviewAgent
from agents.test_gen_agent import TestGenAgent
from agents.explainer_agent import ExplainerAgent
from agents.tech_debt_agent import TechDebtAgent
from agents.pr_summary_agent import PRSummaryAgent
from agents.alert_agent import AlertAgent

DEBT_ALERT_THRESHOLD = 80
MAX_REVIEW_RETRIES = 1


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------
# Annotated fields with reducers handle parallel node writes safely:
#   - errors: lists are concatenated (operator.add)
#   - timings: dicts are merged (custom reducer)

def _merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}


class PipelineState(dict):
    """
    LangGraph state — mirrors AgentContext fields plus pipeline metadata.

    Using plain TypedDict-style keys so we can construct AgentContext from it.
    Annotated fields have reducers for safe parallel merges.
    """
    pass


# We define state as a TypedDict with annotations for LangGraph
from typing import TypedDict


class PipelineState(TypedDict, total=False):
    # Input (set before pipeline starts)
    code: str
    filename: str
    language: str
    model: str

    # ReviewAgent output
    review_issues: list
    review_summary: str

    # TestGenAgent output
    generated_tests: str

    # ExplainerAgent output
    explanation: str

    # TechDebtAgent output
    debt_score: Optional[int]
    debt_hotspots: list

    # AlertAgent output (conditional)
    alert_message: str

    # PRSummaryAgent output
    pr_title: str
    pr_body: str

    # Pipeline metadata
    timings: Annotated[dict, _merge_dicts]
    errors: Annotated[list, operator.add]
    review_retries: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state_to_context(state: PipelineState) -> AgentContext:
    """Convert LangGraph state dict → AgentContext for passing to agents."""
    ctx = AgentContext(
        code=state["code"],
        filename=state["filename"],
        language=state.get("language", "python"),
        model=state.get("model", "llama3.1:8b"),
    )
    ctx.review_issues = list(state.get("review_issues") or [])
    ctx.review_summary = state.get("review_summary") or ""
    ctx.generated_tests = state.get("generated_tests") or ""
    ctx.explanation = state.get("explanation") or ""
    ctx.debt_score = state.get("debt_score")
    ctx.debt_hotspots = list(state.get("debt_hotspots") or [])
    ctx.alert_message = state.get("alert_message") or ""
    ctx.pr_title = state.get("pr_title") or ""
    ctx.pr_body = state.get("pr_body") or ""
    ctx.timings = dict(state.get("timings") or {})
    ctx.errors = list(state.get("errors") or [])
    return ctx


def _timed(agent, ctx: AgentContext) -> tuple[AgentContext, float]:
    start = time.time()
    ctx = agent.run(ctx)
    return ctx, round(time.time() - start, 2)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def review_node(state: PipelineState) -> dict:
    """
    Runs ReviewAgent. On retry (review_retries > 0) the agent re-runs with
    the same context — the LLM nondeterminism often resolves the parse error.
    """
    retries = state.get("review_retries", 0)
    if retries == 0:
        print("\n[ReviewAgent]")
    else:
        print(f"\n[ReviewAgent] retry {retries}/{MAX_REVIEW_RETRIES}")

    ctx = _state_to_context(state)
    # Clear any prior parse errors before retry so they don't accumulate
    ctx.errors = [e for e in ctx.errors if "failed to parse JSON" not in e]

    agent = ReviewAgent(model=state.get("model", "llama3.1:8b"))
    ctx, elapsed = _timed(agent, ctx)
    print(f"  Done in {elapsed}s")

    return {
        "review_issues": ctx.review_issues,
        "review_summary": ctx.review_summary,
        "errors": ctx.errors,
        "timings": {"ReviewAgent": elapsed},
        "review_retries": retries,
    }


def review_router(state: PipelineState) -> Literal["review_node", "test_gen_node"]:
    """
    Retry ReviewAgent once if it produced a JSON parse error.
    After MAX_REVIEW_RETRIES attempts, continue regardless.
    """
    had_parse_error = any("failed to parse JSON" in e for e in state.get("errors", []))
    retries = state.get("review_retries", 0)

    if had_parse_error and retries < MAX_REVIEW_RETRIES:
        # Increment retry counter before looping back
        return "review_node"
    return "test_gen_node"


def test_gen_node(state: PipelineState) -> dict:
    print("\n[TestGenAgent]")
    ctx = _state_to_context(state)
    agent = TestGenAgent(model=state.get("model", "llama3.1:8b"))
    ctx, elapsed = _timed(agent, ctx)
    print(f"  Done in {elapsed}s")
    return {
        "generated_tests": ctx.generated_tests,
        "errors": ctx.errors,
        "timings": {"TestGenAgent": elapsed},
    }


def explainer_node(state: PipelineState) -> dict:
    print("\n[ExplainerAgent]")
    ctx = _state_to_context(state)
    agent = ExplainerAgent(model=state.get("model", "llama3.1:8b"))
    ctx, elapsed = _timed(agent, ctx)
    print(f"  Done in {elapsed}s")
    return {
        "explanation": ctx.explanation,
        "errors": ctx.errors,
        "timings": {"ExplainerAgent": elapsed},
    }


def debt_node(state: PipelineState) -> dict:
    print("\n[TechDebtAgent]")
    ctx = _state_to_context(state)
    agent = TechDebtAgent(model=state.get("model", "llama3.1:8b"))
    ctx, elapsed = _timed(agent, ctx)
    print(f"  Done in {elapsed}s")
    return {
        "debt_score": ctx.debt_score,
        "debt_hotspots": ctx.debt_hotspots,
        "errors": ctx.errors,
        "timings": {"TechDebtAgent": elapsed},
    }


def debt_router(state: PipelineState) -> Literal["alert_node", "pr_node"]:
    """Route to AlertAgent if debt_score exceeds the critical threshold."""
    score = state.get("debt_score")
    if score is not None and score > DEBT_ALERT_THRESHOLD:
        return "alert_node"
    return "pr_node"


def alert_node(state: PipelineState) -> dict:
    print("\n[AlertAgent]")
    ctx = _state_to_context(state)
    agent = AlertAgent()
    ctx, elapsed = _timed(agent, ctx)
    print(f"  Done in {elapsed}s")
    return {
        "alert_message": ctx.alert_message,
        "timings": {"AlertAgent": elapsed},
    }


def pr_node(state: PipelineState) -> dict:
    print("\n[PRSummaryAgent]")
    ctx = _state_to_context(state)
    agent = PRSummaryAgent(model=state.get("model", "llama3.1:8b"))
    ctx, elapsed = _timed(agent, ctx)
    print(f"  Done in {elapsed}s")
    return {
        "pr_title": ctx.pr_title,
        "pr_body": ctx.pr_body,
        "errors": ctx.errors,
        "timings": {"PRSummaryAgent": elapsed},
    }


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph():
    """Build and compile the LangGraph pipeline."""
    graph = StateGraph(PipelineState)

    # Register nodes
    graph.add_node("review_node", review_node)
    graph.add_node("test_gen_node", test_gen_node)
    graph.add_node("explainer_node", explainer_node)
    graph.add_node("debt_node", debt_node)
    graph.add_node("alert_node", alert_node)
    graph.add_node("pr_node", pr_node)

    # Entry point
    graph.add_edge(START, "review_node")

    # Retry conditional: loop back to review or fan out to parallel
    graph.add_conditional_edges(
        "review_node",
        review_router,
        {
            "review_node": "review_node",
            "test_gen_node": "test_gen_node",
        },
    )

    # Parallel fan-out: test_gen and explainer run simultaneously
    graph.add_edge("review_node", "explainer_node")

    # Fan-in: both parallel nodes must complete before debt analysis
    graph.add_edge("test_gen_node", "debt_node")
    graph.add_edge("explainer_node", "debt_node")

    # Conditional routing: alert if debt is critical
    graph.add_conditional_edges(
        "debt_node",
        debt_router,
        {
            "alert_node": "alert_node",
            "pr_node": "pr_node",
        },
    )

    # Alert always leads to PR
    graph.add_edge("alert_node", "pr_node")
    graph.add_edge("pr_node", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class LangGraphPipeline:
    """
    Drop-in replacement for SequentialPipeline using LangGraph.

    Usage:
        pipeline = LangGraphPipeline(model="llama3.1:8b")
        context = pipeline.run(context)
    """

    def __init__(self, model: str = "llama3.1:8b"):
        self.model = model
        self.graph = build_graph()

    def run(self, context: AgentContext) -> AgentContext:
        print("\nCodeCoach LangGraph Pipeline")
        print("-" * 50)

        initial_state: PipelineState = {
            "code": context.code,
            "filename": context.filename,
            "language": context.language,
            "model": self.model,
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

        final_state = self.graph.invoke(initial_state)

        print("\n" + "-" * 50)
        print("Pipeline complete.")

        # Merge final state back into the AgentContext
        context.review_issues = final_state.get("review_issues", [])
        context.review_summary = final_state.get("review_summary", "")
        context.generated_tests = final_state.get("generated_tests", "")
        context.explanation = final_state.get("explanation", "")
        context.debt_score = final_state.get("debt_score")
        context.debt_hotspots = final_state.get("debt_hotspots", [])
        context.alert_message = final_state.get("alert_message", "")
        context.pr_title = final_state.get("pr_title", "")
        context.pr_body = final_state.get("pr_body", "")
        context.timings = final_state.get("timings", {})
        context.errors = final_state.get("errors", [])

        if context.timings:
            timing_str = " → ".join(
                f"{name} ({t}s)" for name, t in context.timings.items()
            )
            print(f"  Timings: {timing_str}")

        if context.errors:
            print(f"\n  Errors ({len(context.errors)}):")
            for err in context.errors:
                print(f"    - {err}")

        return context

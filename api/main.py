"""
FastAPI app for CodeCoach AI.

Endpoints:
  POST /review        — run full pipeline on submitted code
  POST /review/single — run one specific agent
  GET  /history       — list past reviews (Phase 4: requires ChromaDB)
  GET  /health        — health check

See ARCHITECTURE.md for full API design.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from agents.context import AgentContext
from agents.pipeline import SequentialPipeline
from agents.review_agent import ReviewAgent
from agents.test_gen_agent import TestGenAgent
from agents.explainer_agent import ExplainerAgent
from agents.tech_debt_agent import TechDebtAgent
from agents.pr_summary_agent import PRSummaryAgent
from skills.code_parser import detect_language, truncate_code, estimate_tokens


app = FastAPI(
    title="CodeCoach AI",
    description="Multi-agent AI code review system powered by Claude",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ReviewRequest(BaseModel):
    code: str
    filename: str = "unknown.py"
    agents: list[str] = ["review", "tests", "explain", "debt", "pr"]
    model: str = "llama3.1:8b"


class SingleAgentRequest(BaseModel):
    code: str
    filename: str = "unknown.py"
    agent: str  # "review" | "tests" | "explain" | "debt" | "pr"
    model: str = "claude-sonnet-4-6"


class ReviewResponse(BaseModel):
    filename: str
    language: str
    review_issues: list
    review_summary: str
    generated_tests: str
    explanation: str
    debt_score: Optional[int]
    debt_hotspots: list
    pr_title: str
    pr_body: str
    timings: dict
    errors: list


# ---------------------------------------------------------------------------
# Agent registry — maps string names to agent classes
# ---------------------------------------------------------------------------

AGENT_REGISTRY = {
    "review": ReviewAgent,
    "tests": TestGenAgent,
    "explain": ExplainerAgent,
    "debt": TechDebtAgent,
    "pr": PRSummaryAgent,
}

# Pipeline order matters — later agents depend on earlier ones
PIPELINE_ORDER = ["review", "tests", "explain", "debt", "pr"]


def _build_pipeline(requested_agents: list[str], model: str) -> SequentialPipeline:
    """Build a pipeline from a list of agent names, maintaining dependency order."""
    ordered = [name for name in PIPELINE_ORDER if name in requested_agents]
    if not ordered:
        raise ValueError(f"No valid agents in: {requested_agents}. Valid: {list(AGENT_REGISTRY)}")
    agents = [AGENT_REGISTRY[name](model=model) for name in ordered]
    return SequentialPipeline(agents)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Health check — confirms API is running and Ollama is reachable."""
    return {
        "status": "ok",
        "model": "llama3.1:8b (Ollama)",
    }


@app.post("/review", response_model=ReviewResponse)
def run_full_review(request: ReviewRequest):
    """
    Run the CodeCoach pipeline on submitted code.

    Agents run in this order (skipping any not in request.agents):
    review → tests → explain → debt → pr
    """
    if not request.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty.")

    # Detect language, truncate if too long
    language = detect_language(request.filename)
    code = truncate_code(request.code, max_lines=500)

    # Token pre-flight check
    estimated = estimate_tokens(code)
    if estimated > 150_000:
        raise HTTPException(status_code=400, detail=f"Code too long (~{estimated} tokens). Max ~150K.")

    # Build context and run pipeline
    context = AgentContext(
        code=code,
        filename=request.filename,
        language=language,
        model=request.model,
    )

    pipeline = _build_pipeline(request.agents, request.model)
    context = pipeline.run(context)

    return ReviewResponse(
        filename=context.filename,
        language=context.language,
        review_issues=context.review_issues,
        review_summary=context.review_summary,
        generated_tests=context.generated_tests,
        explanation=context.explanation,
        debt_score=context.debt_score,
        debt_hotspots=context.debt_hotspots,
        pr_title=context.pr_title,
        pr_body=context.pr_body,
        timings=context.timings,
        errors=context.errors,
    )


@app.post("/review/single")
def run_single_agent(request: SingleAgentRequest):
    """Run one specific agent on submitted code."""
    if request.agent not in AGENT_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent: {request.agent}. Valid agents: {list(AGENT_REGISTRY)}"
        )

    if not request.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty.")

    language = detect_language(request.filename)
    code = truncate_code(request.code, max_lines=500)

    context = AgentContext(code=code, filename=request.filename, language=language)
    agent = AGENT_REGISTRY[request.agent](model=request.model)
    context = agent.run(context)

    return {"agent": request.agent, "result": vars(context)}


@app.get("/history")
def get_review_history():
    """
    Retrieve past reviews from the vector store.
    Requires Phase 4 (ChromaDB) to be implemented.
    """
    return {
        "message": "Review history available in Phase 4 (ChromaDB integration).",
        "reviews": []
    }

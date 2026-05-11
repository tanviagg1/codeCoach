"""
AgentContext — the shared state object that flows through the pipeline.

Every agent reads from this object and writes results back to it.
Think of it as the "conversation" between agents — earlier agents
enrich the context so later agents have more to work with.

See ARCHITECTURE.md for a full field-by-field explanation.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentContext:
    # ----------------------------------------------------------------
    # Input (required at pipeline start)
    # ----------------------------------------------------------------
    code: str
    filename: str
    language: str = "python"

    # ----------------------------------------------------------------
    # After ReviewAgent
    # ----------------------------------------------------------------
    review_issues: list = field(default_factory=list)
    # Each issue: {"line": int, "message": str, "severity": "CRITICAL|HIGH|MEDIUM|LOW"}
    review_summary: str = ""

    # ----------------------------------------------------------------
    # After TestGenAgent
    # ----------------------------------------------------------------
    generated_tests: str = ""
    # Full pytest file as a string — ready to write to disk

    # ----------------------------------------------------------------
    # After ExplainerAgent
    # ----------------------------------------------------------------
    explanation: str = ""
    # Plain-English explanation of what the code does

    # ----------------------------------------------------------------
    # After TechDebtAgent
    # ----------------------------------------------------------------
    debt_score: Optional[int] = None
    # Integer 0-100: 0 = pristine, 100 = unmaintainable
    debt_hotspots: list = field(default_factory=list)
    # Each hotspot: {"line": int, "description": str, "severity": str}

    # ----------------------------------------------------------------
    # After TechDebtAgent (conditional — only if debt_score > 80)
    # ----------------------------------------------------------------
    alert_message: str = ""
    # Set by AlertAgent when debt is CRITICAL (> 80)

    # ----------------------------------------------------------------
    # After PRSummaryAgent
    # ----------------------------------------------------------------
    pr_title: str = ""
    pr_body: str = ""

    # ----------------------------------------------------------------
    # After VectorStore.store_review (Phase 4)
    # ----------------------------------------------------------------
    review_id: str = ""
    # UUID assigned when this review is stored in ChromaDB

    # ----------------------------------------------------------------
    # Pipeline metadata (filled throughout)
    # ----------------------------------------------------------------
    timings: dict = field(default_factory=dict)
    # {"ReviewAgent": 3.2, "TestGenAgent": 4.1, ...}
    errors: list = field(default_factory=list)
    # Non-fatal agent errors — pipeline continues even if this grows
    model: str = "claude-sonnet-4-6"

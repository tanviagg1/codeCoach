"""
AlertAgent — fires when debt_score exceeds the CRITICAL threshold (> 80).

This agent is inserted conditionally by the LangGraph pipeline.
It does NOT call the LLM — it formats a structured alert from existing context data.

See PHASES.md Phase 3 for the conditional routing design.
"""

from agents.base import BaseAgent
from agents.context import AgentContext

CRITICAL_THRESHOLD = 80


class AlertAgent(BaseAgent):
    """
    Generates a critical debt alert when debt_score > 80.

    Reads from context:
    - debt_score, debt_hotspots, filename

    Writes to context:
    - alert_message: formatted warning string
    """

    def run(self, context: AgentContext) -> AgentContext:
        if context.debt_score is None or context.debt_score <= CRITICAL_THRESHOLD:
            return context

        critical_hotspots = [
            h for h in context.debt_hotspots if h.get("severity") == "CRITICAL"
        ]
        high_hotspots = [
            h for h in context.debt_hotspots if h.get("severity") == "HIGH"
        ]

        lines = [
            f"CRITICAL DEBT ALERT — {context.filename}",
            f"Debt score: {context.debt_score}/100 (threshold: {CRITICAL_THRESHOLD})",
            f"This file needs immediate attention before merging.",
            "",
        ]

        if critical_hotspots:
            lines.append("Critical hotspots:")
            for h in critical_hotspots:
                lines.append(f"  - Line {h.get('line', '?')}: {h.get('description', '')}")

        if high_hotspots:
            lines.append("High-severity hotspots:")
            for h in high_hotspots:
                lines.append(f"  - Line {h.get('line', '?')}: {h.get('description', '')}")

        context.alert_message = "\n".join(lines)
        print(f"  ALERT: Debt score {context.debt_score}/100 exceeds threshold — review required.")

        return context

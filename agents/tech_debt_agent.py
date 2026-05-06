"""
TechDebtAgent — scores technical debt and identifies hotspot areas.

Tech debt score: 0 (pristine) to 100 (unmaintainable).
Debt hotspots: specific lines or sections that contribute most to debt.

This agent is added in Phase 2 but stubbed here for the architecture.

See AGENTS_GUIDE.md for agent conventions.
See prompts/tech_debt.md for the prompt template.
"""

import json
import anthropic

from agents.base import BaseAgent
from agents.context import AgentContext


class TechDebtAgent(BaseAgent):
    """
    Analyzes technical debt in the submitted code.

    Reads from context:
    - code, language
    - review_issues: uses these as additional debt signals

    Writes to context:
    - debt_score: integer 0-100
    - debt_hotspots: list of {line, description, severity} dicts
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic()
        self.model = model
        self.prompt_template = self._load_prompt("tech_debt.md")

    def run(self, context: AgentContext) -> AgentContext:
        # 1. Validate prerequisites
        if not context.code:
            raise ValueError("TechDebtAgent requires context.code to be set.")

        # 2. Format existing issues for prompt
        issues_str = "None"
        if context.review_issues:
            issues_str = "\n".join(
                f"- Line {i.get('line', '?')}: {i.get('message', '')} [{i.get('severity', '?')}]"
                for i in context.review_issues
            )

        # 3. Build prompt
        prompt = self.prompt_template.replace("{{code}}", context.code)
        prompt = prompt.replace("{{language}}", context.language)
        prompt = prompt.replace("{{issues}}", issues_str)

        # 4. Call Claude API
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.2,
                system=(
                    "You are a software architect who specializes in identifying and "
                    "quantifying technical debt. You score debt consistently across "
                    "many codebases. Think step by step before producing your JSON output."
                ),
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()

            # Strip code blocks if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)

            # 5. Write to context
            context.debt_score = int(result.get("debt_score", 0))
            context.debt_hotspots = result.get("hotspots", [])

            severity_label = (
                "LOW" if context.debt_score < 30
                else "MODERATE" if context.debt_score < 60
                else "HIGH" if context.debt_score < 80
                else "CRITICAL"
            )
            print(f"  Debt score: {context.debt_score}/100 ({severity_label})")
            print(f"  Hotspots: {len(context.debt_hotspots)}")

        except json.JSONDecodeError as e:
            context.errors.append(f"TechDebtAgent: failed to parse JSON: {e}")
        except anthropic.APIError as e:
            context.errors.append(f"TechDebtAgent: API error: {e}")

        return context

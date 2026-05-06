"""
PRSummaryAgent — generates a PR title and description based on the full review.

This is the last agent in the pipeline. It has access to the full enriched
context from all previous agents and synthesizes them into a professional
PR description.

This agent demonstrates "chained agent output" — it meaningfully uses the
outputs of 3 other agents (ReviewAgent, ExplainerAgent, TechDebtAgent).

See AGENTS_GUIDE.md for agent conventions.
See prompts/pr_summary.md for the prompt template.
"""

import json
import anthropic

from agents.base import BaseAgent
from agents.context import AgentContext


class PRSummaryAgent(BaseAgent):
    """
    Generates a PR title and description from the full review context.

    Reads from context:
    - review_summary: what issues were found
    - explanation: what the code does
    - debt_score, debt_hotspots: tech debt context

    Writes to context:
    - pr_title: short, conventional commits style title
    - pr_body: full markdown PR description
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic()
        self.model = model
        self.prompt_template = self._load_prompt("pr_summary.md")

    def run(self, context: AgentContext) -> AgentContext:
        # 1. Gather all upstream agent outputs
        review_summary = context.review_summary or "No review summary available."
        explanation = context.explanation or "No explanation available."
        debt_info = (
            f"Debt score: {context.debt_score}/100. "
            f"Hotspots: {len(context.debt_hotspots)}"
            if context.debt_score is not None
            else "Debt analysis not run."
        )
        issue_count = len(context.review_issues)
        critical = sum(1 for i in context.review_issues if i.get("severity") == "CRITICAL")
        high = sum(1 for i in context.review_issues if i.get("severity") == "HIGH")

        # 2. Build prompt
        prompt = self.prompt_template.replace("{{filename}}", context.filename)
        prompt = prompt.replace("{{review_summary}}", review_summary)
        prompt = prompt.replace("{{explanation}}", explanation)
        prompt = prompt.replace("{{debt_info}}", debt_info)
        prompt = prompt.replace("{{issue_count}}", str(issue_count))
        prompt = prompt.replace("{{critical_count}}", str(critical))
        prompt = prompt.replace("{{high_count}}", str(high))

        # 3. Call Claude API
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.6,  # Slightly creative — PR descriptions should read naturally
                system=(
                    "You are a senior engineer who writes clear, professional pull request "
                    "descriptions. You follow conventional commits for titles and write "
                    "descriptions that help reviewers understand what changed and why."
                ),
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()

            # Strip markdown if wrapped
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)

            # 4. Write to context
            context.pr_title = result.get("title", "")
            context.pr_body = result.get("body", "")

            print(f"  PR title: {context.pr_title}")

        except json.JSONDecodeError as e:
            context.errors.append(f"PRSummaryAgent: failed to parse JSON: {e}")
        except anthropic.APIError as e:
            context.errors.append(f"PRSummaryAgent: API error: {e}")

        return context

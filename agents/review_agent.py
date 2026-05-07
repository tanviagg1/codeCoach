"""
ReviewAgent — analyzes code for quality issues, security problems, and style violations.

This is the first agent in the pipeline. Its output (review_issues, review_summary)
is used by downstream agents: TestGenAgent uses issues to generate targeted tests,
TechDebtAgent uses them to calculate a debt score.

See AGENTS_GUIDE.md for how to write and test agents.
See prompts/review.md for the prompt template.
"""

import json
import ollama

from agents.base import BaseAgent
from agents.context import AgentContext

SYSTEM_PROMPT = (
    "You are a senior software engineer with 10 years of experience "
    "in code review, security, and production systems. "
    "You have reviewed thousands of pull requests. "
    "Think step by step before producing your final JSON output."
)


class ReviewAgent(BaseAgent):
    """
    Analyzes submitted code and returns a structured list of issues.

    Output fields written to context:
    - review_issues: list of {line, message, severity} dicts
    - review_summary: one-paragraph human-readable summary
    """

    def __init__(self, model: str = "llama3.1:8b"):
        self.client = ollama.Client()
        self.model = model
        # Load prompt once at init — not on every run
        self.prompt_template = self._load_prompt("review.md")

    def run(self, context: AgentContext) -> AgentContext:
        # 1. Validate prerequisites
        if not context.code:
            raise ValueError("ReviewAgent requires context.code to be set.")

        # 2. Build prompt by substituting placeholders
        prompt = self.prompt_template.replace("{{code}}", context.code)
        prompt = prompt.replace("{{language}}", context.language)
        prompt = prompt.replace("{{filename}}", context.filename)

        # 3. Call Ollama
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.2},  # Low temp: consistent, structured output
            )
            raw = response.message.content.strip()

            # 4. Parse JSON — strip markdown code blocks if model wrapped it
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)

            # 5. Write to context
            context.review_issues = result.get("issues", [])
            context.review_summary = result.get("summary", "")

            issue_count = len(context.review_issues)
            print(f"  Issues found: {issue_count}")
            for issue in context.review_issues:
                severity = issue.get("severity", "?")
                line = issue.get("line", "?")
                msg = issue.get("message", "")
                print(f"    - Line {line}: {msg[:60]} ({severity})")

        except json.JSONDecodeError as e:
            context.errors.append(f"ReviewAgent: failed to parse JSON response: {e}")
            print(f"  Warning: could not parse response as JSON.")
        except Exception as e:
            context.errors.append(f"ReviewAgent: error: {e}")
            print(f"  Warning: {e}")

        return context

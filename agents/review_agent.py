"""
ReviewAgent — analyzes code for quality issues, security problems, and style violations.

This is the first agent in the pipeline. Its output (review_issues, review_summary)
is used by downstream agents: TestGenAgent uses issues to generate targeted tests,
TechDebtAgent uses them to calculate a debt score.

Phase 4 addition: optional RAG injection via VectorStore.
If a vector_store is provided, top-3 similar past reviews are fetched and
injected into the prompt via the {{past_reviews}} placeholder.

See AGENTS_GUIDE.md for how to write and test agents.
See prompts/review.md for the prompt template.
"""

import json
from typing import Optional
import ollama

from agents.base import BaseAgent
from agents.context import AgentContext

SYSTEM_PROMPT = (
    "You are a senior software engineer with 10 years of experience "
    "in code review, security, and production systems. "
    "You have reviewed thousands of pull requests. "
    "Think step by step before producing your final JSON output."
)


def _format_past_reviews(reviews: list[dict]) -> str:
    """Format similar past reviews for injection into the prompt."""
    if not reviews:
        return ""

    lines = ["## Similar Past Reviews (for context — do not repeat these, use them as signals)"]
    for i, review in enumerate(reviews, 1):
        lines.append(
            f"\n### Past Review {i} — {review['filename']} "
            f"(similarity: {review['similarity_score']}, debt: {review['debt_score']}/100)"
        )
        if review["review_summary"]:
            lines.append(f"Summary: {review['review_summary']}")
        if review["issues"]:
            lines.append("Key issues found:")
            for issue in review["issues"][:3]:
                lines.append(
                    f"  - Line {issue.get('line', '?')}: {issue.get('message', '')} "
                    f"[{issue.get('severity', '?')}]"
                )
    lines.append("")
    return "\n".join(lines)


class ReviewAgent(BaseAgent):
    """
    Analyzes submitted code and returns a structured list of issues.

    Output fields written to context:
    - review_issues: list of {line, message, severity} dicts
    - review_summary: one-paragraph human-readable summary

    Args:
        model: Ollama model to use
        vector_store: Optional VectorStore for RAG — injects similar past reviews
    """

    def __init__(self, model: str = "llama3.1:8b", vector_store=None):
        self.client = ollama.Client()
        self.model = model
        self.vector_store = vector_store
        self.prompt_template = self._load_prompt("review.md")

    def run(self, context: AgentContext) -> AgentContext:
        # 1. Validate prerequisites
        if not context.code:
            raise ValueError("ReviewAgent requires context.code to be set.")

        # 2. RAG: fetch similar past reviews if vector_store is available
        past_reviews_text = ""
        if self.vector_store:
            try:
                similar = self.vector_store.find_similar_reviews(context.code, top_k=3)
                if similar:
                    past_reviews_text = _format_past_reviews(similar)
                    print(f"  RAG: injecting {len(similar)} similar past review(s)")
            except Exception as e:
                context.errors.append(f"ReviewAgent: RAG lookup failed: {e}")

        # 3. Build prompt
        prompt = self.prompt_template.replace("{{code}}", context.code)
        prompt = prompt.replace("{{language}}", context.language)
        prompt = prompt.replace("{{filename}}", context.filename)
        prompt = prompt.replace("{{past_reviews}}", past_reviews_text)

        # 4. Call Ollama
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.2},
            )
            raw = response.message.content.strip()

            # Strip markdown code blocks if model wrapped it
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

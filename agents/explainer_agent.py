"""
ExplainerAgent — produces a plain-English explanation of the code.

Designed to help junior developers understand what a piece of code does
without needing to read every line. Output is intentionally human-readable
(not JSON) since it's consumed by people, not downstream agents.

(PRSummaryAgent does read the explanation to write its PR body.)

See AGENTS_GUIDE.md for agent conventions.
See prompts/explainer.md for the prompt template.
"""

import anthropic

from agents.base import BaseAgent
from agents.context import AgentContext


class ExplainerAgent(BaseAgent):
    """
    Explains what the submitted code does in plain English.

    Reads from context:
    - code, language, filename

    Writes to context:
    - explanation: a 2-4 paragraph plain-English explanation
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic()
        self.model = model
        self.prompt_template = self._load_prompt("explainer.md")

    def run(self, context: AgentContext) -> AgentContext:
        # 1. Validate prerequisites
        if not context.code:
            raise ValueError("ExplainerAgent requires context.code to be set.")

        # 2. Build prompt
        prompt = self.prompt_template.replace("{{code}}", context.code)
        prompt = prompt.replace("{{language}}", context.language)
        prompt = prompt.replace("{{filename}}", context.filename)

        # 3. Call Claude API
        # Higher temperature for natural-sounding explanation (not robotic)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.7,
                system=(
                    "You are a senior developer who excels at mentoring junior engineers. "
                    "You explain code clearly, using simple language and relatable analogies. "
                    "You avoid jargon unless you explain it immediately after."
                ),
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()

            # 4. Write to context (plain text, no parsing needed)
            context.explanation = raw

            # Print a short preview
            preview = raw[:100].replace("\n", " ")
            print(f"  Explanation: {preview}...")

        except anthropic.APIError as e:
            context.errors.append(f"ExplainerAgent: API error: {e}")
            print(f"  Warning: API error: {e}")

        return context

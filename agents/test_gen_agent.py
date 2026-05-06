"""
TestGenAgent — generates pytest unit tests for the submitted code.

This agent runs after ReviewAgent so it can generate tests that specifically
target the issues found. If ReviewAgent found a SQL injection vulnerability,
TestGenAgent will generate a test that covers that input path.

Output: a complete, ready-to-run pytest file as a string.

See AGENTS_GUIDE.md for agent conventions.
See prompts/test_gen.md for the prompt template.
"""

import anthropic

from agents.base import BaseAgent
from agents.context import AgentContext


class TestGenAgent(BaseAgent):
    """
    Generates pytest unit tests for the submitted code.

    Reads from context:
    - code, language, filename: the code to test
    - review_issues: issues found by ReviewAgent (to generate targeted tests)

    Writes to context:
    - generated_tests: full pytest file as a string
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic()
        self.model = model
        self.prompt_template = self._load_prompt("test_gen.md")

    def run(self, context: AgentContext) -> AgentContext:
        # 1. Validate prerequisites
        if not context.code:
            raise ValueError("TestGenAgent requires context.code to be set.")

        # 2. Format issues as a readable string for the prompt
        issues_str = "No issues found by ReviewAgent."
        if context.review_issues:
            lines = [
                f"- Line {i.get('line', '?')}: {i.get('message', '')} [{i.get('severity', '?')}]"
                for i in context.review_issues
            ]
            issues_str = "\n".join(lines)

        # 3. Build prompt
        prompt = self.prompt_template.replace("{{code}}", context.code)
        prompt = prompt.replace("{{language}}", context.language)
        prompt = prompt.replace("{{filename}}", context.filename)
        prompt = prompt.replace("{{issues}}", issues_str)

        # 4. Call Claude API
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.3,
                system=(
                    "You are a senior software engineer specializing in test-driven development. "
                    "You write thorough pytest unit tests that cover happy paths, edge cases, "
                    "and error conditions. Your tests are self-contained and runnable."
                ),
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()

            # 5. Extract just the Python code if it's wrapped in a code block
            if "```python" in raw:
                raw = raw.split("```python")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            # 6. Write to context
            context.generated_tests = raw

            # Count test functions
            test_count = raw.count("def test_")
            print(f"  Generated {test_count} test function{'s' if test_count != 1 else ''}")

        except anthropic.APIError as e:
            context.errors.append(f"TestGenAgent: API error: {e}")
            print(f"  Warning: API error: {e}")

        return context

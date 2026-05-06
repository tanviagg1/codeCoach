# Agents Guide

How to read, write, test, and extend agents in CodeCoach AI.

---

## The BaseAgent Contract

Every agent inherits from `BaseAgent` and implements one method:

```python
class BaseAgent(ABC):
    @abstractmethod
    def run(self, context: AgentContext) -> AgentContext:
        pass
```

Rules every agent must follow:
1. **Read from context** — never assume external state
2. **Validate prerequisites** at the top — raise if required context fields are missing
3. **Write results to context** — don't return raw strings
4. **Never crash the pipeline** — catch agent-level errors, append to `context.errors`
5. **Return context** — always, even if the agent did nothing

---

## Anatomy of an Agent

```python
class MyAgent(BaseAgent):
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic()
        self.model = model
        # Load prompt once at init, not on every run
        self.prompt_template = self._load_prompt("prompts/my_agent.md")

    def run(self, context: AgentContext) -> AgentContext:
        # 1. Validate prerequisites
        if not context.code:
            raise ValueError("MyAgent requires context.code")

        # 2. Build the prompt from template
        prompt = self.prompt_template.replace("{{code}}", context.code)
        prompt = prompt.replace("{{language}}", context.language)

        # 3. Call Claude API
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.3,
                system="You are a senior engineer...",
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text

            # 4. Parse response
            result = json.loads(raw)

            # 5. Write to context
            context.my_field = result["my_field"]

        except json.JSONDecodeError as e:
            context.errors.append(f"MyAgent: failed to parse response: {e}")
        except anthropic.APIError as e:
            context.errors.append(f"MyAgent: API error: {e}")

        return context

    def _load_prompt(self, path: str) -> str:
        with open(path) as f:
            return f.read()
```

---

## Agent Responsibilities

| Agent | Reads from context | Writes to context |
|---|---|---|
| ReviewAgent | `code`, `language` | `review_issues`, `review_summary` |
| TestGenAgent | `code`, `language`, `review_issues` | `generated_tests` |
| ExplainerAgent | `code`, `language` | `explanation` |
| TechDebtAgent | `code`, `review_issues` | `debt_score`, `debt_hotspots` |
| PRSummaryAgent | `review_summary`, `debt_score`, `explanation` | `pr_title`, `pr_body` |

Note: TestGenAgent reads `review_issues` so it can generate tests that specifically cover the found issues.

---

## How to Add a New Agent

1. Create `agents/my_new_agent.py`
2. Create `prompts/my_new_agent.md` (see PROMPTS_GUIDE.md for format)
3. Add the agent to `AgentContext` (new output fields)
4. Add the agent to `SequentialPipeline` in `agents/pipeline.py`
5. Write tests in `tests/test_my_new_agent.py`

Example minimal agent:
```python
from agents.base import BaseAgent
from agents.context import AgentContext
import anthropic, json

class MyNewAgent(BaseAgent):
    def __init__(self, model="claude-sonnet-4-6"):
        self.client = anthropic.Anthropic()
        self.model = model
        with open("prompts/my_new_agent.md") as f:
            self.prompt_template = f.read()

    def run(self, context: AgentContext) -> AgentContext:
        if not context.code:
            raise ValueError("MyNewAgent requires context.code")
        prompt = self.prompt_template.replace("{{code}}", context.code)
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system="You are...",
                messages=[{"role": "user", "content": prompt}]
            )
            context.my_new_field = resp.content[0].text
        except Exception as e:
            context.errors.append(f"MyNewAgent: {e}")
        return context
```

---

## How to Test an Agent

Always test with a **mock Claude client** so tests don't call the real API:

```python
from unittest.mock import MagicMock, patch
from agents.review_agent import ReviewAgent
from agents.context import AgentContext

def make_mock_response(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg

def test_review_agent_parses_issues():
    mock_response = make_mock_response(
        '{"issues": [{"line": 5, "message": "No error handling", "severity": "HIGH"}], '
        '"summary": "One issue found."}'
    )
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        agent = ReviewAgent()
        ctx = AgentContext(code="def foo(): pass", filename="test.py", language="python")
        result = agent.run(ctx)

    assert len(result.review_issues) == 1
    assert result.review_issues[0]["severity"] == "HIGH"
    assert result.review_summary == "One issue found."
```

For integration tests (real API):
```python
import pytest

@pytest.mark.integration
def test_review_agent_real_api():
    agent = ReviewAgent()
    ctx = AgentContext(code="def foo(): x = eval(input())", filename="bad.py", language="python")
    result = agent.run(ctx)
    assert len(result.review_issues) > 0  # Should catch the eval() issue
```

---

## Agent Design Decisions

### Why not use LangChain agents?
LangChain's agent abstraction adds significant complexity for a learner. We start with plain Python classes (easy to understand, test, and debug) and introduce LangGraph in Phase 3 for orchestration.

### Why is the client created in `__init__`?
Creating the `anthropic.Anthropic()` client once per agent (not per call) is more efficient. The client handles connection pooling. This also makes mocking easier in tests.

### Why does the prompt live in a file?
See PROMPTS_GUIDE.md. Short answer: prompts are data, not code. They deserve version control, easy editing, and visibility outside of Python.

### Why does context.errors use append instead of raise?
Non-fatal agent failures (e.g., JSON parse error) shouldn't crash the whole pipeline. The user still gets results from other agents. Critical failures (missing API key, missing file) do raise immediately.

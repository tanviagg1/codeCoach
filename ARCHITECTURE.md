# CodeCoach AI — Architecture

## Design Philosophy

1. **Single Responsibility**: Every agent does exactly one job
2. **Explicit State**: All data flows through `AgentContext` — no hidden globals
3. **Prompts as Data**: Prompt templates live in `prompts/` files, not in code
4. **Fail Gracefully**: Agents append to `context.errors`, never crash the pipeline
5. **Testability**: Every agent can be unit-tested without a real Claude API call (mock the client)

---

## Phase 1 Architecture: Sequential Pipeline

```
main.py (CLI)
    |
    v
SequentialPipeline
    |
    ├── ReviewAgent       reads: code, language
    |                     writes: review_issues, review_summary
    |
    ├── TestGenAgent      reads: code, language, review_issues
    |                     writes: generated_tests
    |
    ├── ExplainerAgent    reads: code, language
    |                     writes: explanation
    |
    ├── TechDebtAgent     reads: code, review_issues
    |                     writes: debt_score, debt_hotspots
    |
    └── PRSummaryAgent    reads: review_summary, debt_score, explanation
                          writes: pr_title, pr_body
```

Each agent:
1. Validates prerequisites from context
2. Loads its prompt template from `prompts/`
3. Formats the prompt with context data
4. Calls Ollama (via `ollama.Client`)
5. Parses the response
6. Writes results back to context
7. Returns the enriched context

---

## AgentContext: The Shared State Object

```python
@dataclass
class AgentContext:
    # Input
    code: str
    filename: str
    language: str

    # After ReviewAgent
    review_issues: list[dict]      # [{line, message, severity}]
    review_summary: str

    # After TestGenAgent
    generated_tests: str           # Full pytest file as string

    # After ExplainerAgent
    explanation: str               # Plain-English explanation

    # After TechDebtAgent
    debt_score: int                # 0-100
    debt_hotspots: list[dict]      # [{line, description, severity}]

    # After PRSummaryAgent
    pr_title: str
    pr_body: str

    # Pipeline metadata
    timings: dict[str, float]
    errors: list[str]
    model: str                     # which Claude model was used
```

---

## Phase 3 Architecture: LangGraph

In Phase 3, the sequential pipeline is replaced with a LangGraph state machine.
This enables:
- **Parallel execution**: ReviewAgent and ExplainerAgent can run simultaneously
- **Conditional routing**: If debt_score > 80, send alert before continuing
- **Retry logic**: If an agent fails, retry it with a different prompt
- **Human-in-the-loop**: Pause for human approval before writing tests

```
          [ReviewAgent]
         /             \
[ExplainerAgent]   [TechDebtAgent]
         \             /
          [TestGenAgent]
               |
          [PRSummaryAgent]
               |
             END
```

---

## Phase 4 Architecture: RAG Memory

ChromaDB stores past code reviews as vector embeddings.

When a new file is submitted:
1. Query ChromaDB for similar past reviews
2. Inject top-3 most relevant past reviews into the ReviewAgent prompt
3. This improves review quality for recurring patterns

```
New Code File
     |
     v
EmbeddingService.embed(code)
     |
     v
ChromaDB.query(embedding, top_k=3)
     |
     v
Past Reviews injected into ReviewAgent prompt
     |
     v
ReviewAgent (now has context from past reviews)
     |
     v
Store new review in ChromaDB
```

---

## API Design

```
POST /review
    Body: { "code": "...", "filename": "app.py", "agents": ["all"] }
    Returns: AgentContext as JSON

POST /review/single
    Body: { "code": "...", "filename": "app.py", "agent": "review" }
    Returns: Single agent result

GET /history
    Returns: List of past reviews from ChromaDB

GET /health
    Returns: { "status": "ok", "model": "claude-sonnet-4-6" }
```

---

## Prompt Design

Each prompt template in `prompts/` follows this structure:
```
## Role
You are a [expert role]...

## Task
Your job is to [specific task]...

## Input
{{code}}

## Output Format
Return your response as JSON with this structure:
{ ... }

## Rules
- [constraints]
```

The `{{code}}` placeholder is replaced at runtime by the agent.

---

## Skills vs Agents

| | Skills (`skills/`) | Agents (`agents/`) |
|---|---|---|
| Purpose | Pure utility functions | Orchestrate LLM calls |
| Claude API | Never | Always |
| State | Stateless | Read/write context |
| Example | `parse_language(code)` | `ReviewAgent.run(ctx)` |

Skills are helpers — they parse, format, extract. Agents are decision-makers — they think.

---

## Error Handling Strategy

- **Fatal errors** (missing API key, file not found): raise immediately, stop pipeline
- **Agent errors** (Claude returns malformed JSON): log to `context.errors`, skip that agent, continue
- **Rate limits**: exponential backoff, max 3 retries
- **Empty code**: validate at entry point before pipeline starts

---

## Testing Strategy

```
Unit tests (no API calls):
  - Mock the anthropic.Anthropic client
  - Test agent logic: parsing, context reads/writes, error handling
  - Run with: pytest tests/ -m "not integration"

Integration tests (real API calls):
  - Test against real Claude API
  - Marked with @pytest.mark.integration
  - Run with: pytest tests/ -m "integration"
  - Requires ANTHROPIC_API_KEY env var
```

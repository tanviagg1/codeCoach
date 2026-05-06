# CodeCoach AI — Build Phases

---

## Phase 1: Core Agents + Sequential Pipeline (Current)
**Branch:** `feature/phase-1-core-agents`

### What gets built
- `AgentContext` — shared state dataclass
- `BaseAgent` — abstract base class
- `SequentialPipeline` — runs agents in order
- `ReviewAgent` — code quality + security issues
- `TestGenAgent` — generates pytest unit tests
- `ExplainerAgent` — plain-English explanation
- `main.py` — CLI to run pipeline on a file
- Prompt templates for all 3 agents
- Skills: code_parser, formatter
- Unit tests for all agents (mocked)

### What you learn
- AI agent pattern (perceive, decide, act)
- Sequential pipeline orchestration
- Shared state / accumulator pattern
- Prompt engineering fundamentals
- Claude Messages API

### Definition of Done
- `python main.py --file samples/bad_code.py` runs without errors
- Review issues are detected in `bad_code.py`
- Generated tests are syntactically valid Python
- All unit tests pass

---

## Phase 2: TechDebtAgent + PRSummaryAgent
**Branch:** `feature/phase-2-debt-pr`

### What gets built
- `TechDebtAgent` — debt score (0-100) + hotspot list
- `PRSummaryAgent` — reads output of 3 prior agents, writes PR title + body
- FastAPI `/review` endpoint
- Integration tests

### What you learn
- Chaining agents: later agents consume earlier agent output
- Getting LLMs to return reliable numeric scores
- Tool use / function calling for guaranteed JSON structure
- FastAPI request/response modeling

### Definition of Done
- `POST /review` returns full AgentContext as JSON
- debt_score is always an integer 0-100
- PR description reads naturally and references actual issues found

---

## Phase 3: LangGraph Orchestration
**Branch:** `feature/phase-3-langgraph`

### What gets built
- Replace `SequentialPipeline` with a LangGraph state machine
- ReviewAgent and ExplainerAgent run in parallel
- Conditional routing: if debt_score > 80, insert AlertAgent
- Retry logic: if ReviewAgent returns invalid JSON, retry once with a different prompt

### What you learn
- LangGraph: nodes, edges, conditional routing
- Parallel agent execution
- Human-in-the-loop checkpoints
- State machine design

### Definition of Done
- ReviewAgent and ExplainerAgent output arrive at the same time
- Pipeline handles ReviewAgent JSON failure by retrying gracefully
- LangGraph visual graph can be exported

---

## Phase 4: RAG Memory with ChromaDB
**Branch:** `feature/phase-4-rag`

### What gets built
- `EmbeddingService` — embeds code using Anthropic embeddings
- `VectorStore` — ChromaDB wrapper for storing/querying reviews
- `GET /history` endpoint — list past reviews
- RAG injection: top-3 similar past reviews are injected into ReviewAgent prompt

### What you learn
- What are embeddings? (meaning → numbers)
- Vector similarity search
- ChromaDB as a local vector database
- RAG architecture: retrieve → augment → generate
- Why RAG beats fine-tuning for most use cases

### Definition of Done
- After 5+ reviews stored, similar files get similar review patterns
- `/history` returns reviews sorted by similarity to a query
- Review quality improves measurably for recurring patterns

---

## Phase 5: Streamlit UI
**Branch:** `feature/phase-5-ui`

### What gets built
- Streamlit UI: paste code, click Review, see results in real time
- Streaming Claude responses (results appear as they generate)
- Review history dashboard: past reviews, trends, debt scores over time
- Export to PDF or Markdown

### What you learn
- Streamlit for rapid AI UI development
- Streaming responses from Claude API
- Visualizing AI output (charts, color-coded severity)
- Session state management in Streamlit

### Definition of Done
- Full pipeline visible in browser with real-time streaming
- Review history shows trend charts
- Can export any review as Markdown

---

## Future Ideas (Post Phase 5)

- **GitHub integration**: trigger CodeCoach on every PR via GitHub Actions
- **VS Code extension**: right-click any file → "CodeCoach Review"
- **Slack bot**: post review summaries to a Slack channel
- **Team analytics**: track which engineers have the most HIGH severity issues over time
- **Multi-language support**: add specialized ReviewAgent prompts for Java, TypeScript, Go
- **Custom rule sets**: teams define their own rules in a config file

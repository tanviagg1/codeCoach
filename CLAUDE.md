# CodeCoach AI

## Purpose
Multi-agent AI system that reviews code, generates tests, analyzes tech debt, explains code to junior developers, and drafts PR descriptions — all powered by the Claude API.

## Stack
- LLM: Anthropic Claude API (claude-sonnet-4-6)
- Agent Framework: Sequential pipeline (Phase 1), LangGraph (Phase 3)
- RAG Memory: ChromaDB + Anthropic embeddings (Phase 3)
- API: FastAPI
- Tests: pytest
- UI: Streamlit (Phase 5)

## Folder Structure
```
codeCoach/
├── agents/           # One file per agent — each does ONE job
├── prompts/          # All prompt templates as .md files — NEVER inline prompts in code
├── skills/           # Reusable tools agents can call
├── api/              # FastAPI app
├── memory/           # ChromaDB vector store
├── hooks/            # Pre/post review lifecycle hooks
├── tests/            # pytest unit + integration tests
├── samples/          # Sample code files for testing the pipeline
├── .claude/          # Claude Code settings and hooks
├── CLAUDE.md         # This file — always read first
├── ARCHITECTURE.md   # Deep technical design
├── LEARNINGS.md      # AI engineering concepts — update after each phase
├── AI_CONCEPTS.md    # Reference: tokens, temperature, embeddings, RAG
├── AGENTS_GUIDE.md   # How to read/write/test agents
├── PROMPTS_GUIDE.md  # How prompts are structured and why
└── PHASES.md         # Build roadmap — which phase adds what
```

## How to Run

### Prerequisites
```bash
export ANTHROPIC_API_KEY=your_key_here
pip install -r requirements.txt
```

### Run the full pipeline on a file
```bash
python main.py --file samples/bad_code.py
```

### Run a specific agent only
```bash
python main.py --file samples/bad_code.py --agent review
python main.py --file samples/bad_code.py --agent tests
python main.py --file samples/bad_code.py --agent explain
python main.py --file samples/bad_code.py --agent debt
python main.py --file samples/bad_code.py --agent pr
```

### Run the API
```bash
uvicorn api.main:app --reload
```

### Run tests
```bash
pytest tests/ -v
pytest tests/ -m "not integration"   # skip tests that call Claude API
```

## Key API Endpoints
- `POST /review` — Run full pipeline on submitted code
- `POST /review/single` — Run one agent on submitted code
- `GET /history` — Fetch past reviews from ChromaDB
- `GET /docs` — FastAPI auto-generated Swagger UI

## Conventions
- Prompts live in `prompts/` as `.md` files — never hardcode prompts inside agent files
- Each agent has ONE responsibility — if it does two things, split it
- Agents communicate via `AgentContext` — never pass raw strings between agents
- Skills in `skills/` are pure functions — no side effects, no API calls
- All Claude API calls go through the agent, not the skill
- Tests that call Claude API must be marked `@pytest.mark.integration`
- The `AgentContext.errors` list is how agents report non-fatal issues
- Update `LEARNINGS.md` after each new concept is introduced

## Branch Strategy
- `main` — stable, always deployable
- `feature/phase-1-core-agents` — ReviewAgent, TestGenAgent, ExplainerAgent, CLI
- `feature/phase-2-debt-pr` — TechDebtAgent, PRSummaryAgent
- `feature/phase-3-langgraph` — Replace sequential pipeline with LangGraph
- `feature/phase-4-rag` — ChromaDB memory, review history
- `feature/phase-5-ui` — Streamlit dashboard

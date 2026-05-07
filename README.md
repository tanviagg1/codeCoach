# CodeCoach AI

> A multi-agent AI system that acts as your personal senior developer — reviewing code, generating tests, explaining logic, catching tech debt, and writing your PR descriptions.

## What It Does

Paste any code file into CodeCoach and get back:

| Agent | What it produces |
|---|---|
| ReviewAgent | Code quality issues, security flags, style violations |
| TestGenAgent | Ready-to-run pytest unit tests |
| ExplainerAgent | Plain-English explanation for junior developers |
| TechDebtAgent | Tech debt hotspots with severity scores |
| PRSummaryAgent | A complete PR title + description |

## Quick Start

```bash
# 1. Install Ollama from https://ollama.com then pull the model
ollama pull llama3.1:8b

# 2. Clone and install
git clone https://github.com/tanviagarwal/codeCoach.git
cd codeCoach
pip install -r requirements.txt

# 3. Run on any Python file
python main.py --file samples/bad_code.py

# 4. Or hit the API
uvicorn api.main:app --reload
# then POST to http://localhost:8000/review
```

## Example Output

```
[ReviewAgent]
  Issues found: 4
  - Line 12: No input validation on user_id parameter (HIGH)
  - Line 28: Hardcoded secret key — use environment variable (CRITICAL)
  - Line 45: Nested loops O(n^2) — consider dict lookup (MEDIUM)
  - Line 67: Broad except clause swallows all errors (LOW)
  Done in 3.2s

[TestGenAgent]
  Generated 6 test cases
  Coverage target: happy path + 3 edge cases + 2 error cases
  Done in 4.1s

[ExplainerAgent]
  Summary: This module handles user authentication...
  Done in 2.8s

[TechDebtAgent]
  Debt score: 62/100 (MODERATE)
  Hotspots: 3
  Done in 2.5s

[PRSummaryAgent]
  PR title: "fix: add input validation and remove hardcoded secrets"
  Done in 1.9s
```

## Architecture

```
Code Input
    |
    v
[ReviewAgent] --> Issues + Severity
    |
    v
[TestGenAgent] --> pytest test file
    |
    v
[ExplainerAgent] --> Plain-English explanation
    |
    v
[TechDebtAgent] --> Debt score + hotspots
    |
    v
[PRSummaryAgent] --> PR title + body
    |
    v
Final Report
```

All agents share an `AgentContext` object — the state that flows through the pipeline.

## Learning Resources in This Repo

- `LEARNINGS.md` — AI engineering concepts explained as you build
- `AI_CONCEPTS.md` — Reference: tokens, temperature, embeddings, RAG
- `AGENTS_GUIDE.md` — How to write and test a new agent
- `PROMPTS_GUIDE.md` — Prompt engineering patterns used here
- `ARCHITECTURE.md` — Full technical design decisions
- `PHASES.md` — Roadmap: what gets built in each phase

## Project Phases

- **Phase 1** (current): Core agents + sequential pipeline + CLI
- **Phase 2**: TechDebtAgent + PRSummaryAgent
- **Phase 3**: Replace pipeline with LangGraph (branching, retries)
- **Phase 4**: ChromaDB RAG — store and recall past reviews
- **Phase 5**: Streamlit UI dashboard

## Tech Stack

- **LLM**: Ollama (`llama3.1:8b` — local, no API key needed)
- **Orchestration**: Sequential pipeline → LangGraph
- **Memory**: ChromaDB (vector store for past reviews)
- **API**: FastAPI
- **Tests**: pytest
- **UI**: Streamlit (Phase 5)

## License
MIT

# CodeCoach AI — Learnings

This file documents AI engineering concepts introduced in each phase.
Update it as you complete each phase.

---

## Phase 1 Concepts: Core Agents + Sequential Pipeline

### 1. What is an AI Agent?
An agent is an autonomous unit that:
1. **Perceives** — reads input (code, context)
2. **Decides** — reasons about what to do (via LLM)
3. **Acts** — produces output (review, tests, explanation)

The key difference from a simple function call: an agent uses a language model to *reason*, not just compute.

```python
# Not an agent (just a function)
def count_lines(code): return len(code.splitlines())

# An agent (uses LLM to reason)
class ReviewAgent:
    def run(self, context):
        prompt = self.build_prompt(context.code)
        response = self.claude.messages.create(...)  # LLM reasons here
        context.review_issues = self.parse(response)
        return context
```

### 2. What is a Pipeline?
A pipeline chains multiple agents so output from one becomes input to the next.

```
[Agent1] --> context --> [Agent2] --> context --> [Agent3]
```

Benefits:
- Each agent is focused and testable
- Context accumulates — later agents can use earlier results
- Easy to add/remove/reorder agents

### 3. What is Agent Context / Shared State?
Instead of passing dozens of parameters between agents, we use a single context object — a dataclass that starts small and gets enriched as it flows through the pipeline.

```python
# Context starts with just input
ctx = AgentContext(code="...", filename="app.py", language="python")

# After ReviewAgent
ctx.review_issues = [...]

# After TestGenAgent (can now read review_issues)
ctx.generated_tests = "..."
```

This is the **accumulator pattern** — context grows richer at each step.

### 4. What is Prompt Engineering?
The art of writing instructions for an LLM so it produces the output you want.

Key techniques used in CodeCoach:
- **Role prompting**: "You are a senior Python engineer with 10 years of experience"
- **Output format control**: "Return JSON with exactly these fields: {issues: [], summary: str}"
- **Constraints**: "Only flag issues in the submitted code, not imaginary improvements"
- **Examples (few-shot)**: Show the LLM a sample input/output pair before the real task

Why prompts live in files (`prompts/*.md`):
- Version-controlled separately from code
- Easy to A/B test different prompts
- Non-engineers can read and improve them
- Never lose a prompt when refactoring

### 5. What is the Ollama Chat API?
Ollama runs LLMs locally. The Python client follows the same messages format:

```python
import ollama

client = ollama.Client()
response = client.chat(
    model="llama3.1:8b",
    messages=[
        {"role": "system", "content": "You are a code reviewer..."},  # role + rules
        {"role": "user", "content": code}  # the actual input
    ],
    options={"temperature": 0.2}  # controls randomness
)
result = response.message.content  # the LLM's response
```

Key parameters:
- `model` — which Ollama model to use (must be pulled first: `ollama pull llama3.1:8b`)
- `messages` — conversation history with system + user roles
- `options.temperature` — 0.0 = deterministic, 1.0 = creative
- No API key needed — runs fully local

### 6. What is Temperature?
Temperature controls how "creative" or "random" the LLM's output is.

| Temperature | Behavior | Good for |
|---|---|---|
| 0.0 | Always the same output | JSON extraction, structured data |
| 0.3 | Mostly consistent, slight variation | Code review, analysis |
| 0.7 | Creative, varied | PR descriptions, explanations |
| 1.0 | Very creative, can hallucinate | Brainstorming |

CodeCoach uses:
- `temperature=0.2` for ReviewAgent (want consistent, structured JSON)
- `temperature=0.3` for TestGenAgent (mostly deterministic test code)
- `temperature=0.7` for ExplainerAgent (want natural-sounding explanations)
- `temperature=0.6` for PRSummaryAgent (professional but readable)

---

## Phase 2 Concepts: TechDebtAgent + PRSummaryAgent (Coming Soon)

- Chaining agent outputs: PRSummaryAgent reads from 3 previous agents
- Scoring systems: how to get LLMs to return numeric scores reliably
- Response validation: ensuring LLM returns valid JSON every time

---

## Phase 3 Concepts: LangGraph (Coming Soon)

- Graph-based orchestration vs sequential pipelines
- Nodes vs edges in LangGraph
- Conditional routing: different paths based on agent output
- Parallel agent execution
- Human-in-the-loop checkpoints

---

## Phase 4 Concepts: RAG Memory (Coming Soon)

- What are embeddings? (vectors that encode meaning)
- Vector similarity search (cosine similarity)
- ChromaDB: a local vector database
- Retrieval-Augmented Generation (RAG): inject past knowledge into prompts
- Why RAG beats fine-tuning for most use cases

---

## Phase 5 Concepts: Streamlit UI (Coming Soon)

- Building AI UIs with Streamlit
- Streaming Claude responses to the UI in real time
- Session state management

---

## Key Vocabulary Reference

| Term | Definition |
|---|---|
| Agent | Autonomous unit that uses LLM to reason and act |
| Pipeline | Chain of agents where output flows forward |
| Context | Shared state object that accumulates data |
| Prompt | Instructions given to the LLM |
| System prompt | Sets the LLM's role and behavior |
| Token | Smallest unit of text an LLM processes (~4 chars) |
| Temperature | Controls randomness in LLM output |
| Embedding | Vector representation of text meaning |
| RAG | Retrieval-Augmented Generation — inject retrieved docs into prompts |
| LangGraph | Framework for building stateful, graph-based agent workflows |
| ChromaDB | Local vector database for storing embeddings |

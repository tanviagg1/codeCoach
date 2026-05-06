# AI Concepts Reference

A deeper reference for AI/ML concepts used in CodeCoach AI.
Read this when you want to understand *why* things work the way they do.

---

## Tokens

**What they are:** The smallest unit of text a language model processes. Not a word, not a character — a *token* is somewhere in between.

Examples:
- "Hello" = 1 token
- "CodeCoach" = 2 tokens (Code, Coach)
- "supercalifragilistic" = 6 tokens

**Why it matters:**
- Claude models have a context window measured in tokens (claude-sonnet-4-6 = 200K tokens)
- API costs are per token (input + output)
- `max_tokens` in your API call limits response length
- Long code files can use many tokens — be mindful

**Rule of thumb:** 1 token ≈ 4 characters ≈ 0.75 words

---

## Context Window

**What it is:** The maximum amount of text (input + output) a model can process in a single call.

Claude claude-sonnet-4-6: 200,000 tokens ≈ 150,000 words ≈ 500 pages

**In CodeCoach:** Each agent call gets:
- System prompt (~300 tokens)
- The code being reviewed (~varies)
- Past examples if RAG is active (~500 tokens)
- Response (max_tokens we set)

For large files, we may need to chunk the code before sending it.

---

## System Prompt vs User Message

```python
client.messages.create(
    system="You are a senior Python engineer...",  # System prompt
    messages=[
        {"role": "user", "content": "Review this code: ..."}  # User message
    ]
)
```

| | System Prompt | User Message |
|---|---|---|
| Sets | Role, rules, output format | The actual task input |
| Persists | Throughout the conversation | Per message |
| Analogous to | Job description | Work request |

**Best practice:** Put constraints and format instructions in the system prompt. Put the actual code/data in the user message.

---

## Temperature and Top-P

**Temperature** controls randomness:
```
temperature=0.0 → always picks the most likely next token (deterministic)
temperature=1.0 → picks from a wider distribution (creative, unpredictable)
```

**Top-P (nucleus sampling)** is an alternative: only sample from the top P% of likely tokens.

In practice:
- Use `temperature=0.0–0.3` for structured data extraction (JSON, scores)
- Use `temperature=0.5–0.8` for natural language generation (PR descriptions)
- Never use both temperature and top_p at high values — outputs become incoherent

---

## Embeddings

**What they are:** A way to convert text into a list of numbers (a vector) that encodes its *meaning*.

```
"Python function" → [0.23, -0.87, 0.45, ..., 0.12]  (1536 dimensions)
"def my_func()"  → [0.21, -0.89, 0.44, ..., 0.09]  (similar! same meaning)
"pizza recipe"   → [-0.67, 0.34, -0.21, ..., 0.55] (very different)
```

**Why they matter:**
- Two similar texts have similar vectors (close in vector space)
- This lets us find "similar code reviews" without exact keyword matching
- Used in Phase 4 (RAG) to retrieve relevant past reviews

**Cosine similarity:** The standard way to measure how close two vectors are. Range: -1 (opposite) to 1 (identical).

---

## Retrieval-Augmented Generation (RAG)

**The problem RAG solves:** LLMs only know what they learned during training. They don't know about *your* codebase, *your* past reviews, or events after their training cutoff.

**RAG solution:** Before asking the LLM a question, *retrieve* relevant documents from a database and inject them into the prompt.

```
User submits code
    |
    v
Embed the code → vector
    |
    v
Search ChromaDB for similar past reviews
    |
    v
Top 3 similar reviews retrieved
    |
    v
Inject into prompt:
  "Here are 3 similar past reviews for context: [...]
   Now review this new code: [code]"
    |
    v
LLM has context from past reviews → better output
```

**Why RAG beats fine-tuning:**
- Fine-tuning is expensive, slow, and requires thousands of examples
- RAG works with any amount of data, updated in real-time
- RAG's retrieved context is visible — you can debug what it retrieved

---

## LangGraph (Phase 3 Concept)

**What it is:** A framework for building agents as a graph (nodes + edges) instead of a linear sequence.

**Why use it:**
- **Parallel nodes**: ReviewAgent and ExplainerAgent can run at the same time
- **Conditional edges**: "if debt_score > 80, route to AlertAgent first"
- **Cycles**: retry an agent if its output fails validation
- **Checkpointing**: save state mid-pipeline, resume later

```python
from langgraph.graph import StateGraph

builder = StateGraph(AgentContext)
builder.add_node("review", review_agent.run)
builder.add_node("tests", test_gen_agent.run)
builder.add_edge("review", "tests")  # review must finish before tests
```

---

## Chain of Thought Prompting

**What it is:** Asking the LLM to "think step by step" before giving its final answer.

```
Without CoT:
  User: Is this code secure?
  LLM: No.

With CoT:
  User: Think step by step. Is this code secure?
  LLM:
    Step 1: Check for SQL injection... I see a raw string query on line 12.
    Step 2: Check for hardcoded secrets... I see a password on line 28.
    Step 3: Check for input validation... No validation on user_id.
    Conclusion: Not secure. Issues: [SQL injection, hardcoded password, no validation]
```

CoT dramatically improves accuracy on reasoning tasks. Used in ReviewAgent and TechDebtAgent.

---

## Structured Output / JSON Mode

**The challenge:** LLMs produce text. We need structured data (JSON) to process programmatically.

**Techniques:**
1. **Prompt the format**: "Return JSON with exactly: {issues: [], summary: str}"
2. **Validate the response**: parse JSON, check fields, retry if malformed
3. **Anthropic tool use**: force structured output via tool definitions (Phase 2+)

In CodeCoach Phase 1, we use technique 1 + 2. In Phase 2, we upgrade to tool use for guaranteed structure.

---

## Few-Shot Prompting

**What it is:** Showing the LLM 1–3 examples of input/output pairs before the real task.

```
# Zero-shot (no examples)
"Review this code: [code]"

# One-shot (one example)
"Here is an example review:
  Input: [sample code]
  Output: {issues: [{line: 5, msg: 'No error handling', severity: 'HIGH'}]}

Now review this code: [real code]"
```

Few-shot prompting improves output consistency, especially for custom JSON formats.
Used in ReviewAgent when we want consistent severity scoring.

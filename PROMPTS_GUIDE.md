# Prompts Guide

How prompts are structured in CodeCoach AI and why.

---

## The Golden Rule

**Prompts are data, not code.** They live in `prompts/*.md` files, not inside Python agents.

Why:
- Prompts change frequently — separating them means no Python changes needed
- Non-engineers can read and suggest improvements
- You can A/B test two prompts without touching agent code
- Version history in git shows exactly what changed in the prompt
- Prompts can be reviewed independently in code review

---

## Prompt File Structure

Every prompt in CodeCoach follows this template:

```markdown
## Role
You are a [specific expert persona]. [1-2 sentences of context about their expertise].

## Task
Your job is to [specific, single task]. [Any important constraints].

## Input
{{code}}

(optional: other placeholders like {{language}}, {{issues}})

## Output Format
Return your response as JSON with exactly this structure:
{
  "field1": ...,
  "field2": ...
}
Do not include markdown code blocks. Return raw JSON only.

## Rules
- [Rule 1]
- [Rule 2]
- [Rule 3]
```

---

## The Placeholders

Each prompt uses `{{placeholder}}` syntax. The agent replaces these at runtime:

```python
prompt = self.prompt_template
prompt = prompt.replace("{{code}}", context.code)
prompt = prompt.replace("{{language}}", context.language)
```

Placeholders used across prompts:
- `{{code}}` — the source code to analyze
- `{{language}}` — the programming language (python, javascript, etc.)
- `{{issues}}` — JSON list of issues from ReviewAgent (used in TestGenAgent)
- `{{summary}}` — review summary (used in PRSummaryAgent)

---

## Why Each Prompt Section Matters

### Role
Setting a clear expert persona dramatically improves output quality.

```
Bad:  "Review this code."
Good: "You are a senior Python engineer with 10 years of experience in security
       and production systems. You have reviewed thousands of code changes."
```

The model performs better when it "knows" it should act as an expert.

### Task
One sentence, one task. If you find yourself writing "and also", split into two agents.

```
Bad:  "Review this code for bugs and also generate tests and explain it."
Good: "Review this code for bugs, security issues, and style problems."
```

### Output Format
The most important section for programmatic use. Be extremely explicit:
- Specify exact field names
- Specify exact types (string, array, integer 0-100)
- Say "Return raw JSON only" — otherwise the model wraps it in markdown code blocks
- Show an example if the structure is complex

### Rules
Constraints that prevent the most common LLM failure modes:
- "Only flag issues in the submitted code" — prevents hallucinating issues
- "Do not suggest architectural changes" — keeps scope tight
- "If no issues found, return an empty array" — prevents "None found" free-text

---

## Prompt Engineering Patterns Used in CodeCoach

### 1. Role + Expert Framing
Every prompt starts with: "You are a senior [X] with [Y years] experience in [Z]."

### 2. Output Format Enforcement
Every prompt that needs structured data ends with:
```
Return raw JSON only. No markdown. No code blocks. No explanation.
```

### 3. Severity Vocabulary Control
ReviewAgent and TechDebtAgent constrain severity to exact values:
```
Severity must be exactly one of: "CRITICAL", "HIGH", "MEDIUM", "LOW"
```
Without this, the LLM invents values like "Very High", "Minor", "Serious".

### 4. Negative Constraints
Tell the model what NOT to do. LLMs follow negative constraints well:
```
- Do NOT suggest refactoring unrelated code
- Do NOT flag style issues as security issues
- Do NOT return empty arrays with placeholder text
```

### 5. Chain of Thought for Complex Reasoning
For TechDebtAgent and ReviewAgent, the system prompt ends with:
```
Think step by step before producing your final JSON output.
```
This improves accuracy on complex analysis.

---

## Testing Your Prompts

Before committing a new prompt, test it with:
```bash
# Quick prompt test (requires ANTHROPIC_API_KEY)
python scripts/test_prompt.py --prompt prompts/review.md --file samples/bad_code.py
```

What to check:
1. Is the output valid JSON? (parse it)
2. Do all expected fields exist?
3. Are severity values from the allowed set?
4. Does the model flag known issues in `bad_code.py`?
5. Does the model NOT flag issues in `good_code.py`?

---

## Iterating on Prompts

When a prompt produces bad output:
1. Add the bad output to a test case so you can reproduce it
2. Identify which rule the model broke
3. Add a specific constraint to the Rules section
4. Re-test with `test_prompt.py`
5. Commit with a message describing what you fixed: `prompts: add constraint to prevent hallucinated line numbers`

---

## Prompt Versioning

Prompts are versioned with git like any other file.
When making a significant prompt change:
1. Note the change in the commit message
2. Update `LEARNINGS.md` if it introduces a new pattern
3. Run the full test suite to confirm no regressions

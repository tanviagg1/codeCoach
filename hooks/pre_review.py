"""
pre_review — validation hooks that run before the pipeline starts.

These are NOT Claude Code hooks (those are in .claude/settings.json).
These are Python lifecycle hooks: validation logic that runs before
any agents execute.

Usage in main.py:
    from hooks.pre_review import validate_inputs, check_ollama
    validate_inputs(code, filename)
    check_ollama(model)
"""

from pathlib import Path


def validate_inputs(code: str, filename: str) -> None:
    """
    Validate pipeline inputs before starting any agents.

    Raises ValueError with a clear message if validation fails.
    These are fatal errors — the pipeline should not start.
    """
    if not code or not code.strip():
        raise ValueError(
            "Cannot review empty code. "
            "Provide a non-empty source file."
        )

    if len(code) > 500_000:
        raise ValueError(
            f"Code is too large ({len(code):,} chars). "
            "Maximum is 500,000 characters. Consider reviewing a specific function or class."
        )

    if not filename:
        raise ValueError("Filename is required (used to detect language and name the report).")

    try:
        code.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Code contains non-UTF-8 characters. Only text files are supported.")


def check_ollama(model: str = "llama3.1:8b") -> None:
    """
    Verify Ollama is running and the requested model is available.

    Raises EnvironmentError if Ollama is not reachable or model is missing.
    """
    try:
        import ollama
        client = ollama.Client()
        available = [m.model for m in client.list().models]
        if not any(model in m for m in available):
            raise EnvironmentError(
                f"Model '{model}' is not pulled in Ollama.\n"
                f"Run: ollama pull {model}\n"
                f"Available models: {available or ['(none)']}"
            )
    except ImportError:
        raise EnvironmentError(
            "ollama Python package not installed.\n"
            "Run: pip install ollama"
        )
    except Exception as e:
        if "EnvironmentError" in type(e).__name__:
            raise
        raise EnvironmentError(
            f"Cannot connect to Ollama: {e}\n"
            "Make sure Ollama is running: ollama serve"
        )


def check_prompts_exist(agent_names: list[str]) -> None:
    """
    Verify that prompt files exist for all requested agents.

    Raises FileNotFoundError if any prompt file is missing.
    """
    prompt_map = {
        "review": "prompts/review.md",
        "tests": "prompts/test_gen.md",
        "explain": "prompts/explainer.md",
        "debt": "prompts/tech_debt.md",
        "pr": "prompts/pr_summary.md",
    }
    for name in agent_names:
        prompt_path = prompt_map.get(name)
        if prompt_path and not Path(prompt_path).exists():
            raise FileNotFoundError(
                f"Prompt file missing for agent '{name}': {prompt_path}\n"
                "See PROMPTS_GUIDE.md to create it."
            )

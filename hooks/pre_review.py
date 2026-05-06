"""
pre_review — validation hooks that run before the pipeline starts.

These are NOT Claude Code hooks (those are in .claude/settings.json).
These are Python lifecycle hooks: validation logic that runs before
any agents execute.

Usage in main.py:
    from hooks.pre_review import validate_inputs
    validate_inputs(code, filename)
"""

import os
from pathlib import Path


def validate_inputs(code: str, filename: str) -> None:
    """
    Validate pipeline inputs before starting any agents.

    Raises ValueError with a clear message if validation fails.
    These are fatal errors — the pipeline should not start.

    Args:
        code: Source code to review
        filename: Name of the source file
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

    # Warn about binary files
    try:
        code.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Code contains non-UTF-8 characters. Only text files are supported.")


def check_api_key() -> None:
    """
    Verify the Anthropic API key is set before starting the pipeline.

    Raises EnvironmentError if the key is missing.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY environment variable is not set.\n"
            "Set it with: export ANTHROPIC_API_KEY=your_key_here\n"
            "Get a key at: https://console.anthropic.com"
        )
    if not key.startswith("sk-ant-"):
        raise EnvironmentError(
            "ANTHROPIC_API_KEY looks invalid (should start with 'sk-ant-'). "
            "Check your key at https://console.anthropic.com"
        )


def check_prompts_exist(agent_names: list[str]) -> None:
    """
    Verify that prompt files exist for all requested agents.

    Args:
        agent_names: List of agent names to check (e.g., ["review", "tests"])

    Raises:
        FileNotFoundError if any prompt file is missing
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

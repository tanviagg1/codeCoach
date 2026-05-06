"""
code_parser — utilities for extracting structural information from source code.

These are pure functions: no side effects, no API calls.
Agents use these skills to preprocess code before sending it to Claude.

See ARCHITECTURE.md: "Skills vs Agents" section.
"""

import re
from pathlib import Path


def detect_language(filename: str) -> str:
    """
    Detect the programming language from a filename extension.

    Args:
        filename: The name of the source file (e.g., "app.py", "index.ts")

    Returns:
        A lowercase language string (e.g., "python", "typescript")
    """
    extension_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rb": "ruby",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".sh": "bash",
        ".sql": "sql",
    }
    ext = Path(filename).suffix.lower()
    return extension_map.get(ext, "unknown")


def count_lines(code: str) -> int:
    """Return the number of lines in the code."""
    return len(code.splitlines())


def extract_functions(code: str, language: str = "python") -> list[str]:
    """
    Extract function/method names from code.

    Simple regex-based extraction — not a full AST parser.
    Good enough for prompt context, not for production tooling.

    Args:
        code: Source code string
        language: Programming language

    Returns:
        List of function names found
    """
    patterns = {
        "python": r"^\s*(?:async\s+)?def\s+(\w+)\s*\(",
        "javascript": r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?\()",
        "typescript": r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?\()",
        "java": r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(",
        "go": r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(",
    }
    pattern = patterns.get(language, patterns["python"])
    matches = re.findall(pattern, code, re.MULTILINE)
    # Flatten tuples from groups (javascript pattern has 2 groups)
    return [m if isinstance(m, str) else next((g for g in m if g), "") for m in matches]


def truncate_code(code: str, max_lines: int = 500) -> str:
    """
    Truncate code to a maximum number of lines.

    Used when code is too long to fit in the Claude context window.
    Adds a comment noting the truncation.

    Args:
        code: Source code string
        max_lines: Maximum number of lines to keep

    Returns:
        Truncated code with a truncation notice if needed
    """
    lines = code.splitlines()
    if len(lines) <= max_lines:
        return code
    kept = lines[:max_lines]
    kept.append(f"# ... (truncated at {max_lines} lines — {len(lines) - max_lines} lines omitted)")
    return "\n".join(kept)


def estimate_tokens(text: str) -> int:
    """
    Rough estimate of token count for a text string.

    Rule of thumb: 1 token ≈ 4 characters.
    This is a heuristic, not exact. Use for pre-flight checks only.

    Args:
        text: Any text string

    Returns:
        Estimated token count
    """
    return len(text) // 4

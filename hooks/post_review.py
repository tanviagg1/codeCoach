"""
post_review — actions that run after the pipeline completes.

These are Python lifecycle hooks — not Claude Code hooks.
They handle saving output, writing test files to disk, and logging.

Usage in main.py:
    from hooks.post_review import save_outputs, log_summary
    save_outputs(context, output_dir="output")
"""

import json
import os
from datetime import datetime
from pathlib import Path

from agents.context import AgentContext


def save_outputs(context: AgentContext, output_dir: str = "output") -> dict[str, str]:
    """
    Save all agent outputs to the output directory.

    Creates:
    - output/<filename>_review.json    — structured review issues + debt
    - output/<filename>_tests.py       — generated pytest file
    - output/<filename>_explanation.txt — plain-English explanation
    - output/<filename>_pr.md          — PR title + body in markdown

    Args:
        context: Fully run AgentContext
        output_dir: Directory to write files to

    Returns:
        Dict mapping output type → file path written
    """
    Path(output_dir).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(context.filename).stem
    paths = {}

    # Review JSON
    if context.review_issues or context.review_summary:
        review_data = {
            "filename": context.filename,
            "language": context.language,
            "issues": context.review_issues,
            "summary": context.review_summary,
            "debt_score": context.debt_score,
            "debt_hotspots": context.debt_hotspots,
            "timings": context.timings,
            "errors": context.errors,
            "model": context.model,
            "reviewed_at": timestamp,
        }
        path = f"{output_dir}/{base}_review_{timestamp}.json"
        Path(path).write_text(json.dumps(review_data, indent=2))
        paths["review"] = path
        print(f"  Review saved: {path}")

    # Generated tests
    if context.generated_tests:
        path = f"{output_dir}/{base}_tests_{timestamp}.py"
        Path(path).write_text(context.generated_tests)
        paths["tests"] = path
        print(f"  Tests saved:  {path}")

    # Explanation
    if context.explanation:
        path = f"{output_dir}/{base}_explanation_{timestamp}.txt"
        Path(path).write_text(context.explanation)
        paths["explanation"] = path
        print(f"  Explanation:  {path}")

    # PR description
    if context.pr_title or context.pr_body:
        pr_content = f"# {context.pr_title}\n\n{context.pr_body}"
        path = f"{output_dir}/{base}_pr_{timestamp}.md"
        Path(path).write_text(pr_content)
        paths["pr"] = path
        print(f"  PR summary:   {path}")

    return paths


def log_summary(context: AgentContext) -> None:
    """
    Print a concise summary of what the pipeline produced.

    Used at the end of main.py to give the user a quick overview
    before they look at the full output files.
    """
    issue_count = len(context.review_issues)
    critical = sum(1 for i in context.review_issues if i.get("severity") == "CRITICAL")
    high = sum(1 for i in context.review_issues if i.get("severity") == "HIGH")

    print("\n" + "=" * 50)
    print("  CODECOACH SUMMARY")
    print("=" * 50)
    print(f"  File:    {context.filename} ({context.language})")
    print(f"  Issues:  {issue_count} total ({critical} critical, {high} high)")

    if context.debt_score is not None:
        print(f"  Debt:    {context.debt_score}/100")

    if context.generated_tests:
        test_count = context.generated_tests.count("def test_")
        print(f"  Tests:   {test_count} generated")

    if context.pr_title:
        print(f"  PR:      {context.pr_title}")

    if context.errors:
        print(f"  Errors:  {len(context.errors)} warning(s)")

    total_time = sum(context.timings.values())
    print(f"  Time:    {total_time:.1f}s total")
    print("=" * 50)

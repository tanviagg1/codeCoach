"""
formatter — utilities for formatting pipeline output for display.

Pure functions that take AgentContext data and produce formatted strings.
Used by main.py to print the final report and by the API to structure responses.
"""

from agents.context import AgentContext


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
SEVERITY_SYMBOLS = {
    "CRITICAL": "[CRITICAL]",
    "HIGH":     "[HIGH]    ",
    "MEDIUM":   "[MEDIUM]  ",
    "LOW":      "[LOW]     ",
}


def format_review_issues(issues: list) -> str:
    """Format review issues as a sorted, readable table."""
    if not issues:
        return "  No issues found. Clean code!"
    sorted_issues = sorted(issues, key=lambda i: SEVERITY_ORDER.get(i.get("severity", "LOW"), 9))
    lines = []
    for issue in sorted_issues:
        sym = SEVERITY_SYMBOLS.get(issue.get("severity", "LOW"), "[?]       ")
        line = issue.get("line", "?")
        msg = issue.get("message", "")
        lines.append(f"  {sym} Line {line:>4}: {msg}")
    return "\n".join(lines)


def format_debt_score(score: int, hotspots: list) -> str:
    """Format tech debt score with a visual bar."""
    if score is None:
        return "  Debt analysis not run."

    filled = int(score / 10)
    bar = "=" * filled + "-" * (10 - filled)
    label = (
        "PRISTINE" if score < 20
        else "LOW" if score < 40
        else "MODERATE" if score < 60
        else "HIGH" if score < 80
        else "CRITICAL"
    )

    lines = [f"  Debt Score: {score}/100 [{bar}] {label}"]
    if hotspots:
        lines.append("  Hotspots:")
        for h in hotspots:
            sym = SEVERITY_SYMBOLS.get(h.get("severity", "LOW"), "[?]       ")
            lines.append(f"    {sym} Line {h.get('line', '?'):>4}: {h.get('description', '')}")
    return "\n".join(lines)


def format_full_report(context: AgentContext) -> str:
    """Produce the complete final report from a fully run AgentContext."""
    sep = "=" * 60
    lines = [
        sep,
        f"  CodeCoach AI Report — {context.filename}",
        sep,
    ]

    # Review issues
    lines.append("\nCODE REVIEW")
    lines.append("-" * 40)
    lines.append(format_review_issues(context.review_issues))
    if context.review_summary:
        lines.append(f"\n  Summary: {context.review_summary}")

    # Tech debt
    lines.append("\nTECH DEBT")
    lines.append("-" * 40)
    lines.append(format_debt_score(context.debt_score, context.debt_hotspots))

    # Explanation
    if context.explanation:
        lines.append("\nCODE EXPLANATION")
        lines.append("-" * 40)
        for para in context.explanation.split("\n\n"):
            lines.append(f"  {para.strip()}")

    # Generated tests
    if context.generated_tests:
        lines.append("\nGENERATED TESTS")
        lines.append("-" * 40)
        test_count = context.generated_tests.count("def test_")
        lines.append(f"  {test_count} test function(s) generated.")
        lines.append("  Run with: pytest generated_tests.py")

    # PR Summary
    if context.pr_title:
        lines.append("\nPR SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Title: {context.pr_title}")
        lines.append("")
        for body_line in context.pr_body.splitlines():
            lines.append(f"  {body_line}")

    # Pipeline metadata
    if context.timings:
        lines.append("\nPIPELINE TIMINGS")
        lines.append("-" * 40)
        for name, t in context.timings.items():
            lines.append(f"  {name:<25} {t}s")

    if context.errors:
        lines.append("\nWARNINGS")
        lines.append("-" * 40)
        for err in context.errors:
            lines.append(f"  ! {err}")

    lines.append("\n" + sep)
    return "\n".join(lines)

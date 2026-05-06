"""
main.py — CLI entry point for CodeCoach AI.

Usage:
    python main.py --file samples/bad_code.py
    python main.py --file samples/bad_code.py --agent review
    python main.py --file samples/bad_code.py --agents review,tests,explain
    python main.py --file samples/bad_code.py --save

See CLAUDE.md for full usage and conventions.
"""

import argparse
import sys

from agents.context import AgentContext
from agents.pipeline import SequentialPipeline
from agents.review_agent import ReviewAgent
from agents.test_gen_agent import TestGenAgent
from agents.explainer_agent import ExplainerAgent
from agents.tech_debt_agent import TechDebtAgent
from agents.pr_summary_agent import PRSummaryAgent
from hooks.pre_review import validate_inputs, check_api_key, check_prompts_exist
from hooks.post_review import save_outputs, log_summary
from skills.code_parser import detect_language, truncate_code
from skills.git_tools import read_file
from skills.formatter import format_full_report


AGENT_REGISTRY = {
    "review": ReviewAgent,
    "tests": TestGenAgent,
    "explain": ExplainerAgent,
    "debt": TechDebtAgent,
    "pr": PRSummaryAgent,
}

# Order matters — later agents use earlier agents' output
PIPELINE_ORDER = ["review", "tests", "explain", "debt", "pr"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="CodeCoach AI — multi-agent code review powered by Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --file samples/bad_code.py
  python main.py --file app.py --agent review
  python main.py --file app.py --agents review,tests
  python main.py --file app.py --save
        """
    )
    parser.add_argument("--file", required=True, help="Path to the source file to review")
    parser.add_argument(
        "--agent",
        help="Run a single agent (review|tests|explain|debt|pr)"
    )
    parser.add_argument(
        "--agents",
        help="Comma-separated list of agents to run (e.g. review,tests)"
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save outputs to the output/ directory"
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-6",
        help="Claude model to use (default: claude-sonnet-4-6)"
    )
    return parser.parse_args()


def resolve_agents(args) -> list[str]:
    """Determine which agents to run based on CLI args."""
    if args.agent:
        if args.agent not in AGENT_REGISTRY:
            print(f"Unknown agent: {args.agent}. Valid: {list(AGENT_REGISTRY)}")
            sys.exit(1)
        return [args.agent]
    if args.agents:
        requested = [a.strip() for a in args.agents.split(",")]
        invalid = [a for a in requested if a not in AGENT_REGISTRY]
        if invalid:
            print(f"Unknown agents: {invalid}. Valid: {list(AGENT_REGISTRY)}")
            sys.exit(1)
        return requested
    # Default: run all agents
    return list(PIPELINE_ORDER)


def main():
    args = parse_args()
    agent_names = resolve_agents(args)

    # --- Pre-flight checks ---
    try:
        check_api_key()
        check_prompts_exist(agent_names)
    except (EnvironmentError, FileNotFoundError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    # --- Load the file ---
    try:
        code = read_file(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    # --- Validate inputs ---
    try:
        validate_inputs(code, args.file)
    except ValueError as e:
        print(f"Validation error: {e}")
        sys.exit(1)

    # --- Detect language, truncate if needed ---
    language = detect_language(args.file)
    code = truncate_code(code, max_lines=500)

    print(f"\nCodeCoach AI")
    print(f"  File:     {args.file}")
    print(f"  Language: {language}")
    print(f"  Agents:   {', '.join(agent_names)}")
    print(f"  Model:    {args.model}")

    # --- Build pipeline ---
    ordered = [name for name in PIPELINE_ORDER if name in agent_names]
    agents = [AGENT_REGISTRY[name](model=args.model) for name in ordered]
    pipeline = SequentialPipeline(agents)

    # --- Create context ---
    context = AgentContext(
        code=code,
        filename=args.file,
        language=language,
        model=args.model,
    )

    # --- Run ---
    context = pipeline.run(context)

    # --- Output ---
    print("\n" + format_full_report(context))
    log_summary(context)

    if args.save:
        print("\nSaving outputs...")
        paths = save_outputs(context)
        print(f"  Saved {len(paths)} file(s) to output/")


if __name__ == "__main__":
    main()

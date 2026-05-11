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
from agents.langgraph_pipeline import LangGraphPipeline
from agents.review_agent import ReviewAgent
from agents.test_gen_agent import TestGenAgent
from agents.explainer_agent import ExplainerAgent
from agents.tech_debt_agent import TechDebtAgent
from agents.pr_summary_agent import PRSummaryAgent
from agents.alert_agent import AlertAgent
from hooks.pre_review import validate_inputs, check_ollama, check_prompts_exist
from hooks.post_review import save_outputs, log_summary
from memory.vector_store import VectorStore
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
        "--model", default="llama3.1:8b",
        help="Ollama model to use (default: llama3.1:8b)"
    )
    parser.add_argument(
        "--sequential", action="store_true",
        help="Use the old sequential pipeline instead of LangGraph"
    )
    parser.add_argument(
        "--no-rag", action="store_true",
        help="Disable RAG injection from past reviews"
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
        check_ollama(args.model)
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

    # --- Set up VectorStore for RAG (Phase 4) ---
    vector_store = None
    if not args.no_rag:
        try:
            vector_store = VectorStore()
        except Exception as e:
            print(f"  Warning: VectorStore unavailable ({e}). Running without RAG.")

    # --- Build pipeline ---
    if args.sequential or args.agent or args.agents:
        # Single-agent or subset runs use the sequential pipeline
        ordered = [name for name in PIPELINE_ORDER if name in agent_names]
        if "review" in ordered and vector_store:
            agents = [
                AGENT_REGISTRY[name](model=args.model, vector_store=vector_store)
                if name == "review"
                else AGENT_REGISTRY[name](model=args.model)
                for name in ordered
            ]
        else:
            agents = [AGENT_REGISTRY[name](model=args.model) for name in ordered]
        pipeline = SequentialPipeline(agents)
    else:
        # Full pipeline defaults to LangGraph (parallel + conditional routing)
        pipeline = LangGraphPipeline(model=args.model, vector_store=vector_store)

    # --- Create context ---
    context = AgentContext(
        code=code,
        filename=args.file,
        language=language,
        model=args.model,
    )

    # --- Run ---
    context = pipeline.run(context)

    # --- Store review in ChromaDB (Phase 4) ---
    if vector_store and context.review_summary:
        try:
            vector_store.store_review(context)
        except Exception as e:
            print(f"  Warning: could not store review: {e}")

    # --- Output ---
    print("\n" + format_full_report(context))
    log_summary(context)

    if args.save:
        print("\nSaving outputs...")
        paths = save_outputs(context)
        print(f"  Saved {len(paths)} file(s) to output/")


if __name__ == "__main__":
    main()

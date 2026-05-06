"""
SequentialPipeline — runs a list of agents one by one.

Each agent receives the context enriched by all previous agents.
Timing is tracked per agent. Errors are collected but don't stop the pipeline
(unless a critical error is raised inside an agent itself).

This is Phase 1 orchestration. In Phase 3, this is replaced by LangGraph.
See PHASES.md for the upgrade path.
"""

import time
from agents.base import BaseAgent
from agents.context import AgentContext


class SequentialPipeline:
    """
    Runs agents sequentially, passing the same AgentContext through each.

    The pipeline:
    1. Starts with an input context (code, filename, language)
    2. Passes it to Agent 1 → enriched context
    3. Passes enriched context to Agent 2 → further enriched
    4. ... and so on
    5. Returns the fully enriched context after the last agent

    Each agent's output is available to all subsequent agents via context.
    """

    def __init__(self, agents: list[BaseAgent]):
        if not agents:
            raise ValueError("Pipeline requires at least one agent.")
        self.agents = agents

    def run(self, context: AgentContext) -> AgentContext:
        """
        Execute all agents in order.

        Args:
            context: The initial pipeline state (code + filename + language).

        Returns:
            The fully enriched AgentContext after all agents have run.
        """
        agent_count = len(self.agents)
        print(f"\nStarting pipeline ({agent_count} agent{'s' if agent_count != 1 else ''})")
        print("-" * 50)

        for agent in self.agents:
            print(f"\n[{agent.name}]")
            start = time.time()

            try:
                context = agent.run(context)
            except Exception as e:
                # Critical error: log it and stop the pipeline
                print(f"  FATAL: {e}")
                context.errors.append(f"{agent.name}: FATAL: {e}")
                break

            elapsed = time.time() - start
            context.timings[agent.name] = round(elapsed, 2)
            print(f"  Done in {elapsed:.2f}s")

        print("\n" + "-" * 50)
        print("Pipeline complete.")

        if context.timings:
            timing_str = " → ".join(
                f"{name} ({t}s)" for name, t in context.timings.items()
            )
            print(f"  Timings: {timing_str}")

        if context.errors:
            print(f"\n  Errors ({len(context.errors)}):")
            for err in context.errors:
                print(f"    - {err}")

        return context

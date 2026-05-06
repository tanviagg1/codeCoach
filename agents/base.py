"""
BaseAgent — the abstract contract every agent must fulfill.

All agents inherit from this class and implement run().
This enforces a consistent interface across the pipeline.

See AGENTS_GUIDE.md for detailed guidance on writing agents.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from agents.context import AgentContext


class BaseAgent(ABC):
    """
    Abstract base class for all CodeCoach agents.

    Subclasses must implement run(context) -> context.

    The run() method:
    - Reads from context (never assume global state)
    - Validates prerequisites (raise ValueError if required fields are missing)
    - Calls Claude API
    - Writes results to context
    - Returns the enriched context
    """

    @abstractmethod
    def run(self, context: AgentContext) -> AgentContext:
        """
        Execute this agent's logic.

        Args:
            context: The shared pipeline state. Read inputs from here.

        Returns:
            The same context object, enriched with this agent's output.
        """
        pass

    @property
    def name(self) -> str:
        """The agent's class name — used in pipeline logging and timing."""
        return self.__class__.__name__

    def _load_prompt(self, prompt_filename: str) -> str:
        """
        Load a prompt template from the prompts/ directory.

        Prompts live in files so they can be versioned and edited
        independently of the Python code. See PROMPTS_GUIDE.md.

        Args:
            prompt_filename: Filename inside prompts/ (e.g., "review.md")

        Returns:
            The prompt template string with {{placeholder}} markers.
        """
        prompt_path = Path("prompts") / prompt_filename
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_path}. "
                f"See PROMPTS_GUIDE.md to create it."
            )
        return prompt_path.read_text()

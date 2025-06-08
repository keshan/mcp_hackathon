from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    """Abstract base class for all analysis agents."""

    def __init__(self, name: str, description: str):
        """
        Initializes the base agent.

        Args:
            name: The name of the agent.
            description: A brief description of what the agent does.
        """
        self._name = name
        self._description = description

    @property
    def name(self) -> str:
        """Returns the name of the agent."""
        return self._name

    @property
    def description(self) -> str:
        """Returns the description of the agent."""
        return self._description

    @abstractmethod
    def analyze(self, code_content: str, file_path: str, analysis_depth: str) -> Dict[str, Any]:
        """
        Performs analysis on the given code content.

        Args:
            code_content: The string content of the code to analyze.
            file_path: The path to the file being analyzed (for context).
            analysis_depth: The depth of analysis to perform (e.g., 'quick', 'standard', 'deep').

        Returns:
            A dictionary containing the analysis results.
            The structure of this dictionary will be specific to each agent
            but should be consistent for the orchestrator to aggregate.
            Example: {"issues": [], "recommendations": [], "metrics": {}}
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', description='{self.description}')"

    def parse_thinking_outputs(self, agent_response_str: str) -> Any:
        try:
            if "</think>" in agent_response_str:
                agent_response_str = agent_response_str.split("</think>")[-1].strip()
            return json.loads(agent_response_str)
        except json.JSONDecodeError as e:
            logger.error(f"{self.name}: Failed to parse final aggregation JSON: {e}. Raw response: {agent_response_str}")
            return None
        
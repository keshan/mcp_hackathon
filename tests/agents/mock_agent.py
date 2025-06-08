from typing import Dict, Any
from src.agents.base_agent import BaseAgent

class MockAgent(BaseAgent):
    """A simple mock agent for testing purposes."""

    def __init__(self, name: str = "MockAgent", description: str = "A mock agent."):
        super().__init__(name, description)
        self.analyze_called_with = None

    def analyze(self, code_content: str, file_path: str, analysis_depth: str) -> Dict[str, Any]:
        """Simulates analysis and records the input parameters."""
        self.analyze_called_with = {
            "code_content": code_content,
            "file_path": file_path,
            "analysis_depth": analysis_depth
        }
        return {
            "issues": [{"id": "mock_issue_001", "severity": "low", "description": "This is a mock issue."}],
            "recommendations": ["Consider using more mocks."],
            "metrics": {"mock_metric": 100}
        }

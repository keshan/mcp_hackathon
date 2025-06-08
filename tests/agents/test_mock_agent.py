import pytest
from .mock_agent import MockAgent # Adjusted import path

class TestMockAgent:
    def test_mock_agent_creation(self):
        """Test that the MockAgent can be instantiated."""
        agent = MockAgent()
        assert agent.name == "MockAgent"
        assert agent.description == "A mock agent."
        assert agent.analyze_called_with is None

    def test_mock_agent_analyze(self):
        """Test the analyze method of the MockAgent."""
        agent = MockAgent()
        code_input = "print('hello')"
        path_input = "/path/to/dummy.py"
        depth_input = "quick"

        results = agent.analyze(code_content=code_input, file_path=path_input, analysis_depth=depth_input)

        assert agent.analyze_called_with is not None
        assert agent.analyze_called_with["code_content"] == code_input
        assert agent.analyze_called_with["file_path"] == path_input
        assert agent.analyze_called_with["analysis_depth"] == depth_input

        assert "issues" in results
        assert len(results["issues"]) == 1
        assert results["issues"][0]["id"] == "mock_issue_001"

        assert "recommendations" in results
        assert results["recommendations"][0] == "Consider using more mocks."

        assert "metrics" in results
        assert results["metrics"]["mock_metric"] == 100

    def test_mock_agent_custom_name_description(self):
        """Test MockAgent with custom name and description."""
        custom_name = "CustomMock"
        custom_desc = "A custom mock agent."
        agent = MockAgent(name=custom_name, description=custom_desc)
        assert agent.name == custom_name
        assert agent.description == custom_desc

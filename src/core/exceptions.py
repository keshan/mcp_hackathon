class AppException(Exception):
    """Base class for custom application exceptions."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message

class AgentError(AppException):
    """Raised when an agent encounters an error during its operation."""
    pass

class OrchestratorError(AppException):
    """Raised when the orchestrator encounters an error."""
    pass

class ToolIntegrationError(AppException):
    """Raised when there's an issue with an external tool integration."""
    pass

# Example usage (can be removed or kept for testing):
if __name__ == "__main__":
    try:
        raise AgentError("Something went wrong in an agent.")
    except AppException as e:
        print(f"Caught an app exception: {e}")

    try:
        raise ToolIntegrationError("Failed to connect to Bandit CLI.")
    except AppException as e:
        print(f"Caught a tool integration exception: {e}")

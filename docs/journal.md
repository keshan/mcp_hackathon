# Development Journal

## Task 1: Initialize project structure with proper Python packaging

- Initialized Python project using `uv init`.
- Created `src` and `tests` directories.
- Created `README.md`.
- Created this `journal.md`.
- Verified `.gitignore` (was already present).

## Task 2: Set up development environment with Modal CLI and LlamaIndex. env file with Modal API key, Nebius API key

- Added `llama-index` to `pyproject.toml`.
- Created `.env.example` for API key placeholders.
- Confirmed `.env` is in `.gitignore`.

## Task 3: Create base agent interface and abstract classes

- Created `src/agents` directory.
- Created `src/agents/base_agent.py` with the `BaseAgent` abstract class.
  - Defined `__init__`, `name` property, `description` property, and an abstract `analyze` method.
- Created `src/agents/__init__.py` to export `BaseAgent`.

## Task 4: Implement basic logging and error handling framework

- Created `src/core` directory.
- Created `src/core/logging_config.py` with `get_logger` function and basic console logging setup.
- Created `src/core/exceptions.py` with `AppException` and specific exceptions like `AgentError`, `OrchestratorError`, `ToolIntegrationError`.
- Created `src/core/__init__.py` to export logger and exceptions.

## Task 5: Set up testing framework (pytest) with mock agent tests

- Added `pytest` and `pytest-mock` to `pyproject.toml` [project.optional-dependencies.dev].
- Configured basic pytest settings in `pyproject.toml` [tool.pytest.ini_options].
- Created `tests/agents` directory.
- Created `tests/agents/mock_agent.py` with a `MockAgent` inheriting from `BaseAgent`.
- Created `tests/agents/__init__.py`.
- Created `tests/agents/test_mock_agent.py` with initial test cases for `MockAgent`.

## Phase 1.2: Model Context Protocol (MCP) Setup

### Task 6: Design MCP server architecture for Modal deployment

- **Overview**: MCP server as a Modal application exposing HTTP endpoints for tool execution and context management.
- **Core Components**:
    - `modal.App`: Central container for the MCP server.
    - HTTP Endpoints (`@modal.web_endpoint`): Primarily `/execute_tool` (POST) for requesting tool runs.
        - Request: `{agent_id, session_id, tool_name, tool_params, context}`
        - Response: `{result, new_context, error}`
    - Tool Execution Wrappers (`@app.function`): Dedicated Modal functions for each analysis tool (e.g., `run_bandit_tool`).
        - Each wrapper handles tool execution, output parsing, and error handling.
        - Leverages `modal.Image` for isolated dependency management per tool/group of tools.
    - Context Management: Primarily stateless via request/response context fields. `modal.Dict` or `modal.Cls` for optional persistent session context if needed.
    - Security: `modal.Secret` for API keys/sensitive configs. Endpoint security via tokens/shared secrets. Careful tool input handling.
    - Configuration: A `TOOL_REGISTRY` mapping tool names to Modal functions.
- **Interaction Flow**: Orchestrator calls `/execute_tool` -> MCP endpoint dispatches to specific tool wrapper Modal function -> Tool wrapper executes tool and returns structured result -> MCP endpoint relays result to Orchestrator.
- **Advantages**: Scalability, isolated dependencies, simplified deployment via Modal.

### Task 7: Implement basic MCP server with health checks

- Added `modal` to `pyproject.toml` dependencies.
- Created `src/mcp_server` directory.
- Created `src/mcp_server/main.py`:
    - Defined a `modal.App` named `mcp-server-app`.
    - Defined a `modal.Image` (`mcp_image`) with Python 3.12 and `fastapi` (for potential future use).
    - Implemented a `/health` GET web endpoint using `@app.function(image=mcp_image)` and `@modal.web_endpoint`.
    - The health endpoint returns `{"status": "ok", "message": "MCP Server is healthy"}`.
- Created `src/mcp_server/__init__.py`.
- Added notes on how to run locally (`modal serve ...`) and deploy (`modal deploy ...`).

### Task 8: Create agent context isolation and management system

- Updated `src/mcp_server/main.py` to define the `/execute_tool` POST endpoint.
- Added Pydantic models (`ToolExecutionRequest`, `ToolExecutionResponse`) for request/response validation and structure.
    - `ToolExecutionRequest` includes `agent_id`, `session_id`, `tool_name`, `tool_params`, and `context: Optional[Dict]`.
    - `ToolExecutionResponse` includes `session_id`, `tool_name`, `result`, `new_context`, and `error`.
- The `/execute_tool` endpoint currently mocks tool execution but demonstrates the context pass-through:
    - It receives `session_id` and `context` from the request.
    - It includes `session_id` and `new_context` (echoing the received context for now) in the response.
- This establishes the pattern for stateless context handling. `session_id` is key for agents to manage their own context across calls.
- Fixed a lint error by removing a duplicate, empty `health` function definition.

### Task 9: Implement secure tool execution environment

- Manually updated [src/mcp_server/main.py](cci:7://file:///Users/keshan/Documents/mcp_hackathon/src/mcp_server/main.py:0:0-0:0) to correctly implement the [execute_tool](cci:1://file:///Users/keshan/Documents/mcp_hackathon/src/mcp_server/main.py:10:0-26:8) endpoint:
    - The [execute_tool](cci:1://file:///Users/keshan/Documents/mcp_hackathon/src/mcp_server/main.py:10:0-26:8) function now uses `base_tool_image`.
    - It dispatches calls to tool-specific Modal functions ([run_bandit_tool](cci:1://file:///Users/keshan/Documents/mcp_hackathon/src/mcp_server/main.py:97:0-115:57), [run_pydocstyle_tool](cci:1://file:///Users/keshan/Documents/mcp_hackathon/src/mcp_server/main.py:136:0-146:57)) via a `TOOL_REGISTRY`.
    - Placeholder logic within [execute_tool](cci:1://file:///Users/keshan/Documents/mcp_hackathon/src/mcp_server/main.py:10:0-26:8) was removed.
- Defined separate Modal images for tools (`bandit_image`, `pydocstyle_image`) to isolate dependencies. `base_tool_image` is used for general functions like [execute_tool](cci:1://file:///Users/keshan/Documents/mcp_hackathon/src/mcp_server/main.py:10:0-26:8) and [health](cci:1://file:///Users/keshan/Documents/mcp_hackathon/src/mcp_server/main.py:137:0-141:68).
- Created mock tool wrapper functions ([run_bandit_tool](cci:1://file:///Users/keshan/Documents/mcp_hackathon/src/mcp_server/main.py:97:0-115:57), [run_pydocstyle_tool](cci:1://file:///Users/keshan/Documents/mcp_hackathon/src/mcp_server/main.py:136:0-146:57)):
    - Each uses its specific image and placeholder `mcp_secrets`.
    - They simulate tool execution (e.g., Bandit finding a "TODO", Pydocstyle checking for a basic docstring) and return a mock result and the passed-through context.
- Implemented `TOOL_REGISTRY` mapping tool names to these Modal function handles.
- The `/execute_tool` endpoint now:
    - Looks up the tool in `TOOL_REGISTRY`.
    - Calls the tool's Modal function (`.remote()`) with `tool_params` and `context`.
    - Returns the tool's result and updated context, or an error if the tool is not found or an exception occurs during execution.
- This setup establishes a secure (via image isolation and potential secrets management) and extensible way to add and call analysis tools.

**Objective:** Begin Phase 2: Analyser Agent (Orchestrator) Implementation. Task 11: Implement LlamaIndex Multi-Agent Orchestrator integration.

**Key Activities & Changes:**

1.  **Created Orchestrator Module (`src/orchestrator`):**
    *   Added `src/orchestrator/__init__.py`.
    *   Created `src/orchestrator/main.py` with a basic `CodeAnalysisOrchestrator` class.
    *   Updated `pyproject.toml` to include `src/orchestrator` in packages for build.

2.  **Implemented LlamaIndex Tool Wrappers:**
    *   Defined LlamaIndex `FunctionTool` instances for `bandit_code_scan` and `pydocstyle_code_check` within `src/orchestrator/main.py`.
    *   These tools utilize an `mcp_tool_wrapper` function to delegate execution.

3.  **Implemented Live MCP Server Calling (`mcp_tool_wrapper`):**
    *   Added `httpx` as a project dependency to `pyproject.toml`.
    *   Modified `mcp_tool_wrapper` to make HTTP POST requests to the deployed Modal MCP server endpoint (`https://keshan--mcp-server-app-execute-tool.modal.run`).
    *   Ensured the payload sent to the MCP server includes the required `agent_id` field.
    *   Correctly handled the JSON response format from the MCP server (which returns a list: `[response_dict, status_code]`).
    *   Added basic error handling for HTTP requests and JSON parsing.

4.  **Tested Orchestrator to MCP Server Integration:**
    *   Successfully ran `src/orchestrator/main.py`.
    *   Verified that the orchestrator calls the live MCP server.
    *   Confirmed that the mock tool results (Bandit finding a TODO, Pydocstyle finding missing docstrings) are correctly retrieved and processed by the orchestrator.

**Issues Encountered & Resolutions:**

*   **Initial file creation failure:** `write_to_file` failed to create `src/orchestrator` directory implicitly. Resolved by using `mkdir -p` command first.
*   **HTTP 422 Error (Missing `agent_id`):** The MCP server required `agent_id` in the payload. Resolved by adding it to the `mcp_tool_wrapper`'s request payload.
*   **TypeError (`'list' object has no attribute 'get'`):** The MCP server returns `[response_dict, status_code]`. The orchestrator was trying to call `.get()` on the list. Resolved by accessing `response_payload[0]` to get the dictionary before processing.

**Next Steps:**

*   Proceed with LLM integration into the `CodeAnalysisOrchestrator` using LlamaIndex agent capabilities (e.g., `AgentRunner`).
*   Refine tool descriptions for better LLM understanding.
*   Make server URL and agent ID configurable.

## Session Ending 2025-06-08

**Objective**: Integrate OpenAILike LLM with Nebius API into the multi-agent orchestrator, ensure MCP tool invocation, and fix related import/runtime errors.

**Key Activities & Changes**:

1.  **LLM Integration**:
    *   Replaced `MockChatLLM` with `OpenAILike` from `llama_index.llms.openai_like` in `src/orchestrator/main.py`.
    *   Configured `OpenAILike` to use Nebius API endpoint (`NEBIUS_API_BASE`) and API key (`NEBIUS_API_KEY`) from environment variables.
    *   Set `is_chat_model=True` for `OpenAILike`.

2.  **Dependency Management & Imports**:
    *   Added `llama-index-llms-openai-like` package using `uv add`.
    *   Resolved multiple `ModuleNotFoundError` and `ImportError` issues by:
        *   Correcting the import path for `OpenAILike` to `llama_index.llms.openai_like`.
        *   Removing `ListToolRetriever` and passing tools directly to `ReActAgentWorker.from_tools()`.
        *   Ensuring `Dict`, `Optional` from `typing` were imported.
        *   Importing `BaseModel as PydanticBaseModel` from `llama_index.core.tools.types` and `Field as PydanticField` from `pydantic`.

3.  **Tool Invocation & Agent Setup**:
    *   Ensured `ReActAgentWorker` is initialized correctly with the `OpenAILike` LLM and the list of async tools.
    *   Verified that the `mcp_tool_wrapper` correctly calls the MCP server and processes responses.
    *   The agent successfully used `bandit_tool` and `pydocstyle_tool` via the MCP server.

4.  **Observability**:
    *   Confirmed Arize Phoenix launches correctly and is configured as the LlamaIndex global handler.
    *   The script output indicates successful LLM calls and tool interactions, which should be traceable in Phoenix.

5.  **Error Resolution**:
    *   Addressed `NameError` for `Dict`, `PydanticBaseModel`.
    *   The script now runs without Python errors, successfully performing code analysis using the LLM and tools.

6.  **Documentation**:
    *   Updated `docs/implementation.md` to reflect completed sub-tasks for Task 11.

**Outcome**: The orchestrator now successfully uses a real LLM (`OpenAILike` with Nebius) to dynamically invoke tools (Bandit, Pydocstyle) via the MCP server, with observability through Arize Phoenix. All critical import and runtime errors from the integration process have been resolved.


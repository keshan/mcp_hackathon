import modal
from typing import Dict, Any, Optional
from fastapi import Body # For more detailed request body specification if needed
from pydantic import BaseModel

# Pydantic models for request and response bodies
class ToolExecutionRequest(BaseModel):
    agent_id: str
    session_id: str
    tool_name: str
    tool_params: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None

class ToolExecutionResponse(BaseModel):
    session_id: str
    tool_name: str
    result: Optional[Dict[str, Any]] = None # Placeholder for actual tool result
    new_context: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# Define the Modal app
# Using auto_create=True for simpler local iteration if not running `modal deploy` first.
# For production, you'd typically deploy with a name.
app = modal.App(
    name="mcp-server-app"
)

# --- Images for Tools ---
# General image for tools that might use FastAPI or basic Python
base_tool_image = modal.Image.debian_slim(python_version="3.12").pip_install("fastapi>=0.100.0", "uvicorn", "pydantic>=2.0")

# Example: Image specific for Bandit (if it had unique system dependencies or pip packages)
bandit_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(["bandit"])
    # .apt_install(["some_system_dependency_for_bandit"]) # If needed
)

# Example: Image specific for Pydocstyle
pydocstyle_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(["pydocstyle"])
)

# Placeholder for shared secrets. Create this secret in Modal if you need to store actual values.
# e.g., modal secret create mcp-common-secrets NEBIUS_API_KEY=your_key_here
# mcp_secrets = [modal.Secret.from_name("mcp-common-secrets")] # Commented out for now


@app.function(image=base_tool_image, min_containers=1) # min_containers for faster responses
@modal.fastapi_endpoint(method="POST")
async def execute_tool(request: ToolExecutionRequest):
    """
    Endpoint to execute a specified tool with given parameters and context.
    """
    tool_function = TOOL_REGISTRY.get(request.tool_name)

    if not tool_function:
        error_response = ToolExecutionResponse(
            session_id=request.session_id,
            tool_name=request.tool_name,
            error=f"Tool '{request.tool_name}' not found in registry."
        )
        return error_response.model_dump(), 404

    try:
        # Call the Modal function for the specific tool.
        # .remote() is used for async invocation if the function is defined with async def
        # or if you want to run it truly in the background from another Modal function.
        # For a direct call from a web_endpoint that awaits, .call() or direct await can be used.
        # Let's assume tool wrappers might be async.
        tool_result_data, updated_context_data = tool_function.remote(
            request.tool_params, request.context
        )

        response_data = ToolExecutionResponse(
            session_id=request.session_id,
            tool_name=request.tool_name,
            result=tool_result_data,
            new_context=updated_context_data,
            error=None
        )
        return response_data.model_dump(), 200
    except Exception as e:
        # Log the exception properly in a real scenario
        print(f"Error executing tool {request.tool_name}: {e}") # Basic logging for now
        error_response = ToolExecutionResponse(
            session_id=request.session_id,
            tool_name=request.tool_name,
            error=f"Error executing tool '{request.tool_name}': {str(e)}"
        )
        return error_response.model_dump(), 500


# --- Tool Wrapper Functions ---
@app.function(image=bandit_image)
def run_bandit_tool(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Simulates running the Bandit security tool."""
    code_to_analyze = params.get("code", "")
    # In a real scenario: run bandit command, parse output
    # For now, mock output:
    mock_bandit_issues = []
    if "TODO" in code_to_analyze:
        mock_bandit_issues.append({
            "test_id": "B001", 
            "severity": "LOW", 
            "confidence": "HIGH",
            "message": "Code contains a TODO comment.",
            "line": code_to_analyze.find("TODO") + 1 # Example line number
        })
    
    result = {"tool": "bandit", "issues": mock_bandit_issues, "files_analyzed": 1}
    # Context can be updated if needed, e.g., context["bandit_last_run_summary"] = ...
    return result, context if context is not None else {}

@app.function(image=pydocstyle_image)
def run_pydocstyle_tool(params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Simulates running the Pydocstyle documentation tool."""
    code_to_analyze = params.get("code", "")
    # In a real scenario: run pydocstyle, parse output
    mock_pydocstyle_errors = []
    if not """""" in code_to_analyze and not "'''" in code_to_analyze: # Very naive check
        mock_pydocstyle_errors.append({"code": "D100", "message": "Missing docstring in public module"})

    result = {"tool": "pydocstyle", "errors": mock_pydocstyle_errors, "files_checked": 1}
    return result, context if context is not None else {}

# --- Tool Registry ---
TOOL_REGISTRY: Dict[str, modal.Function] = {
    "bandit": run_bandit_tool,
    "pydocstyle": run_pydocstyle_tool,
    # Add other tools here as they are implemented
}


@app.function(image=base_tool_image)
@modal.fastapi_endpoint(method="GET")
async def health():
    """Health check endpoint for the MCP server."""
    return {"status": "ok", "message": "MCP Server is healthy"}, 200

# To run this locally for testing the web endpoint (requires Modal CLI setup):
# modal serve src/mcp_server/main.py
#
# To deploy this to Modal Cloud:
# modal deploy src/mcp_server/main.py

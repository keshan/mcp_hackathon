import modal
import os
import sys
from loguru import logger
from typing import Dict, Any, Optional
from fastapi import Body # For more detailed request body specification if needed
from pydantic import BaseModel
import re

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
base_tool_image = modal.Image.debian_slim(python_version="3.12").pip_install("fastapi>=0.100.0", "uvicorn", "pydantic>=2.0", "loguru")

# Example: Image specific for Bandit (if it had unique system dependencies or pip packages)
bandit_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(["bandit", "loguru"])
    # .apt_install(["some_system_dependency_for_bandit"]) # If needed
)

# Example: Image specific for Pydocstyle
pydocstyle_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(["pydocstyle", "loguru"])
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
def run_bandit_tool(params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Runs the Bandit security tool on the provided Python code."""
    import subprocess
    import tempfile
    import json
    import os

    code_to_analyze = params.get("code", "")
    if not code_to_analyze:
        return {"tool": "bandit", "issues": [], "files_analyzed": 0, "error": "No code provided"}, context or {}

    issues = []
    files_analyzed_count = 0
    bandit_error_output = None

    try:
        # Create a temporary file to store the code
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False) as tmp_file:
            tmp_file_name = tmp_file.name
            tmp_file.write(code_to_analyze)
            tmp_file.flush() # Ensure all data is written
        
        # Construct the bandit command
        # -r: recursive (though for a single file, not strictly necessary but harmless)
        # -f json: output format
        # We target the specific temporary file
        cmd = ["bandit", "-r", tmp_file_name, "-f", "json"]
        
        # Execute Bandit
        # Bandit exits with 0 if no issues, 1 if issues found. We don't use check=True for this reason.
        completed_process = subprocess.run(cmd, capture_output=True, text=True)
        files_analyzed_count = 1 # We analyzed the one temp file

        if completed_process.stderr:
            # Bandit often prints non-fatal warnings or info to stderr, capture it for context
            bandit_error_output = completed_process.stderr
            logger.warning(f"Bandit stderr: {bandit_error_output}")

        if completed_process.stdout:
            try:
                bandit_output = json.loads(completed_process.stdout)
                # The 'results' key in Bandit's JSON output contains the list of issues.
                issues = bandit_output.get("results", []) 
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Bandit JSON output: {e}")
                logger.error(f"Bandit stdout was: {completed_process.stdout}")
                bandit_error_output = bandit_error_output or ""
                bandit_error_output += f"\nJSON parsing error: {e}\nStdout: {completed_process.stdout}"
        else:
            # This case might happen if bandit crashes before producing JSON
            logger.warning("Bandit produced no stdout. Check stderr.")
            if not bandit_error_output:
                 bandit_error_output = "Bandit produced no stdout and no stderr. Command may have failed silently or had no issues and no verbose output."

    except FileNotFoundError:
        # This happens if 'bandit' command is not found in PATH
        logger.error("Bandit command not found. Ensure it's installed in the Modal image and in PATH.")
        return {"tool": "bandit", "issues": [], "files_analyzed": 0, "error": "Bandit command not found on server."}, context or {}
    except Exception as e:
        logger.error(f"An unexpected error occurred while running Bandit: {e}")
        return {"tool": "bandit", "issues": [], "files_analyzed": 0, "error": f"Server-side error: {str(e)}"}, context or {}
    finally:
        # Clean up the temporary file
        if 'tmp_file_name' in locals() and os.path.exists(tmp_file_name):
            os.remove(tmp_file_name)

    result = {
        "tool": "bandit", 
        "issues": issues, 
        "files_analyzed": files_analyzed_count
    }
    if bandit_error_output:
        result["bandit_stderr"] = bandit_error_output # Optionally include stderr for debugging

    return result, context or {}

@app.function(image=pydocstyle_image)
def run_pydocstyle_tool(params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Runs the Pydocstyle documentation tool on the provided Python code."""
    import subprocess
    import tempfile
    import os
    import re
    # Logger should be available from the global import at the top of the file

    code_to_analyze = params.get("code", "")
    if not code_to_analyze:
        return {"tool": "pydocstyle", "errors": [], "files_checked": 0, "message": "No code provided"}, context or {}

    pydocstyle_errors = []
    files_checked_count = 0
    error_output_detail = None

    # Regex to parse pydocstyle's typical two-line output for each violation:
    # Line 1: <filename>:<line_number> <context description>
    # Line 2: (indented) <error_code>: <error_message>
    # Example:
    # /tmp/tmpxyz.py:1 at module level:
    #         D100: Missing docstring in public module
    # Group 1: Filename (e.g., /tmp/tmpxyz.py) - captured but not directly used in final error dict
    # Group 2: Line number (e.g., 1)
    # Group 3: Context on first line (e.g., " at module level:") - captured but not directly used
    # Group 4: Error code (e.g., D100)
    # Group 5: Message (e.g., "Missing docstring in public module")
    error_block_pattern = re.compile(
        r"^(.*?):(\d+)(.*?)\n\s+([A-Z]\d{3}):\s*(.*?)(?=\n\S|$)",
        re.MULTILINE
    )
    # The lookahead (?=\n\S|$) ensures the message (group 5) doesn't greedily consume subsequent error blocks.
    # It means "match until a newline followed by a non-whitespace char (likely start of next file path) or end of string".

    try:
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False) as tmp_file:
            tmp_file_name = tmp_file.name
            tmp_file.write(code_to_analyze)
            tmp_file.flush()

        cmd = ["pydocstyle", tmp_file_name]
        completed_process = subprocess.run(cmd, capture_output=True, text=True)
        files_checked_count = 1

        if completed_process.stdout:
            full_stdout = completed_process.stdout.strip()
            processed_text_indices = [False] * len(full_stdout)

            for match in error_block_pattern.finditer(full_stdout):
                _filename, line_num_str, _context, error_code, message = match.groups()
                error_entry = {
                    "code": error_code.strip(),
                    "message": message.strip()
                }
                if line_num_str: # Should always be present with this regex
                    error_entry["line"] = int(line_num_str)
                pydocstyle_errors.append(error_entry)
                
                # Mark the matched part as processed
                for i in range(match.start(), match.end()):
                    processed_text_indices[i] = True
            
            # Collect any text that wasn't part of a matched error block
            unparsed_segments = []
            current_segment_start = -1
            for i in range(len(full_stdout)):
                if not processed_text_indices[i] and full_stdout[i] not in ('\n', '\r'):
                    if current_segment_start == -1:
                        current_segment_start = i
                elif current_segment_start != -1:
                    unparsed_segments.append(full_stdout[current_segment_start:i])
                    current_segment_start = -1
            if current_segment_start != -1:
                unparsed_segments.append(full_stdout[current_segment_start:])
            
            remaining_unparsed = "\n".join(segment.strip() for segment in unparsed_segments if segment.strip()).strip()
            if remaining_unparsed:
                logger.warning(f"Unparsed segments from pydocstyle stdout: \n{remaining_unparsed}")
                if error_output_detail is None: error_output_detail = ""
                error_output_detail += remaining_unparsed + "\n"

        if completed_process.stderr:
            logger.warning(f"Pydocstyle stderr: {completed_process.stderr.strip()}")
            if error_output_detail is None: error_output_detail = ""
            error_output_detail += "Pydocstyle stderr: " + completed_process.stderr.strip() + "\n"

    except FileNotFoundError:
        logger.error("pydocstyle command not found. Ensure it's installed in the Modal image and in PATH.")
        return {"tool": "pydocstyle", "errors": [], "files_checked": 0, "message": "pydocstyle command not found on server."}, context or {}
    except Exception as e:
        logger.exception("An unexpected error occurred while running pydocstyle:")
        return {"tool": "pydocstyle", "errors": [], "files_checked": 0, "message": f"Server-side error: {str(e)}"}, context or {}
    finally:
        if 'tmp_file_name' in locals() and os.path.exists(tmp_file_name):
            os.remove(tmp_file_name)

    result = {
        "tool": "pydocstyle", 
        "errors": pydocstyle_errors, 
        "files_checked": files_checked_count
    }
    if error_output_detail:
        result["output_details"] = error_output_detail # For any unparsed or stderr messages

    return result, context or {}

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


@app.function(image=base_tool_image)
@modal.fastapi_endpoint(method="GET")
async def list_tools():
    """Returns a list of available tool names."""
    return {"tools": list(TOOL_REGISTRY.keys())}, 200

# To run this locally for testing the web endpoint (requires Modal CLI setup):
# modal serve src/mcp_server/main.py
#
# To deploy this to Modal Cloud:
# modal deploy src/mcp_server/main.py

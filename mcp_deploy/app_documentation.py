import gradio as gr
import httpx
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
MODAL_MCP_ENDPOINT = os.getenv("MODAL_MCP_ENDPOINT", "") # Should be like "https://username--mcp-server-app-execute-tool.modal.run"
TOOL_NAME = "pydocstyle"
AGENT_ID = "gradio-pydocstyle-ui"
SESSION_ID = "default_session"

# Example Python code with potential pydocstyle issues
EXAMPLE_CODE = """
# No module docstring here

def example_function_missing_docstring():
    pass

class ExampleClassMissingDocstring:
    def method_missing_docstring(self):
        pass

def well_documented_function():
    \"\"\"This function is well documented.\"\"\"
    return True
"""

async def call_mcp_tool(tool_params_json: str) -> str:
    """Calls the specified MCP tool on the Modal server with JSON parameters."""
    if not MODAL_MCP_ENDPOINT:
        return json.dumps({"error": "MODAL_MCP_ENDPOINT environment variable is not set. Please set it in your .env file."})
    
    print(f"Attempting to use Modal Endpoint for Pydocstyle: {MODAL_MCP_ENDPOINT}")

    try:
        tool_params = json.loads(tool_params_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON input for tool parameters: {str(e)}"})

    payload = {
        "tool_name": TOOL_NAME,
        "tool_params": tool_params, # Expects {'code': '...'}
        "agent_id": AGENT_ID,
        "session_id": SESSION_ID,
        "context": {}
    }

    print(f"Calling MCP tool: {TOOL_NAME} at {MODAL_MCP_ENDPOINT} with params: {tool_params}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(MODAL_MCP_ENDPOINT, json=payload)
        
        response.raise_for_status() # Will raise an exception for 4XX/5XX responses
        
        # The Modal endpoint returns a tuple: [response_dict, status_code]
        # We need to parse the response content if it's a string, or access the first element if it's already a list/tuple
        raw_response_data = response.json()
        print(raw_response_data) # For debugging the raw response from Modal

        if isinstance(raw_response_data, list) and len(raw_response_data) > 0:
            # Assuming the actual result is the first element of the list (the dict part of the tuple)
            mcp_result = raw_response_data[0]
        elif isinstance(raw_response_data, dict): # If it directly returns the dict (less likely based on current MCP server)
            mcp_result = raw_response_data
        else:
            return json.dumps({"error": "Unexpected response format from MCP server", "raw_response": str(raw_response_data)})

        return json.dumps(mcp_result, indent=2)
    
    except httpx.HTTPStatusError as e:
        error_message = f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
        print(error_message)
        try:
            # Attempt to parse error response from server if JSON
            error_details = e.response.json()
            return json.dumps({"error": "HTTP Error from MCP Server", "details": error_details, "status_code": e.response.status_code}, indent=2)
        except json.JSONDecodeError:
            return json.dumps({"error": error_message}, indent=2)
    except httpx.RequestError as e:
        error_message = f"Request error occurred: {str(e)}"
        print(error_message)
        return json.dumps({"error": error_message}, indent=2)
    except json.JSONDecodeError as e:
        # This might happen if the response from Modal isn't valid JSON, though raise_for_status should catch HTTP errors first.
        error_message = f"Failed to decode JSON response from MCP server: {str(e)}"
        print(error_message)
        return json.dumps({"error": error_message, "raw_response_text": response.text if 'response' in locals() else 'N/A'}, indent=2)
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(error_message)
        return json.dumps({"error": error_message}, indent=2)

# Gradio Interface
iface = gr.Interface(
    fn=call_mcp_tool,
    inputs=gr.Code(
        value=json.dumps({"code": EXAMPLE_CODE}, indent=2),
        language="json",
        label="Pydocstyle Tool Parameters (JSON - must include 'code' key)"
    ),
    outputs=gr.Code(language="json", label="Pydocstyle Analysis Output"),
    title="Pydocstyle Documentation Checker (via MCP on Modal)",
    description=(
        "Enter Python code as a JSON object under the 'code' key to check for documentation style issues using Pydocstyle. "
        "The application sends the code to a Pydocstyle tool running on a Modal Labs MCP server and displays the results."
        "Ensure your MODAL_MCP_ENDPOINT is set in a .env file (e.g., MODAL_MCP_ENDPOINT=https://your-modal-app-url/execute_tool)."
    ),
    allow_flagging="never"
)

if __name__ == "__main__":
    if not MODAL_MCP_ENDPOINT:
        print("ERROR: MODAL_MCP_ENDPOINT is not set. Please create a .env file in the mcp_deploy directory with this variable.")
        print("Example .env content: MODAL_MCP_ENDPOINT=https://your-username--mcp-server-app-execute-tool.modal.run")
    else:
        print(f"Using Modal MCP Endpoint: {MODAL_MCP_ENDPOINT}")
    iface.launch(server_name="0.0.0.0")

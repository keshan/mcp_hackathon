import gradio as gr
import httpx
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Placeholder for the Modal MCP endpoint
# The user will need to replace this with their actual Modal endpoint URL.
# It will try to get it from .env or environment variables first.
MODAL_MCP_ENDPOINT = os.getenv("MODAL_MCP_ENDPOINT", "YOUR_MODAL_MCP_ENDPOINT_HERE")

# --- Fetch available tools --- 
def get_mcp_server_base_url():
    if MODAL_MCP_ENDPOINT == "YOUR_MODAL_MCP_ENDPOINT_HERE" or not MODAL_MCP_ENDPOINT:
        return None
    # Assuming MODAL_MCP_ENDPOINT is like "https://<user>--mcp-server-app-execute-tool.modal.run"
    # We want "https://<user>--mcp-server-app-list-tools.modal.run" or similar base for /tools
    # A more robust way would be to have a separate env var for base URL or derive it carefully.
    # For now, let's assume the /execute_tool part is specific and we can construct /tools
    # This might need adjustment based on actual Modal URL structure for different functions in the same app.
    # A common pattern is that the function name is part of the URL.
    # If execute_tool is https://XYZ.modal.run, then list_tools might be https://XYZ.modal.run (if it's the root of another function)
    # or it might be part of the same app, e.g. https://<app_name>.modal.run/list_tools
    # Given the current Modal endpoint structure, we'll replace the function-specific part.
    if MODAL_MCP_ENDPOINT.endswith("/execute_tool"):
        base_url = MODAL_MCP_ENDPOINT[:-len("/execute_tool")]
    elif MODAL_MCP_ENDPOINT.endswith("execute_tool"):
         base_url = MODAL_MCP_ENDPOINT[:-len("execute_tool")] # if no trailing slash in env
    else: # Fallback, might not be correct
        base_url = MODAL_MCP_ENDPOINT
    return base_url

def fetch_available_tools():
    base_url = get_mcp_server_base_url()
    if not base_url:
        print("MODAL_MCP_ENDPOINT not set, cannot fetch tools.")
        return ["Error: MCP Endpoint not configured"]
    
    tools_url = f"{base_url}/tools" # Assuming /tools is relative to the app's base
    # If your Modal functions have distinct subdomains like <user>--<app>-<function>.modal.run
    # then tools_url would be constructed by replacing 'execute-tool' with 'list-tools' in MODAL_MCP_ENDPOINT
    # e.g., MODAL_MCP_ENDPOINT.replace("-execute-tool", "-list-tools")
    # For now, using a simpler relative path approach, adjust if needed.
    
    # Let's try replacing the function name in the URL if it's a common pattern
    # keshan--mcp-server-app-execute-tool.modal.run -> keshan--mcp-server-app-list-tools.modal.run
    if "--mcp-server-app-execute-tool" in MODAL_MCP_ENDPOINT:
        tools_url = MODAL_MCP_ENDPOINT.replace("--mcp-server-app-execute-tool", "--mcp-server-app-list-tools")
    else:
        print(f"Warning: Could not reliably determine /tools URL from {MODAL_MCP_ENDPOINT}. Using fallback {tools_url}")

    try:
        print(f"Fetching tools from: {tools_url}")
        with httpx.Client(timeout=10.0) as client:
            response = client.get(tools_url)
        response.raise_for_status()
        raw_data = response.json()
        
        # Check if data is a list [response_dict, status_code] as returned by Modal's FastAPI endpoint
        data_to_check = None
        if isinstance(raw_data, list) and len(raw_data) > 0 and isinstance(raw_data[0], dict):
            data_to_check = raw_data[0]
            print(f"Adjusted for Modal's list response format. Using: {data_to_check}")
        elif isinstance(raw_data, dict):
            data_to_check = raw_data # Standard dict response
        else:
            print(f"Unexpected raw data format: {raw_data}")
            return [f"Error: Unexpected raw data format ({str(raw_data)[:100]}...)"]

        if data_to_check and "tools" in data_to_check and isinstance(data_to_check["tools"], list):
            print(f"Successfully fetched tools: {data_to_check['tools']}")
            return data_to_check["tools"] if data_to_check["tools"] else ["No tools found"]
        else:
            print(f"Unexpected format for tools list (after potential adjustment): {data_to_check}")
            return [f"Error: Unexpected tools format ({str(data_to_check)[:100]}...)"]
    except httpx.HTTPStatusError as e:
        print(f"HTTP error fetching tools: {e.response.status_code} - {e.response.text}")
        return [f"Error fetching tools (HTTP {e.response.status_code})"]
    except Exception as e:
        print(f"Error fetching tools: {str(e)}")
        return [f"Error fetching tools: {str(e)[:100]}..."]

available_tools = fetch_available_tools()
# ---

async def call_mcp_tool_on_modal(tool_name: str, tool_parameters_json: str):
    if MODAL_MCP_ENDPOINT == "YOUR_MODAL_MCP_ENDPOINT_HERE" or not MODAL_MCP_ENDPOINT:
        return {"error": "MODAL_MCP_ENDPOINT is not set. Please create a .env file in the 'mcp_deploy' directory with MODAL_MCP_ENDPOINT='your_url' or set it as an environment variable."}

    try:
        tool_parameters = json.loads(tool_parameters_json)
    except json.JSONDecodeError as e:
        return {"error": "Invalid JSON format for tool parameters.", "details": str(e)}

    payload = {
        "tool_name": tool_name,
        "parameters": tool_parameters
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            print(f"Calling MCP tool: {tool_name} at {MODAL_MCP_ENDPOINT} with params: {tool_parameters}")
            response = await client.post(MODAL_MCP_ENDPOINT, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_message = f"HTTP error: {e.response.status_code}"
            try:
                error_details = e.response.json()
                error_message += f" - {json.dumps(error_details)}"
            except json.JSONDecodeError:
                error_message += f" - {e.response.text}"
            return {"error": error_message}
        except httpx.RequestError as e:
            return {"error": f"Request error for {e.request.url!r}: {str(e)}"}
        except Exception as e:
            return {"error": f"An unexpected error occurred: {str(e)}"}


# Define Gradio inputs and outputs
if available_tools and not available_tools[0].startswith("Error"):
    tool_name_input = gr.Dropdown(
        label="Select MCP Tool",
        choices=available_tools,
        value=available_tools[0] if available_tools else None,
        info="Select a tool from the list fetched from the server."
    )
    default_examples = [
        [available_tools[0], '{"query": "example query"}'] if available_tools else ["your_tool_name", "{}"],
        [available_tools[1], '{"url": "https://example.com"}'] if len(available_tools) > 1 else ["your_tool_name", "{}"]
    ]
else:
    tool_name_input = gr.Textbox(
        label="MCP Tool Name (Error fetching list - Enter Manually)",
        placeholder="e.g., bandit (use the exact name from your Modal deployment)",
        info=f"Could not fetch tool list: {available_tools[0] if available_tools else 'Unknown error'}. Please enter tool name manually."
    )
    default_examples = [
        ["bandit", '{"code": "import os\nos.system(\"echo hello\")"}'],
        ["pydocstyle", '{"code": "def my_func():\n  pass"}']
    ]

tool_params_input = gr.Textbox(
    label="Tool Parameters (JSON string)",
    placeholder='e.g., {"query": "latest AI news"}',
    lines=5,
    info="Enter parameters as a valid JSON string. For example, if a tool takes 'query' and 'limit', use: {\"query\": \"example\", \"limit\": 10}"
)
output_display = gr.JSON(label="MCP Tool Output")

# Create the Gradio interface
iface = gr.Interface(
    fn=call_mcp_tool_on_modal,
    inputs=[tool_name_input, tool_params_input],
    outputs=output_display,
    title="MCP Tool Interface (via Modal)",
    description=(
        "Interface with MCP tools hosted on Modal. "
        "Enter the tool name and its parameters in JSON format. "
        "Ensure `MODAL_MCP_ENDPOINT` is correctly set in a `.env` file in the `mcp_deploy` directory or as an environment variable. "
        "The endpoint should point to your Modal function that handles MCP tool execution."
    ),
    examples=default_examples,
    allow_flagging="never"
)

if __name__ == "__main__":
    print(f"Attempting to use Modal Endpoint: {MODAL_MCP_ENDPOINT}")
    if MODAL_MCP_ENDPOINT == "YOUR_MODAL_MCP_ENDPOINT_HERE" or not MODAL_MCP_ENDPOINT:
        print("\nWARNING: MODAL_MCP_ENDPOINT is not configured. The app will show an error on submit.")
        print("Please create a .env file in the 'mcp_deploy' directory with:")
        print("MODAL_MCP_ENDPOINT=\"your_actual_modal_mcp_endpoint_url\"\n")
    iface.launch(mcp_server=True)

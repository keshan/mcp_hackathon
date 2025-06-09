import gradio as gr
import httpx
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MODAL_MCP_ENDPOINT = os.getenv("MODAL_MCP_ENDPOINT", "YOUR_MODAL_MCP_ENDPOINT_HERE")
BANDIT_TOOL_NAME = "bandit"

async def call_bandit_tool_on_modal(tool_parameters_json: str):
    if MODAL_MCP_ENDPOINT == "YOUR_MODAL_MCP_ENDPOINT_HERE" or not MODAL_MCP_ENDPOINT:
        return {"error": "MODAL_MCP_ENDPOINT is not set. Please create a .env file in the 'mcp_deploy' directory with MODAL_MCP_ENDPOINT='your_url' or set it as an environment variable."}

    try:
        tool_parameters = json.loads(tool_parameters_json)
    except json.JSONDecodeError as e:
        return {"error": "Invalid JSON format for tool parameters.", "details": str(e)}

    # Ensure 'code' parameter is present, as Bandit expects it.
    if "code" not in tool_parameters:
        return {"error": "Missing 'code' parameter in JSON. Bandit requires a 'code' field with the Python code string to analyze."}

    payload = {
        "tool_name": BANDIT_TOOL_NAME,
        "tool_params": tool_parameters,
        "agent_id": "gradio-bandit-ui",
        "session_id": "default_session"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            print(f"Calling MCP tool: {BANDIT_TOOL_NAME} at {MODAL_MCP_ENDPOINT} with params: {tool_parameters}")
            response = await client.post(MODAL_MCP_ENDPOINT, json=payload)
            response.raise_for_status()
            print(response.json())
            
            # Handle Modal's [response_dict, status_code] tuple format
            raw_response_data = response.json()
            if isinstance(raw_response_data, list) and len(raw_response_data) > 0 and isinstance(raw_response_data[0], dict):
                actual_response = raw_response_data[0]
            elif isinstance(raw_response_data, dict):
                actual_response = raw_response_data
            else:
                return {"error": "Unexpected response format from MCP server", "details": raw_response_data}
            return actual_response
            
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
tool_params_input = gr.Textbox(
    label="Bandit Parameters (JSON string with 'code' field)",
    placeholder='e.g., {\"code\": \"import os\nprint(os.listdir(\".\"))\"}',
    lines=10,
    info="Enter parameters as a valid JSON string. Must include a 'code' field containing the Python code to analyze."
)
output_display = gr.JSON(label="Bandit Analysis Output")

# Example for Bandit tool
bandit_example_code = """import subprocess\n\n# Example of a potential security risk with subprocess\nsubprocess.call("ls -l", shell=True)"""
bandit_example_params = json.dumps({"code": bandit_example_code}, indent=2)

# Create the Gradio interface
iface = gr.Interface(
    fn=call_bandit_tool_on_modal,
    inputs=[tool_params_input],
    outputs=output_display,
    title="Bandit Security Scanner Interface (via Modal MCP)",
    description="""Interface with the Bandit security scanner tool hosted on Modal via the MCP server.
Provide Python code within a JSON structure under the 'code' key.
Ensure `MODAL_MCP_ENDPOINT` is correctly set in a .env file in the `mcp_deploy` directory or as an environment variable.
The endpoint should point to your Modal function that handles MCP tool execution (e.g., /execute_tool).""",
    examples=[
        [bandit_example_params]
    ],
    allow_flagging="never"
)

if __name__ == "__main__":
    print(f"Attempting to use Modal Endpoint for Bandit: {MODAL_MCP_ENDPOINT}")
    if MODAL_MCP_ENDPOINT == "YOUR_MODAL_MCP_ENDPOINT_HERE" or not MODAL_MCP_ENDPOINT:
        print("\nWARNING: MODAL_MCP_ENDPOINT is not configured. The app will show an error on submit.")
        print("Please create a .env file in the 'mcp_deploy' directory with:")
        print("MODAL_MCP_ENDPOINT=\"your_actual_modal_mcp_endpoint_url\"\n")
    iface.launch(server_name="0.0.0.0") # mcp_server=True removed as it's not needed for this direct app

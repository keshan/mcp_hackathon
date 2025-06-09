# src/core/mcp_tools.py
# MCP tool wrappers and utility functions
import warnings

# Display deprecation warning
warnings.warn(
    "The functions in this module are deprecated and will be removed in a future version. "
    "Please use the direct Modal MCP server integration instead.",
    DeprecationWarning,
    stacklevel=2
)


import os
import httpx
import uuid
from typing import Dict, Any, List # Added List
from llama_index.core.tools import FunctionTool, adapt_to_async_tool
from loguru import logger

try:
    from .schemas import ToolCodeInputSchema
except ImportError:
    logger.warning("Could not import ToolCodeInputSchema from .schemas, trying src.core.schemas")
    from src.core.schemas import ToolCodeInputSchema

MCP_AGENT_ID = str(uuid.uuid4())
logger.info(f"MCP Tool Agent ID: {MCP_AGENT_ID}")

global_tool_outputs: List[Dict[str, Any]] = [] # Type hint for clarity

def mcp_tool_wrapper(tool_name: str, agent_id_param: str, **kwargs) -> Dict[str, Any]:
    payload = {
        "agent_id": agent_id_param,
        "session_id": "session_001", 
        "tool_name": tool_name,
        "tool_params": kwargs,
        "context": {}
    }
    logger.info(f"MCP Tool Wrapper: Calling tool '{tool_name}' for agent '{agent_id_param}' with params: {kwargs}")
    mcp_server_url = os.getenv("MCP_SERVER_URL")
    if not mcp_server_url:
        logger.error("MCP_SERVER_URL environment variable not set. Cannot call MCP tools.")
        return {"error": "MCP_SERVER_URL not configured."}
        
    try:
        with httpx.Client() as client:
            response = client.post(mcp_server_url, json=payload, timeout=60.0)
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"MCP Tool Wrapper: Response status: {response.status_code}")
        logger.debug(f"MCP Tool Wrapper: Response content: {response_data}")

        if isinstance(response_data, list) and len(response_data) > 0:
            actual_response_dict = response_data[0]
            if not isinstance(actual_response_dict, dict):
                logger.error(f"MCP Tool Wrapper: Expected dict, got {type(actual_response_dict)}")
                return {"error": "Unexpected response format from MCP server", "details": response_data}
        else:
            logger.error(f"MCP Tool Wrapper: Unexpected response format (expected list): {response_data}")
            return {"error": "Unexpected response format from MCP server", "details": response_data}
        
        logger.info(f"MCP Tool Wrapper: Parsed tool response dict: {actual_response_dict}")

        if actual_response_dict.get("error"):
            logger.error(f"MCP Tool Wrapper: Error from tool '{tool_name}': {actual_response_dict['error']}")
            return {"error": actual_response_dict['error'], "details": actual_response_dict}
        
        tool_result_to_return = actual_response_dict.get("result", {"error": "No result found", "details": actual_response_dict})
        
        global_tool_outputs.append({
            "tool_name": tool_name,
            "output": tool_result_to_return,
            "raw_input": kwargs
        })
        return tool_result_to_return

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if e.response else "No response body"
        logger.error(f"MCP HTTP error: {e.response.status_code} - {error_detail}")
        return {"error": f"HTTP error: {e.response.status_code}", "details": error_detail}
    except httpx.RequestError as e:
        logger.error(f"MCP Request error: {e}")
        return {"error": f"Request error: {str(e)}"}
    except Exception as e:
        logger.exception(f"MCP Unexpected error calling tool '{tool_name}'")
        return {"error": f"Unexpected error: {str(e)}"}

pydocstyle_mcp_tool = FunctionTool.from_defaults(
    fn=lambda code: mcp_tool_wrapper("pydocstyle", agent_id_param=MCP_AGENT_ID, code=code),
    name="pydocstyle_mcp_tool",
    description="Runs Pydocstyle to check Python code for adherence to docstring conventions. Input is the code string.",
    fn_schema=ToolCodeInputSchema
)
adapted_pydocstyle_mcp_tool = adapt_to_async_tool(pydocstyle_mcp_tool)

def get_all_tool_outputs() -> List[Dict[str, Any]]:
    return list(global_tool_outputs)

def clear_tool_outputs():
    global_tool_outputs.clear()

logger.info("MCP Tools module initialized.")

# src/orchestrator/main.py

from llama_index.core.agent import AgentRunner, ReActAgentWorker # Added ReActAgentWorker
from llama_index.core.tools import FunctionTool, adapt_to_async_tool
from llama_index.core.tools.types import BaseModel as PydanticBaseModel  # For schema definition
from pydantic import Field as PydanticField  # For schema definition

from llama_index.llms.openai_like import OpenAILike # Corrected import for Nebius LLM
import os # For API Key
from typing import Any, Dict, Optional # Added Dict and Optional
import llama_index.core
import json # For MCP tool communication & final results printing
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from phoenix.otel import register
from loguru import logger
from dotenv import load_dotenv
import uuid

load_dotenv()

AGENT_ID = str(uuid.uuid4())
logger.info(f"Orchestrator Agent ID: {AGENT_ID}")

# Setup Arize Phoenix for logging/observability using OpenInference
os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = "http://localhost:6006" # Ensure Phoenix is running and accessible here
logger.info("Attempting to initialize Arize Phoenix with OpenInference...")
try:
    tracer_provider = register()
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)
    logger.info("Arize Phoenix instrumentor initialized with LlamaIndex.")
    logger.info("Ensure Phoenix is running at http://localhost:6006 to view traces.")
except Exception as e:
    logger.error(f"Failed to initialize Arize Phoenix instrumentor: {e}")
    logger.info("Proceeding without Phoenix observability.")

import httpx
import uuid # For generating session_id

MCP_SERVER_URL = "https://keshan--mcp-server-app-execute-tool.modal.run"

# Global list to store tool outputs directly from the wrapper
global_tool_outputs = []

# Wrapper to call MCP server tools
def mcp_tool_wrapper(tool_name: str, agent_id_param: str, **kwargs) -> Dict[str, Any]:
    payload = {
        "agent_id": agent_id_param,
        "session_id": "session_001", 
        "tool_name": tool_name,
        "tool_params": kwargs,
        "context": {}
    }
    logger.info(f"MCP Tool Wrapper: Calling tool '{tool_name}' with params: {kwargs}")
    try:
        with httpx.Client() as client: 
            response = client.post(MCP_SERVER_URL, json=payload, timeout=60.0)
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"MCP Tool Wrapper: Response status: {response.status_code}")
        logger.debug(f"MCP Tool Wrapper: Response content: {response_data}")
        logger.debug(f"MCP Tool Wrapper: Request payload: {payload}")
        logger.info(f"MCP Tool Wrapper: Raw response data: {response_data}")

        # The MCP server returns a list: [response_dict, status_code]
        if isinstance(response_data, list) and len(response_data) > 0:
            actual_response_dict = response_data[0]
            if not isinstance(actual_response_dict, dict):
                logger.error(f"MCP Tool Wrapper: Expected dict as first element of response list, got {type(actual_response_dict)}")
                return {"error": "Unexpected response format from MCP server", "details": response_data}
        else:
            logger.error(f"MCP Tool Wrapper: Unexpected response format from MCP server (expected list): {response_data}")
            return {"error": "Unexpected response format from MCP server", "details": response_data}
        
        logger.info(f"MCP Tool Wrapper: Parsed tool response dict: {actual_response_dict}")

        if actual_response_dict.get("error"):
            logger.error(f"MCP Tool Wrapper: Error from tool '{tool_name}': {actual_response_dict['error']}")
            return {"error": actual_response_dict['error'], "details": actual_response_dict}
        
        tool_result_to_return = actual_response_dict.get("result", {"error": "No result found in MCP response", "details": actual_response_dict})
        # Append the full processed response dict to our global list
        global_tool_outputs.append({
            "tool_name": tool_name, # Add tool_name for clarity
            "output": tool_result_to_return,
            "raw_input": kwargs # Capture the input params to the tool
        })
        return tool_result_to_return

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if e.response else "No response body"
        logger.error(f"MCP Tool Wrapper: HTTP error calling tool '{tool_name}': {e.response.status_code} - {error_detail}")
        return {"error": f"HTTP error: {e.response.status_code}", "details": error_detail}
    except httpx.RequestError as e:
        logger.error(f"MCP Tool Wrapper: Request error calling MCP tool '{tool_name}': {e}")
        return {"error": f"Request error: {str(e)}"}
    except Exception as e:
        logger.error(f"MCP Tool Wrapper: Unexpected error calling tool '{tool_name}': {e}")
        return {"error": f"Unexpected error: {str(e)}"}

# Define Pydantic model for tool input schema
class CodeInputSchema(PydanticBaseModel):
    code: str = PydanticField(..., description="The Python code snippet to analyze.")

# Create LlamaIndex tools from the mcp_tool_wrapper
bandit_tool = FunctionTool.from_defaults(
    fn=lambda code: mcp_tool_wrapper("bandit", agent_id_param=AGENT_ID, code=code),
    name="bandit_tool",
    description="Runs Bandit security linter on Python code to find common security issues. Input is the code string.",
    fn_schema=CodeInputSchema
)

pydocstyle_tool = FunctionTool.from_defaults(
    fn=lambda code: mcp_tool_wrapper("pydocstyle", agent_id_param=AGENT_ID, code=code),
    name="pydocstyle_tool",
    description="Runs Pydocstyle to check Python code for adherence to docstring conventions. Input is the code string.",
    fn_schema=CodeInputSchema
)

class CodeAnalysisOrchestrator:
    def __init__(self):
        self.llm = OpenAILike(
            model=os.environ.get("NEBIUS_LLM", "Qwen/Qwen3-30B-A3B"), 
            api_base=os.environ.get("NEBIUS_API_BASE", "https://api.studio.nebius.com/v1/"),
            api_key=os.environ.get("NEBIUS_API_KEY"),
            is_chat_model=True
        )
        if not self.llm.api_key:
            logger.warning("NEBIUS_API_KEY environment variable not set. LLM calls will likely fail.")
        
        adapted_bandit_tool = adapt_to_async_tool(bandit_tool)
        adapted_pydocstyle_tool = adapt_to_async_tool(pydocstyle_tool)
        self.tools = [adapted_bandit_tool, adapted_pydocstyle_tool]

        self.agent_worker = ReActAgentWorker.from_tools(
            tools=self.tools, # Pass tools directly
            llm=self.llm,
            verbose=True
        )
        self.agent = AgentRunner(self.agent_worker, llm=self.llm, verbose=True)
        logger.info(f"Orchestrator initialized with LLM: {type(self.llm).__name__} and Agent: {type(self.agent).__name__}")

    def analyze_code(self, query: str):
        global global_tool_outputs # Ensure we're referencing the global list
        global_tool_outputs.clear() # Clear for current analysis run
        logger.info(f"Orchestrator: Starting analysis with query:\n{query}")
        try:
            agent_response = self.agent.query(query)
            logger.info(f"Orchestrator: Agent textual response: {agent_response.response}")
            logger.debug(f"Orchestrator: agent_response type: {type(agent_response)}")
            logger.debug(f"Orchestrator: agent_response attributes: {dir(agent_response)}")
            # This log is now more specific and covers the case where source_nodes might exist but be empty.
            # The old 'sources' attribute check is removed as it's confirmed to be 'source_nodes'.
            if not (hasattr(agent_response, 'source_nodes') and agent_response.source_nodes):
                 actual_source_nodes_val = getattr(agent_response, 'source_nodes', 'Attribute not found or None')
                 logger.debug(f"Orchestrator: agent_response.source_nodes is missing, None, or empty. Value: {actual_source_nodes_val}")
                 logger.debug(f"Orchestrator: agent_response.metadata: {agent_response.metadata}")
            results = {
                "llm_response": agent_response.response,
                "tool_outputs": []
            }
            # Process outputs from the global list instead of agent_response.source_nodes
            if global_tool_outputs:
                logger.info(f"Orchestrator: Found {len(global_tool_outputs)} tool outputs in global list. Processing them.")
                for i, tool_data in enumerate(global_tool_outputs):
                    logger.debug(f"Orchestrator: --- Processing captured tool_data {i} ---")
                    logger.debug(f"Orchestrator: captured tool_data {i}: {tool_data}")
                    results["tool_outputs"].append(tool_data) # Append the already structured data
                    logger.debug(f"Orchestrator: --- Finished processing captured tool_data {i} ---")
            else:
                logger.info("Orchestrator: global_tool_outputs list is empty. No tool outputs captured directly.")
        except Exception as e:
            logger.exception("Orchestrator: Error during agent execution:") 
            results = {"error": str(e)}
        
        logger.info("Orchestrator: Analysis complete.")
        return results

if __name__ == "__main__":
    sample_code_to_analyze = (
        "import os\n\n"
        "def my_function_without_docstring():\n"
        "    # TODO: Add proper error handling\n"
        "    print(\"Hello, world!\")\n"
        "    return os.getenv(\"DANGEROUS_VAR\")\n"
    )

    orchestrator = CodeAnalysisOrchestrator()

    analysis_query = f"""Analyze the following Python code:

```python
{sample_code_to_analyze}
```

First, run a security scan using bandit_tool to find common vulnerabilities. Then, check the code for adherence to docstring conventions using pydocstyle_tool."""

    logger.info("\n--- Running Code Analysis ---")
    final_results = orchestrator.analyze_code(analysis_query)

    logger.info("\n--- Final Aggregated Results ---")
    logger.info(f"Final Aggregated Results:\n{json.dumps(final_results, indent=2)}")

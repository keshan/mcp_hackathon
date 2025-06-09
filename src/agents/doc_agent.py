# src/agents/doc_agent.py
from loguru import logger
from llama_index.core.agent import AgentRunner, ReActAgentWorker
from llama_index.core.tools import FunctionTool
import json
from gradio_client import Client

from src.core.llm import get_llm
from src.core.schemas import OutputSchema
from src.core.utils import parse_thinking_outputs

# Gradio client function for Pydocstyle
def run_gradio_documentation_check(code_snippet: str) -> dict:
    """
    Analyzes a Python code snippet for documentation style using a Gradio-based Pydocstyle MCP tool.

    Args:
        code_snippet: The Python code string to analyze.

    Returns:
        A dictionary containing the Pydocstyle analysis results.
    """
    logger.info(f"Running Gradio documentation check for code (first 200 chars): {code_snippet[:200]}...")
    try:
        # client = Client(src="Agents-MCP-Hackathon/documentation_mcp_tool", hf_token=os.getenv("HUGGING_FACE_TOKEN")) # If private
        client = Client(src="Agents-MCP-Hackathon/documentation_mcp_tool")

        parameters = {"code": code_snippet}
        tool_parameters_json = json.dumps(parameters)

        # The Gradio client's predict method returns a string which is the JSON output from the Gradio app's output component.
        raw_json_string_output = client.predict(
            tool_params_json=tool_parameters_json,
            api_name="/predict"
        )
        logger.info(f"Gradio documentation check raw string output: {raw_json_string_output}")

        if not raw_json_string_output:
            logger.error("Gradio documentation tool returned an empty response.")
            return {"error": "Empty response from documentation tool", "raw_output": raw_json_string_output}

        # Parse the JSON string output from Gradio
        # This string is expected to be a JSON representation of a list containing a dictionary (the MCP server response)
        # e.g., "[{'session_id': ..., 'result': ..., 'error': ...}, 200]"
        # However, the useful part is often the 'result' field within the first element's dictionary.
        parsed_outer_list = json.loads(raw_json_string_output)
        
        if isinstance(parsed_outer_list, list) and len(parsed_outer_list) > 0 and isinstance(parsed_outer_list[0], dict):
            mcp_response_dict = parsed_outer_list[0]
            # We are interested in the 'result' field from the MCP tool's actual response
            if mcp_response_dict.get("error"):
                 logger.error(f"Documentation tool reported an error: {mcp_response_dict.get('error')}")
                 return {"error": f"Error from documentation tool: {mcp_response_dict.get('error')}", "details": mcp_response_dict}
            
            actual_tool_result = mcp_response_dict.get("result")
            if actual_tool_result:
                logger.info(f"Extracted Pydocstyle result: {actual_tool_result}")
                return actual_tool_result # This should be like {'tool': 'pydocstyle', 'errors': [...], ...}
            else:
                logger.error("Gradio documentation tool response did not contain a 'result' field in the expected place.")
                return {"error": "Malformed result from documentation tool", "raw_mcp_response": mcp_response_dict}
        else:
            logger.error(f"Unexpected structure after parsing Gradio documentation tool string: {parsed_outer_list}")
            return {"error": "Unexpected result structure from documentation tool", "raw_parsed_output": parsed_outer_list}

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gradio documentation tool string to JSON: {raw_json_string_output}. Error: {e}")
        return {"error": "Failed to parse result from documentation tool", "raw_output": raw_json_string_output if 'raw_json_string_output' in locals() else 'N/A'}
    except Exception as e:
        logger.exception("Error calling Gradio documentation tool:")
        return {"error": f"Exception during Gradio documentation tool call: {str(e)}"}

# Create LlamaIndex FunctionTool
gradio_pydocstyle_tool = FunctionTool.from_defaults(
    fn=run_gradio_documentation_check,
    name="gradio_documentation_scanner",
    description="Runs a documentation style check (Pydocstyle) on the provided Python code using an external Gradio-based tool. Input is the code string. Returns JSON analysis results which include a list of 'errors' with details like 'code', 'message', and 'line'."
)

class DocAgent:
    def __init__(self):
        self.llm = get_llm()
        self.tools = [gradio_pydocstyle_tool]

        self.agent_worker = ReActAgentWorker.from_tools(
            tools=self.tools,
            llm=self.llm,
            verbose=True
        )
        self.agent = AgentRunner(self.agent_worker, llm=self.llm, verbose=True)
        logger.info(f"DocAgent initialized with LLM: {self.llm.model if hasattr(self.llm, 'model') else type(self.llm).__name__} and Agent: {type(self.agent).__name__}")
        logger.info(f"DocAgent tools: {[tool.metadata.name for tool in self.tools]}")

    def analyze_documentation(self, query: str) -> OutputSchema:
        prompt = f"""
        Analyzes the documentation of the provided Python code snippet using its LLM agent and available tools.
        Focus on PEP 257 compliance and general docstring quality. 
        Use the 'gradio_documentation_scanner' tool to get Pydocstyle results and incorporate these findings into your analysis.
        Provide a summary of findings and detailed issues if any. If the tool finds issues, prioritize them in your response.
        The output must only be in the following JSON format. Do not output anything other than this JSON object:
        {{
            "issue": "Issues found in the code (summarize tool findings if any, otherwise LLM assessment)",
            "reason": "Reason for the issue (explain tool findings if any, otherwise LLM reasoning)",
            "fixed_code": "Fixed code (if applicable, otherwise original code)",
            "feedback": "Feedback on the code quality and suggestions for improvement (can include LLM suggestions and tool details)"
        }}
        Code to analyze:
        ```python
        {query}
        ```
        """
        logger.info(f"DocAgent: Received query for documentation analysis:\n{query[:200]}...")

        try:
            agent_response = self.agent.query(prompt)
            llm_json_response = parse_thinking_outputs(agent_response.response)
            
            logger.info(f"DocAgent: LLM JSON response after agent query: {llm_json_response}")

            if llm_json_response:
                final_output_schema = OutputSchema(
                    code=query, 
                    issue=llm_json_response.get("issue", "No issue details provided by agent."),
                    feedback=llm_json_response.get("feedback", "No feedback provided by agent."),
                    fixed_code=llm_json_response.get("fixed_code", query),
                    reason=llm_json_response.get("reason", "No reason provided by agent.")
                )
            else:
                logger.warning("DocAgent: Agent did not produce a parsable JSON response. Constructing a default error response.")
                final_output_schema = OutputSchema(
                    code=query,
                    issue="Agent Response Error",
                    feedback="Agent did not produce the expected JSON output. Raw response: " + str(agent_response.response),
                    fixed_code=query,
                    reason="Agent failed to format its output correctly after processing."
                )

        except Exception as e:
            logger.exception("DocAgent: Error during documentation analysis agent execution:")
            final_output_schema = OutputSchema(
                code=query,
                issue="Agent Execution Error",
                feedback=f"An error occurred: {str(e)}",
                fixed_code=query,
                reason="The documentation analysis agent encountered an internal error."
            )
        
        return final_output_schema

logger.info("DocAgent (LLM-powered) module loaded.")

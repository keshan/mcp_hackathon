# src/agents/security_agent.py
from loguru import logger
import json

from llama_index.core.agent import AgentRunner, ReActAgentWorker

from src.core.llm import get_llm
from src.core.schemas import OutputSchema
from src.core.utils import parse_thinking_outputs
from gradio_client import Client
from llama_index.core.tools import FunctionTool
import os # For HUGGING_FACE_TOKEN if needed in the future


def run_gradio_security_check(code_snippet: str) -> dict:
    """
    Analyzes a Python code snippet for security vulnerabilities using a Gradio-based MCP tool.

    Args:
        code_snippet: The Python code string to analyze.

    Returns:
        A dictionary containing the security analysis results from the Bandit tool.
    """
    logger.info(f"Running Gradio security check for code (first 200 chars): {code_snippet[:200]}...")
    try:
        # For private spaces, a Hugging Face token might be needed:
        # hf_token = os.getenv("HUGGING_FACE_TOKEN")
        # client = Client(src="Agents-MCP-Hackathon/security_mcp_tools", hf_token=hf_token)
        client = Client(src="Agents-MCP-Hackathon/security_mcp_tools")

        parameters = {"code": code_snippet}
        tool_parameters_json = json.dumps(parameters)

        result = client.predict(
            tool_parameters_json=tool_parameters_json,
            api_name="/predict"  # As specified in the API documentation
        )
        logger.info(f"Gradio security check raw result: {result}")

        # The Gradio 'json' component output type might already be a dict/list.
        # If it's a string, try to parse it.
        if isinstance(result, str):
            try:
                parsed_result = json.loads(result)
                logger.info(f"Parsed Gradio security check result: {parsed_result}")
                return parsed_result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gradio security check result string to JSON: {result}. Error: {e}")
                return {"error": "Failed to parse result from security tool", "raw_output": result}
        elif isinstance(result, (dict, list)):
            logger.info(f"Gradio security check result (already dict/list): {result}")
            return result # Result is already in the desired format
        else:
            logger.warning(f"Unexpected type for Gradio security check result: {type(result)}. Raw: {result}")
            return {"error": "Unexpected result type from security tool", "raw_output": result}

    except Exception as e:
        logger.exception("Error calling Gradio security tool:")
        return {"error": f"Exception during Gradio security tool call: {str(e)}"}

gradio_bandit_tool = FunctionTool.from_defaults(
    fn=run_gradio_security_check,
    name="gradio_security_scanner",
    description="Runs a security scan on the provided Python code using an external Gradio-based security tool (Bandit). Input is the code string. Returns JSON analysis results which may include issues, confidence levels, and line numbers."
)

class SecurityAgent:
    def __init__(self):
        self.llm = get_llm()
        # Tools specific to this agent
        self.tools = [gradio_bandit_tool]

        self.agent_worker = ReActAgentWorker.from_tools(
            tools=self.tools,
            llm=self.llm,
            verbose=True  # Enable verbose logging for the agent's thoughts
        )
        self.agent = AgentRunner(self.agent_worker, llm=self.llm, verbose=True)
        logger.info(f"SecurityAgent initialized with LLM: {self.llm.model if hasattr(self.llm, 'model') else type(self.llm).__name__} and Agent: {type(self.agent).__name__}")
        logger.info(f"SecurityAgent tools: {[tool.metadata.name for tool in self.tools]}")

    def analyze_security(self, query: str) -> OutputSchema:
        prompt = f"""
        Analyzes the security of the provided code snippet using its LLM agent.
        Analyze the security of the following Python code for common vulnerabilities. 
        You can use the tools like bandit at your disposal and use that results also 
        for your assessment to make it much better. Provide a summary of findings and detailed issues if any. 
        The output must only be in the following JSON format. strictly adhere to this format. 
        Do not output anything other than this JSON object:
        {{
            "issue": "Issues found in the code as a text",
            "reason": "Reason for the issue and reasons for tagging them as issues tools used and their results",
            "fixed_code": "Fixed code",
            "feedback": "Feedback for the code"
        }}

        --- CODE START ---
        {query}
        --- CODE END ---
        """
        logger.info(f"SecurityAgent: Received query for security analysis:\n{query}")
        
        # clear_tool_outputs() # No longer needed as tool outputs are handled by the agent's ReAct loop

        try:
            agent_response = self.agent.query(prompt)
            
            # The agent's response should be the final JSON, incorporating tool outputs during its reasoning.
            llm_json_response = parse_thinking_outputs(agent_response.response)
            
            logger.info(f"SecurityAgent: LLM JSON response after agent query: {llm_json_response}")

            final_output_schema = None # Initialize with a type hint if possible, e.g., Optional[OutputSchema]

            if llm_json_response:
                final_output_schema = OutputSchema(
                    code=query, 
                    issue=llm_json_response.get("issue", "No issue details provided by agent."),
                    feedback=llm_json_response.get("feedback", "No feedback provided by agent."),
                    fixed_code=llm_json_response.get("fixed_code", query), # Default to original if not fixed
                    reason=llm_json_response.get("reason", "No reason provided by agent.")
                )
            else:
                # This case handles if parse_thinking_outputs returns None (e.g., agent didn't produce valid JSON)
                logger.warning("SecurityAgent: Agent did not produce a parsable JSON response. Constructing a default error response.")
                final_output_schema = OutputSchema(
                    code=query,
                    issue="Agent Response Error",
                    feedback="Agent did not produce the expected JSON output. Raw response: " + str(agent_response.response),
                    fixed_code=query,
                    reason="Agent failed to format its output correctly after processing."
                )

        except Exception as e:
            logger.exception("SecurityAgent: Error during security analysis agent execution:")
            final_output_schema = OutputSchema(
                    code=query, 
                    issue="SecurityAgent Execution Error", 
                    feedback=f"Error in SecurityAgent: {str(e)}",
                    fixed_code=query, 
                    reason="Exception during agent processing."
                )
        
        logger.info("SecurityAgent: Analysis complete. Returning OutputSchema.")
        return final_output_schema

logger.info("SecurityAgent (LLM-powered) module loaded.")

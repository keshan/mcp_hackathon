# src/agents/security_agent.py
from loguru import logger
import json

from llama_index.core.agent import AgentRunner, ReActAgentWorker

from src.core.llm import get_llm
from src.core.schemas import OutputSchema
from src.core.utils import parse_thinking_outputs
from src.core.mcp_tools import (
    adapted_bandit_mcp_tool, # The LlamaIndex tool for Bandit
    get_all_tool_outputs,
    clear_tool_outputs,
)

class SecurityAgent:
    def __init__(self):
        self.llm = get_llm()
        # Tools specific to this agent
        self.tools = [adapted_bandit_mcp_tool]

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
        The query should contain the code and instructions for analysis. You can use the
        tools at your disposal and use that results also for your assessment. 
        The output must only be in the following JSON format. strictly adhere to this format. 
        Do not output anything other than this JSON object:
        {{
            "issue": "Issues found in the code as a text",
            "reason": "Reason for the issue and reasons for tagging them as issues tools used and their results",
            "fixed_code": "Fixed code",
            "feedback": "Feedback for the code"
        }}

        Here's the query:
        {query}
        """
        logger.info(f"SecurityAgent: Received query for security analysis:\n{query}")
        
        clear_tool_outputs() 

        try:
            agent_response = self.agent.query(prompt)
                  
            llm_json_response = parse_thinking_outputs(agent_response.response)
            
            logger.info(f"SecurityAgent: LLM JSON response: {llm_json_response}")

            tool_outputs_data = get_all_tool_outputs()
            
            final_output_schema: Optional[OutputSchema] = None

            if llm_json_response:
                 final_output_schema = OutputSchema(
                    code=query, 
                    issue=llm_json_response.get("issue", "Unknown Issue"),
                    feedback=llm_json_response.get("feedback", "No feedback provided"),
                    fixed_code=llm_json_response.get("fixed_code", query),
                    reason=llm_json_response.get("reason", "No reason given by Security Analysis Agent LLM.")
                )

            for tool_call_data in tool_outputs_data:
                if tool_call_data.get("tool_name") == "bandit_mcp_tool": # Matches the FunctionTool name
                    bandit_output = tool_call_data.get("output", {})
                    bandit_issues = bandit_output.get("issues", []) # Assuming 'issues' is the key
                    for issue in bandit_issues:
                        final_output_schema = OutputSchema(
                            code=query, # Could try to get from raw_input if complex
                            issue=f"Bandit-{issue.get('test_id', 'UnknownIssue')}",
                            feedback=issue.get('message', issue.get('text', 'No message')), # Bandit uses 'message' or 'text'
                            fixed_code=query, # Could try to get from raw_input if complex
                            reason=f"Security issue identified by Bandit ({issue.get('test_id', 'UnknownIssue')}). Severity: {issue.get('severity', 'N/A')}"
                        )
            
            if not tool_outputs_data:
                logger.info("SecurityAgent: No specific tool outputs captured by this agent's run.")


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

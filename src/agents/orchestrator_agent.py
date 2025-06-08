# src/agents/orchestrator_agent.py
import json
from loguru import logger
from typing import List, Optional

from llama_index.core.agent import AgentRunner, ReActAgentWorker

from src.core.llm import get_llm
from src.core.schemas import CodeInputSchema, OutputSchema, OrchestratorDecision
from src.agents.doc_agent import DocAgent
from src.agents.security_agent import SecurityAgent

class CodeAnalysisOrchestrator:
    def __init__(self):
        self.llm = get_llm()
        
        self.doc_agent = DocAgent()
        self.security_agent = SecurityAgent()

        self.orchestrator_agent_worker = ReActAgentWorker.from_tools(
            tools=[], 
            llm=self.llm,
            verbose=True
        )
        self.orchestrator_agent = AgentRunner(self.orchestrator_agent_worker, llm=self.llm, verbose=True)
        logger.info(f"CodeAnalysisOrchestrator initialized with LLM: {self.llm.model if hasattr(self.llm, 'model') else type(self.llm).__name__}")
        logger.info("Orchestrator's own agent initialized for planning and aggregation.")

    def _convert_code_input_to_string(self, code_input: CodeInputSchema) -> str:
        return code_input.code

    # def _format_outputs_for_prompt(self, agent_name: str, output_schema: Optional[OutputSchema]) -> str:
    #     if not output_schema:
    #         return f"{agent_name}: No findings reported or agent not run."
        
    #     lines = [f"{agent_name} Findings:"]
    #     for out_line in output_schema.results:
    #         details = f"Issue: {out_line.issue}, Feedback: {out_line.feedback}"
    #         if out_line.line_number > 0:
    #             details += f", Line: {out_line.line_number}"
    #         if out_line.reason:
    #              details += f", Reason: {out_line.reason}"
    #         lines.append(f"- {details}")
    #     return "\n".join(lines)

    def analyze_code(self, code_input: CodeInputSchema) -> OutputSchema:
        code_string = self._convert_code_input_to_string(code_input)
        if not code_string.strip():
            logger.warning("Orchestrator: Received empty code for analysis.")
            return OutputSchema(code="", issue="Orchestrator Input Error", feedback="No code provided for analysis.", reason="Input code was empty.")

        logger.info("Orchestrator: Starting analysis for code snippet...")

        assessment_prompt = f"""You are a master software analysis orchestrator.
Given the following Python code:
--- CODE START ---
{code_string}
--- CODE END ---

1. Assess the code and determine the required analysis depth: 'minimum', 'standard', or 'deep'.
2. Based on the depth and code content, decide which specialized analysis agents to invoke: 'DocAgent' for documentation, 'SecurityAgent' for security. You can choose one, both, or none if the code is trivial.
3. Respond ONLY with a JSON object containing your assessment. Do not add any other text before or after the JSON.
   Example JSON:
   {OrchestratorDecision.model_json_schema()}
"""
        logger.info("Orchestrator: Performing initial assessment with its own LLM agent...")
        assessment_response_str = self.orchestrator_agent.query(assessment_prompt).response
        logger.debug(f"Orchestrator: Raw assessment response from LLM: {assessment_response_str}")

        assessment = {}
        invoke_doc_agent = False
        invoke_security_agent = False
        
        try:
            # Attempt to find JSON within the response string if it's not purely JSON
            json_start_index = assessment_response_str.find('{')
            json_end_index = assessment_response_str.rfind('}') + 1
            if json_start_index != -1 and json_end_index != -1 and json_start_index < json_end_index:
                json_str = assessment_response_str[json_start_index:json_end_index]
                assessment = json.loads(json_str)
                invoke_doc_agent = assessment.get("invoke_doc_agent", False)
                invoke_security_agent = assessment.get("invoke_security_agent", False)
                logger.info(f"Orchestrator: Assessment complete. Depth: {assessment.get('analysis_depth')}, Invoke Doc: {invoke_doc_agent}, Invoke Security: {invoke_security_agent}")
                logger.debug(f"Orchestrator: Assessment reasoning: {assessment.get('reasoning')}")
            else:
                raise json.JSONDecodeError("No JSON object found in response", assessment_response_str, 0)
        except json.JSONDecodeError as e:
            logger.error(f"Orchestrator: Failed to parse assessment JSON: {e}. Raw response: {assessment_response_str}. Defaulting to full analysis.")
            invoke_doc_agent = True
            invoke_security_agent = True
            assessment = {{
                "analysis_depth": "standard (defaulted due to parsing error)",
                "invoke_doc_agent": True,
                "invoke_security_agent": True,
                "reasoning": f"Assessment parsing failed. Raw response: {assessment_response_str}. Proceeding with default full analysis."
            }}

        doc_agent_output: Optional[OutputSchema] = None
        if invoke_doc_agent:
            doc_agent_query = f"Analyze the documentation of the following Python code. Focus on PEP 257 compliance and general docstring quality. Provide a summary of findings and detailed issues if any.\n\n--- CODE START ---\n{code_string}\n--- CODE END ---"
            logger.info("Orchestrator: Invoking DocAgent...")
            doc_agent_output = self.doc_agent.analyze_documentation(doc_agent_query)
            logger.info("Orchestrator: DocAgent finished.")

        security_agent_output: Optional[OutputSchema] = None
        if invoke_security_agent:
            security_agent_query = f"Analyze the security of the following Python code for common vulnerabilities using Bandit. Provide a summary of findings and detailed issues if any.\n\n--- CODE START ---\n{code_string}\n--- CODE END ---"
            logger.info("Orchestrator: Invoking SecurityAgent...")
            security_agent_output = self.security_agent.analyze_security(security_agent_query)
            logger.info("Orchestrator: SecurityAgent finished.")

        doc_findings_str = doc_agent_output.model_dump_json() if doc_agent_output else ""
        security_findings_str = security_agent_output.model_dump_json() if security_agent_output else ""
        initial_assessment_details = json.dumps(assessment, indent=2) if assessment else ""

        aggregation_prompt = f"""You are a master software analysis orchestrator. You have received analysis results from specialized agents.
The original code snippet was:
--- CODE START ---
{code_string}
--- CODE END ---

Your Initial Assessment and Plan was:
{initial_assessment_details}

Documentation Agent Findings:
{doc_findings_str}

Security Agent Findings:
{security_findings_str}

Please synthesize all this information into a single, comprehensive analysis.
This analysis include the aggregation from Documentation Agent and Security Agent.
Provide an overall summary of the issues in the code as mentioned by Documentation 
Agent and Security Agent as single text, then list the detailed findings/feedbacks 
from both the agents as a single text. Similarly synthesize the reason for each issue 
as mentioned by both the agents as single text. and a suggested fixes applied to the
initial code if no suggestions are provided by the agents, then leave it empty.
Your response should be the final analysis report. Be clear and actionable.
the final output must strictly be ONLY in following JSON format:
{OutputSchema.model_json_schema()}
"""
        logger.info("Orchestrator: Performing final aggregation with its own LLM agent...")
        final_report_str = self.orchestrator_agent.query(aggregation_prompt).response
        logger.info("Orchestrator: Aggregation complete.")

        try:
            if "</think>" in final_report_str:
                final_report_str = final_report_str.split("</think>")[-1].strip()
            final_json_str = json.loads(final_report_str)
        except json.JSONDecodeError as e:
            logger.error(f"Orchestrator: Failed to parse final aggregation JSON: {e}. Raw response: {final_report_str}")
            final_json_str = None

        final_outputs: OutputSchema = OutputSchema(
            code=code_string, # General summary, no specific code line
            issue=final_json_str.get("issue", "Unknown Issue"),
            feedback=final_json_str.get("feedback", "No feedback provided"),
            reason=final_json_str.get("reason", "No reason given by Orchestrator LLM."),
            fixed_code=final_json_str.get("fixed_code", "")
        )
        
        logger.info("Orchestrator: Full analysis process complete.")
        return final_outputs, doc_agent_output, security_agent_output

logger.info("CodeAnalysisOrchestrator (multi-agent capable) module loaded.")

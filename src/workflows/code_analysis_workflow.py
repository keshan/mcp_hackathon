# src/workflows/code_analysis_workflow.py
import json
import uuid # For generating unique request IDs
from typing import Optional, Dict, Any, Union

from loguru import logger
from pydantic import BaseModel # Ensure BaseModel is imported

from llama_index.core.workflow import (
    Workflow,
    StartEvent,
    StopEvent,
    Event,
    Context,
    step,
)

from src.core.schemas import CodeInputSchema, OutputSchema, OrchestratorDecision
from src.agents.doc_agent import DocAgent
from src.agents.security_agent import SecurityAgent
from src.core.llm import get_llm # Assuming this returns a LlamaIndex compatible LLM
from src.core.utils import parse_thinking_outputs


# --- Composite Output Schema ---
class WorkflowCompleteOutput(BaseModel):
    request_id: str
    final_aggregated_output: OutputSchema
    doc_agent_output: Optional[OutputSchema] = None
    security_agent_output: Optional[OutputSchema] = None

# --- Event Definitions ---
class CodeAnalysisRequestEvent(Event):
    request_id: str
    code_input: CodeInputSchema

class InitialAssessmentEvent(Event):
    request_id: str
    code_string: str
    assessment: OrchestratorDecision

class DocAnalysisRequestTrigger(Event): # Renamed to avoid confusion with Complete
    request_id: str
    code_string: str

class SecurityAnalysisRequestTrigger(Event): # Renamed
    request_id: str
    code_string: str

class DocAnalysisCompleteEvent(Event):
    request_id: str
    doc_findings: Optional[OutputSchema]

class SecurityAnalysisCompleteEvent(Event):
    request_id: str
    security_findings: Optional[OutputSchema]

class AggregationReadyEvent(Event):
    request_id: str
    code_string: str
    assessment: OrchestratorDecision # The original assessment
    doc_findings: Optional[OutputSchema]
    security_findings: Optional[OutputSchema]


# --- Workflow Definition ---
class CodeAnalysisWorkflow(Workflow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.llm = get_llm() 
        self.doc_agent = DocAgent()
        self.security_agent = SecurityAgent()
        logger.info("CodeAnalysisWorkflow initialized.")

    @step
    async def start_analysis(self, ev: StartEvent) -> CodeAnalysisRequestEvent:
        code_input = ev.code_input
        request_id = getattr(ev, 'request_id', None)
        current_request_id = request_id or str(uuid.uuid4())
        logger.info(f"[{current_request_id}] Workflow started. Received code input.")
        return CodeAnalysisRequestEvent(request_id=current_request_id, code_input=code_input)

    @step
    async def initial_assessment_step(self, ev: CodeAnalysisRequestEvent) -> InitialAssessmentEvent:
        logger.info(f"[{ev.request_id}] Performing initial assessment...")
        code_string = ev.code_input.code
        if not code_string.strip():
            logger.warning(f"[{ev.request_id}] Received empty code for analysis.")
            decision = OrchestratorDecision(
                analysis_depth="minimum",
                invoke_doc_agent=False,
                invoke_security_agent=False,
                reasoning="Input code was empty."
            )
            return InitialAssessmentEvent(request_id=ev.request_id, code_string=code_string, assessment=decision)

        assessment_prompt = f"""You are a master software analysis orchestrator. Given the following Python code:
--- CODE START ---
{code_string}
--- CODE END ---

1. Assess the code and determine the required analysis depth: 'minimum', 'standard', or 'deep'.
2. Based on the depth and code content, decide which specialized analysis agents to invoke: 'DocAgent' for documentation, 'SecurityAgent' for security. You can choose one, both, or none if the code is trivial.
3. Respond ONLY with a JSON object containing your assessment. Do not add any other text before or after the JSON.
   Example JSON schema of the pydantic model:
   {OrchestratorDecision.model_json_schema()}
"""
        
        llm_response = await self.llm.acomplete(assessment_prompt)
        assessment_response_str = llm_response.text # Adapt if LLM model gives different response structure
        logger.debug(f"[{ev.request_id}] Raw assessment LLM response: {assessment_response_str}")

        decision: OrchestratorDecision
        try:
            json_start_index = assessment_response_str.find('{')
            json_end_index = assessment_response_str.rfind('}') + 1
            if json_start_index != -1 and json_end_index != -1 and json_start_index < json_end_index:
                json_str = assessment_response_str[json_start_index:json_end_index]
                decision_dict = json.loads(json_str)
                decision = OrchestratorDecision(**decision_dict)
            else: raise json.JSONDecodeError("No JSON found", "", 0)
            logger.info(f"[{ev.request_id}] Assessment: Depth: {decision.analysis_depth}, Doc: {decision.invoke_doc_agent}, Sec: {decision.invoke_security_agent}")
        except Exception as e:
            logger.error(f"[{ev.request_id}] Assessment JSON parsing error: {e}. Defaulting.")
            decision = OrchestratorDecision(analysis_depth="standard", invoke_doc_agent=True, invoke_security_agent=True, reasoning=f"Parse error: {e}")
        return InitialAssessmentEvent(request_id=ev.request_id, code_string=code_string, assessment=decision)

    @step
    async def dispatch_agencies_step(self, ctx: Context, ev: InitialAssessmentEvent) -> Union[DocAnalysisRequestTrigger, SecurityAnalysisRequestTrigger, AggregationReadyEvent, None]:
        logger.info(f"[{ev.request_id}] Dispatcher: Assessment received. Doc: {ev.assessment.invoke_doc_agent}, Sec: {ev.assessment.invoke_security_agent}")

        # If no agents are to be invoked, we can proceed directly to aggregation.
        if not ev.assessment.invoke_doc_agent and not ev.assessment.invoke_security_agent:
            logger.info(f"[{ev.request_id}] Dispatcher: No agents to invoke. Proceeding to aggregation.")
            return AggregationReadyEvent(
                request_id=ev.request_id,
                code_string=ev.code_string,
                assessment=ev.assessment,
                doc_findings=None,
                security_findings=None
            )
        
        # Otherwise, initialize the state for this request_id in the context
        workflow_state = {
            "assessment": ev.assessment,
            "code_string": ev.code_string,
            "doc_findings": "EXPECTED" if ev.assessment.invoke_doc_agent else None,
            "security_findings": "EXPECTED" if ev.assessment.invoke_security_agent else None,
        }
        await ctx.set(ev.request_id, workflow_state)
        
        if ev.assessment.invoke_doc_agent:
            logger.info(f"[{ev.request_id}] Dispatcher: Sending DocAnalysisRequestTrigger.")
            ctx.send_event(DocAnalysisRequestTrigger(request_id=ev.request_id, code_string=ev.code_string))

        if ev.assessment.invoke_security_agent:
            logger.info(f"[{ev.request_id}] Dispatcher: Sending SecurityAnalysisRequestTrigger.")
            ctx.send_event(SecurityAnalysisRequestTrigger(request_id=ev.request_id, code_string=ev.code_string))

        return None

    @step(num_workers=2)
    async def doc_analysis_step(self, ev: DocAnalysisRequestTrigger) -> DocAnalysisCompleteEvent:
        logger.info(f"[{ev.request_id}] DocAgent: Starting analysis for request.")
        try:
            findings = self.doc_agent.analyze_documentation(ev.code_string)
            logger.info(f"[{ev.request_id}] DocAgent: Analysis complete.")
            return DocAnalysisCompleteEvent(request_id=ev.request_id, doc_findings=findings)
        except Exception as e:
            logger.error(f"[{ev.request_id}] DocAgent: Error: {e}")
            return DocAnalysisCompleteEvent(request_id=ev.request_id, doc_findings=None)

    @step(num_workers=2)
    async def security_analysis_step(self, ev: SecurityAnalysisRequestTrigger) -> SecurityAnalysisCompleteEvent:
        logger.info(f"[{ev.request_id}] SecurityAgent: Starting analysis for request.")
        try:
            findings = self.security_agent.analyze_security(ev.code_string)
            logger.info(f"[{ev.request_id}] SecurityAgent: Analysis complete.")
            return SecurityAnalysisCompleteEvent(request_id=ev.request_id, security_findings=findings)
        except Exception as e:
            logger.error(f"[{ev.request_id}] SecurityAgent: Error: {e}")
            return SecurityAnalysisCompleteEvent(request_id=ev.request_id, security_findings=None)

    @step(num_workers=2) # This step can run concurrently for different events
    async def collector_step(self, ctx: Context, ev: Union[DocAnalysisCompleteEvent, SecurityAnalysisCompleteEvent]) -> Optional[AggregationReadyEvent]:
        request_id = ev.request_id
        logger.info(f"[{request_id}] Collector: Received event {type(ev).__name__}.")

        # Retrieve the state for this request_id from the context
        workflow_state = await ctx.get(request_id, default=None)
        if workflow_state is None:
            logger.warning(f"[{request_id}] Collector: Received an event for an unknown or expired request. Discarding.")
            return None

        # Update state based on the event received
        if isinstance(ev, DocAnalysisCompleteEvent):
            workflow_state["doc_findings"] = ev.doc_findings
        elif isinstance(ev, SecurityAnalysisCompleteEvent):
            workflow_state["security_findings"] = ev.security_findings

        # Persist the updated state
        await ctx.set(request_id, workflow_state)

        # Check if all expected results have arrived
        doc_done = workflow_state.get("doc_findings") != "EXPECTED"
        sec_done = workflow_state.get("security_findings") != "EXPECTED"

        if doc_done and sec_done:
            logger.info(f"[{request_id}] Collector: All agent results received. Triggering aggregation.")
            # The context is managed per-run, so manual cleanup is not needed.
            return AggregationReadyEvent(
                request_id=request_id,
                code_string=workflow_state["code_string"],
                assessment=workflow_state["assessment"],
                doc_findings=workflow_state["doc_findings"],
                security_findings=workflow_state["security_findings"],
            )
        
        logger.info(f"[{request_id}] Collector: Waiting for more results. Doc done: {doc_done}, Sec done: {sec_done}")
        return None

    @step
    async def aggregation_step(self, ev: AggregationReadyEvent) -> StopEvent:
        logger.info(f"[{ev.request_id}] Aggregator: Starting final aggregation.")
        
        # Prepare the thinking process prompt
        final_prompt = f"""You are a master software analysis orchestrator.
Code to analyze:
---
{ev.code_string}
---

Initial assessment was: {ev.assessment.reasoning}

Analysis results from specialized agents:

1.  **Documentation Agent Findings**:
    ```json
    {json.dumps(ev.doc_findings.model_dump() if ev.doc_findings else {'status': 'not_run'}, indent=2)}
    ```

2.  **Security Agent Findings**:
    ```json
    {json.dumps(ev.security_findings.model_dump() if ev.security_findings else {'status': 'not_run'}, indent=2)}
    ```

Synthesize these findings into a single, actionable, and user-friendly summary. Focus on providing clear, constructive feedback. The final output must be a JSON object adhering to this Pydantic schema:

```json
{OutputSchema.model_json_schema()}
```
Respond ONLY with the JSON object.
"""
        
        try:
            llm_response = await self.llm.acomplete(final_prompt)
            response_text = llm_response.text
            logger.debug(f"[{ev.request_id}] Aggregator: Raw LLM response: {response_text}")

            # Extract JSON from the response
            json_start_index = response_text.find('{')
            json_end_index = response_text.rfind('}') + 1
            if json_start_index != -1 and json_end_index != -1:
                json_str = response_text[json_start_index:json_end_index]
                final_output = OutputSchema(**json.loads(json_str))
            else:
                raise ValueError("No valid JSON found in the aggregator response.")

            logger.info(f"[{ev.request_id}] Aggregator: Aggregation complete.")
        except Exception as e:
            logger.error(f"[{ev.request_id}] Aggregator: Failed to aggregate results: {e}")
            final_output = OutputSchema(
                summary="Failed to generate a final summary due to an internal error.",
                recommendations=["Please check the logs for more details."],
                issues=[]
            )

        # Prepare the final event to stop the workflow
        final_event = WorkflowCompleteOutput(
            request_id=ev.request_id,
            final_aggregated_output=final_output,
            doc_agent_output=ev.doc_findings,
            security_agent_output=ev.security_findings,
        )
        return StopEvent(result=final_event)
        
        # Persist changes back to context
        await ctx.set(request_id, workflow_state)

        # Check if all expected results have arrived
        doc_expected = workflow_state["assessment"].invoke_doc_agent
        sec_expected = workflow_state["assessment"].invoke_security_agent

        doc_received = (workflow_state.get("doc_findings") != "EXPECTED") if doc_expected else True
        sec_received = (workflow_state.get("security_findings") != "EXPECTED") if sec_expected else True

        if doc_received and sec_received:
            logger.info(f"[{request_id}] Collector: All expected analyses received. Ready for aggregation.")
            actual_doc_findings = workflow_state.get("doc_findings") if workflow_state.get("doc_findings") != "EXPECTED" else None
            actual_sec_findings = workflow_state.get("security_findings") if workflow_state.get("security_findings") != "EXPECTED" else None
            
            return AggregationReadyEvent(
                request_id=request_id,
                code_string=workflow_state["code_string"],
                assessment=workflow_state["assessment"],
                doc_findings=actual_doc_findings,
                security_findings=actual_sec_findings
            )
        else:
            logger.debug(f"[{request_id}] Collector: Waiting. Doc received: {doc_received}, Sec received: {sec_received}.")

        return None

    @step
    async def final_aggregation_step(self, ctx: Context, ev: AggregationReadyEvent) -> StopEvent:
        logger.info(f"[{ev.request_id}] Performing final aggregation...")
        code_string = ev.code_string
        doc_findings_str = ev.doc_findings.model_dump_json(indent=2) if ev.doc_findings else "No findings from DocAgent."
        security_findings_str = ev.security_findings.model_dump_json(indent=2) if ev.security_findings else "No findings from SecurityAgent."
        initial_assessment_details = ev.assessment.model_dump_json(indent=2)

        aggregation_prompt = f"""Synthesize analysis for code:
{code_string}
Assessment:
{initial_assessment_details}
Doc Findings:
{doc_findings_str}
Security Findings:
{security_findings_str}
Respond ONLY with JSON: {OutputSchema.model_json_schema()}"""

        llm_response = await self.llm.acomplete(aggregation_prompt)
        final_report_str = llm_response.text
        logger.debug(f"[{ev.request_id}] Raw aggregation LLM response: {final_report_str}")
        
        final_json_dict = parse_thinking_outputs(final_report_str)

        final_aggregated_output = OutputSchema(
            code=code_string,
            issue=final_json_dict.get("issue", "Aggregation Incomplete"),
            feedback=final_json_dict.get("feedback", "Could not generate aggregated feedback."),
            reason=final_json_dict.get("reason", "N/A"),
            fixed_code=final_json_dict.get("fixed_code", "")
        )

        workflow_result = WorkflowCompleteOutput(
            request_id=ev.request_id,
            final_aggregated_output=final_aggregated_output,
            doc_agent_output=ev.doc_findings,
            security_agent_output=ev.security_findings
        )
        
        logger.info(f"[{ev.request_id}] Workflow complete. Final result packaged.")
        # Clean up the state for this request from the context
        await ctx.set(ev.request_id, None)
        return StopEvent(result=workflow_result)

logger.info("CodeAnalysisWorkflow module loaded.")

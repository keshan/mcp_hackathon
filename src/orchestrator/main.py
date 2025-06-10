# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "llama-index-core",
#     "llama-index-llms-openai-like",
#     "pydantic",
#     "python-dotenv",
#     "loguru",
#     "httpx",
#     "openinference-instrumentation-llama-index",
#     "arize-phoenix",
# ]
# ///
# src/orchestrator/main.py

import asyncio
import json
import uuid
from loguru import logger

# Core setup modules
from src.core.observability import setup_observability
from src.core.schemas import CodeInputSchema

# Import the new workflow
from src.workflows.code_analysis_workflow import CodeAnalysisWorkflow, WorkflowCompleteOutput

# Setup observability (includes load_dotenv())
# This should be called once when the application/script starts.
setup_observability()

async def main():
    logger.info("MAIN: Initializing CodeAnalysisWorkflow...")
    workflow = CodeAnalysisWorkflow(verbose=True, timeout=180)

    sample_code_to_analyze_str = (
        "import os\n\n"
        "def my_function_without_docstring():\n"
        "    # This function lacks a docstring.\n"
        "    print(\"Hello, world!\")\n"
        "    password = os.getenv(\"MY_PASSWORD\") # Potential security issue: using getenv for sensitive data\n"
        "    return password\n\n"
        "def another_function_with_docstring():\n"
        "    \"\"\"This is a good docstring.\"\"\"\n"
        "    pass"
    )

    code_input = CodeInputSchema(code=sample_code_to_analyze_str)
    
    request_id = f"local_run_{uuid.uuid4()}"
    logger.info(f"MAIN: [{request_id}] Starting workflow for code (first 100 chars): {sample_code_to_analyze_str[:100]}...")
    result: WorkflowCompleteOutput = await workflow.run(code_input=code_input, request_id=request_id)

    if result:
        logger.info(f"--- Workflow Result for Request ID: {result.request_id} ---")
        
        logger.info("--- Final Aggregated Output ---")
        logger.info(result.final_aggregated_output.model_dump_json(indent=2))

        if result.doc_agent_output:
            logger.info("--- Doc Agent Output ---")
            logger.info(result.doc_agent_output.model_dump_json(indent=2))
        else:
            logger.info("--- Doc Agent Output: Not run or no findings ---")

        if result.security_agent_output:
            logger.info("--- Security Agent Output ---")
            logger.info(result.security_agent_output.model_dump_json(indent=2))
        else:
            logger.info("--- Security Agent Output: Not run or no findings ---")
    else:
        logger.error("MAIN: Workflow did not return a result.")

    logger.info("MAIN: Script finished.")

if __name__ == "__main__":
    asyncio.run(main())

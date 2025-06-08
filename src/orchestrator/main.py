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

import json
from loguru import logger

# Core setup modules
from src.core.observability import setup_observability
from src.core.schemas import CodeInputSchema # MODIFIED: Import necessary schemas

# Import the orchestrator
from src.agents.orchestrator_agent import CodeAnalysisOrchestrator

# Setup observability (includes load_dotenv())
# This should be called once when the application/script starts.
setup_observability()

if __name__ == "__main__":
    logger.info("MAIN: Initializing CodeAnalysisOrchestrator...")
    orchestrator = CodeAnalysisOrchestrator()
    
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

    # Convert the string to CodeInputSchema
    code_input = CodeInputSchema(code=sample_code_to_analyze_str)
    
    logger.info(f"MAIN: Sending CodeInputSchema to orchestrator. Code (first 100 chars): {sample_code_to_analyze_str[:100]}...")
    final_outputs, doc_agent_output, security_agent_output = orchestrator.analyze_code(code_input) 
    
    logger.info("MAIN: Orchestrator analysis results (OutputSchema):")
    
    results_dict = {}
    if final_outputs:
        try:
            results_dict = final_outputs.model_dump(mode='json') # Pydantic v2+
        except AttributeError:
            try:
                results_dict = final_outputs.dict() # Pydantic v1
            except AttributeError:
                logger.error("MAIN: Could not convert final_outputs to dict. It might not be a Pydantic model or is None.")
                results_dict = {"error": "Failed to serialize output schema."}
        except Exception as e:
            logger.error(f"MAIN: Error serializing OutputSchema: {e}")
            results_dict = {"error": f"Failed to serialize output schema: {str(e)}"}
    else:
        logger.warning("MAIN: final_outputs is None.")
        results_dict = {"warning": "Orchestrator returned None."}
        
    logger.info(json.dumps(results_dict, indent=4))

    logger.info("MAIN: Script finished.")

# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "gradio",
#     "llama-index-core",
#     "llama-index-llms-openai-like",
#     "pydantic",
#     "python-dotenv",
#     "loguru",
#     "httpx",
#     "openinference-instrumentation-llama-index",
#     "arize-phoenix",
#     "gradio-codeanalysisviewer",
# ]
# ///

import gradio as gr
import json
from gradio_codeanalysisviewer import CodeAnalysisViewer
from loguru import logger

# Core setup modules
from src.core.observability import setup_observability
from src.core.schemas import CodeInputSchema

# Import the orchestrator
from src.agents.orchestrator_agent import CodeAnalysisOrchestrator

# Initialize orchestrator once
# Ensure environment variables are loaded for orchestrator initialization if needed
# setup_observability() will handle dotenv loading
_orchestrator_instance = None

def get_orchestrator():
    global _orchestrator_instance
    if _orchestrator_instance is None:
        logger.info("UI: Initializing CodeAnalysisOrchestrator for the first time...")
        _orchestrator_instance = CodeAnalysisOrchestrator()
    return _orchestrator_instance

def pydantic_to_dict(model_instance):
    """Helper function to convert a Pydantic model instance to a dictionary."""
    if not model_instance:
        return None
    try:
        # Pydantic v2+
        return model_instance.model_dump(mode='json')
    except AttributeError:
        try:
            # Pydantic v1
            return model_instance.dict()
        except AttributeError:
            logger.error(f"Failed to serialize: Input is not a Pydantic model or is None. Type: {type(model_instance)}")
            return {"error": "Output is not a Pydantic model or is None."}
    except Exception as e:
        logger.error(f"Error serializing Pydantic model: {e}")
        return {"error": f"Failed to serialize output: {str(e)}"}

def analyze_code_ui(code_str: str):
    """Analyzes the input code string using the orchestrator and returns results."""
    if not code_str or not code_str.strip():
        logger.warning("UI: No code provided for analysis.")
        empty_result = {"info": "No code provided."}
        return empty_result, empty_result, empty_result

    orchestrator = get_orchestrator()
    code_input = CodeInputSchema(code=code_str)
    
    logger.info(f"UI: Sending CodeInputSchema to orchestrator. Code (first 100 chars): {code_str[:100].replace('\n', ' ')}...")
    
    try:
        final_outputs, doc_agent_output, security_agent_output = orchestrator.analyze_code(code_input)
    except Exception as e:
        logger.error(f"UI: Error during orchestrator.analyze_code: {e}", exc_info=True)
        error_result = {"error": f"Analysis failed: {str(e)}"}
        return error_result, error_result, error_result

    logger.info("UI: Orchestrator analysis complete. Serializing outputs...")

    final_results_dict = pydantic_to_dict(final_outputs)
    doc_agent_dict = pydantic_to_dict(doc_agent_output)
    security_agent_dict = pydantic_to_dict(security_agent_output)

    if final_results_dict is None: final_results_dict = {"info": "No combined output from orchestrator."}
    # if doc_agent_dict is None: doc_agent_dict = {"info": "No output from documentation agent."}
    # if security_agent_dict is None: security_agent_dict = {"info": "No output from security agent."}
    
    return final_results_dict

# Create the Gradio interface
iface = gr.Interface(
    fn=analyze_code_ui,
    inputs=gr.Textbox(
        lines=20, 
        label="Python Code to Analyze", 
        placeholder="Paste your Python code here..."
    ),
    outputs=[
        CodeAnalysisViewer(label="Overall Code Analysis")
    ],
    title="Agentic Code Analyzer",
    description=(
        "Enter Python code to be analyzed by a multi-agent system. "
        "The system will perform a comprehensive analysis of your Python code, covering documentation, security, and other aspects, providing combined insights."
    ),
    allow_flagging="never",
    examples=[
        [
            "import os\n\ndef my_function_without_docstring():\n    print(\"Hello, world!\")\n    password = os.getenv(\"MY_PASSWORD\")\n    return password\n\ndef another_function_with_docstring():\n    \"\"\"This is a good docstring.\"\"\"\n    pass"
        ]
    ]
)

if __name__ == "__main__":
    # Setup observability (includes load_dotenv())
    # This should be called once when the application/script starts.
    setup_observability()
    
    logger.info("UI: Launching Gradio interface...")
    # The get_orchestrator() call here pre-initializes it if not already done,
    # ensuring any startup messages from it appear before Gradio's server messages.
    get_orchestrator() 
    iface.launch() # Add share=True if you want a public link: iface.launch(share=True)

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
import asyncio
from gradio_codeanalysisviewer import CodeAnalysisViewer
from loguru import logger


# Core setup modules
from src.core.observability import setup_observability
from src.core.schemas import CodeInputSchema

# Import the workflow
from src.workflows.code_analysis_workflow import CodeAnalysisWorkflow, WorkflowCompleteOutput

# Initialize workflow once
_workflow_instance = None

def get_workflow():
    global _workflow_instance
    if _workflow_instance is None:
        logger.info("UI: Initializing CodeAnalysisWorkflow for the first time...")
        _workflow_instance = CodeAnalysisWorkflow(timeout=120)
    return _workflow_instance

def pydantic_to_dict(model_instance):
    """Helper function to convert a Pydantic model instance to a dictionary."""
    if not model_instance:
        return None
    try:
        return model_instance.model_dump(mode='json')
    except Exception as e:
        logger.error(f"Error serializing Pydantic model: {e}")
        return {"error": f"Failed to serialize output: {str(e)}"}

async def analyze_code_ui(code_str: str):
    """Analyzes the input code string using the workflow and returns results."""
    if not code_str or not code_str.strip():
        logger.warning("UI: No code provided for analysis.")
        return {"info": "No code provided."}

    workflow = get_workflow()
    code_input = CodeInputSchema(code=code_str)
    
    logger.info(f"UI: Sending code to workflow. Code (first 100 chars): {code_str[:100].replace('\n', ' ')}...")
    
    try:
        # Run the async workflow, passing the input data as keyword arguments
        result: WorkflowCompleteOutput = await workflow.run(code_input=code_input)
        
        # Extract the final aggregated output
        final_outputs = result.final_aggregated_output
        
    except Exception as e:
        logger.error(f"UI: Error during workflow execution: {e}", exc_info=True)
        return {"error": f"Analysis failed: {str(e)}"}

    logger.info("UI: Workflow analysis complete. Serializing outputs...")

    final_results_dict = pydantic_to_dict(final_outputs)

    if final_results_dict is None:
        final_results_dict = {"info": "No combined output from workflow."}
    
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
    setup_observability()
    
    logger.info("UI: Launching Gradio interface...")
    # Pre-initialize the workflow to show any startup messages
    get_workflow()
    iface.launch(server_name="0.0.0.0")

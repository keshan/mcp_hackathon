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
        _workflow_instance = CodeAnalysisWorkflow(timeout=600)
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

async def analyze_code_logic(code_str: str):
    """The core logic for analyzing code, separated from UI updates."""
    if not code_str or not code_str.strip():
        logger.warning("UI: No code provided for analysis.")
        return {"info": "No code provided."}

    workflow = get_workflow()
    code_input = CodeInputSchema(code=code_str)
    
    logger.info(f"UI: Sending code to workflow. Code (first 100 chars): {code_str[:100].replace('\n', ' ')}...")
    
    try:
        result: WorkflowCompleteOutput = await workflow.run(code_input=code_input)
        final_outputs = result.final_aggregated_output
    except Exception as e:
        logger.error(f"UI: Error during workflow execution: {e}", exc_info=True)
        return {"error": f"Analysis failed: {str(e)}"}

    logger.info("UI: Workflow analysis complete. Serializing outputs...")
    final_results_dict = pydantic_to_dict(final_outputs)

    if final_results_dict is None:
        final_results_dict = {"info": "No combined output from workflow."}
    
    return final_results_dict

async def run_analysis_and_update_ui(code_str):
    """
    A generator function that updates the UI to show a waiting message,
    runs the analysis, and then displays the result.
    """
    # Define the animated loader HTML
    animated_loader_html = """
<div style="display: flex; justify-content: center; align-items: center; flex-direction: column; height: 100%; padding: 20px;">
    <style>
        .loader {
            border: 8px solid #f0f0f0; /* Light grey */
            border-top: 8px solid #3498db; /* Blue */
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1.5s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
    <div class="loader"></div>
    <h3 style="margin-top: 20px; color: #4a4a4a;">Hold on tight, the analysis will take a few moments...</h3>
</div>
"""
    # 1. Show waiting message, hide previous results
    yield {
        waiting_message: gr.Markdown(animated_loader_html, visible=True),
        output_viewer: gr.update(visible=False),
    }

    # 2. Run the actual analysis
    results_dict = await analyze_code_logic(code_str)

    # 3. Hide waiting message, show new results
    yield {
        waiting_message: gr.update(visible=False),
        output_viewer: gr.update(value=results_dict, visible=True),
    }

# --- UI Definition with gr.Blocks ---
with gr.Blocks(theme=gr.themes.Soft()) as iface:
    gr.Markdown("# Agentic Code Analyzer")
    gr.Markdown(
        "Enter Python code to be analyzed by a multi-agent system. "
        "The system will perform a comprehensive analysis of your Python code, covering documentation, security, and other aspects, providing combined insights."
    )

    with gr.Row():
        code_input = gr.Textbox(
            lines=20, 
            label="Python Code to Analyze", 
            placeholder="Paste your Python code here...",
            elem_id="code_input_textbox"
        )

    analyze_button = gr.Button("Analyze Code")
    
    # Waiting message component, initially hidden
    waiting_message = gr.Markdown(visible=False)
    
    # Output viewer, initially hidden until first analysis
    output_viewer = CodeAnalysisViewer(label="Overall Code Analysis", visible=False)

    # Connect the button to the UI update function
    analyze_button.click(
        fn=run_analysis_and_update_ui,
        inputs=[code_input],
        outputs=[waiting_message, output_viewer]
    )

    gr.Examples(
        examples=[
            [
                "import os\n\ndef my_function_without_docstring():\n    print(\"Hello, world!\")\n    password = os.getenv(\"MY_PASSWORD\")\n    return password\n\ndef another_function_with_docstring():\n    \"\"\"This is a good docstring.\"\"\"\n    pass"
            ]
        ],
        inputs=[code_input]
    )

if __name__ == "__main__":
    # Temporarily disabled for HF Space.
    #setup_observability()
    logger.info("UI: Launching Gradio interface...")
    get_workflow()
    # Use queue() to handle multiple users and prevent timeouts on the UI side
    iface.queue().launch(server_name="0.0.0.0")

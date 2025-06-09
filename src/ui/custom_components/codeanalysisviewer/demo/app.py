
import gradio as gr
from gradio_codeanalysisviewer import CodeAnalysisViewer


# Prepare an example dictionary matching the OutputSchema structure
example_data = {
    "code": "def greet(name):\n    print(f\"Hello, {name}!\")\n\ngreet(\"User\")",
    "issue": "Security Risk: Use of f-string in print might be risky if 'name' is user-controlled and not sanitized.",
    "reason": "Formatted string literals (f-strings) can be vulnerable to injection if they include unsanitized user input, though in this specific 'print' case, the direct risk is low unless the output is piped elsewhere or has special terminal interpretations.",
    "fixed_code": "def greet(name):\n    # Sanitize name if it comes from an external source, e.g., name = escape(name)\n    print(f\"Hello, {name}!\")\n\ngreet(\"User\")",
    "feedback": "#### Security Feedback:\n* **Issue**: Potential for injection with f-string.\n* **Severity**: Low (in this context).\n* **Recommendation**: Always sanitize external inputs used in f-strings, especially if they are logged or displayed in sensitive contexts. For simple printing, the risk is minimal.\n\n#### Documentation Feedback:\n* The function `greet` is missing a docstring.\n* Consider adding type hints."
}

# Use the example_value from the component itself for the examples list
# This ensures we're using the structure defined within the component's backend
component_example = CodeAnalysisViewer().example_value()

demo = gr.Interface(
    lambda data_dict: data_dict,  # The function now expects and returns a dictionary
    CodeAnalysisViewer(label="Input Analysis (Interactive - if it were input)"), # This would be for input, not our primary use case
    CodeAnalysisViewer(label="Code Analysis Output"), # This is how we'll use it as an output display
    examples=[[component_example], [example_data]] # Provide examples
)


if __name__ == "__main__":
    demo.launch()


import gradio as gr
from app import demo as app
import os

_docs = {'CodeAnalysisViewer': {'description': 'A custom Gradio component to display code analysis results in a structured format.\nIt expects a dictionary matching the OutputSchema structure as its value.', 'members': {'__init__': {'value': {'type': 'dict | Callable | None', 'default': 'None', 'description': 'default text to provide in textbox. If a function is provided, the function will be called each time the app loads to set the initial value of this component.'}, 'placeholder': {'type': 'str | None', 'default': 'None', 'description': 'placeholder hint to provide behind textbox.'}, 'label': {'type': 'str | I18nData | None', 'default': 'None', 'description': 'the label for this component, displayed above the component if `show_label` is `True` and is also used as the header if there are a table of examples for this component. If None and used in a `gr.Interface`, the label will be the name of the parameter this component corresponds to.'}, 'every': {'type': 'Timer | float | None', 'default': 'None', 'description': 'Continously calls `value` to recalculate it if `value` is a function (has no effect otherwise). Can provide a Timer whose tick resets `value`, or a float that provides the regular interval for the reset Timer.'}, 'inputs': {'type': 'Component | Sequence[Component] | set[Component] | None', 'default': 'None', 'description': 'Components that are used as inputs to calculate `value` if `value` is a function (has no effect otherwise). `value` is recalculated any time the inputs change.'}, 'show_label': {'type': 'bool | None', 'default': 'None', 'description': 'if True, will display label.'}, 'scale': {'type': 'int | None', 'default': 'None', 'description': 'relative size compared to adjacent Components. For example if Components A and B are in a Row, and A has scale=2, and B has scale=1, A will be twice as wide as B. Should be an integer. scale applies in Rows, and to top-level Components in Blocks where fill_height=True.'}, 'min_width': {'type': 'int', 'default': '160', 'description': 'minimum pixel width, will wrap if not sufficient screen space to satisfy this value. If a certain scale value results in this Component being narrower than min_width, the min_width parameter will be respected first.'}, 'interactive': {'type': 'bool | None', 'default': 'None', 'description': 'if True, will be rendered as an editable textbox; if False, editing will be disabled. If not provided, this is inferred based on whether the component is used as an input or output.'}, 'visible': {'type': 'bool', 'default': 'True', 'description': 'If False, component will be hidden.'}, 'rtl': {'type': 'bool', 'default': 'False', 'description': 'If True and `type` is "text", sets the direction of the text to right-to-left (cursor appears on the left of the text). Default is False, which renders cursor on the right.'}, 'elem_id': {'type': 'str | None', 'default': 'None', 'description': 'An optional string that is assigned as the id of this component in the HTML DOM. Can be used for targeting CSS styles.'}, 'elem_classes': {'type': 'list[str] | str | None', 'default': 'None', 'description': 'An optional list of strings that are assigned as the classes of this component in the HTML DOM. Can be used for targeting CSS styles.'}, 'render': {'type': 'bool', 'default': 'True', 'description': 'If False, component will not render be rendered in the Blocks context. Should be used if the intention is to assign event listeners now but render the component later.'}, 'key': {'type': 'int | str | tuple[int | str, ...] | None', 'default': 'None', 'description': "in a gr.render, Components with the same key across re-renders are treated as the same component, not a new component. Properties set in 'preserved_by_key' are not reset across a re-render."}, 'preserved_by_key': {'type': 'list[str] | str | None', 'default': '"value"', 'description': "A list of parameters from this component's constructor. Inside a gr.render() function, if a component is re-rendered with the same key, these (and only these) parameters will be preserved in the UI (if they have been changed by the user or an event listener) instead of re-rendered based on the values provided during constructor."}}, 'postprocess': {'value': {'type': 'dict | None', 'description': 'Expects a dictionary (OutputSchema) from the backend function.'}}, 'preprocess': {'return': {'type': 'dict | None', 'description': 'The payload to be used in the backend function.'}, 'value': None}}, 'events': {'change': {'type': None, 'default': None, 'description': 'Triggered when the value of the CodeAnalysisViewer changes either because of user input (e.g. a user types in a textbox) OR because of a function update (e.g. an image receives a value from the output of an event trigger). See `.input()` for a listener that is only triggered by user input.'}, 'input': {'type': None, 'default': None, 'description': 'This listener is triggered when the user changes the value of the CodeAnalysisViewer.'}, 'submit': {'type': None, 'default': None, 'description': 'This listener is triggered when the user presses the Enter key while the CodeAnalysisViewer is focused.'}}}, '__meta__': {'additional_interfaces': {}, 'user_fn_refs': {'CodeAnalysisViewer': []}}}

abs_path = os.path.join(os.path.dirname(__file__), "css.css")

with gr.Blocks(
    css=abs_path,
    theme=gr.themes.Default(
        font_mono=[
            gr.themes.GoogleFont("Inconsolata"),
            "monospace",
        ],
    ),
) as demo:
    gr.Markdown(
"""
# `gradio_codeanalysisviewer`

<div style="display: flex; gap: 7px;">
<img alt="Static Badge" src="https://img.shields.io/badge/version%20-%200.0.1%20-%20orange">  
</div>

A nicer view to show the Agentic code analyser outputs
""", elem_classes=["md-custom"], header_links=True)
    app.render()
    gr.Markdown(
"""
## Installation

```bash
pip install gradio_codeanalysisviewer
```

## Usage

```python

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

```
""", elem_classes=["md-custom"], header_links=True)


    gr.Markdown("""
## `CodeAnalysisViewer`

### Initialization
""", elem_classes=["md-custom"], header_links=True)

    gr.ParamViewer(value=_docs["CodeAnalysisViewer"]["members"]["__init__"], linkify=[])


    gr.Markdown("### Events")
    gr.ParamViewer(value=_docs["CodeAnalysisViewer"]["events"], linkify=['Event'])




    gr.Markdown("""

### User function

The impact on the users predict function varies depending on whether the component is used as an input or output for an event (or both).

- When used as an Input, the component only impacts the input signature of the user function.
- When used as an output, the component only impacts the return signature of the user function.

The code snippet below is accurate in cases where the component is used as both an input and an output.

- **As input:** Is passed, the payload to be used in the backend function.
- **As output:** Should return, expects a dictionary (OutputSchema) from the backend function.

 ```python
def predict(
    value: dict | None
) -> dict | None:
    return value
```
""", elem_classes=["md-custom", "CodeAnalysisViewer-user-fn"], header_links=True)




    demo.load(None, js=r"""function() {
    const refs = {};
    const user_fn_refs = {
          CodeAnalysisViewer: [], };
    requestAnimationFrame(() => {

        Object.entries(user_fn_refs).forEach(([key, refs]) => {
            if (refs.length > 0) {
                const el = document.querySelector(`.${key}-user-fn`);
                if (!el) return;
                refs.forEach(ref => {
                    el.innerHTML = el.innerHTML.replace(
                        new RegExp("\\b"+ref+"\\b", "g"),
                        `<a href="#h-${ref.toLowerCase()}">${ref}</a>`
                    );
                })
            }
        })

        Object.entries(refs).forEach(([key, refs]) => {
            if (refs.length > 0) {
                const el = document.querySelector(`.${key}`);
                if (!el) return;
                refs.forEach(ref => {
                    el.innerHTML = el.innerHTML.replace(
                        new RegExp("\\b"+ref+"\\b", "g"),
                        `<a href="#h-${ref.toLowerCase()}">${ref}</a>`
                    );
                })
            }
        })
    })
}

""")

demo.launch()

# MCP Deploy - Gradio Interface for Bandit Security Scanner (via Modal MCP)

This directory contains a Gradio application to specifically interface with the Bandit security scanner, hosted on Modal via your MCP server.

## Setup

1.  **Create a virtual environment (recommended):**
    Navigate to the `mcp_deploy` directory.
    ```bash
    cd mcp_deploy
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

2.  **Install dependencies using `uv`:**
    Make sure `uv` is installed. If not, refer to [uv installation guide](https://github.com/astral-sh/uv).
    Ensure your virtual environment is active.
    ```bash
    uv pip install -r requirements.txt
    ```
    Alternatively, if you prefer to manage dependencies directly with `uv` (recommended for this project's overall guidelines):
    ```bash
    # Ensure .venv is activated or tell uv to use it
    # uv venv .venv # (if not already created and activated)
    # source .venv/bin/activate
    uv add gradio httpx python-dotenv # This will update requirements.txt if it exists or create pyproject.toml
    uv sync # This installs based on lock file or pyproject.toml
    ```
    For simplicity with `requirements.txt` already provided, `uv pip install -r requirements.txt` is straightforward for this specific app.

3.  **Set the Modal MCP Endpoint:**
    The application needs to know the URL of your Modal-hosted MCP tools. You can set this as an environment variable `MODAL_MCP_ENDPOINT`.
    Create a `.env` file in this `mcp_deploy` directory by copying `.env.example`:
    ```bash
    cp .env.example .env
    ```
    Then, edit the `.env` file:
    ```
    MODAL_MCP_ENDPOINT="your_actual_modal_mcp_endpoint_url"
    ```
    The application will load this using `python-dotenv`. Alternatively, you can set it directly in your shell environment or modify the `MODAL_MCP_ENDPOINT` variable in `app.py` (not recommended for secrets).

## Running the Application

Once the setup is complete, and your virtual environment is active, run the Gradio app from the `mcp_deploy` directory:
```bash
uv run python app_security.py
```
Or if you are already in the activated venv and `uv` is configured for the project:
```bash
python app_security.py
```

The application will start, and you can access it through the URL provided in your terminal (usually `http://127.0.0.1:7860`).

## Usage

1.  The application is hardcoded to use the `bandit` tool.
2.  Provide the parameters for Bandit in JSON string format. This JSON **must** include a `"code"` field containing the Python code string you want Bandit to analyze (e.g., `{"code": "import os\nprint(os.listdir('.'))"}`).
3.  Click "Submit".
4.  The analysis output from Bandit (via the MCP server) will be displayed in JSON format.

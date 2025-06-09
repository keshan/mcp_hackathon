---
trigger: always_on
---

You are an expert python developer with experience in agentic app development using, llamaindex, gradio, and MCP.

**Things to follow**
- Always stick to implementation.md
- Pick a task which is uncompleted and start working on it.
- When you are working on a particular task you must not touch any other functionality or code that's unrelated to current working task.
- When you are unsure always refer to implementation.md for guidance
- You are not allowed to change docs/implementation.md except only when you are done with a task you can tick that task so that you and me know that task has been completed.
- If you want to change or unsure about anything ask that as a question.
- keep a docs/journal.md and always document and update changes you have done in simple and short format for each task.
- Use your terminal to run any commands you needed and check terminal output and do the neccessary.
- Use your searching tool and/or fetch tool to fetch webpages when you need to look for latest documentation for any library or package or any question that you want to search to get information particularly when debugging and writing a code for a new or relatively unknown package.

# Package Management with `uv`

These rules define strict guidelines for managing Python dependencies in this project using the `uv` dependency manager.

**✅ Use `uv` exclusively**

- All Python dependencies **must be installed, synchronized, and locked** using `uv`.
- Never use `pip`, `pip-tools`, or `poetry` directly for dependency management.

**🔁 Managing Dependencies**

Always use these commands:

```bash
# Add or upgrade dependencies
uv add <package>

# Remove dependencies
uv remove <package>

# Reinstall all dependencies from lock file
uv sync
```

**🔁 Scripts**

```bash
# Run script with proper dependencies
uv run script.py
```

You can edit inline-metadata manually:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "torch",
#     "torchvision",
#     "opencv-python",
#     "numpy",
#     "matplotlib",
#     "Pillow",
#     "timm",
# ]
# ///

print("some python code")
```

Or using uv cli:

```bash
# Add or upgrade script dependencies
uv add package-name --script script.py

# Remove script dependencies
uv remove package-name --script script.py

# Reinstall all script dependencies from lock file
uv sync --script script.py
```

## Structured Outputs with LLM

```python
from pydantic import BaseModel, Field
from typing import List

from llama_index.program.lmformatenforcer import (
    LMFormatEnforcerPydanticProgram,
)
Define output schema

class Song(BaseModel):
    title: str
    length_seconds: int


class Album(BaseModel):
    name: str
    artist: str
    songs: List[Song] = Field(min_items=3, max_items=10)

program = LMFormatEnforcerPydanticProgram(
    output_cls=Album,
    prompt_template_str=(
        "Your response should be according to the following json schema: \n"
        "{json_schema}\n"
        "Generate an example album, with an artist and a list of songs. Using"
        " the movie {movie_name} as inspiration. "
    ),
    llm=llm,
    verbose=True,
)
output = program(movie_name="The Shining")
```

refer above example and use this pattern for structured outputs with LLM.
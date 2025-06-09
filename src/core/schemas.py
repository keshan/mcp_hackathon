# src/core/schemas.py
# Pydantic schemas for data validation and structure

from typing import List, Optional
from llama_index.core.tools.types import BaseModel as PydanticBaseModel
from pydantic import Field as PydanticField

class ToolCodeInputSchema(PydanticBaseModel):
    """Schema for tools that take a single code string as input."""
    code: str = PydanticField(..., description="The Python code snippet to analyze.")

class CodeInputSchema(PydanticBaseModel):
    """Schema for tools that take a single code string as input."""
    code: str = PydanticField(..., description="The Python code snippet to analyze.")

class OutputSchema(PydanticBaseModel):
    """Represents an analyzed line of code with feedback."""
    code: str = PydanticField(..., description="The original code content.")
    issue: str = PydanticField(..., description="Specific issue identified in the code.")
    reason: str = PydanticField(..., description="Reason for the issue.")
    fixed_code: Optional[str] = PydanticField(None, description="The suggested fixed code, if any.")
    feedback: str = PydanticField(..., description="General feedback about the code. give this feedback text in markdown format.")

class OrchestratorDecision(PydanticBaseModel):
    """Represents the decision made by the orchestrator."""
    analysis_depth: str = PydanticField(..., description="The depth of analysis to perform.")
    invoke_doc_agent: bool = PydanticField(..., description="Whether to invoke the documentation agent.")
    invoke_security_agent: bool = PydanticField(..., description="Whether to invoke the security agent.")
    reasoning: str = PydanticField(..., description="Reasoning for the decision.")
    

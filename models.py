"""
models.py
---------
Pydantic models describing the shape of the API's request and response
bodies. Keeping these separate from main.py makes the API contract easy
to find and easy to change independently of the analysis logic.
"""

from typing import List
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Incoming payload: the raw Python source code submitted by the user."""
    code: str = Field(..., description="Python source code to analyze")


class AnalyzeResponse(BaseModel):
    """
    Outgoing payload: the analysis result.

    Field names intentionally use camelCase to match the JSON contract
    specified for the frontend (timeComplexity, spaceComplexity, etc.)
    """
    timeComplexity: str
    spaceComplexity: str
    detectedLines: List[int]
    loopDepth: int
    recursionDetected: bool

    # Small bonus (not required by the spec, but cheap and useful):
    # a short human-readable explanation of how the result was derived.
    explanation: List[str] = Field(default_factory=list)



from typing import List
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    code: str = Field(..., description="Python source code to analyze")


class AnalyzeResponse(BaseModel):
    
    timeComplexity: str
    spaceComplexity: str
    detectedLines: List[int]
    loopDepth: int
    recursionDetected: bool

   
    explanation: List[str] = Field(default_factory=list)

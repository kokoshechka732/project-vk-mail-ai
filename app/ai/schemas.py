from pydantic import BaseModel, Field
from typing import Literal, Optional


Importance = Literal["low", "medium", "high"]


class DeepSeekEmailClassification(BaseModel):
    importance: Importance = Field(..., description="low/medium/high")
    category: str = Field(..., description="short category label")
    summary: str = Field(..., description="1-3 sentences, short")
    suggested_folder: str = Field(..., description="one of allowed folders")
    confidence: float = Field(..., ge=0.0, le=1.0)
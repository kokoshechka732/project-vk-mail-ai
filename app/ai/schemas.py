from pydantic import BaseModel, Field
from typing import Literal, Optional, List

Importance = Literal["low", "medium", "high"]


class AIEmailClassification(BaseModel):
    category: str = Field(
        ...,
        description="academic|work|events|finance|services|spam|personal|other OR custom folder name",
    )
    importance: Importance
    summary: str  # 1 sentence <=150 chars (мы дополнительно обрежем)
    actions: List[str] = Field(default_factory=list)
    deadline: Optional[str] = None  # YYYY-MM-DD or null
    suggested_folder: str
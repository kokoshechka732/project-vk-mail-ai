from pydantic import BaseModel, Field
from typing import Literal, Optional, List

Importance = Literal["low", "medium", "high"]

class AIEmailClassification(BaseModel):
    category: str = Field(
        ...,
        description="academic|work|events|finance|services|spam|personal|other OR custom folder name"
    )
    importance: Importance
    summary: str  # 1 sentence <=150 chars
    actions: List[str] = Field(default_factory=list)
    deadline: Optional[str] = None  # YYYY-MM-DD HH:MM or null (формат строго: 2025-06-15 12:30)
    suggested_folder: Optional[str] = None  # Теперь может быть None, если AI не уверен

# ✅ ДОБАВЬ ЭТОТ КЛАСС
class FolderIntent(BaseModel):
    name: str = Field(..., description="Название папки (2-10 слов)")
    description: str = Field(..., description="Развернутое описание целей папки")
    keywords: List[str] = Field(default_factory=list, description="Ключевые слова для сортировки")
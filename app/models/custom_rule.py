from sqlalchemy import DateTime, ForeignKey, Text, Boolean, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class CustomRule(Base):
    __tablename__ = "custom_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    folder_id: Mapped[int] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), index=True, nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
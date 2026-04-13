from sqlalchemy import DateTime, ForeignKey, String, Text, Boolean, Integer, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    mail_account_id: Mapped[int] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # legacy/primary folder (можно оставить для удобства)
    folder_id: Mapped[int | None] = mapped_column(
        ForeignKey("folders.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    imap_uid: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    from_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    received_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_importance: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ai_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_classified_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
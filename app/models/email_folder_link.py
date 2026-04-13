from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmailFolderLink(Base):
    __tablename__ = "email_folder_links"
    __table_args__ = (
        UniqueConstraint("email_id", "folder_id", name="uq_email_folder_link"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), index=True, nullable=False)
    folder_id: Mapped[int] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
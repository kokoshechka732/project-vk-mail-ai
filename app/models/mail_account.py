from sqlalchemy import DateTime, ForeignKey, String, Integer, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MailAccount(Base):
    __tablename__ = "mail_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # "gmail"
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)

    # MVP УПРОЩЕНИЕ: храним пароль приложения в открытом виде (ПОТОМ ЗАМЕНИМ НА ШИФРОВАНИЕ)
    app_password: Mapped[str] = mapped_column(String(255), nullable=False)

    imap_host: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_port: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
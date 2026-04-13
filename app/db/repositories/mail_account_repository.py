from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mail_account import MailAccount
from app.models.user import User


class MailAccountRepository:
    async def get_active_gmail(self, session: AsyncSession, user_id: int) -> MailAccount | None:
        res = await session.execute(
            select(MailAccount).where(
                MailAccount.user_id == user_id,
                MailAccount.provider == "gmail",
                MailAccount.is_active == True,  # noqa: E712
            )
        )
        return res.scalar_one_or_none()

    async def list_active_gmail_with_vk(self, session: AsyncSession) -> list[tuple[MailAccount, int]]:
        """
        Возвращает список (mail_account, vk_user_id) для фонового обхода.
        """
        res = await session.execute(
            select(MailAccount, User.vk_user_id)
            .join(User, User.id == MailAccount.user_id)
            .where(
                MailAccount.provider == "gmail",
                MailAccount.is_active == True,  # noqa: E712
            )
        )
        return list(res.all())

    async def upsert_gmail(
        self,
        session: AsyncSession,
        user_id: int,
        email_address: str,
        app_password: str,
    ) -> MailAccount:
        existing = await self.get_active_gmail(session, user_id)
        if existing:
            existing.email_address = email_address
            existing.app_password = app_password
            existing.imap_host = "imap.gmail.com"
            existing.imap_port = 993
            return existing

        obj = MailAccount(
            user_id=user_id,
            provider="gmail",
            email_address=email_address,
            app_password=app_password,
            imap_host="imap.gmail.com",
            imap_port=993,
            is_active=True,
        )
        session.add(obj)
        await session.flush()
        return obj
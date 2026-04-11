from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.mail_account import MailAccount


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

    async def upsert_gmail(self, session: AsyncSession, user_id: int, email_address: str, app_password: str) -> MailAccount:
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
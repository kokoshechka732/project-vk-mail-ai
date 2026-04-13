from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email import Email


class EmailRepository:
    async def exists_by_uid(self, session: AsyncSession, mail_account_id: int, imap_uid: int) -> bool:
        res = await session.execute(
            select(Email.id).where(
                Email.mail_account_id == mail_account_id,
                Email.imap_uid == imap_uid,
            )
        )
        return res.scalar_one_or_none() is not None

    async def save(self, session: AsyncSession, email: Email) -> Email:
        session.add(email)
        await session.flush()
        return email

    async def list_last(self, session: AsyncSession, user_id: int, limit: int = 10) -> list[Email]:
        res = await session.execute(
            select(Email).where(Email.user_id == user_id).order_by(Email.id.desc()).limit(limit)
        )
        return list(res.scalars().all())

    async def max_uid(self, session: AsyncSession, mail_account_id: int) -> int:
        res = await session.execute(
            select(func.max(Email.imap_uid)).where(Email.mail_account_id == mail_account_id)
        )
        v = res.scalar_one_or_none()
        return int(v or 0)

    async def list_last_without_summary(self, session: AsyncSession, user_id: int, limit: int = 50) -> list[Email]:
        res = await session.execute(
            select(Email)
            .where(Email.user_id == user_id, Email.ai_summary.is_(None))
            .order_by(Email.id.desc())
            .limit(limit)
        )
        return list(res.scalars().all())
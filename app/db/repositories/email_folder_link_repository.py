from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_folder_link import EmailFolderLink
from app.models.email import Email


class EmailFolderLinkRepository:
    async def add_link_if_missing(self, session: AsyncSession, email_id: int, folder_id: int) -> bool:
        res = await session.execute(
            select(EmailFolderLink.id).where(
                EmailFolderLink.email_id == email_id,
                EmailFolderLink.folder_id == folder_id,
            )
        )
        if res.scalar_one_or_none() is not None:
            return False
        session.add(EmailFolderLink(email_id=email_id, folder_id=folder_id))
        await session.flush()
        return True

    async def count_in_folder(self, session: AsyncSession, user_id: int, folder_id: int) -> int:
        res = await session.execute(
            select(func.count(EmailFolderLink.email_id))
            .select_from(EmailFolderLink)
            .join(Email, Email.id == EmailFolderLink.email_id)
            .where(Email.user_id == user_id, EmailFolderLink.folder_id == folder_id)
        )
        return int(res.scalar_one() or 0)

    async def list_last_in_folder(self, session: AsyncSession, user_id: int, folder_id: int, limit: int = 5) -> list[Email]:
        res = await session.execute(
            select(Email)
            .join(EmailFolderLink, EmailFolderLink.email_id == Email.id)
            .where(Email.user_id == user_id, EmailFolderLink.folder_id == folder_id)
            .order_by(Email.id.desc())
            .limit(limit)
        )
        return list(res.scalars().all())

    async def backfill_from_email_folder_id(self, session: AsyncSession, user_id: int, limit: int = 2000) -> int:
        """
        Мягкая миграция старых данных:
        для писем, у которых Email.folder_id заполнен, создаём link, если его нет.
        """
        res = await session.execute(
            select(Email)
            .where(Email.user_id == user_id, Email.folder_id.is_not(None))
            .order_by(Email.id.desc())
            .limit(limit)
        )
        emails = list(res.scalars().all())
        added = 0
        for e in emails:
            if e.folder_id is None:
                continue
            ok = await self.add_link_if_missing(session, e.id, e.folder_id)
            if ok:
                added += 1
        return added
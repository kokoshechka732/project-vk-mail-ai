from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.init_db import ensure_schema
from app.db.session import AsyncSessionMaker
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.folder_repository import FolderRepository
from app.db.repositories.email_folder_link_repository import EmailFolderLinkRepository
from app.models.email import Email
from app.models.email_folder_link import EmailFolderLink

class FolderViewService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.folder_repo = FolderRepository()
        self.link_repo = EmailFolderLinkRepository()

    async def get_folder_email_ids(self, session: AsyncSession, user_id: int, folder_name: str) -> list[int]:
        folders = await self.folder_repo.ensure_system_folders(session, user_id)
        folder = folders.get(folder_name) or await self.folder_repo.get_by_name(session, user_id, folder_name)
        if not folder: return []
        res = await session.execute(
            select(EmailFolderLink.email_id)
            .where(EmailFolderLink.folder_id == folder.id)
            .order_by(EmailFolderLink.id.desc())
        )
        return [row[0] for row in res.all()]

    async def get_email_by_index(self, session: AsyncSession, user_id: int, email_ids: list[int], index: int) -> Email | None:
        if index < 0 or index >= len(email_ids): return None
        eid = email_ids[index]
        res = await session.execute(select(Email).where(Email.id == eid, Email.user_id == user_id))
        return res.scalar_one_or_none()
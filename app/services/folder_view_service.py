from sqlalchemy import select, func

from app.db.init_db import ensure_schema
from app.db.session import AsyncSessionMaker
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.folder_repository import FolderRepository
from app.db.repositories.email_folder_link_repository import EmailFolderLinkRepository


class FolderViewService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.folder_repo = FolderRepository()
        self.link_repo = EmailFolderLinkRepository()

    async def last_emails_in_folder(self, vk_user_id: int, folder_name: str, limit: int = 5) -> str:
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return "Сначала напиши «Начать»."

                folders = await self.folder_repo.ensure_system_folders(session, user.id)
                folder = folders.get(folder_name)
                if not folder:
                    # может быть кастомная
                    folder = await self.folder_repo.get_by_name(session, user.id, folder_name)
                if not folder:
                    return "Папка не найдена."

                # мягкая миграция legacy folder_id -> links
                await self.link_repo.backfill_from_email_folder_id(session, user.id, limit=2000)

                total = await self.link_repo.count_in_folder(session, user.id, folder.id)
                if total == 0:
                    return f"Папка «{folder_name}»: писем пока нет."

                emails = await self.link_repo.list_last_in_folder(session, user.id, folder.id, limit=limit)

                lines = [
                    f"Папка: {folder_name} | всего писем: {total} | показываю последние {min(limit, total)}:"
                ]
                for e in emails:
                    subj = e.subject or "(без темы)"
                    frm = e.from_email or "(неизвестно)"
                    lines.append(f"- {frm} | {subj}")

                return "\n".join(lines)
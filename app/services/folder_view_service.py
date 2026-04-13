from sqlalchemy import select, func

from app.db.init_db import ensure_schema
from app.db.session import AsyncSessionMaker
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.folder_repository import FolderRepository
from app.models.email import Email


class FolderViewService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.folder_repo = FolderRepository()

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
                    return "Папка не найдена."

                total_res = await session.execute(
                    select(func.count(Email.id)).where(
                        Email.user_id == user.id,
                        Email.folder_id == folder.id,
                    )
                )
                total = int(total_res.scalar_one())

                res = await session.execute(
                    select(Email)
                    .where(Email.user_id == user.id, Email.folder_id == folder.id)
                    .order_by(Email.id.desc())
                    .limit(limit)
                )
                emails = list(res.scalars().all())

                if total == 0:
                    return f"Папка «{folder_name}»: писем пока нет."

                lines = [f"Папка: {folder_name} | всего писем: {total} | показываю последние {min(limit, total)}:"]
                for e in emails:
                    subj = e.subject or "(без темы)"
                    frm = e.from_email or "(неизвестно)"
                    lines.append(f"- {frm} | {subj}")
                return "\n".join(lines)
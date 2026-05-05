from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.folder import Folder

# ✅ НОВЫЙ НАБОР ПАПОК ПО MVP
SYSTEM_FOLDERS = ["Важное", "Учёба", "Работа"]
MAX_CUSTOM_FOLDERS = 3

class FolderRepository:
    async def list_by_user(self, session: AsyncSession, user_id: int) -> list[Folder]:
        res = await session.execute(
            select(Folder).where(Folder.user_id == user_id).order_by(Folder.id.asc())
        )
        return list(res.scalars().all())

    async def get_by_name(self, session: AsyncSession, user_id: int, name: str) -> Folder | None:
        res = await session.execute(
            select(Folder).where(Folder.user_id == user_id, Folder.name == name)
        )
        return res.scalar_one_or_none()

    async def create(self, session: AsyncSession, user_id: int, name: str, is_system: bool = True) -> Folder:
        obj = Folder(user_id=user_id, name=name, is_system=is_system)
        session.add(obj)
        await session.flush()
        return obj
    # Вставьте этот метод внутрь класса FolderRepository
    async def update_description(self, session: AsyncSession, folder_id: int, description: str | None) -> None:
        """Обновляет описание папки"""
        folder = await session.get(Folder, folder_id)
        if folder:
            folder.description = description
            await session.flush()
    async def ensure_system_folders(self, session: AsyncSession, user_id: int) -> dict[str, Folder]:
        # 🔽 Чистим сироты один раз за сессию
        await self.clean_orphaned_links(session)
        
        existing = await self.list_by_user(session, user_id)
        by_name = {f.name: f for f in existing}
        for name in SYSTEM_FOLDERS:
            if name not in by_name:
                by_name[name] = await self.create(session, user_id, name, is_system=True)
        return by_name

    async def get_custom_folders(self, session: AsyncSession, user_id: int) -> list[Folder]:
        res = await session.execute(
            select(Folder).where(Folder.user_id == user_id, Folder.is_system == False)
        )
        return list(res.scalars().all())

    async def count_custom_folders(self, session: AsyncSession, user_id: int) -> int:
        res = await session.execute(
            select(func.count(Folder.id)).where(Folder.user_id == user_id, Folder.is_system == False)
        )
        return int(res.scalar_one() or 0)

    async def delete_custom_folder(self, session: AsyncSession, user_id: int, folder_id: int) -> bool:
        from app.models.email_folder_link import EmailFolderLink
        from app.models.custom_rule import CustomRule
        from sqlalchemy import delete
        
        folder = await session.get(Folder, folder_id)
        if not folder or folder.is_system:
            return False
            
        # 1. Удаляем связки email-folder
        await session.execute(delete(EmailFolderLink).where(EmailFolderLink.folder_id == folder_id))
        # 2. Удаляем кастомные правила папки
        await session.execute(delete(CustomRule).where(CustomRule.folder_id == folder_id))
        # 3. Удаляем саму папку
        await session.delete(folder)
        await session.flush()
        return True
    async def clean_orphaned_links(self, session: AsyncSession) -> int:
        """Удаляет email_folder_links и обнуляет emails.folder_id для несуществующих папок"""
        from app.models.email_folder_link import EmailFolderLink
        from app.models.email import Email
        from sqlalchemy import delete, update
        
        # Сироты в связках
        orphans_stmt = (
            delete(EmailFolderLink)
            .where(EmailFolderLink.folder_id.not_in(
                select(Folder.id)
            ))
        )
        res = await session.execute(orphans_stmt)
        
        # Сироты в emails.folder_id
        await session.execute(
            update(Email)
            .where(Email.folder_id.not_in(select(Folder.id)))
            .values(folder_id=None)
        )
        await session.flush()
        return res.rowcount
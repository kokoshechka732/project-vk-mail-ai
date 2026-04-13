from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder

SYSTEM_FOLDERS = ["Важное", "Учёба", "Стажировки", "Рассылки", "Несортированное", "Спам"]


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

    async def ensure_system_folders(self, session: AsyncSession, user_id: int) -> dict[str, Folder]:
        existing = await self.list_by_user(session, user_id)
        by_name = {f.name: f for f in existing}
        for name in SYSTEM_FOLDERS:
            if name not in by_name:
                by_name[name] = await self.create(session, user_id, name, is_system=True)
        return by_name

    async def get_custom_folder(self, session: AsyncSession, user_id: int) -> Folder | None:
        res = await session.execute(
            select(Folder)
            .where(Folder.user_id == user_id, Folder.is_system == False)  # noqa: E712
            .order_by(Folder.id.asc())
        )
        return res.scalars().first()

    async def create_custom_folder(self, session: AsyncSession, user_id: int, name: str) -> tuple[bool, str, Folder | None]:
        """
        Создаёт единственную кастомную папку. Если уже есть — не создаёт.
        """
        existing = await self.get_custom_folder(session, user_id)
        if existing:
            return False, "CUSTOM_EXISTS", existing
        obj = await self.create(session, user_id, name=name, is_system=False)
        return True, "OK", obj
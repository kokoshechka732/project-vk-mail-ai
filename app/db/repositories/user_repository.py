from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.user import User

class UserRepository:
    async def get_by_vk_id(self, session: AsyncSession, vk_user_id: int) -> User | None:
        res = await session.execute(select(User).where(User.vk_user_id == vk_user_id))
        return res.scalar_one_or_none()

    async def create(self, session: AsyncSession, vk_user_id: int) -> User:
        user = User(vk_user_id=vk_user_id)
        session.add(user)
        await session.flush()
        return user

    async def get_or_create(self, session: AsyncSession, vk_user_id: int) -> User:
        user = await self.get_by_vk_id(session, vk_user_id)
        if user:
            return user

        try:
            return await self.create(session, vk_user_id)
        except IntegrityError:
            # если два апдейта одновременно
            await session.rollback()
            user = await self.get_by_vk_id(session, vk_user_id)
            if user:
                return user
            raise
from app.db.session import AsyncSessionMaker
from app.db.repositories.user_repository import UserRepository


class UserService:
    def __init__(self) -> None:
        self.repo = UserRepository()

    async def ensure_user(self, vk_user_id: int):
        async with AsyncSessionMaker() as session:
            async with session.begin():
                return await self.repo.get_or_create(session, vk_user_id)
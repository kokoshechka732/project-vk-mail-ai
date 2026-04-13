from app.db.init_db import ensure_schema
from app.db.session import AsyncSessionMaker
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.mail_account_repository import MailAccountRepository


class AccountInfoService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.mail_repo = MailAccountRepository()

    async def get_gmail_info(self, vk_user_id: int) -> str:
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return "Сначала напиши «Начать»."
                acc = await self.mail_repo.get_active_gmail(session, user.id)
                if not acc:
                    return "Gmail не подключен. Нажми «Подключить Gmail»."
                return f"Gmail подключен: {acc.email_address}"
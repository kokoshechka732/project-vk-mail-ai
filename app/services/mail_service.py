from app.db.init_db import ensure_schema
from app.db.session import AsyncSessionMaker
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.mail_account_repository import MailAccountRepository
from app.mail.imap_client import check_gmail_imap


class MailService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.mail_repo = MailAccountRepository()

    async def connect_gmail(self, vk_user_id: int, email_address: str, app_password: str) -> tuple[bool, str]:
        await ensure_schema()
        email_address = email_address.strip()
        app_password = app_password.replace(" ", "").strip()  # Gmail app password часто с пробелами

        ok, code = await check_gmail_imap(email_address, app_password)
        if not ok:
            return False, code

        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_or_create(session, vk_user_id)
                await self.mail_repo.upsert_gmail(session, user.id, email_address, app_password)

        return True, "OK"
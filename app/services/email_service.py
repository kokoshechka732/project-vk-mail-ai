from app.db.init_db import ensure_schema
from app.db.session import AsyncSessionMaker
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.mail_account_repository import MailAccountRepository
from app.db.repositories.email_repository import EmailRepository
from app.models.email import Email

from app.mail.imap_client import fetch_last_n_gmail
from app.mail.parser import parse_email


class EmailService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.mail_repo = MailAccountRepository()
        self.email_repo = EmailRepository()

    async def fetch_and_store_last(self, vk_user_id: int, n: int = 10) -> tuple[int, str]:
        await ensure_schema()

        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return 0, "NO_USER"

                acc = await self.mail_repo.get_active_gmail(session, user.id)
                if not acc:
                    return 0, "NO_MAIL"
                try:
                    raw_list = await fetch_last_n_gmail(acc.email_address, acc.app_password, n=n)
                except TimeoutError:
                    return 0, "IMAP_TIMEOUT"
                except Exception:
                    return 0, "IMAP_ERROR"
                saved = 0
                for uid, raw_bytes in raw_list:
                    if await self.email_repo.exists_by_uid(session, acc.id, uid):
                        continue

                    parsed = parse_email(raw_bytes)
                    email = Email(
                        user_id=user.id,
                        mail_account_id=acc.id,
                        imap_uid=uid,
                        message_id=parsed["message_id"],
                        subject=parsed["subject"],
                        from_email=parsed["from_email"],
                        received_at=parsed["received_at"],
                        body_text=parsed["body_text"],
                        has_attachments=parsed["has_attachments"],
                    )
                    await self.email_repo.save(session, email)
                    saved += 1

                return saved, "OK"

    async def build_digest_text(self, vk_user_id: int, limit: int = 10) -> tuple[bool, str]:
        await ensure_schema()

        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return False, "Сначала напиши «Начать»."

                emails = await self.email_repo.list_last(session, user.id, limit=limit)
                if not emails:
                    return True, "Писем пока нет. Нажми «Проверить почту»."

                lines = ["Дайджест (последние письма):"]
                for e in emails:
                    dt = e.received_at.strftime("%Y-%m-%d %H:%M") if e.received_at else "без даты"
                    subj = e.subject or "(без темы)"
                    frm = e.from_email or "(неизвестно)"
                    lines.append(f"- {dt} | {frm} | {subj}")

                return True, "\n".join(lines)
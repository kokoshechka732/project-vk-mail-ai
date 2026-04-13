from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.init_db import ensure_schema
from app.db.session import AsyncSessionMaker
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.mail_account_repository import MailAccountRepository
from app.db.repositories.email_repository import EmailRepository
from app.db.repositories.folder_repository import FolderRepository

from app.models.email import Email

from app.mail.imap_client import fetch_last_n_gmail, fetch_last_n_gmail_all
from app.mail.parser import parse_email

from app.ai.client import DeepSeekClient
from app.ai.prompts import ALLOWED_FOLDERS


def _truncate_vk(text: str, limit: int = 3500) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 50] + "\n...\n(обрезано)"


def guess_folder(subject: str | None, from_email: str | None) -> str:
    s = (subject or "").lower()
    f = (from_email or "").lower()

    if any(x in s for x in ["стаж", "intern", "internship", "vacanc", "job", "карьер"]):
        return "Стажировки"
    if any(x in s for x in ["дедлайн", "deadline", "срок", "сдать", "экзамен"]):
        return "Важное"
    if any(x in f for x in ["no-reply", "noreply"]) or any(x in s for x in ["unsubscribe", "подписк", "рассыл"]):
        return "Рассылки"
    if any(x in s for x in ["лекц", "семинар", "пара", "курс", "учеб", "зачет", "зачёт"]):
        return "Учёба"
    return "Несортированное"


class EmailService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.mail_repo = MailAccountRepository()
        self.email_repo = EmailRepository()
        self.folder_repo = FolderRepository()

    async def fetch_and_store_last(self, vk_user_id: int, n: int = 25) -> tuple[int, str]:
        await ensure_schema()

        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return 0, "NO_USER"

                acc = await self.mail_repo.get_active_gmail(session, user.id)
                if not acc:
                    return 0, "NO_MAIL"

                folders = await self.folder_repo.ensure_system_folders(session, user.id)

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

                    folder_name = guess_folder(parsed["subject"], parsed["from_email"])
                    folder_id = folders[folder_name].id

                    email = Email(
                        user_id=user.id,
                        mail_account_id=acc.id,
                        imap_uid=uid,
                        message_id=parsed["message_id"],
                        subject=parsed["subject"],
                        from_email=parsed["from_email"],
                        received_at=parsed["received_at"],
                        body_text=None,
                        has_attachments=False,
                        folder_id=folder_id,
                    )
                    await self.email_repo.save(session, email)
                    saved += 1

                return saved, "OK"

    async def sort_last_emails(self, vk_user_id: int, limit: int = 25) -> tuple[bool, str]:
        await ensure_schema()

        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return False, "Сначала напиши «Начать»."

                folders = await self.folder_repo.ensure_system_folders(session, user.id)

                emails = await self.email_repo.list_last(session, user.id, limit=limit)
                if not emails:
                    return True, "Писем в БД пока нет. Нажми «Проверить почту»."

                cnt = Counter()
                for e in emails:
                    folder_name = guess_folder(e.subject, e.from_email)
                    e.folder_id = folders[folder_name].id
                    cnt[folder_name] += 1

                parts = ["Сортировка выполнена (последние письма):"]
                for name in ["Важное", "Учёба", "Стажировки", "Рассылки", "Несортированное"]:
                    parts.append(f"- {name}: {cnt.get(name, 0)}")
                return True, "\n".join(parts)

    async def ai_classify_last_emails(self, vk_user_id: int, limit: int = 25) -> tuple[bool, str]:
        """
        AI-классификация последних писем:
        - заполняет ai_summary/ai_importance/ai_category/ai_confidence/ai_classified_at
        - обновляет folder_id по suggested_folder
        """
        await ensure_schema()
        client = DeepSeekClient()

        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return False, "Сначала напиши «Начать»."

                folders = await self.folder_repo.ensure_system_folders(session, user.id)
                emails = await self.email_repo.list_last(session, user.id, limit=limit)
                if not emails:
                    return True, "Писем пока нет. Нажми «Проверить почту»."

                cnt = Counter()
                for e in emails:
                    received_str = e.received_at.isoformat() if e.received_at else None

                    try:
                        result = await client.classify_header(
                            subject=e.subject,
                            from_email=e.from_email,
                            received_at=received_str,
                        )
                    except Exception:
                        # fallback: оставляем heuristic
                        folder_name = guess_folder(e.subject, e.from_email)
                        e.folder_id = folders[folder_name].id
                        cnt[folder_name] += 1
                        continue

                    # записываем AI поля
                    e.ai_summary = result.summary[:2000]
                    e.ai_importance = result.importance
                    e.ai_category = result.category[:64]
                    e.ai_confidence = float(result.confidence)
                    e.ai_classified_at = datetime.now(timezone.utc)

                    # suggested folder -> folder_id
                    folder_name = result.suggested_folder if result.suggested_folder in ALLOWED_FOLDERS else "Несортированное"
                    e.folder_id = folders[folder_name].id
                    cnt[folder_name] += 1

                parts = ["AI-классификация выполнена (последние письма):"]
                for name in ["Важное", "Учёба", "Стажировки", "Рассылки", "Несортированное"]:
                    parts.append(f"- {name}: {cnt.get(name, 0)}")
                parts.append("Дайджест теперь может показывать ai_summary.")
                return True, "\n".join(parts)

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

                lines = ["Дайджест (последние письма из БД):"]
                for e in emails:
                    frm = e.from_email or "(неизвестно)"
                    subj = e.subject or "(без темы)"
                    if e.ai_summary:
                        lines.append(f"- {frm} | {subj}\n  {e.ai_summary}")
                    else:
                        lines.append(f"- {frm} | {subj}")

                return True, _truncate_vk("\n".join(lines))

    async def debug_list_inbox_headers(self, vk_user_id: int, n: int = 50) -> tuple[bool, str]:
        await ensure_schema()

        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return False, "Сначала напиши «Начать»."

                acc = await self.mail_repo.get_active_gmail(session, user.id)
                if not acc:
                    return False, "Сначала подключи Gmail."

                try:
                    raw_list = await fetch_last_n_gmail_all(acc.email_address, acc.app_password, n=n)
                except TimeoutError:
                    return False, "IMAP timeout. Попробуй позже."
                except Exception:
                    return False, "IMAP error. Попробуй позже."

        lines = [f"DEBUG INBOX (последние {len(raw_list)}):"]
        for uid, raw in raw_list:
            parsed = parse_email(raw)
            subj = parsed["subject"] or "(без темы)"
            frm = parsed["from_email"] or "(неизвестно)"
            lines.append(f"- {frm} | {subj}")

        return True, _truncate_vk("\n".join(lines))
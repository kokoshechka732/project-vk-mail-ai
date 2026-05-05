from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from vkbottle import API
from app.ai.client import AIClient
from app.core.settings import settings
from app.db.init_db import ensure_schema
from app.db.repositories.custom_rule_repository import CustomRuleRepository
from app.db.repositories.email_folder_link_repository import EmailFolderLinkRepository
from app.db.repositories.email_repository import EmailRepository
from app.db.repositories.folder_repository import FolderRepository
from app.db.repositories.mail_account_repository import MailAccountRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import AsyncSessionMaker
from app.mail.imap_client import fetch_last_n_gmail_preview, fetch_since_uid_gmail_preview
from app.mail.parser import parse_email_preview
from app.models.email import Email
from app.security.crypto import decrypt

logger = logging.getLogger("email")

def _truncate_vk(text: str, limit: int = 3500) -> str:
    return text if len(text) <= limit else text[:limit-50] + "\n... (обрезано)"

def guess_folder_fallback(subject: str | None, from_email: str | None, body: str | None) -> str:
    s = (subject or "").casefold()
    f = (from_email or "").casefold()
    b = (body or "").casefold()
    text = " ".join([s, f, b])
    if any(x in text for x in ["дедлайн", "deadline", "срок", "сдать", "экзамен", "важно", "urgent"]): return "Важное"
    if any(x in s for x in ["стаж", "intern", "vacanc", "job", "карьер", "работ"]): return "Работа"
    if any(x in s for x in ["лекц", "семинар", "пара", "курс", "учеб", "зачет"]): return "Учёба"
    return "Важное"

def _need_important(ai_importance: str | None, deadline: str | None, actions: list[str] | None) -> bool:
    return (ai_importance or "").lower() == "high" or bool(deadline) or bool(actions)

class EmailService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.mail_repo = MailAccountRepository()
        self.email_repo = EmailRepository()
        self.folder_repo = FolderRepository()
        self.rule_repo = CustomRuleRepository()
        self.link_repo = EmailFolderLinkRepository()
        self.ai_client = AIClient()
        self._poll_lock = asyncio.Lock()

    async def sync_after_connect(self, vk_user_id: int, n: int = 15) -> tuple[int, str]:
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user: return 0, "NO_USER"
                acc = await self.mail_repo.get_active_gmail(session, user.id)
                if not acc: return 0, "NO_MAIL"
                await self.folder_repo.ensure_system_folders(session, user.id)
                
                try:
                    raw_list = await fetch_last_n_gmail_preview(acc.email_address, decrypt(acc.app_password), n=n)
                except Exception:
                    logger.exception("IMAP fetch error for vk=%s", vk_user_id)
                    return 0, "IMAP_ERROR"
                
                # ✅ Передаём сессию вниз, чтобы избежать вложенности
                saved_new = await self._store_raw_only_new(session, vk_user_id, raw_list)
                uids = [uid for uid, _, _ in raw_list]
                await self._ai_backfill_for_uids_robust(session, vk_user_id, uids)
                return saved_new, "OK"

    async def sync_new(self, vk_user_id: int) -> tuple[int, str]:
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user: return 0, "NO_USER"
                acc = await self.mail_repo.get_active_gmail(session, user.id)
                if not acc: return 0, "NO_MAIL"
                await self.folder_repo.ensure_system_folders(session, user.id)
                max_uid = await self.email_repo.max_uid(session, acc.id)
                
                try:
                    raw_list = await fetch_since_uid_gmail_preview(acc.email_address, decrypt(acc.app_password), since_uid=max_uid, max_messages=200)
                except Exception:
                    logger.exception("IMAP sync error for vk=%s", vk_user_id)
                    return 0, "IMAP_ERROR"
                
                saved = 0
                if raw_list:
                    saved = await self._store_raw_only_new(session, vk_user_id, raw_list)
                    uids = [uid for uid, _, _ in raw_list]
                    await self._ai_backfill_for_uids_robust(session, vk_user_id, uids)
                else:
                    await self._ai_backfill_for_last(session, vk_user_id, limit=15)
                return saved, "OK"

    async def _store_raw_only_new(self, session, vk_user_id: int, raw_list: list[tuple[int, bytes, bytes]]) -> int:
        user = await self.user_repo.get_by_vk_id(session, vk_user_id)
        if not user: return 0
        acc = await self.mail_repo.get_active_gmail(session, user.id)
        if not acc: return 0

        saved = 0
        skipped = 0
        for uid, raw_bytes, _ in raw_list:
            if await self.email_repo.exists_by_uid(session, acc.id, uid):
                skipped += 1
                continue
            try:
                parsed = parse_email_preview(raw_bytes, b"")
            except Exception as e:
                logger.warning("Parser failed for uid=%s: %s", uid, e)
                continue
            email = Email(
                user_id=user.id, mail_account_id=acc.id, imap_uid=uid,
                message_id=parsed["message_id"], subject=parsed["subject"],
                from_email=parsed["from_email"], received_at=parsed["received_at"],
                body_text=parsed["body_text"], has_attachments=False, folder_id=None
            )
            await self.email_repo.save(session, email)
            saved += 1
        logger.info("Sync: fetched=%d, new=%d, skipped(duplicates)=%d for vk=%d", len(raw_list), saved, skipped, vk_user_id)
        return saved

    async def _ai_backfill_for_last(self, session, vk_user_id: int, limit: int = 15) -> None:
        user = await self.user_repo.get_by_vk_id(session, vk_user_id)
        if not user: return
        emails = await self.email_repo.list_last(session, user.id, limit=limit)
        ids = [e.id for e in emails if not e.ai_summary]
        if ids:
            await self._ai_classify_and_assign(session, vk_user_id, ids)

    async def _ai_backfill_for_uids_robust(self, session, vk_user_id: int, uids: list[int]) -> None:
        if not uids: return
        user = await self.user_repo.get_by_vk_id(session, vk_user_id)
        if not user: return
        acc = await self.mail_repo.get_active_gmail(session, user.id)
        if not acc: return
        
        q1 = select(Email).where(Email.mail_account_id == acc.id, Email.imap_uid.in_(uids))
        emails = list((await session.execute(q1)).scalars().all())
        if not emails:
            q2 = select(Email).where(Email.user_id == user.id, Email.imap_uid.in_(uids))
            emails = list((await session.execute(q2)).scalars().all())
            
        ids = [e.id for e in emails if not e.ai_summary]
        if ids:
            await self._ai_classify_and_assign(session, vk_user_id, ids)

    async def _ai_classify_and_assign(self, session, vk_user_id: int, email_ids: list[int]) -> None:
        user = await self.user_repo.get_by_vk_id(session, vk_user_id)
        if not user: return
        
        folders = await self.folder_repo.ensure_system_folders(session, user.id)
        important_folder = folders.get("Важное")
        custom_folders = await self.folder_repo.get_custom_folders(session, user.id)
        custom_folder_names = [f.name for f in custom_folders]
        
        custom_rules_payload = []
        if custom_folders:
            for cf in custom_folders:
                rules = await self.rule_repo.list_active_by_folder(session, cf.id)
                custom_rules_payload.extend([{"folder": cf.name, "rule_text": r.rule_text} for r in rules])
                
        emails = list((await session.execute(select(Email).where(Email.id.in_(email_ids)))).scalars().all())
        
        for e in emails:
            if e.ai_summary: continue
            received_str = e.received_at.isoformat() if e.received_at else None
            
            try:
                result = await self.ai_client.classify_email(
                    subject=e.subject, from_email=e.from_email, received_at=received_str,
                    body_snippet=e.body_text, user_folders=custom_folder_names, user_rules=custom_rules_payload
                )
                summary = (result.summary or "").strip()[:150]
                e.ai_summary = summary
                e.ai_importance = result.importance
                e.ai_deadline = result.deadline
                e.ai_actions = json.dumps(result.actions or [], ensure_ascii=False)
                e.ai_category = (result.category or "")[:64]
                e.ai_classified_at = datetime.now(timezone.utc)
                primary_name = (result.suggested_folder or "Важное").strip()
                ai_deadline = result.deadline
                ai_actions = result.actions or []
            except Exception as ex:
                logger.warning("AI failed for email %s, using fallback: %s", e.id, ex)
                primary_name = guess_folder_fallback(e.subject, e.from_email, e.body_text)
                e.ai_summary = None
                e.ai_classified_at = datetime.now(timezone.utc)
                ai_deadline = None
                ai_actions = []
                
            primary_folder = folders.get(primary_name)
            if not primary_folder:
                custom = next((f for f in custom_folders if f.name == primary_name), None)
                primary_folder = custom
            if not primary_folder:
                primary_folder = folders.get("Важное")
                primary_name = "Важное"
                
            if primary_folder:
                e.folder_id = primary_folder.id
                await self.link_repo.add_link_if_missing(session, e.id, primary_folder.id)
            if important_folder and _need_important(e.ai_importance, ai_deadline, ai_actions):
                await self.link_repo.add_link_if_missing(session, e.id, important_folder.id)

    async def build_digest_text(self, vk_user_id: int, limit: int = 5) -> tuple[bool, str]:
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user: return False, "Сначала напиши «Начать»."
                emails = await self.email_repo.list_last(session, user.id, limit=limit)
                if not emails: return True, "Писем пока нет."
                
                lines = ["📬 Дайджест (саммари последних писем):"]
                for e in emails:
                    if not e.ai_summary: continue
                    frm = e.from_email or "(unknown)"
                    subj = e.subject or "(no subject)"
                    lines.append(f"- {frm} | {subj}\n{e.ai_summary}")
                return True, _truncate_vk("\n".join(lines))

    async def poll_new_emails_forever(self, api: API, interval_sec: int = 300) -> None:
        await ensure_schema()
        from app.services.reminder_service import reminder_service
        reminder_service.start(api, interval_sec=60)
        logger.info("Background polling started (every %ds)", interval_sec)
        
        while True:
            try:
                async with self._poll_lock:
                    await self._poll_once(api)
            except Exception:
                logger.exception("Poll loop error")
            await asyncio.sleep(interval_sec)

    async def _poll_once(self, api: API) -> None:
        async with AsyncSessionMaker() as session:
            async with session.begin():
                pairs = await self.mail_repo.list_active_gmail_with_vk(session)
                for acc, vk_user_id in pairs:
                    try:
                        if not acc.app_password:
                            logger.warning("Empty password for vk_id=%s", vk_user_id)
                            continue
                            
                        decrypted_pass = decrypt(acc.app_password)
                        max_uid = await self.email_repo.max_uid(session, acc.id)
                        raw_list = await fetch_since_uid_gmail_preview(acc.email_address, decrypted_pass, since_uid=max_uid, max_messages=200)
                        
                        if not raw_list:
                            continue
                            
                        saved = await self._store_raw_only_new(session, vk_user_id, raw_list)
                        uids = [uid for uid, _, _ in raw_list]
                        await self._ai_backfill_for_uids_robust(session, vk_user_id, uids)
                        
                        if saved > 0:
                            await api.messages.send(user_id=vk_user_id, random_id=0, message=f"✅ Новые письма: {saved}. Обработал и разложил по папкам.")
                    except Exception:
                        logger.exception("Polling failed for vk_user_id=%s", vk_user_id)

email_service = EmailService()
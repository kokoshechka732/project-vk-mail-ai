import asyncio
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from vkbottle import API
from app.core.settings import settings
from app.db.session import AsyncSessionMaker
from app.models.user import User
from app.models.email import Email

logger = logging.getLogger("reminder")

class ReminderService:
    def __init__(self) -> None:
        self._running = False
        self.tz = ZoneInfo(settings.USER_TIMEZONE)

    def start(self, api: API, interval_sec: int | None = None) -> None:
        if self._running: return
        self._running = True
        interval = interval_sec or settings.REMINDER_CHECK_INTERVAL_SEC
        asyncio.ensure_future(self._loop(api, interval))

    def stop(self) -> None:
        self._running = False

    async def _loop(self, api: API, interval_sec: int) -> None:
        logger.info(f"Reminder service started (every {interval_sec}s, tz={settings.USER_TIMEZONE})")
        while self._running:
            try:
                await self._check_and_send(api)
            except Exception:
                logger.exception("Reminder check failed")
            await asyncio.sleep(interval_sec)

    async def _check_and_send(self, api: API) -> None:
        now_tz = datetime.now(self.tz)
        async with AsyncSessionMaker() as session:
            # ✅ ТОЛЬКО HIGH + есть дедлайн + не все напоминания отправлены
            stmt = select(Email).where(
                Email.ai_importance == "high",
                Email.ai_deadline.isnot(None),
                Email.folder_id.isnot(None)
            )
            result = await session.execute(stmt)
            emails = result.scalars().all()
            
            for email in emails:
                try:
                    await self._process_email(api, session, email, now_tz)
                except Exception:
                    logger.warning(f"Reminder processing failed for email {email.id}")
            await session.commit()

    async def _process_email(self, api: API, session, email: Email, now: datetime) -> None:
        deadline_dt = self._parse_deadline(email.ai_deadline)
        if not deadline_dt: return

        deadline_tz = deadline_dt.replace(tzinfo=self.tz)
        diff_minutes = (deadline_tz - now).total_seconds() / 60
        sent_offsets = json.loads(email.reminder_sent or "[]")

        for offset in settings.REMINDER_OFFSETS_MINUTES:
            if str(offset) in sent_offsets: continue
            target_diff = offset
            if abs(diff_minutes - target_diff) <= (settings.REMINDER_TOLERANCE_SEC / 60):
                user = await session.get(User, email.user_id)
                if not user: continue

                acts = ""
                try:
                    a = json.loads(email.ai_actions or "[]")
                    acts = f"\n👉 Действия: {', '.join(a)}" if a else ""
                except: pass

                msg = (
                    f"⏰ НАПОМИНАНИЕ ({abs(offset)}мин до дедлайна)\n"
                    f"📌 {email.subject or 'Важное письмо'}\n"
                    f"📅 Дедлайн: {deadline_tz.strftime('%d.%m в %H:%M')}\n"
                    f"💡 {email.ai_summary or 'Нет саммари'}{acts}"
                )
                try:
                    await api.messages.send(user_id=user.vk_user_id, random_id=0, message=msg)
                    logger.info("Sent reminder to vk=%s for email=%s (offset=%s)", user.vk_user_id, email.id, offset)
                    sent_offsets.append(str(offset))
                    email.reminder_sent = json.dumps(sent_offsets)
                    email.last_reminder_at = datetime.now(self.tz)
                except Exception as e:
                    logger.warning(f"Failed to send reminder for email {email.id}: {e}")
                break  # отправляем только одно напоминание за цикл

    def _parse_deadline(self, deadline_str: str | None) -> datetime | None:
        if not deadline_str: return None
        try:
            if " " in deadline_str:
                return datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
            return datetime.strptime(deadline_str, "%Y-%m-%d").replace(hour=9, minute=0)
        except Exception:
            logger.warning(f"Invalid deadline format: {deadline_str}")
            return None

reminder_service = ReminderService()
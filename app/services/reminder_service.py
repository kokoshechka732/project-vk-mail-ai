import asyncio
import logging
from datetime import datetime, timezone, timedelta
import json
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

    def start(self, api: API, interval_sec: int = 3600) -> None:
        if self._running:
            return
        self._running = True
        asyncio.ensure_future(self._loop(api, interval_sec))

    async def _loop(self, api: API, interval_sec: int) -> None:
        logger.info("Reminder service started (every %ds)", interval_sec)
        while self._running:
            try:
                await self._check_and_send(api)
            except Exception:
                logger.exception("Reminder check failed")
            await asyncio.sleep(interval_sec)

    async def _check_and_send(self, api: API) -> None:
        async with AsyncSessionMaker() as session:
            async with session.begin():
                users_res = await session.execute(select(User))
                for user in users_res.scalars().all():
                    await self._process_user(api, session, user.id, user.vk_user_id)

    async def _process_user(self, api: API, session, user_id: int, vk_id: int) -> None:
        cooldown = datetime.now(timezone.utc) - timedelta(hours=settings.REMINDER_COOLDOWN_HOURS)
        stmt = select(Email).where(
            Email.user_id == user_id,
            (Email.ai_importance == "high") | (Email.ai_deadline.isnot(None)),
            (Email.last_reminder_at.is_(None)) | (Email.last_reminder_at < cooldown)
        ).order_by(Email.id.desc()).limit(3)
        res = await session.execute(stmt)
        emails = list(res.scalars().all())
        if not emails:
            return
        reminders = []
        for e in emails:
            e.last_reminder_at = datetime.now(timezone.utc)
            acts = ""
            try:
                a = json.loads(e.ai_actions or "[]")
                acts = f"\n👉 Действия: {', '.join(a)}" if a else ""
            except:
                pass
            dl = f"⏰ Дедлайн: {e.ai_deadline}\n" if e.ai_deadline else ""
            reminders.append(f"📌 {e.subject or 'Важное письмо'}\n{dl}{e.ai_summary or ''}{acts}")
        await session.commit()
        text = "🔔 НАПОМИНАНИЕ О ВАЖНОМ:\n" + "\n\n".join(reminders)
        try:
            await api.messages.send(user_id=vk_id, random_id=0, message=text)
            logger.info("Sent reminder to vk=%s", vk_id)
        except Exception:
            logger.warning("Failed to send reminder to vk=%s", vk_id)

reminder_service = ReminderService()
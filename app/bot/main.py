from __future__ import annotations
import asyncio
import logging
import sys
from pathlib import Path
import truststore
truststore.inject_into_ssl()
from vkbottle import API
from vkbottle.bot import Bot, Message
from app.core.settings import settings
from app.db.session import AsyncSessionMaker
from app.bot.insecure_http import InsecureAiohttpClient
from app.bot.keyboards import main_menu_json, cancel_menu_json, yes_no_menu_json, folders_menu_json, custom_folder_actions_json, email_nav_json
from app.services.user_service import UserService
from app.services.mail_service import MailService
from app.services.email_service import EmailService
from app.services.account_info_service import AccountInfoService
from app.services.folder_view_service import FolderViewService
from app.services.folder_service import FolderService
from app.bot.keyboards import (
    main_menu_json, cancel_menu_json, yes_no_menu_json,
    folders_menu_json, custom_folder_actions_json, email_nav_json
)
from app.db.session import AsyncSessionMaker

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")])
logger = logging.getLogger("app")
logger.info("Bot starting...")

api = API(token=settings.VK_BOT_TOKEN, http_client=InsecureAiohttpClient())
bot = Bot(api=api)
user_service = UserService()
mail_service = MailService()
email_service = EmailService()
info_service = AccountInfoService()
folder_view = FolderViewService()
folder_service = FolderService()

state: dict[int, dict] = {}
def set_state(vk_user_id: int, name: str | None, data: dict | None = None) -> None:
    if name is None: state.pop(vk_user_id, None)
    else: state[vk_user_id] = {"name": name, "data": data or {}}
def get_state_name(vk_user_id: int) -> str | None:
    s = state.get(vk_user_id)
    return s["name"] if s else None
def get_state_data(vk_user_id: int) -> dict:
    s = state.get(vk_user_id)
    return s["data"] if s else {}

_BG_STARTED = False
def start_background_tasks() -> None:
    global _BG_STARTED
    if _BG_STARTED: return
    _BG_STARTED = True
    # 🔽 Исправлено на 60 секунд
    bot.loop_wrapper.add_task(email_service.poll_new_emails_forever(api=api, interval_sec=60))
    logger.info("Background polling task started (every 1 minute).")

async def _render_email_page(message: Message, vk_user_id: int):
    st = get_state_data(vk_user_id)
    if not st or "email_ids" not in st:
        set_state(vk_user_id, None)
        await message.answer("Навигация сброшена. Выберите папку заново.", keyboard=main_menu_json())
        return

    folder_name = st["folder_name"]
    email_ids = st["email_ids"]
    idx = st["current_index"]
    
    if not email_ids:
        set_state(vk_user_id, None)
        await message.answer("📭 Папка пуста.", keyboard=main_menu_json())
        return
        
    try:
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await user_service.repo.get_by_vk_id(session, vk_user_id)
                if not user: return
                email = await folder_view.get_email_by_index(session, user.id, email_ids, idx)
    except Exception:
        set_state(vk_user_id, None)
        await message.answer("Не удалось загрузить письмо.", keyboard=main_menu_json())
        return

    if not email:
        set_state(vk_user_id, None)
        await message.answer("Письмо не найдено.", keyboard=main_menu_json())
        return

    subj = email.subject or "(без темы)"
    frm = email.from_email or "(неизвестно)"
    dt = email.received_at.strftime("%d.%m %H:%M") if email.received_at else "?"
    summ = email.ai_summary or "Саммари ещё не сформировано."

    # 🔽 Ссылка полностью удалена из текста
    txt = f"[{folder_name}]\n👤 {frm}\n🕒 {dt}\n📝 {subj}\n💡 {summ}"
    await message.answer(txt, keyboard=email_nav_json(len(email_ids), idx))
@bot.on.message()
async def router(message: Message):
    start_background_tasks()
    vk_user_id = message.from_id
    text = (message.text or "").strip()
    t = text.casefold()
    await user_service.ensure_user(vk_user_id)
    st_name = get_state_name(vk_user_id)
    st_data = get_state_data(vk_user_id)

    if t == "отмена":
        set_state(vk_user_id, None)
        await message.answer("Ок, отменил.", keyboard=main_menu_json())
        return
    if t in ("начать", "start", "старт"):
        set_state(vk_user_id, None)
        await message.answer("Привет! Выбери действие:", keyboard=main_menu_json())
        return
    if t == "помощь":
        await message.answer("Кнопки: Подключить Gmail, Проверить почту, Мои папки, Дайджест. Для Gmail нужен App Password при включенной 2FA.", keyboard=main_menu_json())
        return
    if t == "назад в меню":
        set_state(vk_user_id, None)
        await message.answer("Меню:", keyboard=main_menu_json())
        return
    if t == "мой gmail":
        msg = await info_service.get_gmail_info(vk_user_id)
        await message.answer(msg, keyboard=main_menu_json())
        return
    if t == "подключить gmail":
        acc = await folder_service.get_active_gmail_account(vk_user_id)
        if acc:
            set_state(vk_user_id, "wait_reconnect_confirm", {"email": acc.email_address})
            await message.answer(f"Уже подключено: {acc.email_address}\nПереподключить? (Да/Нет)", keyboard=yes_no_menu_json())
            return
        set_state(vk_user_id, "wait_gmail_email", {})
        await message.answer("Введи Gmail адрес (пример: student@gmail.com).", keyboard=cancel_menu_json())
        return
    if t == "проверить почту":
        await message.answer("Проверяю новые письма...")
        saved, code = await email_service.sync_new(vk_user_id)
        if code == "NO_MAIL": await message.answer("Сначала подключи Gmail.", keyboard=main_menu_json()); return
        if code == "IMAP_TIMEOUT": await message.answer("Gmail отвечает слишком долго.", keyboard=main_menu_json()); return
        if code == "IMAP_ERROR": await message.answer("Ошибка IMAP.", keyboard=main_menu_json()); return
        await message.answer(f"Готово! Новых писем: {saved}", keyboard=main_menu_json())
        return
    if t == "дайджест":
        ok, digest_text = await email_service.build_digest_text(vk_user_id, limit=5)
        await message.answer(digest_text, keyboard=main_menu_json())
        return

    if st_name == "wait_reconnect_confirm":
        if t == "да": set_state(vk_user_id, "wait_gmail_email", {}); await message.answer("Введи Gmail адрес:", keyboard=cancel_menu_json()); return
        if t == "нет": set_state(vk_user_id, None); await message.answer("Ок.", keyboard=main_menu_json()); return
        await message.answer("Ответь «Да» или «Нет».", keyboard=yes_no_menu_json()); return
    if st_name == "wait_gmail_email":
        email = text.strip()
        if "@" not in email or "." not in email: await message.answer("Это не email. Повтори:", keyboard=cancel_menu_json()); return
        st_data["email"] = email
        set_state(vk_user_id, "wait_gmail_pass", st_data)
        await message.answer("Введи App Password:", keyboard=cancel_menu_json())
        return
    if st_name == "wait_gmail_pass":
        app_pass = text
        email = st_data.get("email")
        if not email: set_state(vk_user_id, "wait_gmail_email", {}); await message.answer("Введи email заново:", keyboard=cancel_menu_json()); return
        await message.answer("Проверяю доступ...")
        ok, code = await mail_service.connect_gmail(vk_user_id, email, app_pass)
        set_state(vk_user_id, None)
        if not ok: await message.answer("Ошибка входа. Проверь данные.", keyboard=main_menu_json()); return
        await message.answer("Gmail подключен. Скачиваю последние 15 писем...")
        saved, _ = await email_service.sync_after_connect(vk_user_id, n=15)
        await message.answer(f"Готово! Обработано: {saved}", keyboard=main_menu_json())
        return

    if t == "мои папки":
        folder_names, can_create, custom_names = await folder_service.get_folder_menu_info(vk_user_id)
        set_state(vk_user_id, "folders_menu", {"custom_names": custom_names})
        await message.answer("Выбери папку:", keyboard=folders_menu_json(folder_names, can_create))
        return
    if st_name == "folders_menu":
        folder_names, can_create, custom_names = await folder_service.get_folder_menu_info(vk_user_id)
        set_state(vk_user_id, "folders_menu", {"custom_names": custom_names})
        
        if t == "создать папку":
            if not can_create:
                await message.answer(f"Лимит: 3 кастомные папки. Удали одну.", keyboard=folders_menu_json(folder_names, False))
                return
            set_state(vk_user_id, "wait_custom_desc", {})
            await message.answer("Опиши, что складывать сюда.\nПример: «хакатоны, олимпиады, стажировки в IT»", keyboard=cancel_menu_json())
            return

        matched = next((fn for fn in folder_names if fn.strip().casefold() == t.strip().casefold()), None)
        
        if matched:
            is_custom = matched.strip().casefold() in [n.strip().casefold() for n in custom_names]
            if is_custom:
                set_state(vk_user_id, "custom_folder_menu", {"custom_name": matched})
                await message.answer(f"Папка «{matched}». Что сделать?", keyboard=custom_folder_actions_json(matched))
                return

            async with AsyncSessionMaker() as session:
                async with session.begin():
                    user = await user_service.repo.get_by_vk_id(session, vk_user_id)
                    if not user: return
                    email_ids = await folder_view.get_folder_email_ids(session, user.id, matched)
                    if not email_ids:
                        await message.answer(f"📭 Папка «{matched}» пуста.", keyboard=folders_menu_json(folder_names, can_create))
                        return
                    set_state(vk_user_id, "view_email_page", {"folder_name": matched, "email_ids": email_ids, "current_index": 0})
                    await _render_email_page(message, vk_user_id)
                    return
        await message.answer("Выбери папку кнопкой или «Назад в меню».", keyboard=folders_menu_json(folder_names, can_create))
        return
    if st_name == "custom_folder_menu":
        custom_name = st_data.get("custom_name")
        if not custom_name:
            set_state(vk_user_id, None)
            await message.answer("Папка не найдена.", keyboard=main_menu_json())
            return

        if t == "назад к папкам":
            folder_names, can_create, _ = await folder_service.get_folder_menu_info(vk_user_id)
            set_state(vk_user_id, "folders_menu", {})
            await message.answer("Выбери папку:", keyboard=folders_menu_json(folder_names, can_create))
            return

        if t.startswith("открыть:"):
            clicked_name = t.replace("открыть:", "").strip()
            folder_names, can_create, _ = await folder_service.get_folder_menu_info(vk_user_id)
            matched = next((fn for fn in folder_names if fn.strip().casefold() == clicked_name.strip().casefold()), None)
            if matched:
                async with AsyncSessionMaker() as session:
                    async with session.begin():
                        user = await user_service.repo.get_by_vk_id(session, vk_user_id)
                        if not user: return
                        email_ids = await folder_view.get_folder_email_ids(session, user.id, matched)
                        if not email_ids:
                            await message.answer(f"📭 Папка «{matched}» пуста. Возвращаюсь к списку папок.", keyboard=folders_menu_json(folder_names, can_create))
                            set_state(vk_user_id, "folders_menu", {})
                            return
                        set_state(vk_user_id, "view_email_page", {"folder_name": matched, "email_ids": email_ids, "current_index": 0})
                        await _render_email_page(message, vk_user_id)
                        return

        if t == "удалить папку":
            async with AsyncSessionMaker() as session:
                async with session.begin():
                    user = await user_service.repo.get_by_vk_id(session, vk_user_id)
                    if not user: return
                    folder = await folder_service.folder_repo.get_by_name(session, user.id, custom_name)
                    if folder:
                        await folder_service.folder_repo.delete_custom_folder(session, user.id, folder.id)
            folder_names, can_create, _ = await folder_service.get_folder_menu_info(vk_user_id)
            set_state(vk_user_id, "folders_menu", {})
            await message.answer(f"🗑 Папка «{custom_name}» удалена.", keyboard=folders_menu_json(folder_names, can_create))
            return

        await message.answer("Выбери действие.", keyboard=custom_folder_actions_json(custom_name))
        return
    if st_name == "view_email_page":
        st = get_state_data(vk_user_id)
        email_ids = st.get("email_ids", [])
        idx = st.get("current_index", 0)
        total = len(email_ids)

        if total == 0:
            set_state(vk_user_id, None)
            await message.answer("📭 Папка пуста.", keyboard=main_menu_json())
            return

        # 🔽 Кнопка "Папки" → выбрасывает в выбор папок
        if t == "папки":
            folder_names, can_create, _ = await folder_service.get_folder_menu_info(vk_user_id)
            set_state(vk_user_id, "folders_menu", {})
            await message.answer("Выбери папку:", keyboard=folders_menu_json(folder_names, can_create))
            return

        # 🔽 Клик по кнопке "1/9" → подсказка ввода номера
        if "/" in t and t.replace("/", "").replace(" ", "").isdigit():
            await message.answer(f"Напишите номер письма, к которому хотите перейти (от 1 до {total}).", keyboard=cancel_menu_json())
            return

        # 🔽 Цикличная навигация (0-1 → n, n+1 → 0)
        if t == "назад":
            st["current_index"] = (idx - 1) % total
            set_state(vk_user_id, "view_email_page", st)
            await _render_email_page(message, vk_user_id)
            return
        elif t == "далее":
            st["current_index"] = (idx + 1) % total
            set_state(vk_user_id, "view_email_page", st)
            await _render_email_page(message, vk_user_id)
            return

        # 🔽 Ввод номера вручную (после подсказки или напрямую)
        if t.replace(" ", "").isdigit():
            try:
                num = int(t)
                if 1 <= num <= total:
                    st["current_index"] = num - 1
                    set_state(vk_user_id, "view_email_page", st)
                    await _render_email_page(message, vk_user_id)
                    return
            except ValueError:
                pass

        set_state(vk_user_id, "view_email_page", st)
        await _render_email_page(message, vk_user_id)
        return
    if st_name == "wait_custom_desc":
        raw = text.strip()
        if len(raw) < 5: await message.answer("Описание слишком короткое:", keyboard=cancel_menu_json()); return
        await message.answer("🤖 Анализирую описание и создаю папку...")
        intent = await email_service.ai_client.parse_folder_intent(raw)
        ok, msg = await folder_service.create_custom_folder_ai(vk_user_id, intent.name, intent.description, intent.keywords)
        set_state(vk_user_id, None)
        await message.answer(msg, keyboard=main_menu_json())
        return
    if st_name == "wait_email_number":
        try:
            num = int(text.strip())
            st = get_state_data(vk_user_id)
            if 1 <= num <= len(st["email_ids"]):
                st["current_index"] = num - 1
                set_state(vk_user_id, "view_email_page", st)
                await _render_email_page(message, vk_user_id)
                return
        except ValueError: pass
        await message.answer("Неверный формат:", keyboard=cancel_menu_json())
        return

    await message.answer("Не понял. Нажми «Начать».", keyboard=main_menu_json())

if __name__ == "__main__":
    bot.run_forever()
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
from app.bot.keyboards import (
main_menu_json, cancel_menu_json, yes_no_menu_json,
folders_menu_json, custom_folder_actions_json, email_nav_json,
app_password_intro_json, jump_to_email_json
)
from app.services.user_service import UserService
from app.services.mail_service import MailService
from app.services.email_service import EmailService
from app.services.account_info_service import AccountInfoService
from app.services.folder_view_service import FolderViewService
from app.services.folder_service import FolderService
from app.db.init_db import ensure_schema

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
level=logging.INFO,
format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")]
)
logger = logging.getLogger("app")

api = API(token=settings.VK_BOT_TOKEN, http_client=InsecureAiohttpClient())
bot = Bot(api=api)
user_service = UserService()
mail_service = MailService()
email_service = EmailService()
info_service = AccountInfoService()
folder_view = FolderViewService()
folder_service = FolderService()

# --- State Management ---
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

# --- Text Templates ---
INSTRUCTION_TEXT = (
"👋 Привет! Я Flow Agent — твой умный помощник для почты.\n\n"
"🤖 Что я умею:\n"
"• 📂 Сортирую письма по папкам (Учёба, Работа, Важное)\n"
"• ⏰ Нахожу дедлайны и напоминаю о них\n"
"• 📝 Делаю краткие саммари писем\n"
"• 📬 Формирую дайджест последних новостей\n\n"
"⚙️ Быстрые действия:\n"
"• «Мой Gmail» — подключить или изменить почту\n"
"• «Дедлайны» — список срочных задач\n"
"• «Дайджест» — обзор последних писем\n"
"• «Мои папки» — управление сортировкой\n\n"
"🆘 Помощь: @your_vk_id"
)

APP_PASSWORD_GUIDE = (
"Как получить App Password в Gmail:\n"
"1. Зайдите в https://myaccount.google.com\n"
"2. Раздел Безопасность -> включите двухфакторную аутентификацию.\n"
"3. В поиске страницы введите Пароли приложений (App Passwords).\n"
"4. Выберите Другое -> название Bot -> Создать.\n"
"5. Скопируйте 16-значный код и вернитесь сюда."
)

_BG_STARTED = False

def start_background_tasks() -> None:
    global _BG_STARTED
    if _BG_STARTED: return
    _BG_STARTED = True
    bot.loop_wrapper.add_task(email_service.poll_new_emails_forever(api=api, interval_sec=60))
    logger.info("Background polling task started.")

async def _render_email_page(message: Message, vk_user_id: int):
    st = get_state_data(vk_user_id)
    if not st or "email_ids" not in st:
        set_state(vk_user_id, None)
        await message.answer("•", keyboard=main_menu_json())
        return
    folder_name = st["folder_name"]
    email_ids = st["email_ids"]
    idx = st["current_index"]
    if not email_ids:
        set_state(vk_user_id, None)
        await message.answer("Папка пуста.", keyboard=main_menu_json())
        return
    try:
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await user_service.repo.get_by_vk_id(session, vk_user_id)
                if not user: return
                email = await folder_view.get_email_by_index(session, user.id, email_ids, idx)
    except Exception:
        set_state(vk_user_id, None)
        await message.answer("Ошибка загрузки.", keyboard=main_menu_json())
        return
    if not email:
        set_state(vk_user_id, None)
        await message.answer("Письмо не найдено.", keyboard=main_menu_json())
        return
    subj = email.subject or "(без темы)"
    frm = email.from_email or "(неизвестно)"
    dt = email.received_at.strftime("%d.%m %H:%M") if email.received_at else "?"
    summ = email.ai_summary or "Саммари не сформировано."
    txt = f"[{folder_name}]\nОт: {frm}\nДата: {dt}\nТема: {subj}\nСаммари: {summ}"
    await message.answer(txt, keyboard=email_nav_json(len(email_ids), idx))

@bot.on.message()
async def router(message: Message):
    logger.info("📩 [DEBUG] Получено сообщение от %s: '%s'", message.from_id, message.text)
    start_background_tasks()
    await ensure_schema()
    vk_user_id = message.from_id
    text = (message.text or "").strip()
    t = text.casefold()
    await user_service.ensure_user(vk_user_id)
    st_name = get_state_name(vk_user_id)
    st_data = get_state_data(vk_user_id)

    # 1. Глобальные действия (высокий приоритет)
    if t == "отмена":
        set_state(vk_user_id, None)
        await message.answer("Хорошо, вернемся назад", keyboard=main_menu_json())
        return
    if t in ("начать", "start", "старт"):
        set_state(vk_user_id, None)
        await message.answer("Привет! Я — Flow Agent, твой умный помощник для работы с почтой 🤖📧\n"
                             "Я анализирую входящие письма, сортирую их по папкам, узнаю о дедлайнах и делаю краткие дайджесты.\n"
                             "Давай начнём: подключи свою почту, нажав кнопку «Мой Gmail» ниже 👇", keyboard=main_menu_json())
        return
    if t == "назад в меню":
        set_state(vk_user_id, None)
        await message.answer("Окей, возвращаю в меню", keyboard=main_menu_json())
        return

    # 2. Основные кнопки (работают только из корня)
    if st_name is None:
        if t == "мои папки":
            folder_names, can_create, _ = await folder_service.get_folder_menu_info(vk_user_id)
            set_state(vk_user_id, "folders_menu", {})
            await message.answer("Выбери папку:", keyboard=folders_menu_json(folder_names, can_create))
            return
        if t == "инструкция":
            await message.answer(INSTRUCTION_TEXT, keyboard=main_menu_json())
            return
        if t == "дайджест":
            ok, digest_text = await email_service.build_digest_text(vk_user_id, limit=5)
            await message.answer(digest_text if ok else "Писем пока нет.", keyboard=main_menu_json())
            return
        if t == "дедлайны":
            await message.answer(await email_service.get_active_deadlines_text(vk_user_id), keyboard=main_menu_json())
            return
        if t == "мой gmail":
            acc = await folder_service.get_active_gmail_account(vk_user_id)
            if acc:
                set_state(vk_user_id, "wait_reconnect_confirm", {"email": acc.email_address})
                await message.answer(f"Подключено: {acc.email_address}\nПереподключить?", keyboard=yes_no_menu_json())
            else:
                set_state(vk_user_id, "gmail_intro", {})
                await message.answer(APP_PASSWORD_GUIDE, keyboard=app_password_intro_json())
            return

    # 3. Обработка состояний подключения
    if st_name == "gmail_intro":
        if t == "понятно, я готов":
            set_state(vk_user_id, "wait_gmail_email", {})
            await message.answer("Введите Gmail адрес:", keyboard=cancel_menu_json())
            return
    if st_name == "wait_reconnect_confirm":
        if t == "да":
            set_state(vk_user_id, "gmail_intro", {})
            await message.answer(APP_PASSWORD_GUIDE, keyboard=app_password_intro_json())
        elif t == "нет":
            set_state(vk_user_id, None)
            await message.answer("Окей, настройки Gmail остались прежними", keyboard=main_menu_json())
        return
    if st_name == "wait_gmail_email":
        if "@" not in text or "." not in text:
            await message.answer("Неверный формат почты:", keyboard=cancel_menu_json())
            return
        st_data["email"] = text.strip()
        set_state(vk_user_id, "wait_gmail_pass", st_data)
        await message.answer("Введите 16-значный App Password:", keyboard=cancel_menu_json())
        return
    if st_name == "wait_gmail_pass":
        app_pass = text.strip().replace(" ", "")
        email_addr = st_data.get("email")
        await message.answer("Проверяю доступ...")
        ok, code = await mail_service.connect_gmail(vk_user_id, email_addr, app_pass)
        set_state(vk_user_id, None)
        if ok:
            await message.answer("Подключено. Скачиваю последние письма...")
            saved, _ = await email_service.sync_after_connect(vk_user_id, n=15)
            await message.answer(f"Синхронизировано: {saved} писем.", keyboard=main_menu_json())
        else:
            await message.answer("Ошибка входа. Проверьте пароль.", keyboard=main_menu_json())
        return

    # 4. Навигация по папкам
    if st_name == "folders_menu":
        folder_names, can_create, custom_names = await folder_service.get_folder_menu_info(vk_user_id)
        if t == "создать папку":
            if not can_create:
                await message.answer("Лимит: 3 кастомные папки.", keyboard=folders_menu_json(folder_names, False))
                return
            set_state(vk_user_id, "wait_custom_desc", {})
            await message.answer("Опишите папку:", keyboard=cancel_menu_json())
            return
        
        matched = next((fn for fn in folder_names if fn.strip().casefold() == t.strip().casefold()), None)
        
        if matched:
            is_custom = matched.strip().casefold() in [n.strip().casefold() for n in custom_names]
            if is_custom:
                set_state(vk_user_id, "custom_folder_menu", {"custom_name": matched})
                await message.answer(f"Папка {matched}. Действие?", keyboard=custom_folder_actions_json(matched))
            else:
                async with AsyncSessionMaker() as session:
                    async with session.begin():
                        user = await user_service.repo.get_by_vk_id(session, vk_user_id)
                        if not user: return
                        email_ids = await folder_view.get_folder_email_ids(session, user.id, matched)
                        if not email_ids:
                            await message.answer("Папка пуста.", keyboard=folders_menu_json(folder_names, can_create))
                            return
                        set_state(vk_user_id, "view_email_page", {"folder_name": matched, "email_ids": email_ids, "current_index": 0})
                        await _render_email_page(message, vk_user_id)
            return
        else:
            # !!! НОВОЕ: Если папка не найдена (удалена или ошибка), сообщаем об этом
            logger.warning(f"User tried to open non-existent folder '{t}'")
            await message.answer(f"❌ Папка «{t}» не найдена. Возможно, она была удалена.", keyboard=folders_menu_json(folder_names, can_create))
            return

    if st_name == "custom_folder_menu":
        custom_name = st_data.get("custom_name")
        if t == "назад к папкам":
            folder_names, can_create, _ = await folder_service.get_folder_menu_info(vk_user_id)
            set_state(vk_user_id, "folders_menu", {})
            await message.answer("Выбери папку:", keyboard=folders_menu_json(folder_names, can_create))
            return
        if t.startswith("открыть:"):
            clicked = t.replace("открыть:", "").strip()
            folder_names, can_create, _ = await folder_service.get_folder_menu_info(vk_user_id)
            matched = next((fn for fn in folder_names if fn.strip().casefold() == clicked.strip().casefold()), None)
            if matched:
                async with AsyncSessionMaker() as session:
                    async with session.begin():
                        user = await user_service.repo.get_by_vk_id(session, vk_user_id)
                        if user:
                            email_ids = await folder_view.get_folder_email_ids(session, user.id, matched)
                            if email_ids:
                                set_state(vk_user_id, "view_email_page", {"folder_name": matched, "email_ids": email_ids, "current_index": 0})
                                await _render_email_page(message, vk_user_id)
                            else:
                                await message.answer("Пусто.", keyboard=folders_menu_json(folder_names, can_create))
                                set_state(vk_user_id, "folders_menu", {})
            return
        if t == "удалить папку":
            try:
                async with AsyncSessionMaker() as session:
                    async with session.begin():
                        user = await user_service.repo.get_by_vk_id(session, vk_user_id)
                        if not user:
                            raise ValueError("User not found")
                        
                        folder = await folder_service.folder_repo.get_by_name(session, user.id, custom_name)
                        
                        if not folder:
                            pass
                        else:
                            success = await folder_service.folder_repo.delete_custom_folder(session, user.id, folder.id)
                            if not success:
                                raise RuntimeError("Failed to delete folder")
                
                folder_names, can_create, _ = await folder_service.get_folder_menu_info(vk_user_id)
                set_state(vk_user_id, "folders_menu", {})
                await message.answer(f"✅ Папка «{custom_name}» удалена.", keyboard=folders_menu_json(folder_names, can_create))
                
            except Exception as e:
                logger.error(f"Error deleting folder: {e}")
                folder_names, can_create, _ = await folder_service.get_folder_menu_info(vk_user_id)
                set_state(vk_user_id, "folders_menu", {})
                await message.answer(f"❌ Ошибка при удалении. Обновляю список.", keyboard=folders_menu_json(folder_names, can_create))
            return

    # ✅ ОБНОВЛЕННАЯ ЛОГИКА ПРОСМОТРА ПИСЕМ
    if st_name == "view_email_page":
        st = get_state_data(vk_user_id)
        email_ids = st.get("email_ids", [])
        idx = st.get("current_index", 0)
        total = len(email_ids)
        if total == 0:
            set_state(vk_user_id, None)
            await message.answer("•", keyboard=main_menu_json())
            return
        if t == "в папки":
            folder_names, can_create, _ = await folder_service.get_folder_menu_info(vk_user_id)
            set_state(vk_user_id, "folders_menu", {})
            await message.answer("Выбери папку:", keyboard=folders_menu_json(folder_names, can_create))
            return
        if t == "назад":
            st["current_index"] = (idx - 1) % total
            set_state(vk_user_id, "view_email_page", st)
            await _render_email_page(message, vk_user_id)
            return
        if t == "далее":
            st["current_index"] = (idx + 1) % total
            set_state(vk_user_id, "view_email_page", st)
            await _render_email_page(message, vk_user_id)
            return
        current_button_text = f"{idx + 1}/{total}"
        if t == current_button_text.casefold():
            set_state(vk_user_id, "wait_jump_to_email", st.copy())
            await message.answer(f"Вы можете написать число от 1 до {total}, чтобы перейти к конкретному письму.", keyboard=jump_to_email_json(total))
            return

    if st_name == "wait_jump_to_email":
        email_ids = st_data.get("email_ids", [])
        total = len(email_ids)
        if text.isdigit():
            num = int(text)
            if 1 <= num <= total:
                new_idx = num - 1
                st_data["current_index"] = new_idx
                set_state(vk_user_id, "view_email_page", st_data)
                await _render_email_page(message, vk_user_id)
                return
            else:
                await message.answer(f"Пожалуйста, введите число от 1 до {total}.", keyboard=jump_to_email_json(total))
                return
        else:
            await message.answer("Это не число. Пожалуйста, введите номер письма.", keyboard=jump_to_email_json(total))
            return

    if st_name == "wait_custom_desc":
        raw = text.strip()
        if len(raw) < 5:
            await message.answer("Слишком коротко.", keyboard=cancel_menu_json())
            return
        
        intent_name = raw
        intent_desc = ""
        intent_keywords = []
        
        try:
            logger.info("Attempting to parse folder intent via AI...")
            intent = await email_service.ai_client.parse_folder_intent(raw)
            intent_name = intent.name
            intent_desc = intent.description
            intent_keywords = intent.keywords
            logger.info(f"AI Intent parsed: {intent_name}")
        except Exception as e:
            logger.warning(f"AI failed to parse folder intent ({e}). Using raw input as name.")
            intent_name = raw[:50]
            intent_desc = f"Папка создана пользователем: {raw}"
            intent_keywords = [raw.lower()]
        
        ok, msg = await folder_service.create_custom_folder_ai(vk_user_id, intent_name, intent_desc, intent_keywords)
        set_state(vk_user_id, None)
        await message.answer(msg, keyboard=main_menu_json())
        return

    # Если ничего не подошло, возвращаем в меню
    await message.answer("•", keyboard=main_menu_json())

if __name__ == "__main__":
    bot.run_forever()
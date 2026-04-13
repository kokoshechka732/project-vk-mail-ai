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
from app.bot.insecure_http import InsecureAiohttpClient
from app.bot.keyboards import (
    main_menu_json,
    cancel_menu_json,
    yes_no_menu_json,
    folders_menu_json,
    custom_folder_actions_json,
)
from app.services.user_service import UserService
from app.services.mail_service import MailService
from app.services.email_service import EmailService
from app.services.account_info_service import AccountInfoService
from app.services.folder_view_service import FolderViewService
from app.services.folder_service import FolderService

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
    ],
)
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

# ---------------- STATE (MVP: in-memory) ----------------
state: dict[int, dict] = {}


def set_state(vk_user_id: int, name: str | None, data: dict | None = None) -> None:
    if name is None:
        state.pop(vk_user_id, None)
    else:
        state[vk_user_id] = {"name": name, "data": data or {}}


def get_state_name(vk_user_id: int) -> str | None:
    s = state.get(vk_user_id)
    return s["name"] if s else None


def get_state_data(vk_user_id: int) -> dict:
    s = state.get(vk_user_id)
    return s["data"] if s else {}


# --------------- Background polling ---------------
_BG_STARTED = False


def start_background_tasks() -> None:
    global _BG_STARTED
    if _BG_STARTED:
        return
    _BG_STARTED = True

    # vkbottle way to schedule background coroutine
    bot.loop_wrapper.add_task(email_service.poll_new_emails_forever(api=api, interval_sec=300))
    logger.info("Background polling task started (every 5 minutes).")


@bot.on.message()
async def router(message: Message):
    start_background_tasks()

    vk_user_id = message.from_id
    text = (message.text or "").strip()
    t = text.casefold()

    # ensure user exists
    await user_service.ensure_user(vk_user_id)

    st_name = get_state_name(vk_user_id)
    st_data = get_state_data(vk_user_id)

    # ===== global commands =====
    if t == "отмена":
        set_state(vk_user_id, None)
        await message.answer("Ок, отменил.", keyboard=main_menu_json())
        return

    if t in ("начать", "start", "старт"):
        set_state(vk_user_id, None)
        await message.answer("Привет! Выбери действие:", keyboard=main_menu_json())
        return

    if t == "помощь":
        # ВАЖНО: оставляем как есть (по требованию)
        await message.answer(
            "Кнопки:\n"
            "- Подключить Gmail\n"
            "- Проверить почту\n"
            "- Дайджест\n"
            "- Мой Gmail\n"
            "- Мои папки\n"
            "- Сортировать 25 (разложить последние 25 писем в БД по папкам)\n"
            "- DEBUG: письма (показать заголовки последних писем из Gmail)\n\n"
            "Для Gmail нужен App Password (пароль приложения) при включенной 2FA.",
            keyboard=main_menu_json(),
        )
        return

    if t == "назад в меню":
        set_state(vk_user_id, None)
        await message.answer("Меню:", keyboard=main_menu_json())
        return

    # ===== always-available buttons =====
    if t == "мой gmail":
        msg = await info_service.get_gmail_info(vk_user_id)
        await message.answer(msg, keyboard=main_menu_json())
        return

    if t == "подключить gmail":
        # если уже подключено — спросить подтверждение переподключения
        acc = await folder_service.get_active_gmail_account(vk_user_id)
        if acc:
            set_state(vk_user_id, "wait_reconnect_confirm", {"email": acc.email_address})
            await message.answer(
                f"Уже подключено: {acc.email_address}\nПереподключить? (Да/Нет)",
                keyboard=yes_no_menu_json(),
            )
            return

        set_state(vk_user_id, "wait_gmail_email", {})
        await message.answer("Введи Gmail адрес (пример: student@gmail.com).", keyboard=cancel_menu_json())
        return

    if t == "проверить почту":
        await message.answer("Проверяю новые письма...")
        saved, code = await email_service.sync_new(vk_user_id)
        if code == "NO_MAIL":
            await message.answer("Сначала подключи Gmail (кнопка «Подключить Gmail»).", keyboard=main_menu_json())
            return
        if code == "IMAP_TIMEOUT":
            await message.answer("Gmail отвечает слишком долго. Попробуй ещё раз позже.", keyboard=main_menu_json())
            return
        if code == "IMAP_ERROR":
            await message.answer("Не удалось получить письма из Gmail (ошибка IMAP).", keyboard=main_menu_json())
            return
        if code != "OK":
            await message.answer("Не удалось проверить почту.", keyboard=main_menu_json())
            return

        await message.answer(f"Готово! Новых писем: {saved}", keyboard=main_menu_json())
        return

    if t == "дайджест":
        ok, digest_text = await email_service.build_digest_text(vk_user_id, limit=5)
        await message.answer(digest_text, keyboard=main_menu_json())
        return

    # ===== Gmail connect states =====
    if st_name == "wait_reconnect_confirm":
        if t == "да":
            set_state(vk_user_id, "wait_gmail_email", {})
            await message.answer("Ок. Введи Gmail адрес (пример: student@gmail.com).", keyboard=cancel_menu_json())
            return
        if t == "нет":
            set_state(vk_user_id, None)
            await message.answer("Ок. Оставил текущий Gmail без изменений.", keyboard=main_menu_json())
            return
        await message.answer("Ответь «Да» или «Нет» (или «Отмена»).", keyboard=yes_no_menu_json())
        return

    if st_name == "wait_gmail_email":
        email = text.strip()
        if "@" not in email or "." not in email:
            await message.answer("Похоже, это не email. Введи Gmail адрес ещё раз:", keyboard=cancel_menu_json())
            return
        st_data["email"] = email
        set_state(vk_user_id, "wait_gmail_pass", st_data)
        await message.answer(
            "Теперь введи пароль приложения Gmail (App Password). Можно с пробелами — я их уберу.",
            keyboard=cancel_menu_json(),
        )
        return

    if st_name == "wait_gmail_pass":
        app_pass = text
        email = st_data.get("email")
        if not email:
            set_state(vk_user_id, "wait_gmail_email", {})
            await message.answer("Не нашёл email. Введи Gmail адрес заново:", keyboard=cancel_menu_json())
            return

        await message.answer("Проверяю доступ к Gmail по IMAP...")
        ok, code = await mail_service.connect_gmail(vk_user_id, email, app_pass)
        set_state(vk_user_id, None)

        if not ok:
            if code == "AUTH_ERROR":
                await message.answer(
                    "Не удалось войти. Проверь Gmail адрес и App Password.",
                    keyboard=main_menu_json(),
                )
            elif code == "TIMEOUT":
                await message.answer("Gmail не ответил вовремя. Попробуй позже.", keyboard=main_menu_json())
            else:
                await message.answer("Не удалось подключить Gmail (неизвестная ошибка).", keyboard=main_menu_json())
            return

        # После успешного подключения/переподключения: скачать 15, AI, разложить
        await message.answer("Gmail подключен. Скачиваю последние 15 писем и делаю разбор...")
        saved, sync_code = await email_service.sync_after_connect(vk_user_id, n=15)
        if sync_code == "OK":
            await message.answer(f"Готово! Новых писем сохранено и обработано: {saved}", keyboard=main_menu_json())
        else:
            await message.answer("Gmail подключен, но не удалось сразу скачать письма.", keyboard=main_menu_json())
        return

    # ===== Folders UI =====
    if t == "мои папки":
        folder_names, can_create_custom, custom_name = await folder_service.get_folder_menu_info(vk_user_id)
        set_state(vk_user_id, "folders_menu", {"custom_name": custom_name})
        await message.answer(
            "Выбери папку:",
            keyboard=folders_menu_json(folder_names=folder_names, can_create_custom=can_create_custom),
        )
        return

    if st_name == "folders_menu":
        folder_names, can_create_custom, custom_name = await folder_service.get_folder_menu_info(vk_user_id)

        if t == "создать мою папку":
            if not can_create_custom:
                await message.answer("Кастомная папка уже создана.", keyboard=folders_menu_json(folder_names, False))
                return
            set_state(vk_user_id, "wait_custom_folder_name", {})
            await message.answer("Введи название твоей папки (одна папка на пользователя):", keyboard=cancel_menu_json())
            return

        # Нажатие на папку
        if text in folder_names:
            # если это кастомная — открыть подменю действий
            if custom_name and text == custom_name:
                set_state(vk_user_id, "custom_folder_menu", {"custom_name": custom_name})
                await message.answer(
                    f"Папка «{custom_name}». Что сделать?",
                    keyboard=custom_folder_actions_json(custom_folder_name=custom_name),
                )
                return

            # системная папка — показываем письма
            msg = await folder_view.last_emails_in_folder(vk_user_id, folder_name=text, limit=5)
            await message.answer(
                msg,
                keyboard=folders_menu_json(folder_names=folder_names, can_create_custom=can_create_custom),
            )
            return

        # неизвестное в этом состоянии
        await message.answer(
            "Выбери папку кнопкой или нажми «Назад в меню».",
            keyboard=folders_menu_json(folder_names=folder_names, can_create_custom=can_create_custom),
        )
        return

    if st_name == "wait_custom_folder_name":
        name = text.strip()
        if len(name) < 2:
            await message.answer("Слишком коротко. Введи другое название:", keyboard=cancel_menu_json())
            return

        ok, msg = await folder_service.create_custom_folder(vk_user_id, name=name)
        set_state(vk_user_id, None)
        await message.answer(msg, keyboard=main_menu_json())
        return

    if st_name == "custom_folder_menu":
        custom_name = st_data.get("custom_name")
        if not custom_name:
            set_state(vk_user_id, None)
            await message.answer("Не нашёл кастомную папку. Открой «Мои папки» заново.", keyboard=main_menu_json())
            return

        if t == "назад к папкам":
            folder_names, can_create_custom, custom_name2 = await folder_service.get_folder_menu_info(vk_user_id)
            set_state(vk_user_id, "folders_menu", {"custom_name": custom_name2})
            await message.answer(
                "Выбери папку:",
                keyboard=folders_menu_json(folder_names=folder_names, can_create_custom=can_create_custom),
            )
            return

        if t == f"показать: {custom_name}".casefold():
            msg = await folder_view.last_emails_in_folder(vk_user_id, folder_name=custom_name, limit=5)
            await message.answer(msg, keyboard=custom_folder_actions_json(custom_folder_name=custom_name))
            return

        if t == f"добавить ключевые слова: {custom_name}".casefold():
            set_state(vk_user_id, "wait_custom_keywords", {"custom_name": custom_name})
            await message.answer(
                "Введи ключевые слова через запятую.\n"
                "Пример: оплата, invoice, дедлайн, стипендия",
                keyboard=cancel_menu_json(),
            )
            return

        await message.answer("Выбери действие кнопкой.", keyboard=custom_folder_actions_json(custom_folder_name=custom_name))
        return

    if st_name == "wait_custom_keywords":
        custom_name = st_data.get("custom_name")
        if not custom_name:
            set_state(vk_user_id, None)
            await message.answer("Не нашёл кастомную папку. Открой «Мои папки» заново.", keyboard=main_menu_json())
            return

        keywords_raw = text.strip()
        keywords = [k.strip() for k in keywords_raw.split(",")]
        keywords = [k for k in keywords if k]

        ok, msg = await folder_service.add_keywords_to_custom_folder(vk_user_id, keywords=keywords)
        # Вернуть пользователя в меню кастомной папки
        set_state(vk_user_id, "custom_folder_menu", {"custom_name": custom_name})
        await message.answer(msg, keyboard=custom_folder_actions_json(custom_folder_name=custom_name))
        return

    await message.answer("Не понял. Нажми кнопку меню или напиши «Начать».", keyboard=main_menu_json())


if __name__ == "__main__":
    bot.run_forever()
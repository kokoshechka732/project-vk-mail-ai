import truststore
truststore.inject_into_ssl()

from vkbottle import API
from vkbottle.bot import Bot, Message

from app.core.settings import settings
from app.bot.insecure_http import InsecureAiohttpClient
from app.bot.keyboards import (
    main_menu_json,
    cancel_menu_json,
    folders_menu_json,
    FOLDERS,
)

from app.services.user_service import UserService
from app.services.mail_service import MailService
from app.services.email_service import EmailService
from app.services.account_info_service import AccountInfoService
from app.services.folder_view_service import FolderViewService
import logging
import sys
from pathlib import Path

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


@bot.on.message()
async def router(message: Message):
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
        set_state(vk_user_id, "wait_gmail_email", {})
        await message.answer("Введи Gmail адрес (пример: student@gmail.com).", keyboard=cancel_menu_json())
        return

    if t == "проверить почту":
        await message.answer("Скачиваю последние письма (заголовки)...")
        saved, code = await email_service.fetch_and_store_last(vk_user_id, n=25)

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

        await message.answer(f"Готово! Сохранено новых писем: {saved}", keyboard=main_menu_json())
        return

    if t == "дайджест":
        ok, digest_text = await email_service.build_digest_text(vk_user_id, limit=10)
        await message.answer(digest_text, keyboard=main_menu_json())
        return

    if t == "ai: классифицировать 25":
        await message.answer("AI-классифицирую последние 25 писем...")
        try:
            ok, msg = await email_service.ai_classify_last_emails(vk_user_id, limit=25)
            await message.answer(msg, keyboard=main_menu_json())
        except RuntimeError as e:
            await message.answer(f"AI недоступен: {e}\nДобавь DEEPSEEK_API_KEY в .env", keyboard=main_menu_json())
        return

    if t == "debug: письма":
        await message.answer("DEBUG: получаю последние письма из Gmail (заголовки)...")
        ok, msg = await email_service.debug_list_inbox_headers(vk_user_id, n=50)
        await message.answer(msg, keyboard=main_menu_json())
        return

    # ===== Gmail connect states =====
    if st_name == "wait_gmail_email":
        email = text
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

        if ok:
            await message.answer("Готово! Gmail подключен.", keyboard=main_menu_json())
        else:
            if code == "AUTH_ERROR":
                await message.answer("Не удалось войти. Проверь Gmail адрес и App Password.", keyboard=main_menu_json())
            elif code == "TIMEOUT":
                await message.answer("Gmail не ответил вовремя. Попробуй позже.", keyboard=main_menu_json())
            else:
                await message.answer("Не удалось подключить Gmail (неизвестная ошибка).", keyboard=main_menu_json())
        return

    # ===== Folders UI (buttons) =====
    if t == "мои папки":
        set_state(vk_user_id, "folders_menu", {})
        await message.answer("Выбери папку:", keyboard=folders_menu_json())
        return

    # Если мы в меню папок — не “выкидываем”: показываем папку и оставляем клавиатуру папок
    if st_name == "folders_menu" and text in FOLDERS:
        folder_name = text
        msg = await folder_view.last_emails_in_folder(vk_user_id, folder_name, limit=5)
        await message.answer(msg, keyboard=folders_menu_json())
        return

    # Если пользователь нажал папку, но не в состоянии folders_menu — всё равно покажем и включим меню папок
    if text in FOLDERS:
        set_state(vk_user_id, "folders_menu", {})
        folder_name = text
        msg = await folder_view.last_emails_in_folder(vk_user_id, folder_name, limit=5)
        await message.answer(msg, keyboard=folders_menu_json())
        return

    await message.answer("Не понял. Нажми кнопку меню или напиши «Начать».", keyboard=main_menu_json())


if __name__ == "__main__":
    bot.run_forever()
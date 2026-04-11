import truststore
truststore.inject_into_ssl()

from vkbottle import API
from vkbottle.bot import Bot, Message

from app.core.settings import settings
from app.bot.insecure_http import InsecureAiohttpClient
from app.bot.keyboards import main_menu_json, cancel_menu_json
from app.services.user_service import UserService
from app.services.mail_service import MailService
from app.services.email_service import EmailService
from app.services.account_info_service import AccountInfoService
info_service = AccountInfoService()

api = API(token=settings.VK_BOT_TOKEN, http_client=InsecureAiohttpClient())
bot = Bot(api=api)

user_service = UserService()
mail_service = MailService()
email_service = EmailService()
info_service = AccountInfoService()

# Простейший state в памяти (на MVP ок)
# state: None | "wait_gmail_email" | "wait_gmail_pass"
state: dict[int, dict] = {}


def set_state(vk_user_id: int, name: str | None, data: dict | None = None):
    if name is None:
        state.pop(vk_user_id, None)
    else:
        state[vk_user_id] = {"name": name, "data": data or {}}


def get_state(vk_user_id: int) -> dict | None:
    return state.get(vk_user_id)


@bot.on.message()
async def router(message: Message):
    vk_user_id = message.from_id
    text_raw = message.text or ""
    text = (message.text or "").strip()
    t = text.casefold()  # лучше чем lower для русского/латиницы

    # регистрация пользователя всегда (на MVP удобно)
    await user_service.ensure_user(vk_user_id)
    if t == "мой gmail":
        msg = await info_service.get_gmail_info(vk_user_id)
        await message.answer(msg, keyboard=main_menu_json())
        return
    
    st = get_state(vk_user_id)
    st_name = st["name"] if st else None

    # Отмена в любом состоянии
    if text.lower() == "отмена":
        set_state(vk_user_id, None)
        await message.answer("ок отменил.", keyboard=main_menu_json())
        return

    # === Состояния подключения Gmail ===
    if st_name == "wait_gmail_email":
        email = text.strip()
        if "@" not in email or "." not in email:
            await message.answer("Похоже, это не email. Введи Gmail адрес ещё раз:...", keyboard=cancel_menu_json())
            return

        st["data"]["email"] = email
        set_state(vk_user_id, "wait_gmail_pass", st["data"])
        await message.answer(
            "Теперь введи пароль приложения Gmail (App Password). Можно с пробелами — я их уберу.",
            keyboard=cancel_menu_json(),
        )
        return

    if st_name == "wait_gmail_pass":
        app_pass = text.strip()
        email = st["data"]["email"]

        await message.answer("Проверяю доступ к Gmail по IMAP...")

        ok, code = await mail_service.connect_gmail(vk_user_id, email, app_pass)
        set_state(vk_user_id, None)

        if ok:
            await message.answer("Готово! Gmail подключен.", keyboard=main_menu_json())
        else:
            if code == "AUTH_ERROR":
                await message.answer("Не удалось войти. Проверь Gmail адрес и App Password.", keyboard=main_menu_json())
            elif code == "TIMEOUT":
                await message.answer("Сервер Gmail не ответил вовремя. Попробуй позже.", keyboard=main_menu_json())
            else:
                await message.answer("Не удалось подключить Gmail (неизвестная ошибка).", keyboard=main_menu_json())
        return

    # === Команды/кнопки меню ===
    t = text.lower()

    if t in ("начать", "start", "старт"):
        await message.answer("Привет! Выбери действие:", keyboard=main_menu_json())
        return

    if t == "помощь":
        await message.answer(
            "Команды:\n"
            "- Подключить Gmail: подключение почты\n"
            "- Проверить почту: загрузить последние письма\n"
            "- Дайджест: показать последние письма\n\n"
            "Для Gmail нужен App Password (пароль приложения) при включенной 2FA.",
            keyboard=main_menu_json(),
        )
        return

    if t == "подключить gmail":
        set_state(vk_user_id, "wait_gmail_email", {})
        await message.answer(
            "Введи Gmail адрес (пример: student@gmail.com).",
            keyboard=cancel_menu_json(),
        )
        return

    if t == "проверить почту":
        await message.answer("Скачиваю последние письма...")

        saved, code = await email_service.fetch_and_store_last(vk_user_id, n=10)

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
    if t == "мой gmail":
        msg = await info_service.get_gmail_info(vk_user_id)
        await message.answer(msg, keyboard=main_menu_json())
        return
    # fallback
    await message.answer("Не понял. Нажми кнопку меню или напиши «Начать».", keyboard=main_menu_json())


if __name__ == "__main__":
    bot.run_forever()
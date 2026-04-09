from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import requests
import json

app = FastAPI()

TOKEN = ""
CONFIRMATION = ""


# 🎛 КЛАВИАТУРА
def get_main_keyboard():
    keyboard = {
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "📩 Подключить почту"}, "color": "primary"}
            ],
            [
                {"action": {"type": "text", "label": "📁 Папки"}, "color": "primary"},
                {"action": {"type": "text", "label": "📰 Дайджест"}, "color": "positive"}
            ],
            [
                {"action": {"type": "text", "label": "❓ Помощь"}, "color": "secondary"}
            ]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)


def send_message(user_id, text):
    requests.post(
        "https://api.vk.com/method/messages.send",
        params={
            "user_id": user_id,
            "message": text,
            "random_id": 0,
            "access_token": TOKEN,
            "v": "5.199",
            "keyboard": get_main_keyboard()
        }
    )


@app.post("/")
async def vk_callback(request: Request):
    data = await request.json()

    # 🔑 Подтверждение
    if data["type"] == "confirmation":
        return PlainTextResponse(CONFIRMATION)

    # 💬 Сообщение
    if data["type"] == "message_new":
        user_id = data["object"]["message"]["from_id"]
        text = data["object"]["message"]["text"].lower()

        # 📩 ПОДКЛЮЧЕНИЕ ПОЧТЫ
        if text == "📩 подключить почту":
            send_message(user_id, "📩 Начинаем подключение почты. Скоро добавим Gmail 👀")

        # 📁 ПАПКИ
        elif text == "📁 папки":
            send_message(user_id, "📁 Тут будут твои папки (пока в разработке)")

        # 📰 ДАЙДЖЕСТ
        elif text == "📰 дайджест":
            send_message(user_id, "📰 Настройка дайджеста скоро появится")

        # ❓ ПОМОЩЬ
        elif text == "❓ помощь":
            send_message(user_id, "❓ Я бот для работы с почтой. Скоро буду мощным 😎")

        # 👋 ЛЮБОЕ ДРУГОЕ
        else:
            send_message(user_id, "Выбери действие 👇")

    return PlainTextResponse("ok")
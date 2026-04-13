import json
from typing import Optional, List, Dict

STANDARD_CATEGORIES = [
    "academic",
    "work",
    "events",
    "finance",
    "services",
    "spam",
    "personal",
    "other",
]

# Системные папки в БД/боте (должны совпадать с FolderRepository.SYSTEM_FOLDERS)
SYSTEM_FOLDERS = ["Важное", "Учёба", "Стажировки", "Рассылки", "Несортированное", "Спам"]


def build_messages(
    subject: Optional[str],
    from_email: Optional[str],
    received_at: Optional[str],
    body_snippet: Optional[str],
    user_folders: List[str] | None = None,
    user_rules: List[Dict[str, str]] | None = None,
) -> list[dict]:
    user_folders = user_folders or []
    user_rules = user_rules or []
    allowed_folders = SYSTEM_FOLDERS + user_folders

    payload = {
        "subject": subject or "",
        "from_email": from_email or "",
        "received_at": received_at or "",
        "body_snippet": (body_snippet or "")[:2000],
        "standard_categories": STANDARD_CATEGORIES,
        "user_folders": user_folders,
        "user_rules": user_rules,
        "allowed_folders": allowed_folders,
    }

    system = (
        "Ты — ассистент для классификации электронных писем студента.\n"
        "Твоя задача: проанализировать письмо и вернуть JSON с его категорией, важностью, "
        "кратким содержанием и ключевыми действиями.\n\n"
        "Стандартные категории:\n"
        '- "academic" — учёба, пары, дедлайны, оценки, расписание\n'
        '- "work" — стажировки, вакансии, карьера, HR\n'
        '- "events" — мероприятия, хакатоны, конференции, встречи\n'
        '- "finance" — стипендии, оплаты, счета, налоги\n'
        '- "services" — уведомления сервисов (GitHub, Google, Notion и т.п.)\n'
        '- "spam" — реклама, рассылки, мусор\n'
        '- "personal" — личные письма от людей\n'
        '- "other" — всё остальное\n\n'
        "Также учитывай пользовательские папки, если они переданы ниже.\n"
        "Если письмо подходит под описание пользовательской папки — используй её название "
        "в поле category вместо стандартной категории.\n\n"
        "Уровень важности:\n"
        '- "high" — срочное/важное/требует действий/дедлайн/личное обращение\n'
        '- "medium" — полезно, но не критично\n'
        '- "low" — можно игнорировать\n\n'
        "Правила:\n"
        "- Возвращай ТОЛЬКО JSON (без текста вокруг).\n"
        "- summary: 1 предложение, по сути, до 150 символов.\n"
        "- deadline: дата в формате YYYY-MM-DD или null.\n"
        "- actions: массив строк действий (может быть []).\n"
        "- suggested_folder: выбери строго одну папку из allowed_folders.\n\n"
        "Формат ответа (строго JSON):\n"
        "{"
        '"category":"...",'
        '"importance":"low|medium|high",'
        '"summary":"...",'
        '"actions":["..."],'
        '"deadline":"YYYY-MM-DD"|null,'
        '"suggested_folder":"one of allowed_folders"'
        "}"
    )

    user = "Данные письма:\n" + json.dumps(payload, ensure_ascii=False)
    return [
        {"role": "system", "text": system},
        {"role": "user", "text": user},
    ]
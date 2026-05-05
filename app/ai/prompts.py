import json
from typing import Optional, List, Dict

SYSTEM_FOLDERS = ["Важное", "Учёба", "Работа"]

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
        "allowed_folders": allowed_folders,
        "user_custom_folders": user_folders,
        "user_rules": user_rules,
    }
    
    system = """Ты — AI-ассистент для сортировки и анализа писем студента.
Верни СТРОГО валидный JSON. Без markdown, без комментариев, без пояснений.

ДОСТУПНЫЕ ПАПКИ (suggested_folder обязан быть ОДНОЙ из них ИЛИ null):
- Системные: "Важное", "Учёба", "Работа"
- Кастомные пользователя: {custom}

ПРАВИЛА РАСПРЕДЕЛЕНИЯ:
1. "Учёба" -> вуз, деканат, расписание, пара, зачёт, экзамен, курсовая, библиотека, LMS, преподаватели.
2. "Работа" -> вакансии, стажировки, HR, собеседования, карьера, фриланс, бизнес-переписка.
3. "Важное" -> личная переписка, банки/налоги/госуслуги, срочные уведомления, всё требующее ВНИМАНИЯ.
4. Если письмо точно соответствует описанию/ключевым словам кастомной папки -> используй её.
5. ЕСЛИ ТЫ НЕ УВЕРЕН КАКУЮ ПАПКУ ВЫБРАТЬ, верни suggested_folder: null. Не гадай! Лучше null, чем ошибка.

КАТЕГОРИЯ (category): academic, work, finance, services, spam, personal, other.

ВАЖНОСТЬ (importance): 
- high (срочно/личное/требует действий/есть дедлайн).
- medium (информационное).
- low (рассылка/мусор).

ДЕДЛАЙН (deadline): 
Строка строго формата YYYY-MM-DD HH:MM (например, 2026-05-06 08:00) или null.
ВНИМАНИЕ: ставь deadline, если importance = "high" или "medium" И есть явное упоминание времени/даты сдачи.
Никогда не ставь дедлайн в прошлом. Если указанное время уже прошло, верни deadline: null.
Если дата "06 мая 2026 года в 8 утра", преобразуй в "2026-05-06 08:00".
Если точное время не указано, но есть дата, поставь 09:00.
Если дедлайна нет явно, оставь null.

ДЕЙСТВИЯ (actions): конкретные шаги или [].

САММАРИ (summary): 1 предложение, суть, <=150 символов.

ФОРМАТ ОТВЕТА:
{{"category":"...","importance":"...","summary":"...","actions":[],"deadline":"... или null","suggested_folder":"... или null"}}
""".format(custom="; ".join(user_folders) if user_folders else "(нет)")

    user = "Данные письма:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    
    return [
        {"role": "system", "text": system},
        {"role": "user", "text": user},
    ]
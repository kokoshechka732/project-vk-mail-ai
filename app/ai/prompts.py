import json
from typing import Optional, List, Dict

# ✅ Синхронизировано с folder_repository.py
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
    
    system = (
        "Ты — AI-ассистент для сортировки и анализа писем студента.\n"
        "Верни СТРОГО валидный JSON. Без markdown, без комментариев, без пояснений.\n\n"
        
        "ДОСТУПНЫЕ ПАПКИ (suggested_folder обязан быть ОДНОЙ из них):\n"
        "- Системные: \"Важное\", \"Учёба\", \"Работа\"\n"
        "- Кастомные пользователя: {custom}\n\n"
        
        "ПРАВИЛА РАСПРЕДЕЛЕНИЯ:\n"
        "1. \"Учёба\" -> вуз, деканат, расписание, пара, зачёт, экзамен, курсовая, библиотека, LMS, преподаватели.\n"
        "2. \"Работа\" -> вакансии, стажировки, HR, собеседования, карьера, фриланс, бизнес-переписка.\n"
        "3. \"Важное\" -> личная переписка, банки/налоги/госуслуги, срочные уведомления, всё требующее внимания.\n"
        "4. Если письмо точно соответствует описанию/ключевым словам кастомной папки -> используй её.\n"
        "5. Если не уверен -> \"Важное\".\n\n"
        
        "КАТЕГОРИЯ (category): academic, work, finance, services, spam, personal, other.\n"
        "ВАЖНОСТЬ (importance): high (срочно/личное/требует действий), medium (информационное), low (рассылка/мусор).\n"
        "Дедлайн (deadline): YYYY-MM-DD или null. ВНИМАНИЕ: ставь deadline ТОЛЬКО если importance = \"high\". Для medium/low всегда null.\n"
        "Действия (actions): конкретные шаги или [].\n"
        "Саммари (summary): 1 предложение, суть, <=150 символов.\n\n"
        
        "ФОРМАТ ОТВЕТА:\n"
        '{"category":"...","importance":"...","summary":"...","actions":[],"deadline":"... или null","suggested_folder":"..."}'
    ).format(custom="; ".join(user_folders) if user_folders else "(нет)")
    
    user = "Данные письма:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    
    return [
        {"role": "system", "text": system},
        {"role": "user", "text": user},
    ]
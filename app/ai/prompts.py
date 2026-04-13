import json
from typing import Iterable

ALLOWED_FOLDERS = ["Важное", "Учёба", "Стажировки", "Рассылки", "Несортированное"]


def build_messages(subject: str | None, from_email: str | None, received_at: str | None) -> list[dict]:
    """
    Письма у нас header-only на MVP, поэтому классифицируем по Subject/From/Date.
    """
    payload = {
        "subject": subject or "",
        "from_email": from_email or "",
        "received_at": received_at or "",
        "allowed_folders": ALLOWED_FOLDERS,
    }

    system = (
        "You are an email classifier for a student.\n"
        "Return ONLY valid JSON (no markdown, no code fences, no extra text).\n"
        "The JSON must match this schema:\n"
        "{"
        '"importance":"low|medium|high",'
        '"category":"string",'
        '"summary":"string",'
        '"suggested_folder":"one of allowed_folders",'
        '"confidence":0..1'
        "}\n"
        "Rules:\n"
        "- suggested_folder MUST be exactly one of allowed_folders.\n"
        "- summary is short (1-3 sentences).\n"
        "- If unsure, use folder 'Несортированное' and lower confidence.\n"
    )

    user = (
        "Classify this email header data:\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
import json
import re
import logging
from typing import Optional, List, Dict

import httpx

from app.core.settings import settings
from app.ai.schemas import AIEmailClassification
from app.ai.prompts import build_messages

logger = logging.getLogger("ai")

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _extract_json(text: str) -> str:
    text = (text or "").strip()
    m = _CODE_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text


class YandexGPTClient:
    def __init__(self) -> None:
        if not settings.YANDEX_API_KEY.strip():
            raise RuntimeError("YANDEX_API_KEY is not set in .env")
        if not settings.YANDEX_FOLDER_ID.strip():
            raise RuntimeError("YANDEX_FOLDER_ID is not set in .env")

        self.api_key = settings.YANDEX_API_KEY.strip()
        self.folder_id = settings.YANDEX_FOLDER_ID.strip()
        self.model_name = settings.YANDEX_MODEL_NAME.strip()
        self.model_version = settings.YANDEX_MODEL_VERSION.strip()
        self.endpoint = settings.YANDEX_ENDPOINT.strip()
        self.verify_ssl = bool(settings.YANDEX_VERIFY_SSL)

    @property
    def model_uri(self) -> str:
        return f"gpt://{self.folder_id}/{self.model_name}/{self.model_version}"

    async def classify_email(
        self,
        subject: Optional[str],
        from_email: Optional[str],
        received_at: Optional[str],
        body_snippet: Optional[str],
        user_folders: List[str] | None = None,
        user_rules: List[Dict[str, str]] | None = None,
    ) -> AIEmailClassification:
        messages = build_messages(
            subject=subject,
            from_email=from_email,
            received_at=received_at,
            body_snippet=body_snippet,
            user_folders=user_folders or [],
            user_rules=user_rules or [],
        )

        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "modelUri": self.model_uri,
            "completionOptions": {"stream": False, "temperature": 0, "maxTokens": 800},
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=45.0, verify=self.verify_ssl) as client:
            r = await client.post(self.endpoint, headers=headers, json=body)

        if r.status_code >= 400:
            req_id = r.headers.get("x-request-id")
            logger.error(
                "YandexGPT HTTP %s request_id=%s modelUri=%s response=%s",
                r.status_code,
                req_id,
                self.model_uri,
                r.text,
            )
            raise RuntimeError(f"YandexGPT HTTP {r.status_code}: {r.text}")

        data = r.json()
        text = data["result"]["alternatives"][0]["message"]["text"]
        payload = _extract_json(text)
        obj = json.loads(payload)
        return AIEmailClassification.model_validate(obj)
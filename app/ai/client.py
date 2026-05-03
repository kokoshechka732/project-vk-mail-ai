import json
import re
import logging
from typing import Optional, List, Dict
import httpx
from app.core.settings import settings
from app.ai.schemas import AIEmailClassification
from app.ai.prompts import build_messages

logger = logging.getLogger("ai")

class AIClient:
    def __init__(self):
        self.provider = settings.AI_PROVIDER.lower()
        # verify=False для локальной LLM часто бывает нужно, для API - по настройкам
        verify = True if self.provider == "pollinations" else False
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0), verify=verify)

    async def classify_email(
        self, subject: Optional[str], from_email: Optional[str],
        received_at: Optional[str], body_snippet: Optional[str],
        user_folders: List[str] | None = None,
        user_rules: List[Dict[str, str]] | None = None
    ) -> AIEmailClassification:
        
        # Формируем промпт
        msgs = build_messages(subject, from_email, received_at, body_snippet, user_folders or [], user_rules or [])
        oa_messages = [{"role": m["role"], "content": m.get("text", "")} for m in msgs]

        # Настраиваем запрос в зависимости от провайдера
        if self.provider == "local":
            url = settings.LOCAL_LLM_URL
            model = settings.LOCAL_LLM_MODEL
            headers = {"Content-Type": "application/json"}
        else:
            url = f"{settings.POLLINATIONS_BASE_URL}{settings.POLLINATIONS_CHAT_ENDPOINT}"
            model = settings.POLLINATIONS_MODEL
            headers = {"Content-Type": "application/json"}
            if settings.POLLINATIONS_API_KEY:
                headers["Authorization"] = f"Bearer {settings.POLLINATIONS_API_KEY}"

        body = {
            "model": model,
            "messages": oa_messages,
            "temperature": 0.1, # Низкая температура для стабильного JSON
            "max_tokens": 1000
        }

        try:
            r = await self.client.post(url, headers=headers, json=body)
            r.raise_for_status()
            content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"AI Request failed: {e}")
            raise

        # Парсинг JSON из ответа LLM (иногда они обертывают его в ```json ... ```)
        raw_text = content.strip()
        # Убираем Markdown-обертку, если есть
        if "```" in raw_text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
            if match:
                raw_text = match.group(1).strip()
        
        try:
            obj = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON: {raw_text[:200]}")
            raise RuntimeError("Некорректный ответ от нейросети")

        return AIEmailClassification.model_validate(obj)
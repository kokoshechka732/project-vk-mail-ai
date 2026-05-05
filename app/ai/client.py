import json
import re
import logging
from typing import Optional, List, Dict
import httpx
from app.core.settings import settings
from app.ai.schemas import AIEmailClassification, FolderIntent
from app.ai.prompts import build_messages

logger = logging.getLogger("ai")
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", re.IGNORECASE)

def _extract_json(text: str) -> str:
    text = (text or "").strip()
    m = _CODE_FENCE_RE.search(text)
    if m: 
        return m.group(1).strip()
    m2 = _JSON_OBJECT_RE.search(text)
    if m2: 
        return m2.group(0).strip()
    return text

class AIClient:
    def __init__(self):
        self.provider = settings.AI_PROVIDER.lower()
        # 🔧 Явное определение переменной. 
        # Для pollinations (HTTPS) проверяем SSL, для локального Ollama (HTTP) отключаем.
        verify_ssl = self.provider == "pollinations"
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(45.0), verify=verify_ssl)

    async def classify_email(
        self,
        subject: Optional[str],
        from_email: Optional[str],
        received_at: Optional[str],
        body_snippet: Optional[str],
        user_folders: List[str] | None = None,
        user_rules: List[Dict[str, str]] | None = None
    ) -> AIEmailClassification:
        msgs = build_messages(subject, from_email, received_at, body_snippet, user_folders or [], user_rules or [])
        oa_messages = [{"role": m["role"], "content": m.get("text", "")} for m in msgs]
        
        if self.provider == "local":
            url = settings.LOCAL_LLM_URL
            model = settings.LOCAL_LLM_MODEL
        else:
            url = f"{settings.POLLINATIONS_BASE_URL}{settings.POLLINATIONS_CHAT_ENDPOINT}"
            model = settings.POLLINATIONS_MODEL
            
        headers = {"Content-Type": "application/json"}
        if settings.POLLINATIONS_API_KEY and self.provider != "local":
            headers["Authorization"] = f"Bearer {settings.POLLINATIONS_API_KEY}"
            
        body = {"model": model, "messages": oa_messages, "temperature": 0.1, "max_tokens": 1000}
        
        try:
            r = await self.client.post(url, headers=headers, json=body)
            # Проверяем статус код явно для лучшего лога
            if r.status_code != 200:
                logger.error(f"AI API returned status {r.status_code}: {r.text[:200]}")
                raise RuntimeError(f"API Error {r.status_code}")
                
            r.raise_for_status()
            content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                raise ValueError("Empty LLM response")
        except httpx.ConnectError as e:
            logger.error(f"AI Connection Error: {e}")
            raise
        except httpx.TimeoutException as e:
            logger.error(f"AI Timeout Error: {e}")
            raise
        except Exception as e:
            # Логируем полный traceback или детали, если они есть
            logger.error(f"AI request failed with exception type {type(e).__name__}: {str(e)}")
            raise

        candidate = _extract_json(content)
        
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            logger.error("JSON parse failed. Raw: %s", content[:500])
            raise RuntimeError("LLM returned invalid JSON")
            
        return AIEmailClassification.model_validate(obj)

    async def parse_folder_intent(self, user_text: str) -> FolderIntent:
        prompt = (
            "Извлеки из текста пользователя название папки, её цель и ключевые слова.\n"
            "Верни СТРОГО JSON: {\"name\": \"...\", \"description\": \"...\", \"keywords\": [\"...\"]}.\n"
            f"Текст: {user_text}"
        )
        msgs = [
            {"role": "system", "content": "Ты парсер пользовательских интентов. Отвечай только JSON."},
            {"role": "user", "content": prompt}
        ]
        
        if self.provider == "local":
            url = settings.LOCAL_LLM_URL
            model = settings.LOCAL_LLM_MODEL
        else:
            url = f"{settings.POLLINATIONS_BASE_URL}{settings.POLLINATIONS_CHAT_ENDPOINT}"
            model = settings.POLLINATIONS_MODEL
            
        headers = {"Content-Type": "application/json"}
        if settings.POLLINATIONS_API_KEY and self.provider != "local":
            headers["Authorization"] = f"Bearer {settings.POLLINATIONS_API_KEY}"
            
        try:
            r = await self.client.post(url, headers=headers, json={"model": model, "messages": msgs, "temperature": 0.1})
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("AI folder intent request failed: %s", e)
            raise
            
        raw = _extract_json(content)
        return FolderIntent.model_validate(json.loads(raw))
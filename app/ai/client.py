import json
import re
import httpx

from app.core.settings import settings
from app.ai.schemas import DeepSeekEmailClassification
from app.ai.prompts import build_messages

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

def _extract_json(text: str) -> str:
    text = text.strip()
    m = _CODE_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text


class DeepSeekClient:
    def __init__(self) -> None:
        self.api_key = settings.DEEPSEEK_API_KEY.strip()
        self.model = settings.DEEPSEEK_MODEL.strip()
        self.base_url = settings.DEEPSEEK_BASE_URL.strip().rstrip("/")
        self.endpoint = settings.DEEPSEEK_ENDPOINT.strip()
        self.verify_ssl = bool(settings.DEEPSEEK_VERIFY_SSL)

        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set in .env")

    @property
    def url(self) -> str:
        return f"{self.base_url}{self.endpoint}"

    async def classify_header(self, subject: str | None, from_email: str | None, received_at: str | None) -> DeepSeekEmailClassification:
        messages = build_messages(subject, from_email, received_at)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }

        async with httpx.AsyncClient(timeout=30.0, verify=self.verify_ssl) as client:
            r = await client.post(self.url, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()

        content = data["choices"][0]["message"]["content"]
        content = _extract_json(content)

        obj = json.loads(content)
        return DeepSeekEmailClassification.model_validate(obj)
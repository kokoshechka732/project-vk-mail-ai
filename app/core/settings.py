from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        extra="ignore",
    )

    VK_BOT_TOKEN: str
    DATABASE_URL: str
    FERNET_KEY: str = ""
    AI_PROVIDER: str = "pollinations"

    POLLINATIONS_API_KEY: str = ""
    POLLINATIONS_BASE_URL: str = "https://gen.pollinations.ai"
    POLLINATIONS_CHAT_ENDPOINT: str = "/v1/chat/completions"
    POLLINATIONS_MODEL: str = "openai"
    POLLINATIONS_VERIFY_SSL: bool = True

    LOCAL_LLM_URL: str = "http://localhost:11434/v1/chat/completions"
    LOCAL_LLM_MODEL: str = "phi3:mini"

    USER_TIMEZONE: str = "UTC"
    REMINDER_OFFSETS_MINUTES: list[int] = [-1440, -60, -15]  # 24ч, 1ч, 15мин до дедлайна
    REMINDER_TOLERANCE_SEC: int = 120                      # Окно срабатывания ±5 минут
    REMINDER_CHECK_INTERVAL_SEC: int = 180                # Часовой пояс пользователя
    
    @field_validator("FERNET_KEY")

    @classmethod
    def validate_fernet_key(cls, v):
        if not v or len(v.strip()) < 32:
            raise ValueError("❌ FERNET_KEY не указан или слишком короткий в .env!")
        return v.strip()

settings = Settings()
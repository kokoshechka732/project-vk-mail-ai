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
    
    # 🔑 Ключ шифрования (ОБЯЗАТЕЛЬНО в .env)
    FERNET_KEY: str = ""
    
    # 🤖 Выбор провайдера: "pollinations" (работает сейчас) или "local" (когда поднимешь Ollama)
    AI_PROVIDER: str = "pollinations"

    # 🌐 Pollinations AI
    POLLINATIONS_API_KEY: str = ""
    POLLINATIONS_BASE_URL: str = "https://gen.pollinations.ai"
    POLLINATIONS_CHAT_ENDPOINT: str = "/v1/chat/completions"
    POLLINATIONS_MODEL: str = "openai"
    POLLINATIONS_VERIFY_SSL: bool = True

    # 🏠 Локальная LLM (Ollama)
    LOCAL_LLM_URL: str = "http://localhost:11434/v1/chat/completions"
    LOCAL_LLM_MODEL: str = "phi3:mini"

    # ⏰ Напоминания
    REMINDER_CHECK_INTERVAL_SEC: int = 3600
    REMINDER_COOLDOWN_HOURS: int = 6

    @field_validator("FERNET_KEY")
    @classmethod
    def check_fernet_key(cls, v):
        if not v or len(v.strip()) < 32:
            raise ValueError("❌ FERNET_KEY не указан или слишком короткий в .env!")
        return v.strip()

settings = Settings()
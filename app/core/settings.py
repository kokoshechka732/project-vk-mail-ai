from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        extra="ignore",
    )

    VK_BOT_TOKEN: str
    DATABASE_URL: str

    # DeepSeek
    DEEPSEEK_API_KEY: str
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_ENDPOINT: str = "/chat/completions"
    DEEPSEEK_VERIFY_SSL: bool = True

settings = Settings()
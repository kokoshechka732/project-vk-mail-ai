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

    # YandexGPT
    YANDEX_API_KEY: str
    YANDEX_FOLDER_ID: str
    YANDEX_MODEL_NAME: str = "yandexgpt"
    YANDEX_MODEL_VERSION: str = "latest"
    YANDEX_ENDPOINT: str = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    YANDEX_VERIFY_SSL: bool = True


settings = Settings()
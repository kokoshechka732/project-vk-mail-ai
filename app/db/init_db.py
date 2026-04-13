import asyncio
from app.db.session import engine
from app.db.base import Base
import app.models  # noqa: F401

_schema_ready = False
_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def ensure_schema() -> None:
    """
    Создаёт таблицы один раз, в ТОМ ЖЕ event loop, где работает бот.
    Поэтому не будет ошибок "different loop".
    """
    global _schema_ready
    if _schema_ready:
        return

    async with _get_lock():
        if _schema_ready:
            return
        print("DB: creating tables (create_all)...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _schema_ready = True
        print("DB: schema ready")
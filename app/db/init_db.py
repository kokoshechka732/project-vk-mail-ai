from app.db.session import engine
from app.db.base import Base
from app.db import models  # важно: чтобы User импортировался и попал в metadata

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
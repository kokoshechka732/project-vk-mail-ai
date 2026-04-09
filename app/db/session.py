from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.settings import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionMaker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
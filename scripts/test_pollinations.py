import asyncio
from app.ai.client import PollinationsClient

async def main():
    c = PollinationsClient()
    r = await c.classify_email(
        subject="Срочно: дедлайн сдачи проекта завтра",
        from_email="teacher@university.edu",
        received_at="2026-04-13",
        body_snippet="Нужно сдать до завтра 23:59. В LMS уже открыт прием.",
        user_folders=[],
        user_rules=[],
    )
    print(r)

asyncio.run(main())
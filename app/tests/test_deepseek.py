import asyncio
from ai.client import DeepSeekClient

async def main():
    c = DeepSeekClient()
    r = await c.classify_header(
        subject="Срочно: дедлайн сдачи проекта завтра",
        from_email="teacher@university.edu",
        received_at="2026-04-13T10:00:00Z",
    )
    print(r)

asyncio.run(main())
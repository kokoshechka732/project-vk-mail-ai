from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_rule import CustomRule


class CustomRuleRepository:
    async def list_active_by_folder(self, session: AsyncSession, folder_id: int) -> list[CustomRule]:
        res = await session.execute(
            select(CustomRule)
            .where(CustomRule.folder_id == folder_id, CustomRule.is_active == True)  # noqa: E712
            .order_by(CustomRule.priority.asc(), CustomRule.id.asc())
        )
        return list(res.scalars().all())

    async def add_rule_if_missing(
        self,
        session: AsyncSession,
        user_id: int,
        folder_id: int,
        rule_text: str,
        priority: int = 100,
    ) -> bool:
        norm = (rule_text or "").strip()
        if not norm:
            return False

        # дедуп по точному совпадению текста (casefold)
        res = await session.execute(
            select(CustomRule.id).where(
                CustomRule.folder_id == folder_id,
                CustomRule.is_active == True,  # noqa: E712
                CustomRule.rule_text == norm,
            )
        )
        if res.scalar_one_or_none() is not None:
            return False

        obj = CustomRule(user_id=user_id, folder_id=folder_id, rule_text=norm, priority=priority, is_active=True)
        session.add(obj)
        await session.flush()
        return True
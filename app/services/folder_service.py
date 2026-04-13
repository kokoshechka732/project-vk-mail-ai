from __future__ import annotations

from dataclasses import dataclass

from app.db.init_db import ensure_schema
from app.db.session import AsyncSessionMaker
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.mail_account_repository import MailAccountRepository
from app.db.repositories.folder_repository import FolderRepository, SYSTEM_FOLDERS
from app.db.repositories.custom_rule_repository import CustomRuleRepository
from app.db.repositories.email_folder_link_repository import EmailFolderLinkRepository
from app.db.repositories.email_repository import EmailRepository


@dataclass
class GmailAccountInfo:
    email_address: str


class FolderService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.mail_repo = MailAccountRepository()
        self.folder_repo = FolderRepository()
        self.rule_repo = CustomRuleRepository()
        self.link_repo = EmailFolderLinkRepository()
        self.email_repo = EmailRepository()

    async def get_active_gmail_account(self, vk_user_id: int):
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return None
                return await self.mail_repo.get_active_gmail(session, user.id)

    async def get_folder_menu_info(self, vk_user_id: int) -> tuple[list[str], bool, str | None]:
        """
        Возвращает:
        - folder_names: системные + кастомная (если есть)
        - can_create_custom: можно ли создать кастомную
        - custom_name: имя кастомной (если есть)
        """
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return SYSTEM_FOLDERS[:], True, None

                await self.folder_repo.ensure_system_folders(session, user.id)
                custom = await self.folder_repo.get_custom_folder(session, user.id)

                folder_names = SYSTEM_FOLDERS[:]
                custom_name = None
                if custom:
                    custom_name = custom.name
                    folder_names.append(custom.name)

                can_create_custom = custom is None
                return folder_names, can_create_custom, custom_name

    async def create_custom_folder(self, vk_user_id: int, name: str) -> tuple[bool, str]:
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return False, "Сначала напиши «Начать»."

                await self.folder_repo.ensure_system_folders(session, user.id)
                ok, code, folder = await self.folder_repo.create_custom_folder(session, user.id, name=name)
                if not ok and code == "CUSTOM_EXISTS":
                    return False, f"Кастомная папка уже существует: «{folder.name}»"
                return True, f"Создал твою папку: «{name}». Теперь можешь добавить ключевые слова."

    async def add_keywords_to_custom_folder(self, vk_user_id: int, keywords: list[str]) -> tuple[bool, str]:
        """
        Добавляет ключевые слова к кастомной папке.
        Также делает backfill по последним письмам: если письмо подходит — добавляет линк в кастомную.
        """
        keywords = [k.strip() for k in (keywords or [])]
        keywords = [k for k in keywords if k]
        if not keywords:
            return False, "Не нашёл ключевых слов. Введи через запятую, например: invoice, оплата"

        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user:
                    return False, "Сначала напиши «Начать»."

                await self.folder_repo.ensure_system_folders(session, user.id)
                custom = await self.folder_repo.get_custom_folder(session, user.id)
                if not custom:
                    return False, "Сначала создай кастомную папку («Мои папки» → «Создать мою папку»)."

                added = 0
                for kw in keywords:
                    ok = await self.rule_repo.add_rule_if_missing(session, user.id, custom.id, kw)
                    if ok:
                        added += 1

                # backfill: пробегаем последние 300 писем и добавляем кастомную папку, если совпадает
                rules = await self.rule_repo.list_active_by_folder(session, custom.id)
                rule_texts = [r.rule_text for r in rules]

                emails = await self.email_repo.list_last(session, user.id, limit=300)
                backfilled = 0
                for e in emails:
                    if self._email_matches_keywords(e.subject, e.from_email, e.body_text, rule_texts):
                        ok2 = await self.link_repo.add_link_if_missing(session, e.id, custom.id)
                        if ok2:
                            backfilled += 1

                return True, f"Добавил ключевых слов: {added}. Обновил писем в папке по ключевым словам: {backfilled}."

    @staticmethod
    def _email_matches_keywords(subject: str | None, from_email: str | None, body_text: str | None, rule_texts: list[str]) -> bool:
        text = " ".join([subject or "", from_email or "", body_text or ""]).casefold()
        for kw in rule_texts:
            k = (kw or "").strip().casefold()
            if not k:
                continue
            if k in text:
                return True
        return False
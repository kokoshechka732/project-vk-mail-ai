from __future__ import annotations
import difflib
from app.db.init_db import ensure_schema
from app.db.session import AsyncSessionMaker
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.mail_account_repository import MailAccountRepository
from app.db.repositories.folder_repository import FolderRepository, SYSTEM_FOLDERS, MAX_CUSTOM_FOLDERS
from app.db.repositories.custom_rule_repository import CustomRuleRepository
from app.db.repositories.email_folder_link_repository import EmailFolderLinkRepository
from app.db.repositories.email_repository import EmailRepository

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
                if not user: return None
                return await self.mail_repo.get_active_gmail(session, user.id)

    async def get_folder_menu_info(self, vk_user_id: int) -> tuple[list[str], bool, list[str]]:
        """Возвращает: [все_папки, можно_создать, список_кастомных_папок]"""
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user: return SYSTEM_FOLDERS[:], True, []
                await self.folder_repo.ensure_system_folders(session, user.id)
                custom_folders = await self.folder_repo.get_custom_folders(session, user.id)
                folder_names = SYSTEM_FOLDERS[:] + [f.name for f in custom_folders]
                can_create = await self.folder_repo.count_custom_folders(session, user.id) < MAX_CUSTOM_FOLDERS
                return folder_names, can_create, [f.name for f in custom_folders]

    async def create_custom_folder_ai(self, vk_user_id: int, intent_name: str, intent_desc: str, intent_keywords: list[str]) -> tuple[bool, str]:
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user: return False, "Сначала напиши «Начать»."
                await self.folder_repo.ensure_system_folders(session, user.id)
                
                count = await self.folder_repo.count_custom_folders(session, user.id)
                if count >= MAX_CUSTOM_FOLDERS:
                    return False, f"❌ Лимит достигнут: {MAX_CUSTOM_FOLDERS} кастомных папки."
                
                existing = await self.folder_repo.list_by_user(session, user.id)
                existing_names = [f.name.strip().casefold() for f in existing]
                new_norm = intent_name.strip().casefold()
                
                if new_norm in existing_names:
                    return False, f"❌ Папка «{intent_name}» уже существует."
                for ex in existing_names:
                    if difflib.SequenceMatcher(None, new_norm, ex).ratio() > 0.85:
                        return False, f"⚠️ Название слишком похоже на «{ex}». Уточните."
                
                folder = await self.folder_repo.create(session, user.id, name=intent_name, is_system=False)
                await self.folder_repo.update_description(session, folder.id, intent_desc)
                for kw in intent_keywords:
                    await self.rule_repo.add_rule_if_missing(session, user.id, folder.id, kw)
                return True, f"✅ Создал папку «{intent_name}».\n📝 {intent_desc}"

    async def delete_custom_folder(self, vk_user_id: int, folder_id: int) -> bool:
        await ensure_schema()
        async with AsyncSessionMaker() as session:
            async with session.begin():
                user = await self.user_repo.get_by_vk_id(session, vk_user_id)
                if not user: return False
                return await self.folder_repo.delete_custom_folder(session, user.id, folder_id)
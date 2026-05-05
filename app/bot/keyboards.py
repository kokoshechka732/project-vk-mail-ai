from vkbottle import Keyboard, Text, KeyboardButtonColor

def _safe_label(text: str, max_len: int = 38) -> str:
    """Жёсткая защита от VK API лимита 40 символов"""
    return (text or "")[:max_len].strip()

def main_menu_json() -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text(_safe_label("Подключить Gmail")), color=KeyboardButtonColor.PRIMARY)
    # 🔽 Кнопка "Проверить почту" удалена (сканирование фоновое)
    kb.row()
    kb.add(Text(_safe_label("Мои папки")), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text(_safe_label("Дайджест")), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text(_safe_label("Помощь")), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()

def email_nav_json(total: int, current: int) -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text(f"{current+1}/{total}"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("Далее"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    # 🔽 Заглушка и ссылка удалены. Теперь всегда кнопка возврата.
    kb.add(Text("Папки"), color=KeyboardButtonColor.POSITIVE)
    return kb.get_json()

def cancel_menu_json() -> str:
    return Keyboard(one_time=False).add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE).get_json()

def yes_no_menu_json() -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Да"), color=KeyboardButtonColor.POSITIVE)
    kb.add(Text("Нет"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()

def folders_menu_json(names: list[str], can_create: bool) -> str:
    kb = Keyboard(one_time=False)
    for i, n in enumerate(names):
        kb.add(Text(_safe_label(n)), color=KeyboardButtonColor.PRIMARY)
        if i % 2 == 1: kb.row()
    if can_create:
        kb.row().add(Text("Создать папку"), color=KeyboardButtonColor.POSITIVE)
    kb.row().add(Text("Назад в меню"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()

def custom_folder_actions_json(name: str) -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text(_safe_label(f"Открыть: {name}")), color=KeyboardButtonColor.PRIMARY).row()
    kb.add(Text("Удалить папку"), color=KeyboardButtonColor.NEGATIVE).row()
    kb.add(Text("Назад к папкам"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()

def email_nav_json(total: int, current: int) -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text(f"{current+1}/{total}"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("Далее"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    # 🔽 Вместо заглушки/ссылки теперь всегда кнопка возврата в папки
    kb.add(Text("Папки"), color=KeyboardButtonColor.POSITIVE)
    return kb.get_json()
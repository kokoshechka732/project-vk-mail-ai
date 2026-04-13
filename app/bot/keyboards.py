from __future__ import annotations

from vkbottle import Keyboard, Text, KeyboardButtonColor


def main_menu_json() -> str:
    kb = Keyboard(one_time=False)

    kb.add(Text("Подключить Gmail"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("Проверить почту"), color=KeyboardButtonColor.PRIMARY)
    kb.row()

    kb.add(Text("Мой Gmail"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("Мои папки"), color=KeyboardButtonColor.SECONDARY)
    kb.row()

    kb.add(Text("Дайджест"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("Помощь"), color=KeyboardButtonColor.SECONDARY)

    return kb.get_json()


def cancel_menu_json() -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()


def yes_no_menu_json() -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Да"), color=KeyboardButtonColor.POSITIVE)
    kb.add(Text("Нет"), color=KeyboardButtonColor.NEGATIVE)
    kb.row()
    kb.add(Text("Отмена"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()


def folders_menu_json(folder_names: list[str], can_create_custom: bool) -> str:
    """
    Динамическое меню папок.
    folder_names: имена папок (системные + кастомная если есть)
    can_create_custom: если True — показываем кнопку создания кастомной папки
    """
    kb = Keyboard(one_time=False)

    # Кнопки папок (по 2 в ряд)
    for i, name in enumerate(folder_names):
        kb.add(Text(name), color=KeyboardButtonColor.PRIMARY)
        if i % 2 == 1:
            kb.row()
    if len(folder_names) % 2 == 1:
        kb.row()

    if can_create_custom:
        kb.add(Text("Создать мою папку"), color=KeyboardButtonColor.POSITIVE)
        kb.row()

    kb.add(Text("Назад в меню"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()


def custom_folder_actions_json(custom_folder_name: str) -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text(f"Показать: {custom_folder_name}"), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text(f"Добавить ключевые слова: {custom_folder_name}"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text("Назад к папкам"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()
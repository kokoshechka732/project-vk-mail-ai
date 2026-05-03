from vkbottle import Keyboard, Text, KeyboardButtonColor

def main_menu_json() -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Подключить Gmail"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("Проверить почту"), color=KeyboardButtonColor.POSITIVE)
    kb.row()
    kb.add(Text("Мои папки"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("Дайджест"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text("Помощь"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()

def cancel_menu_json() -> str:
    # Исправлено: one_one -> one_time
    return Keyboard(one_time=False).add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE).get_json()

def yes_no_menu_json() -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Да"), color=KeyboardButtonColor.POSITIVE)
    kb.add(Text("Нет"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()

def folders_menu_json(names: list[str], can_create: bool) -> str:
    kb = Keyboard(one_time=False)
    for i, n in enumerate(names):
        kb.add(Text(n), color=KeyboardButtonColor.PRIMARY)
        if i % 2 == 1: kb.row()
    if can_create:
        kb.row().add(Text("Создать мою папку"), color=KeyboardButtonColor.POSITIVE)
    kb.row().add(Text("Назад в меню"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()

def custom_folder_actions_json(name: str) -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text(f"Показать: {name}"), color=KeyboardButtonColor.PRIMARY).row()
    kb.add(Text(f"Ключевые слова: {name}"), color=KeyboardButtonColor.SECONDARY).row()
    kb.add(Text("Назад к папкам"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()
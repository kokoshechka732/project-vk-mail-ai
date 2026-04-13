from vkbottle import Keyboard, Text, KeyboardButtonColor

FOLDERS = ["Важное", "Учёба", "Стажировки", "Рассылки", "Несортированное"]


def main_menu_json() -> str:
    kb = Keyboard(one_time=False)

    kb.add(Text("Подключить Gmail"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("Проверить почту"), color=KeyboardButtonColor.PRIMARY)
    kb.row()

    kb.add(Text("Мой Gmail"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("Мои папки"), color=KeyboardButtonColor.SECONDARY)
    kb.row()

    kb.add(Text("25"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("DEBUG: письма"), color=KeyboardButtonColor.SECONDARY)
    kb.row()

    kb.add(Text("Дайджест"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("Помощь"), color=KeyboardButtonColor.SECONDARY)

    return kb.get_json()


def cancel_menu_json() -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()


def folders_menu_json() -> str:
    kb = Keyboard(one_time=False)

    kb.add(Text("Важное"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("Учёба"), color=KeyboardButtonColor.PRIMARY)
    kb.row()

    kb.add(Text("Стажировки"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("Рассылки"), color=KeyboardButtonColor.PRIMARY)
    kb.row()

    kb.add(Text("Несортированное"), color=KeyboardButtonColor.PRIMARY)
    kb.row()

    kb.add(Text("Назад в меню"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)

    return kb.get_json()
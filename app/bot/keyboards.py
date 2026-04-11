from vkbottle import Keyboard, Text, KeyboardButtonColor


def main_menu_json() -> str:
    kb = Keyboard(one_time=False)

    kb.add(Text("Подключить Gmail"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("Проверить почту"), color=KeyboardButtonColor.PRIMARY)
    kb.row()

    kb.add(Text("Мой Gmail"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("Дайджест"), color=KeyboardButtonColor.SECONDARY)
    kb.row()

    kb.add(Text("Помощь"), color=KeyboardButtonColor.SECONDARY)

    return kb.get_json()


def cancel_menu_json() -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()
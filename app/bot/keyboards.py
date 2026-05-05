from vkbottle import Keyboard, Text, KeyboardButtonColor

def _safe_label(text: str, max_len: int = 38) -> str:
    return (text or "")[:max_len].strip()

def main_menu_json() -> str:
    kb = Keyboard(one_time=False)
    # Строка 1: Одна большая кнопка
    kb.add(Text("Мои папки"), color=KeyboardButtonColor.POSITIVE)
    kb.row() # Переход на новую строку
    
    # Строка 2: Две кнопки поровну
    kb.add(Text("Мой Gmail"), color=KeyboardButtonColor.SECONDARY)
    kb.add(Text("Дедлайны"), color=KeyboardButtonColor.PRIMARY)
    kb.row() # Переход на новую строку
    
    # Строка 3: Две кнопки поровну
    kb.add(Text("Дайджест"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("Инструкция"), color=KeyboardButtonColor.SECONDARY)
    
    return kb.get_json()

def email_nav_json(total: int, current: int) -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    # Кнопка с номером, по которой можно нажать для перехода к произвольному сообщению
    kb.add(Text(f"{current+1}/{total}"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("Далее"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text("В папки"), color=KeyboardButtonColor.POSITIVE)
    return kb.get_json()

# ✅ НОВАЯ ФУНКЦИЯ: Клавиатура для ввода номера сообщения
def jump_to_email_json(total: int) -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
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
        # Если кнопок много, делаем перенос каждые 2 кнопки для красоты
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

def app_password_intro_json() -> str:
    kb = Keyboard(one_time=False)
    kb.add(Text("Понятно, я готов"), color=KeyboardButtonColor.POSITIVE)
    kb.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()
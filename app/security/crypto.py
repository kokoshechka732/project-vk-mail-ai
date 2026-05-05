from cryptography.fernet import Fernet, InvalidToken
from app.core.settings import settings

_cipher: Fernet | None = None

def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is None:
        key = settings.FERNET_KEY
        if not key:
            raise RuntimeError("❌ FERNET_KEY не найден в .env!")
        _cipher = Fernet(key.encode())
    return _cipher

def encrypt(text: str) -> str:
    if not text: return ""
    return _get_cipher().encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    if not token: return ""
    try:
        return _get_cipher().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("Неверный ключ шифрования или повреждённые данные в БД.")
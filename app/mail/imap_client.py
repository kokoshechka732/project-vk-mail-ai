import asyncio
import imaplib
import logging
import re
import time
from typing import List, Tuple
from functools import wraps

GMAIL_HOST = "imap.gmail.com"
GMAIL_PORT = 993
logger = logging.getLogger("imap")

# Максимальное количество попыток подключения
MAX_RETRIES = 2
RETRY_DELAY_SEC = 2

def retry_imap(func):
    """Декоратор для повторных попыток при сетевых ошибках"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        last_exception = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except (imaplib.IMAP4.error, OSError, ConnectionError, Exception) as e:
                # Проверяем, похоже ли это на ошибку сети/сокета
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ['eof', 'socket', 'connection', 'timed out', 'broken pipe']):
                    last_exception = e
                    if attempt < MAX_RETRIES:
                        logger.warning(f"IMAP network error on attempt {attempt+1}/{MAX_RETRIES}: {e}. Retrying in {RETRY_DELAY_SEC}s...")
                        time.sleep(RETRY_DELAY_SEC)
                    else:
                        logger.error(f"IMAP failed after {MAX_RETRIES} retries: {e}")
                        raise
                else:
                    # Ошибка авторизации или другая критическая - не повторяем
                    raise
        raise last_exception
    return wrapper

def _check_gmail_imap_sync(email: str, password: str) -> tuple[bool, str]:
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=30)
        mail.login(email, password)
        status, _ = mail.select("INBOX")
        if status != "OK":
            return False, "INBOX_ACCESS_DENIED"
        return True, "OK"
    except imaplib.IMAP4.error as e:
        logger.warning("IMAP login error for %s: %s", email, e)
        return False, "AUTH_ERROR"
    except Exception as e:
        logger.error("IMAP check failed for %s: %s", email, e)
        return False, "UNKNOWN_ERROR"
    finally:
        if mail:
            try: mail.logout()
            except: pass

async def check_gmail_imap(email: str, password: str) -> tuple[bool, str]:
    return await asyncio.to_thread(_check_gmail_imap_sync, email, password)

def _extract_uid_from_meta(meta: bytes) -> int:
    match = re.search(rb"UID\s+(\d+)", meta)
    return int(match.group(1)) if match else 0

def _clean_uids(uid_list: list[bytes]) -> list[str]:
    """Фильтрует UID: оставляет только валидные целые числа."""
    cleaned = []
    for uid in uid_list:
        decoded = uid.decode("ascii", errors="replace").strip()
        if decoded.isdigit():
            cleaned.append(decoded)
    return cleaned

@retry_imap
def _fetch_preview_by_uids_sync(email: str, password: str, uid_list: list[bytes], max_messages: int = 200) -> List[Tuple[int, bytes, bytes]]:
    if not uid_list:
        return []
    
    valid_uids = _clean_uids(uid_list)
    if not valid_uids:
        return []
        
    if len(valid_uids) > max_messages:
        valid_uids = valid_uids[-max_messages:]
        
    mail = None
    out: List[Tuple[int, bytes, bytes]] = []
    
    try:
        mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=90)
        mail.login(email, password)
        
        # Важно: перед каждым select нужно убедиться, что мы не в режиме другого ящика
        status, _ = mail.select("INBOX")
        if status != "OK":
            logger.error("❌ INBOX select failed for %s", email)
            return []
            
        # Уменьшаем чанк до 5 для большей стабильности и снижения нагрузки
        chunk_size = 5 
        
        for i in range(0, len(valid_uids), chunk_size):
            chunk = valid_uids[i:i+chunk_size]
            uid_str = " ".join(chunk).strip()
            if not uid_str:
                continue
                
            try:
                status, data = mail.uid("fetch", uid_str, "(RFC822)")
                if status != "OK" or not data:
                    logger.warning("⚠️ Fetch returned non-OK for chunk starting at UID %s", chunk[0])
                    continue
                    
                for item in data:
                    if not isinstance(item, tuple) or len(item) < 2:
                        continue
                    meta, raw_msg = item
                    if not isinstance(raw_msg, bytes) or not raw_msg:
                        continue
                    uid_val = _extract_uid_from_meta(meta)
                    out.append((uid_val, raw_msg, b""))
                    
            except imaplib.IMAP4.error as e:
                logger.warning("⚠️ IMAP UID fetch error for %s: %s | Skipping chunk...", email, e)
                continue
                
    except Exception as e:
        logger.error("💥 IMAP connection/fetch error for %s: %s", email, e)
        # Декоратор retry_imap обработает этот исключение и попробует снова
        raise 
    finally:
        if mail:
            try: 
                mail.close() # Закрываем выбор папки
                mail.logout() # Закрываем соединение
            except Exception:
                pass
                
    return out

@retry_imap
def _fetch_last_n_gmail_preview_sync(email: str, password: str, n: int) -> List[Tuple[int, bytes, bytes]]:
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=90)
        mail.login(email, password)
        
        status, _ = mail.select("INBOX")
        if status != "OK":
            logger.error("❌ INBOX select failed for %s", email)
            return []
            
        status, data = mail.uid("search", None, "ALL")
        if status != "OK" or not data or not data[0]:
            return []
            
        all_uids = data[0].split()
        target = all_uids[-n:] if len(all_uids) > n else all_uids
        
        # Рекурсивный вызов через обертку, чтобы использовать retry логику и правильное закрытие
        return _fetch_preview_by_uids_sync(email, password, target, max_messages=n)
        
    except Exception as e:
        logger.error("❌ Fetch last %s failed for %s: %s", n, email, e)
        raise
    finally:
        if mail:
            try: 
                mail.close()
                mail.logout()
            except: pass

async def fetch_last_n_gmail_preview(email: str, password: str, n: int = 25) -> List[Tuple[int, bytes, bytes]]:
    return await asyncio.to_thread(_fetch_last_n_gmail_preview_sync, email, password, n)

@retry_imap
def _fetch_since_uid_sync(email: str, password: str, since_uid: int, max_messages: int = 200) -> List[Tuple[int, bytes, bytes]]:
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=90)
        mail.login(email, password)
        
        status, _ = mail.select("INBOX")
        if status != "OK":
            logger.error("❌ INBOX select failed for %s", email)
            return []
            
        start_uid = max(1, int(since_uid) + 1)
        status, data = mail.uid("search", None, f"UID {start_uid}:*")
        
        if status != "OK" or not data or not data[0]:
            return []
            
        uids = data[0].split()
        
        # Передаем в функцию, которая умеет работать чанками и имеет retry
        return _fetch_preview_by_uids_sync(email, password, uids, max_messages=max_messages)
        
    except Exception as e:
        logger.error("❌ Fetch since UID failed for %s: %s", email, e)
        raise
    finally:
        if mail:
            try: 
                mail.close()
                mail.logout()
            except: pass

async def fetch_since_uid_gmail_preview(email: str, password: str, since_uid: int, max_messages: int = 200) -> List[Tuple[int, bytes, bytes]]:
    return await asyncio.to_thread(_fetch_since_uid_sync, email, password, since_uid, max_messages)
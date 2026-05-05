import asyncio
import imaplib
import logging
import re
from typing import List, Tuple

GMAIL_HOST = "imap.gmail.com"
GMAIL_PORT = 993
logger = logging.getLogger("imap")

def _check_gmail_imap_sync(email: str, password: str) -> tuple[bool, str]:
    try:
        mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=30)
        mail.login(email, password)
        status, _ = mail.select("INBOX")
        if status != "OK":
            mail.logout()
            return False, "INBOX_ACCESS_DENIED"
        mail.logout()
        return True, "OK"
    except imaplib.IMAP4.error as e:
        logger.warning("IMAP login error for %s: %s", email, e)
        return False, "AUTH_ERROR"
    except Exception as e:
        logger.error("IMAP check failed for %s: %s", email, e)
        return False, "UNKNOWN_ERROR"

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

def _fetch_preview_by_uids_sync(email: str, password: str, uid_list: list[bytes], max_messages: int = 200) -> List[Tuple[int, bytes, bytes]]:
    if not uid_list:
        return []

    valid_uids = _clean_uids(uid_list)
    if not valid_uids:
        return []

    if len(valid_uids) > max_messages:
        valid_uids = valid_uids[-max_messages:]

    mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=90)
    out: List[Tuple[int, bytes, bytes]] = []
    try:
        mail.login(email, password)
        status, _ = mail.select("INBOX")
        if status != "OK":
            logger.error("❌ INBOX select failed for %s", email)
            return []

        # Уменьшаем чанк до 10 для стабильности парсера Gmail
        for i in range(0, len(valid_uids), 10):
            chunk = valid_uids[i:i+10]
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
                logger.warning("⚠️ IMAP UID fetch error for %s: %s | Fallback to single UID...", email, e)
                for u in chunk:
                    try:
                        st, dt = mail.uid("fetch", u, "(RFC822)")
                        if st == "OK" and dt:
                            for it in dt:
                                if isinstance(it, tuple) and len(it) >= 2:
                                    m, r = it
                                    if isinstance(r, bytes) and r:
                                        out.append((_extract_uid_from_meta(m), r, b""))
                    except Exception:
                        pass
            except Exception as e:
                logger.warning("⚠️ Chunk fetch failed for %s: %s", email, e)
    except Exception as e:
        logger.error("💥 IMAP connection error for %s: %s", email, e)
    finally:
        try: mail.logout()
        except: pass
    return out

def _fetch_last_n_gmail_preview_sync(email: str, password: str, n: int) -> List[Tuple[int, bytes, bytes]]:
    mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=90)
    try:
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
        return _fetch_preview_by_uids_sync(email, password, target, max_messages=n)
    except Exception as e:
        logger.error("❌ Fetch last %s failed for %s: %s", n, email, e)
        return []
    finally:
        try: mail.logout()
        except: pass

async def fetch_last_n_gmail_preview(email: str, password: str, n: int = 25) -> List[Tuple[int, bytes, bytes]]:
    return await asyncio.to_thread(_fetch_last_n_gmail_preview_sync, email, password, n)

def _fetch_since_uid_sync(email: str, password: str, since_uid: int, max_messages: int = 200) -> List[Tuple[int, bytes, bytes]]:
    mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=90)
    try:
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
        return _fetch_preview_by_uids_sync(email, password, uids, max_messages=max_messages)
    except Exception as e:
        logger.error("❌ Fetch since UID failed for %s: %s", email, e)
        return []
    finally:
        try: mail.logout()
        except: pass

async def fetch_since_uid_gmail_preview(email: str, password: str, since_uid: int, max_messages: int = 200) -> List[Tuple[int, bytes, bytes]]:
    return await asyncio.to_thread(_fetch_since_uid_sync, email, password, since_uid, max_messages)
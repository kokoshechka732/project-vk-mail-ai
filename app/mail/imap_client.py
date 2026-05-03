import asyncio
import imaplib
import socket
from typing import List, Tuple, Optional

GMAIL_HOST = "imap.gmail.com"
GMAIL_PORT = 993


def _check_gmail_imap_sync(email: str, password: str) -> tuple[bool, str]:
    try:
        mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=30)
        mail.login(email, password)
        mail.select("INBOX")
        mail.logout()
        return True, "OK"
    except imaplib.IMAP4.error:
        return False, "AUTH_ERROR"
    except (socket.timeout, TimeoutError):
        return False, "TIMEOUT"
    except Exception:
        return False, "UNKNOWN_ERROR"


async def check_gmail_imap(email: str, password: str) -> tuple[bool, str]:
    return await asyncio.to_thread(_check_gmail_imap_sync, email, password)



# Замените _fetch_preview_by_uids_sync на:
def _fetch_preview_by_uids_sync(email: str, password: str, uid_list: list[bytes], max_messages: int = 200) -> List[Tuple[int, bytes, bytes]]:
    if not uid_list: return []
    if len(uid_list) > max_messages: uid_list = uid_list[-max_messages:]
    
    mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=90)
    try:
        mail.login(email, password)
        mail.select("INBOX")
        out: List[Tuple[int, bytes, bytes]] = []
        
        # Группируем по 50 для стабильности
        for i in range(0, len(uid_list), 50):
            chunk = uid_list[i:i+50]
            try:
                st, data = mail.uid("fetch", b" ".join(chunk), "(RFC822.HEADER BODY[TEXT])")
                if st != "OK" or not data: continue
                for item in data:
                    if not isinstance(item, tuple) or len(item) < 2: continue
                    meta, payload = item
                    uid = int(meta.split()[0]) if meta else 0
                    out.append((uid, payload or b"", b""))
            except Exception: continue
    finally:
        try: mail.logout()
        except: pass
    return out

def _fetch_last_n_gmail_preview_sync(email: str, password: str, n: int) -> List[Tuple[int, bytes, bytes]]:
    mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=90)
    mail.login(email, password)
    mail.select("INBOX")

    status, data = mail.uid("search", None, "ALL")
    if status != "OK":
        mail.logout()
        return []

    uids = data[0].split() if data and data[0] else []
    last_uids = uids[-n:] if len(uids) > n else uids
    mail.logout()

    return _fetch_preview_by_uids_sync(email, password, last_uids, max_messages=n)


async def fetch_last_n_gmail_preview(email: str, password: str, n: int = 25) -> List[Tuple[int, bytes, bytes]]:
    return await asyncio.to_thread(_fetch_last_n_gmail_preview_sync, email, password, n)


def _fetch_since_uid_sync(
    email: str,
    password: str,
    since_uid: int,
    max_messages: int = 200,
) -> List[Tuple[int, bytes, bytes]]:
    mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=90)
    mail.login(email, password)
    mail.select("INBOX")

    start_uid = max(1, int(since_uid) + 1)
    status, data = mail.uid("search", None, f"UID {start_uid}:*")
    if status != "OK":
        mail.logout()
        return []

    uids = data[0].split() if data and data[0] else []
    mail.logout()

    return _fetch_preview_by_uids_sync(email, password, uids, max_messages=max_messages)


async def fetch_since_uid_gmail_preview(
    email: str,
    password: str,
    since_uid: int,
    max_messages: int = 200,
) -> List[Tuple[int, bytes, bytes]]:
    return await asyncio.to_thread(_fetch_since_uid_sync, email, password, since_uid, max_messages)
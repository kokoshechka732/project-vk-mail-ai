import asyncio
import imaplib
import socket
from typing import List, Tuple

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


def _fetch_last_n_gmail_headers_sync(email: str, password: str, n: int, prefer_unseen: bool) -> List[Tuple[int, bytes]]:
    mail = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT, timeout=60)
    mail.login(email, password)
    mail.select("INBOX")

    uids: list[bytes] = []

    if prefer_unseen:
        status, data = mail.uid("search", None, "UNSEEN")
        if status == "OK" and data and data[0]:
            uids = data[0].split()

    if not uids:
        status, data = mail.uid("search", None, "ALL")
        if status != "OK":
            mail.logout()
            return []
        uids = data[0].split() if data and data[0] else []

    last_uids = uids[-n:] if len(uids) > n else uids

    out: List[Tuple[int, bytes]] = []
    for uid_b in last_uids:
        uid = int(uid_b)
        try:
            st, msg_data = mail.uid(
                "fetch",
                uid_b,
                "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])"
            )
            if st == "OK" and msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                out.append((uid, msg_data[0][1]))
        except (socket.timeout, TimeoutError):
            continue
        except Exception:
            continue

    mail.logout()
    return out


async def fetch_last_n_gmail(email: str, password: str, n: int = 10) -> List[Tuple[int, bytes]]:
    # для сохранения в БД: предпочитаем UNSEEN
    return await asyncio.to_thread(_fetch_last_n_gmail_headers_sync, email, password, n, True)


async def fetch_last_n_gmail_all(email: str, password: str, n: int = 50) -> List[Tuple[int, bytes]]:
    # для DEBUG: просто последние N из ALL
    return await asyncio.to_thread(_fetch_last_n_gmail_headers_sync, email, password, n, False)
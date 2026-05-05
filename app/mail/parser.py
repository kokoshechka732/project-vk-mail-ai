from email import message_from_bytes
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
import logging
from email import message_from_bytes
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime

logger = logging.getLogger("parser")  

def _decode_header(value: str | None) -> str | None:
    if not value:
        return None
    parts = decode_header(value)
    out = ""
    for text, enc in parts:
        if isinstance(text, bytes):
            out += text.decode(enc or "utf-8", errors="replace")
        else:
            out += text
    out = out.strip()
    return out or None


def _decode_text_bytes(b: bytes) -> str:
    if not b:
        return ""
    try:
        return b.decode("utf-8", errors="replace")
    except Exception:
        return b.decode("latin-1", errors="replace")


def _make_preview(text: str, max_lines: int = 20, max_chars: int = 1200) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    lines = lines[:max_lines]
    preview = "\n".join(lines).strip()
    if len(preview) > max_chars:
        preview = preview[:max_chars].rstrip() + "..."
    return preview


def parse_email_preview(raw_message_bytes: bytes, _unused: bytes) -> dict:
    if not raw_message_bytes:
        return {"message_id": None, "subject": None, "from_email": None, "received_at": None, "body_text": None, "has_attachments": False}
        
    try:
        msg = message_from_bytes(raw_message_bytes)
    except Exception as e:
        logger.error("Failed to parse RFC822: %s", e)
        return {"message_id": None, "subject": None, "from_email": None, "received_at": None, "body_text": None, "has_attachments": False}

    subject = _decode_header(msg.get("Subject"))
    message_id = msg.get("Message-ID")
    _, from_addr = parseaddr(msg.get("From", ""))
    from_email = from_addr or None
    
    received_at = None
    raw_date = msg.get("Date")
    if raw_date:
        try: received_at = parsedate_to_datetime(raw_date)
        except: pass
        
    body_text = None
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                body_text = _decode_text_bytes(payload)
                break
        elif content_type == "text/html" and not body_text:
            payload = part.get_payload(decode=True)
            if payload:
                body_text = _decode_text_bytes(payload)
                break
                
    return {
        "message_id": message_id,
        "subject": subject,
        "from_email": from_email,
        "received_at": received_at,
        "body_text": _make_preview(body_text or ""),
        "has_attachments": any(p.get_filename() for p in msg.walk()),
    }
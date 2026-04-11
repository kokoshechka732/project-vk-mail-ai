from email import message_from_bytes
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime


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


def parse_email(raw_bytes: bytes) -> dict:
    msg = message_from_bytes(raw_bytes)

    subject = _decode_header(msg.get("Subject"))
    message_id = msg.get("Message-ID")

    _name, from_addr = parseaddr(msg.get("From", ""))
    from_email = from_addr or None

    # date
    received_at = None
    raw_date = msg.get("Date")
    if raw_date:
        try:
            received_at = parsedate_to_datetime(raw_date)
        except Exception:
            received_at = None

    # body (на День 2 мы качаем только headers → тела нет)
    body_text = None
    has_attachments = False

    if msg.is_multipart():
        for part in msg.walk():
            disp = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                has_attachments = True
                continue

            ctype = part.get_content_type()
            if ctype == "text/plain" and body_text is None:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                body_text = payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        body_text = payload.decode(charset, errors="replace")

    return {
        "message_id": message_id,
        "subject": subject,
        "from_email": from_email,
        "received_at": received_at,
        "body_text": None,
        "has_attachments": False,
    }
"""
J.E.N.N.Y - Email integration (IMAP with Outlook COM fallback)

Reads the latest emails from your mailbox so "check my emails" actually works
instead of dumping you into a web tab. Two backends, tried in order:

  1. IMAP  - uses keys.json `email_user` / `email_pass` / `email_imap_host`
             (host defaults to imap.gmail.com; leave port on 993). Works with
             Gmail, Outlook Live, Yahoo, any IMAP server.
  2. OUTLOOK COM - the classic Windows desktop Outlook app (win32com), hands
             off without any credentials.
  3. Otherwise -> friendly unconfigured message.

Return shape mirrors what the Emails panel expects:
    {"success": bool, "emails": [{from, subject, date, snippet}], "message": str}
"""

from __future__ import annotations

import base64
import datetime
import email
import imaplib
import json
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


def _load_keys() -> dict:
    try:
        return json.loads((DATA_DIR / "keys.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _decode_words(words) -> str:
    """Decode RFC2047 encoded-words into plain text."""
    parts = []
    for part, charset in words or []:
        if isinstance(part, bytes):
            try:
                parts.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                parts.append(part.decode("utf-8", errors="replace"))
        else:
            parts.append(str(part))
    return "".join(parts).strip()


def _clean_addr(raw: str, fallback: str = "Unknown") -> str:
    """Extract a friendly display name / address from an Email header."""
    if not raw:
        return fallback
    words = decode_header(raw)
    name = _decode_words(words)
    name = name.replace("\r\n", " ").strip()
    if name and "@" not in name:
        return name
    if name:
        return name
    return fallback


def _date_fmt(raw: str) -> str:
    try:
        dt = parsedate_to_datetime(raw)
        if dt:
            now = datetime.datetime.now(dt.tzinfo)
            diff = (now - dt).total_seconds()
            if diff < 3600:
                return "just now"
            if diff < 86400:
                return f"{int(diff // 3600)}h ago"
            if diff < 86400 * 30:
                return f"{int(diff // 86400)}d ago"
            return dt.strftime("%b %d, %Y")
    except Exception:
        pass
    return (raw or "")[:30]


def _snippet(text: str, limit: int = 140) -> str:
    text = (text or "").replace("\r\n", " ").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _iter_imap(cn, box: str, count: int):
    """Yield up to `count` messages from the given IMAP folder."""
    status, mdata = cn.select(box, readonly=True)
    if status != "OK":
        return
    status, numbers = cn.search(None, "ALL")
    if status != "OK" or not numbers or not numbers[0]:
        return
    ids = numbers[0].split()
    ids = ids[-count:] if count else ids
    for num in reversed(ids):
        try:
            status, msgdata = cn.fetch(num, "(RFC822)")
            if status != "OK" or not msgdata or not msgdata[0]:
                continue
            raw = msgdata[0][1]
            m = email.message_from_bytes(raw)
            yield m
        except Exception:
            continue


def fetch_emails_imap(count: int = 8) -> tuple[bool, list, str]:
    keys = _load_keys()
    user = str(keys.get("email_user") or keys.get("email_address") or "").strip()
    pwd = str(keys.get("email_pass") or keys.get("email_password") or "").strip()
    if not user or not pwd:
        return False, [], "Email not configured. Add email_user / email_pass (and optional email_imap_host) to data/keys.json."
    host = str(keys.get("email_imap_host") or "imap.gmail.com").strip()
    port = int(keys.get("email_imap_port") or 993)
    try:
        cn = imaplib.IMAP4_SSL(host, port, timeout=30)
        cn.login(user, pwd)
        emails = []
        for m in _iter_imap(cn, "INBOX", count):
            subj = _clean_addr(m.get("Subject", "")) or "(no subject)"
            fr = _clean_addr(m.get("From", ""))
            date = _date_fmt(m.get("Date", ""))
            body_txt = ""
            if m.is_multipart():
                for part in m.walk():
                    if part.get_content_type() == "text/plain" and "attachment" not in (part.get("Content-Disposition") or ""):
                        try:
                            body_txt = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                            break
                        except Exception:
                            continue
            else:
                try:
                    body_txt = m.get_payload(decode=True).decode(m.get_content_charset() or "utf-8", errors="replace")
                except Exception:
                    body_txt = ""
            emails.append({"from": fr, "subject": subj, "date": date, "snippet": _snippet(body_txt)})
        try:
            cn.logout()
        except Exception:
            pass
        return (True, emails, f"Found {len(emails)} recent emails.") if emails else (True, [], "Inbox is empty.")
    except Exception as e:
        return False, [], f"IMAP connection failed: {_safe_err(e)}"


def _safe_err(e: Exception) -> str:
    s = str(e) or e.__class__.__name__
    lines = [l for l in s.splitlines() if l.strip()][:3]
    return " — ".join(lines)[:160]


def fetch_emails_outlook(count: int = 8) -> tuple[bool, list, str]:
    """Read the latest items from the Windows desktop Outlook app (win32com)."""
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6)  # olFolderInbox
        items = list(inbox.Items)
        emails = []
        for it in sorted(items, key=lambda x: getattr(x, "ReceivedTime", datetime.datetime.min), reverse=True)[:count]:
            try:
                emails.append({
                    "from": _clean_addr(getattr(it, "SenderName", "")),
                    "subject": getattr(it, "Subject", "") or "(no subject)",
                    "date": _date_fmt(getattr(it, "ReceivedTime", "").strftime("%a, %d %b %Y %H:%M:%S") if getattr(it, "ReceivedTime", None) else ""),
                    "snippet": _snippet(getattr(it, "Body", "") or ""),
                })
            except Exception:
                continue
        return (True, emails, f"Found {len(emails)} emails in Outlook.") if emails else (True, [], "Outlook inbox is empty.")
    except Exception as e:
        return False, [], f"Outlook unavailable: {_safe_err(e)}"
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass


def fetch_emails(count: int = 8) -> dict:
    """Try IMAP first, then Outlook, then a friendly unconfigured message."""
    ok_imap, emails_imap, msg_imap = fetch_emails_imap(count)
    if ok_imap:
        return {"success": True, "emails": emails_imap, "message": msg_imap, "source": "imap"}
    ok_out, emails_out, msg_out = fetch_emails_outlook(count)
    if ok_out:
        return {"success": True, "emails": emails_out, "message": msg_out, "source": "outlook"}
    if emails_imap or emails_out:
        return {"success": True, "emails": emails_imap or emails_out, "message": "Emails loaded."}
    return {"success": False, "emails": [], "message": msg_imap or msg_out}


# =====================================================================
# MAIL STATUS - unread counts + latest senders, no window switching
# =====================================================================

def _status_imap() -> dict | None:
    keys = _load_keys()
    user = str(keys.get("email_user") or "").strip()
    pwd = str(keys.get("email_pass") or "").strip()
    if not user or not pwd:
        return None
    host = str(keys.get("email_imap_host") or "imap.gmail.com").strip()
    try:
        cn = imaplib.IMAP4_SSL(host, int(keys.get("email_imap_port") or 993))
        cn.login(user, pwd)
        cn.select("INBOX")
        status, unseen = cn.uid("search", None, "UNSEEN")
        unread = len((unseen[0] or b"").split())
        status, latest = cn.uid("search", None, "ALL")
        uids = (latest[0] or b"").split()[-5:]
        senders: list[str] = []
        for uid in reversed(uids):
            status, msg = cn.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            for part in msg or []:
                if isinstance(part, tuple) and part[1]:
                    head = email.message_from_bytes(part[1])
                    senders.append(_clean_addr(head.get("From", "")))
                    break
        cn.logout()
        return {"success": True, "source": "imap", "unread": unread,
                "latest": senders[-3:][::-1], "account": user.split("@")[0]}
    except Exception as e:
        return {"success": False, "source": "imap", "unread": None,
                "latest": [], "message": _safe_err(e)}


def _status_outlook() -> dict | None:
    try:
        import pythoncom
        import win32com.client
    except Exception:
        return None
    try:
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6)  # olFolderInbox
        unread = 0
        try:
            unread = int(inbox.UnReadCount)
        except Exception:
            pass
        items = list(inbox.Items)[:5]
        senders = [str(getattr(it, "SenderName", "") or "").strip() for it in items]
        account = ""
        try:
            account = str(outlook.CurrentUser.Address.split("@")[0])
        except Exception:
            pass
        return {"success": True, "source": "outlook", "unread": unread,
                "latest": [s for s in senders if s][-3:][::-1], "account": account}
    except Exception as e:
        return {"success": False, "source": "outlook", "unread": None,
                "latest": [], "message": _safe_err(e)}
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass


def mail_status() -> dict:
    """Real inbox status: unread count + who wrote last. Never invents numbers."""
    for probe in (_status_imap, _status_outlook):
        st = probe()
        if st and st.get("success"):
            return st
    detail = next((s.get("message") for s in (_status_imap(), _status_outlook())
                   if s and s.get("message")), "")
    # -2147221005 is COM's "class not registered": Outlook simply isn't installed.
    if detail and ("-2147221005" in detail or "Invalid class string" in detail):
        detail = "Outlook isn't installed on this PC"
    return {"success": False, "unread": None, "latest": [], "account": "",
            "message": detail or "No mail backend available (add email_user / email_pass to data/keys.json, or open Outlook once)."}



if __name__ == "__main__":
    import json as _j
    print(_j.dumps(fetch_emails(), indent=2))
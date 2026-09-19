"""
J.E.N.N.Y - Chrome DevTools Protocol bridge

Gives JENNY deep, real control over a dedicated Chrome instance (tabs, YouTube,
WhatsApp/Discord Web) without extensions. The instance runs with
 --remote-debugging-port=9222 on a separate user-data-dir so it never disturbs
the user's normal browsing session.

Only the plain-HTTP management endpoints of the DevTools Protocol are used
(/json/list, /json/new, /json/activate, /json/close); no websocket client is
required.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.request
import urllib.parse
from pathlib import Path

CDP_PORT = 9222
CHROME_USER_DIR = str(Path("C:/Users/harsh/AppData/Local/JENNY-Chrome"))
CHROME_EXE = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe").exists()
    else r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
)


def _cdp_json(path: str, method: str = "GET", payload: str | None = None):
    """Hit a DevTools HTTP endpoint. Returns parsed JSON or None."""
    url = f"http://127.0.0.1:{CDP_PORT}{path}"
    req = urllib.request.Request(url, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
        req.data = payload.encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _port_open() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", CDP_PORT)) == 0


def launch():
    """Start the dedicated JENNY Chrome instance with CDP enabled."""
    if _port_open():
        return True
    if not Path(CHROME_EXE).exists():
        return False
    Path(CHROME_USER_DIR).mkdir(parents=True, exist_ok=True)
    args = [
        CHROME_EXE,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={CHROME_USER_DIR}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    try:
        subprocess.Popen(args, close_fds=True)
    except Exception:
        return False
    for _ in range(30):
        if _port_open():
            break
        time.sleep(0.25)
    return _port_open()


def _ensure():
    return launch()


def tabs() -> list[dict]:
    if not _ensure():
        return []
    data = _cdp_json("/json/list")
    if not isinstance(data, list):
        return []
    out = []
    for t in data:
        if t.get("type") == "page":
            out.append({"id": t.get("id"), "title": t.get("title"), "url": t.get("url")})
    return out


def open_url(url: str) -> dict:
    if not _ensure():
        return {"success": False, "message": "Chrome bridge unavailable"}
    enc = urllib.parse.quote(url, safe=":/?&=+#%,.-")
    data = _cdp_json(f"/json/new?{enc}", method="PUT")
    if not data:
        return {"success": False, "message": "Chrome bridge unreachable"}
    if isinstance(data, dict) and data.get("id"):
        return {"success": True, "tab": {"id": data["id"], "url": data.get("url")}}
    return {"success": (data.get("url") is not None), "message": "Chrome open"}


def _find_tab(sub: str):
    for t in tabs():
        hay = f"{t['title']} {t['url']}".lower()
        if sub.lower() in hay:
            return t
    return None


def activate(sub: str) -> bool:
    t = _find_tab(sub)
    if not t:
        return False
    _cdp_json(f"/json/activate/{t['id']}")
    return True


def close(sub: str) -> bool:
    t = _find_tab(sub)
    if not t:
        return False
    _cdp_json(f"/json/close/{t['id']}")
    return True


def search(query: str, engine: str = "google") -> str:
    """Open a new tab with the search results."""
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    if engine.lower() == "youtube":
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    elif engine.lower() == "bing":
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
    r = open_url(url)
    return url if r.get("success") else ""


def youtube(search_query: str) -> str:
    return search(search_query, engine="youtube")


def status() -> dict:
    ts = tabs()
    active = _cdp_json("/json") or []
    cur = None
    for a in active:
        if a.get("type") == "page" and a.get("url"):
            try:
                if not a.get("title", "").startswith("devtools"):
                    pass
            except Exception:
                pass
    top = ts[0] if ts else None
    return {
        "running": _port_open(),
        "count": len(ts),
        "first": top,
        "tabs": ts,
    }


def youtube_play(query: str) -> bool:
    """Search YouTube and click the first result to start playback.

    Uses keyboard automation (Tab + Enter) since the plain-HTTP CDP endpoints
    can't execute JS. Focus moves to the first result card, which Enter activates.
    """
    url = youtube(query)
    if not url:
        return False
    time.sleep(0.8)
    try:
        import ctypes
        # Ensure the JENNY Chrome window is foreground so key events land there
        # (window was just created via CDP, so it's typically already focused).
        for key in (0x09, 0x0D):  # Tab, Enter -> focus + click first result
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)
            ctypes.windll.user32.keybd_event(key, 0, 2, 0)
            time.sleep(0.4)
        ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)  # Enter to confirm play
        ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
    except Exception:
        pass
    return True


def whatsapp() -> bool:
    url = open_url("https://web.whatsapp.com")
    return bool(url.get("success"))


def discord() -> bool:
    url = open_url("https://discord.com/app")
    return bool(url.get("success"))
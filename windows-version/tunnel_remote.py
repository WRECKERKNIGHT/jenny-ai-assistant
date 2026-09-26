"""
Remote tunnel manager - exposes the local assistant over a public HTTPS
quick tunnel (cloudflared) so phones can reach it from anywhere there is
internet, not just the home Wi-Fi.

  * On demand, downloads cloudflared.exe into the bin folder (GitHub,
    windows-amd64).
  * Spawns:  cloudflared tunnel --url http://127.0.0.1:<port>
    and parses the quick-tunnel URL (https://<name>.trycloudflare.com) from
    its stdout.
  * The HTTPS URL gives phones a SECURE CONTEXT, which unlocks the phone's
    own microphone for voice commands - plain http:// LAN access blocks
    getUserMedia() on mobile browsers.

Security note: a quick tunnel exposes the assistant to the internet. Phone
access still requires pairing approval, but you should only turn this on
when you intend to control Jenny from your phone away from home.
"""

import json
import re
import subprocess
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
PORT = 3005
BIN_DIR = BASE_DIR / "bin"
BIN = BIN_DIR / "cloudflared.exe"
DOWNLOAD_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-windows-amd64.exe"
)
LAST_FILE = BASE_DIR / "data" / "tunnel.json"

_state = {
    "proc": None,
    "url": "",
    "hostname": "",
    "running": False,
    "busy": False,
    "cancel": False,
    "error": "",
    "last_url": "",
    "lock": threading.Lock(),
}


def _load_last():
    try:
        data = json.loads(LAST_FILE.read_text(encoding="utf-8"))
        _state["last_url"] = data.get("url", "")
    except Exception:
        pass


_load_last()


def status():
    with _state["lock"]:
        return {
            "running": bool(_state["running"]),
            "busy": bool(_state["busy"]),
            "url": _state["url"],
            "hostname": _state["hostname"],
            "error": _state["error"],
            "last_url": _state["last_url"],
        }


def stop():
    with _state["lock"]:
        proc = _state["proc"]
        _state["running"] = False
        _state["url"] = ""
        _state["hostname"] = ""
        _state["proc"] = None
        _state["busy"] = False
        _state["cancel"] = True
        _state["error"] = ""
    if proc:
        try:
            proc.terminate()
        except Exception:
            pass
    return {"success": True, "running": False}


def _read_url_stream(proc):
    url = ""
    try:
        for raw in proc.stdout:
            line = raw.decode(errors="ignore").strip()
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m:
                url = m.group(0)
                with _state["lock"]:
                    _state["url"] = url
                    _state["hostname"] = url.replace("https://", "").split(".")[0]
                    _state["last_url"] = url
                    _state["running"] = True
                try:
                    LAST_FILE.parent.mkdir(parents=True, exist_ok=True)
                    LAST_FILE.write_text(json.dumps({"url": url}), encoding="utf-8")
                except Exception:
                    pass
                break
    except Exception:
        pass
    with _state["lock"]:
        if _state.get("url") and _state["running"]:
            pass
        else:
            _state["running"] = False
            _state["url"] = ""
            _state["proc"] = None
    try:
        proc.wait(timeout=5)
    except Exception:
        pass
    return url


def _ensure_binary():
    if BIN.exists():
        return ""
    try:
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        import urllib.request

        tmp = BIN.with_name("cloudflared.exe.tmp")
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass
        req = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "jenny-assistant"})
        with urllib.request.urlopen(req, timeout=300) as r:
            with open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
        tmp.replace(BIN)
        return ""
    except Exception as e:
        return "Could not download cloudflared: %s" % e


def _start_worker():
    err = _ensure_binary()
    with _state["lock"]:
        if _state["cancel"]:
            _state["busy"] = False
            _state["cancel"] = False
            return
    if err:
        with _state["lock"]:
            _state["busy"] = False
            _state["error"] = err
        return
    try:
        proc = subprocess.Popen(
            [str(BIN), "tunnel", "--url", "http://127.0.0.1:%d" % PORT, "--no-autoupdate"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        with _state["lock"]:
            _state["busy"] = False
            _state["error"] = str(e)
        return
    with _state["lock"]:
        _state["proc"] = proc
        _state["busy"] = False
        _state["cancel"] = False
    threading.Thread(target=_read_url_stream, args=(proc,), daemon=True).start()


def start():
    with _state["lock"]:
        if _state["busy"]:
            return {"success": False, "busy": True, "error": "Tunnel is already starting."}
        if _state["running"]:
            return {"success": True, "running": True, "url": _state["url"], "hostname": _state["hostname"]}
        _state["busy"] = True
        _state["cancel"] = False
        _state["error"] = ""
    threading.Thread(target=_start_worker, daemon=True).start()
    return {"success": True, "busy": True, "message": "Starting tunnel — this can take a moment on first run."}
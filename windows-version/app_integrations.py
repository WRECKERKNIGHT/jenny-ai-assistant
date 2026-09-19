"""
J.E.N.N.Y - App integrations

Powers app-specific control beyond media keys: deep Spotify search & play,
Telegram/WhatsApp/Discord messaging, VS Code project opening, per-app audio
session volume, and window-focused remote control.

Everything here is optional: each helper degrades to a clean False/message
when the target app isn't installed, isn't running, or the OS blocks automation.
"""

from __future__ import annotations

import re
import subprocess
import time

try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    import psutil
except Exception:
    psutil = None


def _shell(cmd, timeout=8):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        return None


def _win_enum():
    """Map top-level window titles to process names via psutil."""
    if psutil is None:
        return {}
    out = {}
    try:
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if p.info.get("pid") and p.info.get("name"):
                    out[p.info["pid"]] = p.info["name"]
            except Exception:
                continue
    except Exception:
        pass
    return out


def _find_window(title_part: str) -> tuple[int, str] | None:
    """Locate the top-level foreground-able window whose title contains `title_part`."""
    try:
        import ctypes
        import ctypes.wintypes as wt
    except Exception:
        return None
    if not title_part:
        return None
    lo = title_part.lower()

    def _proc_name(pid):
        names = {v: k for k, v in _win_enum().items()}
        return names.get(pid, "")

    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def _cb(hwnd, lparam):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if lo in title.lower():
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found.append((hwnd, title, _proc_name(pid.value)))
        return True

    ctypes.windll.user32.EnumWindows(_cb, 0)
    if not found:
        return None
    found.sort(key=lambda x: len(x[1]))
    hwnd, title, proc = found[0]
    return hwnd, title


def focus_window(title_part: str) -> tuple[bool, str]:
    """Bring a window matching `title_part` to the foreground."""
    try:
        import ctypes
    except Exception:
        return False, "win32 unavailable"
    hit = _find_window(title_part)
    if not hit:
        return False, f"No window titled '{title_part}' found"
    hwnd, title = hit
    try:
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        return True, f"Focused '{title}'"
    except Exception as e:
        return False, f"Focus failed: {e}"


def foreground_shot() -> str | None:
    """Return the title of the currently focused window."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or None
    except Exception:
        return None


# =====================================================================
# SPOTIFY
# =====================================================================

SPOTIFY_SEARCH_SHORTCUT = "ctrl+l"


def _app_exe_running(name: str) -> bool:
    if psutil is None:
        return True
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info.get("name") or "").lower().startswith(name.lower()):
                return True
        except Exception:
            continue
    return False


def spotify_running() -> bool:
    return _app_exe_running("spotify")


def spotify_action(action: str) -> tuple[bool, str]:
    """playpause / next / previous / stop / volume-up / volume-down using media keys."""
    keys = {
        "playpause": "playpause",
        "play": "play",
        "pause": "pause",
        "next": "next",
        "previous": "previous",
        "stop": "stop",
    }
    target = "spotify"
    from pc_actions import media_play_pause, media_next, media_prev
    fn = {
        "playpause": media_play_pause, "play": media_play_pause,
        "pause": media_play_pause, "stop": media_play_pause,
        "next": media_next, "previous": media_prev,
    }.get(action)
    if not fn:
        return False, "Unknown media action"
    focus_window(target)
    return fn() or True, f"Media {action} sent"


def spotify_search_play(query: str) -> tuple[bool, str]:
    """Open Spotify search and play the top result."""
    if pyautogui is None:
        return False, "pyautogui missing"
    ok, msg = focus_window("Spotify")
    if not ok:
        return False, f"Spotify not focused: {msg}"
    time.sleep(0.3)
    try:
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.2)
        pyautogui.typewrite(query[:60])
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.8)
        pyautogui.press("enter")
        return True, f"Playing '{query}' on Spotify"
    except Exception as e:
        return False, f"Spotify search failed: {e}"


# =====================================================================
# TELEGRAM / WHATSAPP / DISCORD
# =====================================================================

def telegram_send(contact: str, message: str) -> tuple[bool, str]:
    """Type a message into a Telegram Desktop chat."""
    if pyautogui is None:
        return False, "pyautogui missing"
    ok, msg = focus_window("Telegram")
    if not ok:
        subprocess.Popen(["Telegram.exe"], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(2.5)
        ok, msg = focus_window("Telegram")
        if not ok:
            return False, "Telegram didn't come up"
    time.sleep(0.4)
    try:
        pyautogui.hotkey("ctrl", "k")          # quick-switch to chat
        time.sleep(0.4)
        pyautogui.typewrite(contact[:60])
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(0.5)
        pyautogui.typewrite(message[:500])
        time.sleep(0.2)
        pyautogui.press("enter")
        return True, f"Message sent to {contact} on Telegram"
    except Exception as e:
        return False, f"Telegram send failed: {e}"


def whatsapp_open() -> tuple[bool, str]:
    try:
        import chrome_bridge
        ok = chrome_bridge.whatsapp()
        return (ok, "Opened WhatsApp Web") if ok else (False, "WhatsApp Web failed")
    except Exception as e:
        return False, f"WhatsApp bridge error: {e}"


def discord_open() -> tuple[bool, str]:
    try:
        import chrome_bridge
        ok = chrome_bridge.discord()
        return (ok, "Opened Discord") if ok else (False, "Discord open failed")
    except Exception as e:
        return False, f"Discord bridge error: {e}"


# =====================================================================
# VS CODE / DEV
# =====================================================================

def _code_cli() -> str | None:
    from shutil import which
    for c in ("code", "code.cmd"):
        p = which(c)
        if p:
            return p
    for p in (
        r"C:\Users\harsh\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd",
        r"C:\Program Files\Microsoft VS Code\bin\code.cmd",
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ):
        import os
        if os.path.exists(p):
            return p
    return None


def open_project(project: str) -> tuple[bool, str]:
    """Open a project folder. Projects live under ~/Projects by default."""
    base = "C:/Users/harsh/Projects"
    import os
    for root in (base, os.path.join(os.path.expanduser("~"), "Desktop", "Projects"), os.path.expanduser("~")):
        cand = os.path.join(root, project)
        if os.path.isdir(cand):
            cli = _code_cli()
            if cli:
                try:
                    subprocess.Popen([cli, cand], creationflags=subprocess.CREATE_NO_WINDOW)
                    return True, f"Opened project '{project}' in VS Code"
                except Exception:
                    pass
            try:
                subprocess.Popen(["explorer", cand], creationflags=subprocess.CREATE_NO_WINDOW)
                return True, f"Opened project folder '{project}' in Explorer"
            except Exception:
                return False, f"Could not open project '{project}'"
    return False, f"Project '{project}' not found under {base}"


def terminal_in_project(project: str) -> tuple[bool, str]:
    """Open Windows Terminal at a project folder."""
    import os
    cand = os.path.join("C:/Users/harsh/Projects", project)
    if not os.path.isdir(cand):
        return False, f"Project '{project}' not found"
    try:
        r = subprocess.Popen(["wt.exe", "-d", cand], creationflags=subprocess.CREATE_NO_WINDOW)
        return True, f"Terminal opened at {project}"
    except Exception:
        try:
            subprocess.Popen(["cmd.exe", "/k", f"cd /d {cand}"], creationflags=subprocess.CREATE_NO_WINDOW)
            return True, f"Terminal opened at {project}"
        except Exception:
            return False, "Terminal failed"


# =====================================================================
# PER-APP AUDIO SESSION VOLUME (Windows)
# =====================================================================

def _audio_sessions():
    try:
        from pycaw.pycaw import AudioUtilities
        return AudioUtilities.GetAllSessions()
    except Exception:
        return []


def app_volume(app_name: str, pct: int | None = None):
    """Get (or set) the volume of the audio session owned by `app_name`.

    pct=None -> report current; else 0..100.
    """
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import IAudioMeterInformation
    except Exception:
        return False, "pycaw unavailable"
    app_name = app_name.lower()
    for s in _audio_sessions():
        try:
            proc = s.Process
            if proc is None:
                continue
            name = (proc.name() or "").lower()
            if app_name not in name:
                continue
            volume = s._ctl
            if pct is None:
                if hasattr(volume, "GetMasterVolumeLevelScalar"):
                    cur = round(volume.GetMasterVolumeLevelScalar() * 100)
                else:
                    cur = None
                return True, f"{proc.name()} volume: {cur}%"
            if hasattr(volume, "SetMasterVolumeLevelScalar"):
                volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, int(pct) / 100.0)), None)
                return True, f"{proc.name()} volume set to {int(pct)}%"
            return False, "Volume control unsupported"
        except Exception:
            continue
    # Not an active audio session: find by running process and report we can't yet.
    return False, f"No active audio session for '{app_name}'. Play audio in it first."


def list_app_volumes():
    out = []
    for s in _audio_sessions():
        try:
            proc = s.Process
            if proc is None:
                continue
            vol = s._ctl
            cur = None
            if hasattr(vol, "GetMasterVolumeLevelScalar"):
                cur = round(vol.GetMasterVolumeLevelScalar() * 100)
            out.append({"app": proc.name(), "volume": cur})
        except Exception:
            continue
    return out


# =====================================================================
# DISPATCH
# =====================================================================

def run(name: str, value=""):
    """Unified entrypoint so /api/control and chat router use one code path."""
    name = (name or "").lower()
    try:
        if name == "spotify-search":
            return spotify_search_play(str(value))
        if name == "spotify-action":
            return spotify_action(str(value))
        if name == "telegram-send":
            parts = str(value).split("|")
            contact = parts[0] if parts else ""
            message = parts[1] if len(parts) > 1 else ""
            return telegram_send(contact.strip(), message.strip())
        if name == "whatsapp-open":
            return whatsapp_open()
        if name == "discord-open":
            return discord_open()
        if name == "open-project":
            return open_project(str(value))
        if name == "terminal-project":
            return terminal_in_project(str(value))
        if name == "focus-window":
            return focus_window(str(value))
        if name == "app-volume":
            pct = None
            if isinstance(value, (int, float)):
                pct = int(value)
            elif isinstance(value, str) and value.strip().isdigit():
                pct = int(value)
            elif isinstance(value, dict):
                pct = value.get("level")
                return app_volume(str(value.get("app", "")), pct)
            return app_volume(str(value), pct)
        if name == "list-app-volumes":
            return True, ", ".join(f"{v['app']}={v['volume']}%" for v in list_app_volumes()) or "No audio sessions"
        if name == "foreground-window":
            t = foreground_shot()
            return (True, f"Foreground window: {t}") if t else (False, "No foreground window")
    except Exception as e:
        return False, str(e)
    return False, f"Unknown integration: {name}"


if __name__ == "__main__":
    print("foreground:", foreground_shot())
    print("app volumes:", list_app_volumes())
"""
U.L.T.R.O.N. PC Control Actions
Browser + system control executed from ULTRON gestures.
Uses PyAutoGUI hotkeys and PowerShell behind the scenes.
"""
import os
import time
import subprocess
import datetime
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.03
    HAS_PYAUTOGUI = True
except Exception:
    HAS_PYAUTOGUI = False

_browser_proc_info = None


def _hwnd_send(key):
    if HAS_PYAUTOGUI:
        try:
            pyautogui.press(key)
            return True
        except Exception:
            pass
    return False


def _hotkey(*keys):
    if HAS_PYAUTOGUI:
        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception:
            pass
    return False


def _shell(cmd, timeout=10):
    try:
        subprocess.run(cmd, shell=True, capture_output=True,
                       timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception:
        return False


def browser_open(url=None):
    """Open the default browser (optionally at a URL)."""
    target = url or "https://www.google.com"
    if _hotkey("win") or True:
        pass
    try:
        os.startfile(target)
        time.sleep(1.2)
        _hotkey("ctrl", "t")
        return True
    except Exception:
        return _shell(f"start {target}")


def browser_new_tab():
    return _hotkey("ctrl", "t")


def browser_close_tab():
    return _hotkey("ctrl", "w")


def browser_back():
    return _hotkey("alt", "left")


def browser_forward():
    return _hotkey("alt", "right")


def browser_refresh():
    return _hotkey("ctrl", "r")


def browser_search(text=""):
    query = (text or "").strip()
    goto = _hotkey("ctrl", "l")
    if not goto:
        return False
    time.sleep(0.15)
    if query:
        if HAS_PYAUTOGUI:
            pyautogui.typewrite(query, interval=0.01)
        pyautogui.press("enter")
    return True


def browser_new_window():
    return _hotkey("ctrl", "n")


def browser_reopen_tab():
    return _hotkey("ctrl", "shift", "t")


def browser_fullscreen():
    return _hotkey("f11")


def volume_up():
    return _hwnd_send("volumeup")


def volume_down():
    return _hwnd_send("volumedown")


def volume_mute():
    return _hwnd_send("volumemute")


def media_play_pause():
    return _hwnd_send("playpause")


def media_next():
    return _hwnd_send("nexttrack")


def media_prev():
    return _hwnd_send("prevtrack")


def screenshot(dest=None):
    """Save a full-screen screenshot to Desktop (or given path)."""
    if not HAS_PYAUTOGUI:
        return False
    try:
        folder = dest or str(Path.home() / "Desktop")
        path = os.path.join(
            folder,
            f"ultron_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        pyautogui.screenshot(path)
        return path
    except Exception:
        return False


def open_task_manager():
    return _hotkey("ctrl", "shift", "esc")


def show_desktop():
    return _hotkey("win", "d")


def lock_pc():
    return _hotkey("win", "l")


def toggle_browser():
    """Refocus browser; falls back to opening it."""
    opened = browser_open()
    return opened


def close_window_focused():
    return _hotkey("alt", "f4")


def open_app(name):
    apps = {
        "notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe",
        "chrome": "chrome", "edge": "msedge", "vscode": "code",
        "spotify": "spotify", "discord": "discord", "file": "explorer.exe",
        "terminal": "wt.exe", "cmd": "cmd.exe",
        "camera": "microsoft.windows.camera:", "settings": "ms-settings:",
        "controlpanel": "control", "clipboard": "ms-settings:clipboard",
        "clock": "ms-settings:dateandtime", "alarms": "ms-clock:",
    }
    target = apps.get(str(name).lower(), name)
    return _shell(f"start {target}")


def browser_youtube():
    return browser_open("https://www.youtube.com")


def browser_gmail():
    return browser_open("https://mail.google.com")


def browser_github():
    return browser_open("https://github.com")


def speak_feedback(text):
    """Audible confirmation via Windows SAPI (used for gesture results)."""
    if not text:
        return False
    import re as _re
    safe = _re.sub(r'[^0-9a-zA-Z .,!?]', '', str(text))
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "Add-Type -AssemblyName System.Speech;"
        f"$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.Speak('{safe}')"
    )
    return _shell(f"powershell -NoProfile -Command \"{ps}\"", timeout=8)


def lock_screen_timer(seconds=0):
    """Lock the PC now, or after a short countdown for safety."""
    if seconds and seconds > 0:
        time.sleep(min(seconds, 15))
    return lock_pc()


ACTION_INDEX = {
    "browser_open": browser_open,
    "browser_new_tab": browser_new_tab,
    "browser_close_tab": browser_close_tab,
    "browser_back": browser_back,
    "browser_forward": browser_forward,
    "browser_refresh": browser_refresh,
    "browser_search": browser_search,
    "browser_new_window": browser_new_window,
    "browser_reopen_tab": browser_reopen_tab,
    "browser_fullscreen": browser_fullscreen,
    "browser_youtube": browser_youtube,
    "browser_gmail": browser_gmail,
    "browser_github": browser_github,
    "volume_up": volume_up,
    "volume_down": volume_down,
    "volume_mute": volume_mute,
    "media_play_pause": media_play_pause,
    "media_next": media_next,
    "media_prev": media_prev,
    "screenshot": screenshot,
    "task_manager": open_task_manager,
    "show_desktop": show_desktop,
    "lock_pc": lock_pc,
    "lock_screen_timer": lock_screen_timer,
    "close_window": close_window_focused,
    "open_app": open_app,
    "speak_feedback": speak_feedback,
}


def run_action(name, *args):
    fn = ACTION_INDEX.get(name)
    if fn is None:
        return False
    try:
        return fn(*args)
    except Exception:
        return False
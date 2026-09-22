"""
J.E.N.N.Y v2.0 - Desktop Tray App (system tray icon + Mini HUD)

One tiny icon on the right side of the Windows taskbar with everything you need:

  * Double-click the icon -> opens/closes the MINI HUD (always-on-top panel).
  * Right-click menu -> Mini HUD / Modes / Dashboard / Holographic HUD,
                        wake-word on/off, test voice, and Quit.
  * Actually starts the whole assistant: Flask server + neural voice engine
    + proactive speaker + optional wake word — all in one process.

Usage:  pythonw tray.py      (background, no console)
        python  tray.py      (foreground with logs)
"""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import pystray
from PIL import Image

BASE_DIR = Path(__file__).parent
PORT = 3005
SERVER_URL = f"http://127.0.0.1:{PORT}"


# ---------------------------------------------------------------------------
# Small cross-thread command bridge (Tk is not thread-safe)
# ---------------------------------------------------------------------------

_command_queue = []


def queue(cmd, *args):
    _command_queue.append((cmd, args))


# ---------------------------------------------------------------------------
# Server + background helpers
# ---------------------------------------------------------------------------

def is_port_open(port, host="127.0.0.1", timeout=0.3):
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_server(port=PORT):
    sys.path.insert(0, str(BASE_DIR))
    import server
    # Shared always-on routines: telemetry, proactive speaker, wake-word
    # listener (restored from settings) — so JENNY keeps listening in the
    # background even while the user is in another app.
    server.start_background_services()
    from waitress import serve
    serve(server.app, host="0.0.0.0", port=port, threads=16)


def ensure_server():
    if not is_port_open(PORT):
        threading.Thread(target=start_server, daemon=True).start()
        for _ in range(40):
            if is_port_open(PORT):
                break
            time.sleep(0.5)
    else:
        print(f"[i] Server already running on port {PORT}, reusing it.")


# ---------------------------------------------------------------------------
# Wake-word lifecycle
#
# The wake word now runs inside the server itself (always-on, works headless),
# so the tray simply toggles it over HTTP instead of spawning the old
# browser-dependent scripts/wakeword.py subprocess.
# ---------------------------------------------------------------------------

_wake_lock = threading.Lock()


def wake_word_running():
    # The server-side listener is the single source of truth.
    try:
        import json as _json
        import urllib.request as _ur
        with _ur.urlopen(f"http://127.0.0.1:{PORT}/api/wake/status", timeout=2) as r:
            return bool(_json.loads(r.read().decode()).get("on", False))
    except Exception:
        return False


def set_wake_word(on):
    with _wake_lock:
        try:
            import json as _json
            import urllib.request as _ur
            req = _ur.Request(f"http://127.0.0.1:{PORT}/api/wake/toggle",
                              data=_json.dumps({"on": bool(on)}).encode(),
                              headers={"Content-Type": "application/json"})
            with _ur.urlopen(req, timeout=3) as r:
                r.read()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Tray icon
# ---------------------------------------------------------------------------

def _load_icon():
    for p in [BASE_DIR / "public" / "logo.png", BASE_DIR / "logo.png"]:
        try:
            if p.exists():
                with Image.open(p) as im:
                    im = im.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
                    return im
        except Exception:
            continue
    img = Image.new("RGBA", (64, 64), (0, 200, 120, 255))
    return img


def _speak_test():
    import tts_engine
    try:
        mode = open(BASE_DIR / "data" / "mode.json", encoding="utf-8").read().strip().strip('"')
    except Exception:
        mode = "friday"
    tts_engine.speak_async(
        "Voice check complete. All neural engines are ready, Boss.", mode,
    )


def _on_quit(icon, item):
    set_wake_word(False)
    queue("quit")


def _on_toggle_hud(icon, item=None):
    queue("toggle_hud")


def _on_open_modes(icon, item):
    webbrowser.open(f"{SERVER_URL}/modes.html")


def _on_open_dashboard(icon, item):
    webbrowser.open(f"{SERVER_URL}/")


def _on_open_hud_overlay(icon, item):
    webbrowser.open(f"{SERVER_URL}/mini.html")


def _on_wake_toggle(icon, item):
    if wake_word_running():
        set_wake_word(False)
        _refresh_tray_menu(icon)
    else:
        set_wake_word(True)
        _refresh_tray_menu(icon)


def _on_speak_test(icon, item):
    threading.Thread(target=_speak_test, daemon=True).start()


def _build_menu():
    wake_label = "Wake Word: ON" if wake_word_running() else "Wake Word: OFF"
    return pystray.Menu(
        pystray.MenuItem("Mini HUD", _on_toggle_hud, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open Modes", _on_open_modes),
        pystray.MenuItem("Open Dashboard", _on_open_dashboard),
        pystray.MenuItem("Holographic HUD", _on_open_hud_overlay),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(wake_label, _on_wake_toggle),
        pystray.MenuItem("Voice Check", _on_speak_test),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _on_quit),
    )


_icon = None


def _refresh_tray_menu(icon):
    try:
        icon.menu = _build_menu()
    except Exception:
        pass


def _run_tray():
    global _icon
    try:
        icon = pystray.Icon(
            "JENNY",
            _load_icon(),
            "J.E.N.N.Y v2.0 — AI Assistant",
            _build_menu(),
        )
        _icon = icon
        icon.run()
    except Exception as e:
        print(f"[!] Tray failed: {e}")
        queue("quit")


# ---------------------------------------------------------------------------
# Mini HUD (Tk, always-on-top, bottom-right)
# ---------------------------------------------------------------------------

def _toggle_hud(root, hud):
    if hud.get("win") is not None and hud["win"].winfo_exists():
        hud["win"].destroy()
        hud["win"] = None
        hud["visible"] = False
        return
    import tkinter as tk
    w = hud["root"]
    win = tk.Toplevel(w)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.configure(bg="#0b0e14")
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    W, H = 330, 300
    win.geometry(f"{W}x{H}+{sw - W - 24}+{sh - H - 80}")
    hud["win"] = win
    hud["visible"] = True

    accent = "#f5c242"
    cyan = "#00d4ff"

    tk.Label(win, text="J.E.N.N.Y", bg="#0b0e14", fg=accent,
             font=("Segoe UI", 13, "bold")).pack(pady=(12, 2))
    tk.Label(win, text="Neural AI Assistant", bg="#0b0e14", fg="#8a93a3",
             font=("Segoe UI", 8)).pack()

    mode_lbl = tk.Label(win, text="MODE: --", bg="#0b0e14", fg=cyan,
                        font=("Consolas", 10))
    mode_lbl.pack(pady=(10, 2))
    state_lbl = tk.Label(win, text="status: idle", bg="#0b0e14", fg="#6f7888",
                         font=("Consolas", 9))
    state_lbl.pack()

    def buttons(row):
        return tk.Frame(row, bg="#0b0e14")

    bf = buttons(win)
    bf.pack(pady=12)
    btns = [
        ("Modes", lambda: webbrowser.open(f"{SERVER_URL}/modes.html")),
        ("HUD", lambda: webbrowser.open(f"{SERVER_URL}/mini.html")),
        ("Dash", lambda: webbrowser.open(f"{SERVER_URL}/")),
    ]
    for text, cb in btns:
        b = tk.Button(bf, text=text, command=cb, bg="#131a26", fg="#e6e9ef",
                      activebackground="#1c2636", activeforeground="#ffffff",
                      relief="flat", bd=0, padx=14, pady=6, width=6,
                      font=("Segoe UI", 9))
        b.pack(side="left", padx=5)

    wake_btn = tk.Button(win, bg="#131a26", fg="white", relief="flat", bd=0,
                         padx=10, pady=6, font=("Segoe UI", 9),
                         activebackground="#1c2636")
    wake_btn.config(text="Wake Word: OFF" if not wake_word_running() else "Wake Word: ON",
                    command=lambda: (_refresh_hud(root, hud, wake_btn, mode_lbl, state_lbl)))
    wake_btn.pack(pady=4)

    quit_btn = tk.Button(win, text="Quit", command=lambda: queue("quit"),
                         bg="#3a1015", fg="#ff9d9d", relief="flat", bd=0,
                         padx=10, pady=4, font=("Segoe UI", 9))
    quit_btn.pack(pady=(0, 8))

    ctx = {"mode": "--", "speaking": False, "last": ""}

    def refresh():
        if hud.get("win") is None or not hud["win"].winfo_exists():
            return
        try:
            import json
            import urllib.request
            with urllib.request.urlopen(f"{SERVER_URL}/api/voice-info", timeout=2) as r:
                d = json.loads(r.read().decode())
                ctx["mode"] = d.get("mode", "--")
            try:
                with urllib.request.urlopen(f"{SERVER_URL}/api/speak/status", timeout=2) as r:
                    s = json.loads(r.read().decode())
                    ctx["speaking"] = bool(s.get("speaking"))
                    ctx["last"] = (s.get("last") or "")[:60]
            except Exception:
                ctx["speaking"] = False
        except Exception:
            pass
        mode_lbl.config(text=f"MODE: {ctx['mode'].upper()}")
        if ctx["speaking"]:
            state_lbl.config(text=f"status: SPEAKING — \"{ctx['last']}\"", fg="#7dffa1")
        else:
            state_lbl.config(text="status: idle — say 'Hey Jenny' or use the tray", fg="#6f7888")
        wake_btn.config(text="Wake Word: OFF" if not wake_word_running() else "Wake Word: ON")
        root.after(1500, refresh)

    refresh()


def _refresh_hud(root, hud, wake_btn, mode_lbl, state_lbl):
    set_wake_word(not wake_word_running())
    _refresh_tray_menu(_icon)


def _poll_queue(root, hud):
    while _command_queue:
        cmd, args = _command_queue.pop(0)
        if cmd == "toggle_hud":
            _toggle_hud(root, hud)
        elif cmd == "quit":
            try:
                root.destroy()
            except Exception:
                pass
            if _icon is not None:
                try:
                    _icon.stop()
                except Exception:
                    pass
            os._exit(0)
    try:
        root.after(150, _poll_queue, root, hud)
    except Exception:
        pass


def main():
    print("=" * 55)
    print("  J.E.N.N.Y v2.0 — Tray + Mini HUD (port 3005)")
    print("  Double-click the tray icon for the Mini HUD.")
    print("=" * 55)

    ensure_server()

    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    hud = {"root": root, "win": None, "visible": False}

    threading.Thread(target=_run_tray, daemon=True).start()

    # Auto-open the Mini HUD on first launch so the user sees it immediately.
    root.after(1800, lambda: _toggle_hud(root, hud))
    root.after(250, _poll_queue, root, hud)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
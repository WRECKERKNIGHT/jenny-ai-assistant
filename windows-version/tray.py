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

def _json_get(path):
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(f"{SERVER_URL}{path}", timeout=2.5) as r:
            raw = r.read().decode() or "{}"
            return json.loads(raw)
    except Exception:
        return {}


def _json_post(path, payload):
    import json
    import urllib.request
    try:
        req = urllib.request.Request(
            f"{SERVER_URL}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read().decode() or "{}"
            return json.loads(raw)
    except Exception:
        return {}


def _hud_set(hud, state_lbl, text, mic=False):
    try:
        hud.setdefault("uiq", []).append(["set", text, "#7dffa1" if mic else "#c9d4e6"])
        hud.setdefault("state", {})["pause"] = time.time() + 6
    except Exception:
        pass


def _hud_run_reply(hud, state_lbl, msg):
    def work():
        d = _json_post("/api/chat", {"message": msg})
        rep = d.get("reply") or {}
        out = rep.get("text") if isinstance(rep, dict) else None
        if not out:
            out = d.get("text") or "Done."
        cmd = rep.get("command") if isinstance(rep, dict) else None
        hud["uiq"].append(["set", "JENNY: " + str(out).replace("\n", " ")[:150], "#7dffa1"])
        hud["state"]["pause"] = time.time() + 6
        if cmd and isinstance(cmd, dict) and cmd.get("action") != "vault-save":
            _json_post("/api/control", cmd)
        _json_post("/api/speak/fallback", {"text": str(out)})
    threading.Thread(target=work, daemon=True).start()


def _hud_text(hud, entry, state_lbl):
    msg = entry.get().strip()
    if not msg:
        return
    entry.delete(0, "end")
    _hud_set(hud, state_lbl, "query: " + msg[:70])
    _hud_run_reply(hud, state_lbl, msg)


def _hud_finish_mic(hud, mic_btn, st):
    st["mic"] = False
    hud["uiq"].append(["btn", "\u00a0 Mic"])


def _hud_mic(hud, mic_btn, state_lbl):
    st = hud.setdefault("state", {})
    if st.get("mic"):
        st["mic"] = False
        sid = st.get("sid")
        if sid:
            _json_post(f"/api/stt/live/stop/{sid}", {})
            st.pop("sid", None)
        _hud_set(hud, state_lbl, "status: idle")
        try:
            mic_btn.config(text="\u00a0 Mic")
        except Exception:
            pass
        return

    st["mic"] = True
    try:
        mic_btn.config(text="Listening\u2026")
    except Exception:
        pass

    def work():
        _hud_set(hud, state_lbl, "status: listening\u2026", mic=True)
        mics = _json_get("/api/stt/mics").get("mics") or []
        dev = None
        if len(mics) == 1:
            dev = mics[0].get("index")
        elif len(mics) > 1:
            dev = next((m.get("index") for m in mics if m.get("default")), mics[0].get("index"))
        start = _json_post("/api/stt/live/start", {"seconds": 15, "device": dev})
        sid = start.get("sessionId")
        if not sid:
            _hud_set(hud, state_lbl, "mic: could not start", mic=True)
            _hud_finish_mic(hud, mic_btn, st)
            return
        st["sid"] = sid
        final = ""
        deadline = time.time() + 20
        while st.get("mic") and time.time() < deadline:
            time.sleep(0.8)
            state = _json_get(f"/api/stt/live/status/{sid}")
            if state.get("error"):
                break
            if state.get("done"):
                final = (state.get("final") or "").strip()
                break
        _json_post(f"/api/stt/live/stop/{sid}", {})
        st.pop("sid", None)
        _hud_finish_mic(hud, mic_btn, st)
        if final:
            _hud_set(hud, state_lbl, "heard: " + final[:80], mic=True)
            _hud_run_reply(hud, state_lbl, final)
        else:
            _hud_set(hud, state_lbl, "status: idle \u2014 no speech detected")
    threading.Thread(target=work, daemon=True).start()


def _hud_stop_speech(hud, state_lbl):
    def work():
        _json_post("/api/speak/stop", {})
        _hud_set(hud, state_lbl, "status: idle")
    threading.Thread(target=work, daemon=True).start()


def _drain_uiq(root, hud, state_lbl, mic_btn):
    try:
        uiq = hud.get("uiq") or []
        hud["uiq"] = []
        for item in uiq:
            if not item:
                continue
            if item[0] == "set":
                try:
                    state_lbl.config(text=item[1], fg=item[2])
                except Exception:
                    pass
            elif item[0] == "btn":
                try:
                    mic_btn.config(text=item[1])
                except Exception:
                    pass
    except Exception:
        pass
    try:
        if hud.get("win") is not None and hud["win"].winfo_exists():
            root.after(120, _drain_uiq, root, hud, state_lbl, mic_btn)
    except Exception:
        pass


def _hud_wake(wake_btn):
    set_wake_word(not wake_word_running())

    def apply():
        try:
            if wake_btn.winfo_exists():
                wake_btn.config(text="Wake Word: OFF" if not wake_word_running() else "Wake Word: ON")
        except Exception:
            pass

    try:
        wake_btn.after(0, apply)
    except Exception:
        pass


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
    W, H = 372, 424
    win.geometry(f"{W}x{H}+{sw - W - 24}+{sh - H - 96}")
    hud["win"] = win
    hud["visible"] = True

    bg = "#0b0e14"
    panel = "#101624"
    accent = "#f5c242"
    cyan = "#00d4ff"
    txt = "#e6e9ef"
    dim = "#8a93a3"

    header = tk.Frame(win, bg=bg)
    header.pack(fill="x", padx=16, pady=(14, 2))
    tk.Label(header, text="J.E.N.N.Y", bg=bg, fg=accent,
             font=("Segoe UI", 14, "bold")).pack(side="left")
    mode_lbl = tk.Label(header, text="MODE: --", bg=panel, fg=cyan,
                        font=("Segoe UI", 8, "bold"), padx=8, pady=2)
    mode_lbl.pack(side="right")

    tk.Label(win, text="Neural AI Assistant \u2014 taskbar companion",
             bg=bg, fg=dim, font=("Segoe UI", 8)).pack(anchor="w", padx=16)

    state_lbl = tk.Label(win, text="status: idle", bg=bg, fg=dim, anchor="w",
                         justify="left", wraplength=340, font=("Consolas", 9))
    state_lbl.pack(fill="x", padx=16, pady=(8, 2))

    entry = tk.Entry(win, bg=panel, fg=txt, insertbackground=txt, relief="flat",
                     font=("Segoe UI", 11))
    entry.pack(fill="x", padx=16, pady=(12, 8), ipady=7)

    row = tk.Frame(win, bg=bg)
    row.pack(fill="x", padx=16)
    send_btn = tk.Button(row, text="Send", command=lambda: _hud_text(hud, entry, state_lbl),
                         bg=cyan, fg="#04121a", activebackground="#7fe8ff",
                         relief="flat", bd=0, padx=16, pady=8, font=("Segoe UI", 10, "bold"))
    send_btn.pack(side="left", padx=(0, 6))
    mic_btn = tk.Button(row, text="\u00a0 Mic", command=lambda: _hud_mic(hud, mic_btn, state_lbl),
                        bg=panel, fg=txt, activebackground=bg, relief="flat", bd=0,
                        padx=16, pady=8, font=("Segoe UI", 10, "bold"))
    mic_btn.pack(side="left", padx=6)
    stop_btn = tk.Button(row, text="Stop", command=lambda: _hud_stop_speech(hud, state_lbl),
                         bg="#3a1015", fg="#ff9d9d", activebackground="#5a1a22",
                         relief="flat", bd=0, padx=14, pady=8, font=("Segoe UI", 10, "bold"))
    stop_btn.pack(side="left", padx=6)
    voice_btn = tk.Button(row, text="Voice", command=lambda: threading.Thread(target=_speak_test, daemon=True).start(),
                          bg=panel, fg=txt, activebackground=bg, relief="flat", bd=0,
                          padx=14, pady=8, font=("Segoe UI", 10, "bold"))
    voice_btn.pack(side="left", padx=6)

    nav = tk.Frame(win, bg=bg)
    nav.pack(fill="x", padx=16, pady=(10, 0))
    for text, cb in [("Modes", lambda: webbrowser.open(f"{SERVER_URL}/modes.html")),
                     ("HUD", lambda: webbrowser.open(f"{SERVER_URL}/mini.html")),
                     ("Dash", lambda: webbrowser.open(f"{SERVER_URL}/"))]:
        b = tk.Button(nav, text=text, command=cb, bg=panel, fg=txt,
                      activebackground="#1c2636", activeforeground="#ffffff",
                      relief="flat", bd=0, padx=16, pady=6, font=("Segoe UI", 9))
        b.pack(side="left", padx=5)

    wake_btn = tk.Button(win, bg=panel, fg="white", relief="flat", bd=0,
                         padx=10, pady=6, font=("Segoe UI", 9),
                         activebackground="#1c2636")
    wake_btn.config(text="Wake Word: OFF" if not wake_word_running() else "Wake Word: ON",
                    command=lambda: _hud_wake(wake_btn))
    wake_btn.pack(pady=(8, 2))

    quit_btn = tk.Button(win, text="Quit", command=lambda: queue("quit"),
                         bg="#3a1015", fg="#ff9d9d", relief="flat", bd=0,
                         padx=10, pady=4, font=("Segoe UI", 9))
    quit_btn.pack(pady=(2, 8))

    entry.bind("<Return>", lambda e: _hud_text(hud, entry, state_lbl))
    entry.focus_set()

    hud["state"] = {"mode": "--", "speaking": False, "mic": False}
    hud["uiq"] = []
    root.after(120, _drain_uiq, root, hud, state_lbl, mic_btn)

    def refresh():
        if hud.get("win") is None or not hud["win"].winfo_exists():
            return
        st = hud.setdefault("state", {})
        if time.time() < st.get("pause", 0) or st.get("mic"):
            root.after(1500, refresh)
            return
        d = _json_get("/api/voice-info")
        mode = d.get("mode", "--")
        if mode != st["mode"]:
            st["mode"] = mode
            try:
                mode_lbl.config(text=f"MODE: {mode.upper()}")
            except Exception:
                pass
        s = _json_get("/api/speak/status")
        st["speaking"] = bool(s.get("speaking"))
        try:
            if st["speaking"]:
                state_lbl.config(text="status: SPEAKING", fg="#7dffa1")
            else:
                state_lbl.config(text="status: idle \u2014 say 'Hey Jenny' or type below", fg=dim)
        except Exception:
            pass
        try:
            wake_btn.config(text="Wake Word: OFF" if not wake_word_running() else "Wake Word: ON")
        except Exception:
            pass
        root.after(1500, refresh)

    refresh()


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
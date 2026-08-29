"""
J.E.N.N.Y v2.0 — HUD Overlay Mode
Transparent, frameless, always-on-top holographic overlay.
Loads the mini HUD UI served by the local app server.
"""
import sys
import time
import threading
import socket
from pathlib import Path

import webview

BASE_DIR = Path(__file__).parent
PORT = 3005
WIDTH, HEIGHT = 480, 720


def is_port_open(port, host="127.0.0.1", timeout=0.3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_server():
    try:
        from waitress import serve
        sys.path.insert(0, str(BASE_DIR))
        import server
        threading.Thread(target=server.update_telemetry, daemon=True).start()
        serve(server.app, host="0.0.0.0", port=PORT, threads=4)
    except Exception as e:
        print(f"[!] Server failed: {e}")


def main():
    print("=" * 50)
    print("  J.E.N.N.Y v2.0 — HUD Overlay")
    print("=" * 50)

    if not is_port_open(PORT):
        print(f"[*] Starting local server on port {PORT}...")
        t = threading.Thread(target=start_server, daemon=True)
        t.start()
        for _ in range(20):
            if is_port_open(PORT):
                break
            time.sleep(0.5)

    window = webview.create_window(
        "J.E.N.N.Y HUD",
        f"http://127.0.0.1:{PORT}/mini.html",
        width=WIDTH,
        height=HEIGHT,
        x=50,
        y=50,
        frameless=True,
        transparent=True,
        on_top=True,
        resizable=False,
        easy_drag=True,
        shadow=False,
        background_color="#000000",
        text_select=False,
    )

    print("[+] Opening HUD overlay...")
    try:
        webview.start()
    except Exception as e:
        print(f"[!] webview.start failed: {e}")


if __name__ == "__main__":
    main()
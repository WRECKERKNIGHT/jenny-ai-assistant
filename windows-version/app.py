"""
J.E.N.N.Y v2.0 — Desktop App Wrapper
"""
import webview
import threading
import time
import sys
import os
import socket
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).parent
PORT = 3005


def is_port_open(port, host="127.0.0.1", timeout=0.3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_server(port=PORT):
    from waitress import serve
    sys.path.insert(0, str(BASE_DIR))
    import server
    threading.Thread(target=server.update_telemetry, daemon=True).start()
    serve(server.app, host="0.0.0.0", port=port, threads=8)


def play_startup_sound():
    try:
        import winsound
        notes = [523, 659, 784, 1047, 784, 659, 523, 659, 784, 1047, 1319, 1047, 784, 659, 523]
        for freq in notes:
            try:
                winsound.Beep(freq, 180)
            except Exception:
                time.sleep(0.18)
            time.sleep(0.06)
    except ImportError:
        pass


def main():
    argv = sys.argv[1:]
    page = "modes.html"
    debug = False
    port = PORT
    if "--debug" in argv:
        debug = True
    for i, a in enumerate(argv):
        if a == "--page" and i + 1 < len(argv):
            page = argv[i + 1]
        elif a == "--port" and i + 1 < len(argv):
            try:
                port = int(argv[i + 1])
            except ValueError:
                pass
        elif a == "--no-sound":
            pass

    print("=" * 55)
    print(f"  J.E.N.N.Y v2.0 — Starting (page={page}, port={port}, debug={debug})")
    print("=" * 55)

    if "--no-sound" not in argv:
        music_thread = threading.Thread(target=play_startup_sound, daemon=True)
        music_thread.start()

    if not is_port_open(port):
        print("[*] Waiting for server to start...")
        server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
        server_thread.start()
        for _ in range(30):
            if is_port_open(port):
                break
            time.sleep(0.5)
    else:
        print(f"[i] Server already running on port {port}, reusing it.")

    if not is_port_open(port):
        print("[!] Server failed to boot within timeout. Opening anyway...")

    window = webview.create_window(
        "J.E.N.N.Y v2.0",
        f"http://127.0.0.1:{port}/{page}",
        width=1440,
        height=900,
        min_size=(1200, 750),
        background_color="#000000",
        text_select=True,
    )

    print("[+] Opening pywebview window...")
    try:
        webview.start(debug=debug)
    except Exception as e:
        print(f"[!] webview.start failed: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
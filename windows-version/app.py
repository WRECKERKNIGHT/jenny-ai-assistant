"""
J.E.N.N.Y v2.0 — Desktop App Wrapper
"""
import webview
import threading
import time
import sys
import os
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).parent

def start_server():
    from waitress import serve
    sys.path.insert(0, str(BASE_DIR))
    import server
    threading.Thread(target=server.update_telemetry, daemon=True).start()
    serve(server.app, host="0.0.0.0", port=3005, threads=8)

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
    print("=" * 55)
    print("  J.E.N.N.Y v2.0 — Starting...")
    print("=" * 55)

    music_thread = threading.Thread(target=play_startup_sound, daemon=True)
    music_thread.start()

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    print("[*] Waiting for server to start...")
    time.sleep(4)

    window = webview.create_window(
        "J.E.N.N.Y v2.0",
        "http://127.0.0.1:3005/modes.html",
        width=1440,
        height=900,
        min_size=(1200, 750),
        background_color="#000000",
        text_select=True,
    )

    print("[+] Opening pywebview window...")
    try:
        webview.start(debug=False)
    except Exception as e:
        print(f"[!] webview.start failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()

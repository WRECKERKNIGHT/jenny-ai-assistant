"""
J.E.N.N.Y v2.0 — Desktop App Wrapper
Uses pywebview to run the web frontend as a native desktop window.
"""
import webview
import threading
import time
import sys
import os
import winsound
from pathlib import Path

BASE_DIR = Path(__file__).parent

def start_server():
    sys.path.insert(0, str(BASE_DIR))
    import server
    server.app.run(host="0.0.0.0", port=3005, debug=False, threaded=True, use_reloader=False)

def play_intro_music():
    notes = [523, 659, 784, 1047, 784, 659, 523, 659, 784, 1047, 1319, 1047, 784, 659, 523]
    for freq in notes:
        winsound.Beep(freq, 180)
        time.sleep(0.06)

def main():
    print("=" * 55)
    print("  J.E.N.N.Y v2.0 — Desktop AI Assistant")
    print("=" * 55)

    music_thread = threading.Thread(target=play_intro_music, daemon=True)
    music_thread.start()

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(3)

    window = webview.create_window(
        "J.E.N.N.Y v2.0",
        "http://localhost:3005",
        width=1440,
        height=900,
        min_size=(1200, 750),
        background_color="#000000",
        text_select=True,
    )

    print("[+] Opening desktop window...")
    webview.start(debug=False)

if __name__ == "__main__":
    main()
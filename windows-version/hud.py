"""
J.E.N.N.Y v2.0 — HUD Overlay Mode
Transparent, frameless, always-on-top holographic overlay.
Loads the mini HUD UI served by the local app server.

Usage:  python hud.py [--x POS] [--y POS] [--width W] [--height H] [--debug]
"""
import sys
import time
import threading
import socket
from pathlib import Path

import webview

BASE_DIR = Path(__file__).parent
DEFAULT_PORT = 3005
DEFAULT_W, DEFAULT_H = 480, 720
DEFAULT_X, DEFAULT_Y = 50, 50


def is_port_open(port, host="127.0.0.1", timeout=0.3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_server(port):
    try:
        from waitress import serve
        sys.path.insert(0, str(BASE_DIR))
        import server
        threading.Thread(target=server.update_telemetry, daemon=True).start()
        serve(server.app, host="0.0.0.0", port=port, threads=4)
    except Exception as e:
        print(f"[!] Server failed: {e}")


def parse_args(argv):
    args = {"x": DEFAULT_X, "y": DEFAULT_Y, "width": DEFAULT_W, "height": DEFAULT_H, "debug": False, "port": DEFAULT_PORT}
    i = 1
    while i < len(argv):
        flag = argv[i]
        if flag == "--debug":
            args["debug"] = True
        elif flag in ("--x", "--y", "--width", "--height", "--port") and i + 1 < len(argv):
            try:
                args[flag.lstrip("-")] = int(argv[i + 1])
            except ValueError:
                pass
            i += 1
        i += 1
    return args


def main():
    args = parse_args(sys.argv)
    port = args["port"]

    print("=" * 50)
    print(f"  J.E.N.N.Y v2.0 — HUD Overlay  (position={args['x']},{args['y']} size={args['width']}x{args['height']})")
    print("=" * 50)

    if not is_port_open(port):
        print(f"[*] Starting local server on port {port}...")
        t = threading.Thread(target=start_server, args=(port,), daemon=True)
        t.start()
        for _ in range(20):
            if is_port_open(port):
                break
            time.sleep(0.5)
    else:
        print(f"[i] Server already running on port {port}, reusing it.")

    window = webview.create_window(
        "J.E.N.N.Y HUD",
        f"http://127.0.0.1:{port}/mini.html",
        width=args["width"],
        height=args["height"],
        x=args["x"],
        y=args["y"],
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
        webview.start(debug=args["debug"])
    except Exception as e:
        print(f"[!] webview.start failed: {e}")


if __name__ == "__main__":
    main()
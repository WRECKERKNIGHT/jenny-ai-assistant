"""
J.E.N.N.Y - Windows Launcher
Starts server, GUI, and wake word detector
"""

import sys
import os
import time
import threading
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent


def start_server():
    print("[*] Starting J.E.N.N.Y server...")
    server_script = BASE_DIR / "server.py"
    subprocess.Popen(
        [sys.executable, str(server_script)],
        cwd=str(BASE_DIR),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )


def start_overlay():
    print("[*] Starting overlay GUI...")
    gui_script = BASE_DIR / "gui.py"
    subprocess.Popen(
        [sys.executable, str(gui_script), "overlay"],
        cwd=str(BASE_DIR)
    )


def start_main_app():
    print("[*] Starting main application...")
    gui_script = BASE_DIR / "gui.py"
    subprocess.Popen(
        [sys.executable, str(gui_script), "main"],
        cwd=str(BASE_DIR)
    )


def start_wakeword():
    print("[*] Starting wake word detector...")
    wakeword_script = BASE_DIR / "scripts" / "wakeword.py"
    subprocess.Popen(
        [sys.executable, str(wakeword_script)],
        cwd=str(BASE_DIR)
    )


def wait_for_server(timeout=15):
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen("http://localhost:5000", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    print("=" * 55)
    print("  J.E.N.N.Y - Windows AI Assistant Launcher")
    print("  Just a Enhanced Neural Network for You")
    print("=" * 55)
    print()
    print("  Choose launch mode:")
    print("  1. Full App (Server + Main Window)")
    print("  2. Overlay Mode (Server + Transparent Overlay)")
    print("  3. Server Only")
    print("  4. Server + Wake Word Detector")
    print("  5. Everything (Server + Main App + Wake Word)")
    print()

    choice = input("  Enter choice (1-5, default=1): ").strip() or "1"

    if choice == "1":
        start_server()
        print("[*] Waiting for server to start...")
        if wait_for_server():
            print("[+] Server is online!")
            time.sleep(0.5)
            start_main_app()
        else:
            print("[!] Server may still be starting. Check http://localhost:5000")

    elif choice == "2":
        start_server()
        print("[*] Waiting for server to start...")
        if wait_for_server():
            print("[+] Server is online!")
            time.sleep(0.5)
            start_overlay()
        else:
            print("[!] Server may still be starting. Check http://localhost:5000")

    elif choice == "3":
        start_server()
        print("[*] Server starting at http://localhost:5000")
        print("[*] Press Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[*] Shutting down...")

    elif choice == "4":
        start_server()
        if wait_for_server():
            start_wakeword()
            print("[*] Wake word detector active. Say 'Hey Jenny' to activate!")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[*] Shutting down...")

    elif choice == "5":
        start_server()
        if wait_for_server():
            print("[+] Server online!")
            time.sleep(0.3)
            start_main_app()
            time.sleep(0.3)
            start_wakeword()
            print("[+] All systems active!")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[*] Shutting down all components...")

    else:
        print("[!] Invalid choice. Starting default mode...")
        start_server()
        if wait_for_server():
            start_main_app()


if __name__ == '__main__':
    main()

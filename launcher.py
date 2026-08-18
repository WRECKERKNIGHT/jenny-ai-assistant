"""
J.E.N.N.Y v2.0 — Windows Desktop AI Assistant
Launcher: starts server + dashboard
"""
import subprocess
import sys
import time
import os
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).parent
SERVER_PY = BASE_DIR / "server.py"
DASHBOARD_PY = BASE_DIR / "dashboard.py"

def check_deps():
    required = ["flask", "flask_cors", "psutil"]
    optional = ["pyttsx3", "qrcode", "PIL", "speech_recognition", "requests"]
    missing_r = []
    missing_o = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing_r.append(pkg)
    for pkg in optional:
        try:
            __import__(pkg)
        except ImportError:
            missing_o.append(pkg)
    if missing_r:
        print(f"[!] Missing required packages: {', '.join(missing_r)}")
        print(f"    Run: pip install {' '.join(missing_r)}")
        return False
    if missing_o:
        print(f"[*] Optional packages not found: {', '.join(missing_o)}")
        print(f"    Some features may be limited.")
        print(f"    Run: pip install {' '.join(missing_o)}")
    return True

def start_server():
    print("[*] Starting Flask server...")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, str(SERVER_PY)],
        cwd=str(BASE_DIR),
        creationflags=creationflags,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)
    if proc.poll() is not None:
        stderr = proc.stderr.read().decode(errors="replace")
        print(f"[!] Server failed to start: {stderr[:500]}")
        return None
    print(f"[+] Server started (PID: {proc.pid})")
    return proc

def start_dashboard():
    print("[*] Starting dashboard...")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, str(DASHBOARD_PY)],
        cwd=str(BASE_DIR),
        creationflags=creationflags,
    )
    print(f"[+] Dashboard started (PID: {proc.pid})")
    return proc

def main():
    print("=" * 55)
    print("   J.E.N.N.Y v2.0 — Windows Desktop AI Assistant")
    print("   Just an Enhanced Neural Network for You")
    print("=" * 55)
    print()
    if not check_deps():
        print("\nInstall missing packages and try again.")
        input("Press Enter to exit...")
        return
    server_proc = start_server()
    if not server_proc:
        print("\nServer failed. Dashboard will show waiting screen.")
        print("You can start server manually: python server.py")
    dashboard_proc = start_dashboard()
    try:
        dashboard_proc.wait()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
    if server_proc:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except:
            server_proc.kill()
    print("[+] Goodbye, Boss!")

if __name__ == "__main__":
    main()

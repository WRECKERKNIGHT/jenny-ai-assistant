"""
J.E.N.N.Y - Windows Auto-Startup Installer
Registers Jenny to start automatically when Windows boots
"""

import sys
import os
import subprocess
from pathlib import Path


def install_startup():
    # scripts\ -> windows-version\ : server.py and logs\ live one level up.
    base_dir = Path(__file__).resolve().parent.parent
    server_path = base_dir / "server.py"
    python_path = sys.executable
    # Windowless: a console at every boot is what users complain about, so the
    # startup entry runs pythonw.exe and parks stdout/stderr in logs\.
    pythonw = Path(python_path).parent / "pythonw.exe"
    runner = str(pythonw) if pythonw.exists() else python_path
    logs_dir = base_dir / "logs"

    bat_content = f"""@echo off
title J.E.N.N.Y - Starting...
cd /d "{base_dir}"
if not exist "{logs_dir}" mkdir "{logs_dir}"
start "" "{runner}" "{server_path}" --startup >> "{logs_dir}\\jenny_startup.log" 2>&1
"""

    bat_path = base_dir / "jenny-startup.bat"

    with open(bat_path, 'w') as f:
        f.write(bat_content)

    startup_dir = Path(os.environ.get('APPDATA', '')) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut_path = startup_dir / "Jenny-Startup.bat"

    try:
        with open(shortcut_path, 'w') as f:
            f.write(bat_content)
        print(f"[+] Startup entry created at: {shortcut_path}")
        print("[+] J.E.N.N.Y will now start automatically with Windows!")
        return True
    except PermissionError:
        print("[!] Permission denied. Try running as Administrator.")
        return False
    except Exception as e:
        print(f"[!] Error: {e}")
        return False


def uninstall_startup():
    startup_dir = Path(os.environ.get('APPDATA', '')) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut_path = startup_dir / "Jenny-Startup.bat"

    if shortcut_path.exists():
        shortcut_path.unlink()
        print("[+] Startup entry removed!")
    else:
        print("[*] No startup entry found.")


def main():
    print("=" * 50)
    print("  J.E.N.N.Y - Startup Manager")
    print("=" * 50)
    print()
    print("  1. Install auto-start with Windows")
    print("  2. Remove auto-start")
    print()

    choice = input("  Enter choice (1-2): ").strip()

    if choice == "1":
        install_startup()
    elif choice == "2":
        uninstall_startup()
    else:
        print("[!] Invalid choice")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--install':
        install_startup()
    elif len(sys.argv) > 1 and sys.argv[1] == '--uninstall':
        uninstall_startup()
    else:
        main()

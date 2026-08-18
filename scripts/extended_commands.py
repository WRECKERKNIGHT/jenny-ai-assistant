"""
Extended system commands for J.E.N.N.Y
Additional control capabilities for Windows
"""

import os
import re
import sys
import time
import json
import subprocess
import ctypes
import webbrowser
import urllib.parse
from pathlib import Path
from datetime import datetime


def handle_extended_commands(command):
    lower = command.lower().strip()

    if "clipboard" in lower and ("copy" in lower or "paste" in lower or "show" in lower or "read" in lower):
        try:
            result = subprocess.run(['powershell', '-command', 'Get-Clipboard'],
                                    capture_output=True, text=True, timeout=5,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            clip = result.stdout.strip()
            if clip:
                return f"Clipboard content: {clip}, Boss!"
            return "Clipboard is empty, Boss!"
        except Exception:
            return "Couldn't read clipboard, Boss!"

    if "wifi" in lower and ("password" in lower or "info" in lower or "show" in lower):
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'interfaces'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                info_lines = [l.strip() for l in lines if any(k in l.lower() for k in ['ssid', 'signal', 'state', 'radio'])]
                return "WiFi Info:\n" + "\n".join(info_lines[:5]) + "\nStay connected, Boss!"
        except Exception:
            pass
        return "Couldn't get WiFi info, Boss!"

    if "screen resolution" in lower or "display resolution" in lower:
        try:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            return f"Screen resolution: {w} x {h}, Boss!"
        except Exception:
            return "Couldn't get screen resolution, Boss!"

    if "list processes" in lower or "running apps" in lower or "task list" in lower:
        try:
            result = subprocess.run(
                ['tasklist', '/fo', 'csv', '/nh'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            lines = result.stdout.strip().split('\n')
            apps = []
            for line in lines[:15]:
                parts = line.strip('"').split('","')
                if len(parts) >= 5:
                    name = parts[0]
                    mem = parts[4] if len(parts) > 4 else "?"
                    apps.append(f"  {name} - {mem}")
            if apps:
                return "Running processes:\n" + "\n".join(apps) + "\n...and more, Boss!"
        except Exception:
            pass
        return "Couldn't list processes, Boss!"

    if "what time zone" in lower or "time zone" in lower:
        tz = time.tzname
        return f"Time zone: {tz[0]} ({tz[1]}), Boss!"

    if "screen resolution" in lower or "display" in lower and "resolution" in lower:
        try:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            return f"Screen: {w} x {h} pixels, Boss!"
        except Exception:
            return "Couldn't detect screen resolution, Boss!"

    if "computer name" in lower or "pc name" in lower or "hostname" in lower:
        return f"Computer name: {os.environ.get('COMPUTERNAME', 'Unknown')}, Boss!"

    if "username" in lower or "who am i" in lower and "login" in lower:
        return f"You're logged in as: {os.environ.get('USERNAME', 'Unknown')}, Boss!"

    if "current directory" in lower or "where am i" in lower or "pwd" in lower:
        return f"Current directory: {os.getcwd()}, Boss!"

    if "system info" in lower or "pc info" in lower or "computer info" in lower:
        info = [
            f"OS: {platform.system()} {platform.release()}",
            f"Machine: {platform.machine()}",
            f"Processor: {platform.processor()}",
            f"Python: {platform.python_version()}",
            f"Computer: {os.environ.get('COMPUTERNAME', 'N/A')}",
        ]
        return "\n".join(info) + "\nThat's your system specs, Boss!"

    if "open control panel" in lower:
        os.system("control")
        return "Opening Control Panel, Boss!"

    if "open settings" in lower or "open windows settings" in lower:
        os.system("start ms-settings:")
        return "Opening Windows Settings, Boss!"

    if "open task manager" in lower:
        os.system("start taskmgr")
        return "Opening Task Manager, Boss!"

    if "open device manager" in lower:
        os.system("start devmgmt.msc")
        return "Opening Device Manager, Boss!"

    if "open disk management" in lower:
        os.system("start diskmgmt.msc")
        return "Opening Disk Management, Boss!"

    if "open event viewer" in lower:
        os.system("start eventvwr")
        return "Opening Event Viewer, Boss!"

    if "open registry editor" in lower:
        os.system("start regedit")
        return "Opening Registry Editor, Boss!"

    if "open services" in lower:
        os.system("start services.msc")
        return "Opening Services, Boss!"

    if "open command prompt" in lower or "open cmd" in lower:
        os.system("start cmd")
        return "Opening Command Prompt, Boss!"

    if "open powershell" in lower:
        os.system("start powershell")
        return "Opening PowerShell, Boss!"

    if "open windows explorer" in lower or "open file explorer" in lower:
        os.system("start explorer")
        return "Opening File Explorer, Boss!"

    if "open recycle bin" in lower:
        os.system("start shell:RecycleBinFolder")
        return "Opening Recycle Bin, Boss!"

    if "open temp folder" in lower or "open temp" in lower:
        os.startfile(os.environ.get('TEMP', 'C:\\Windows\\Temp'))
        return "Opening Temp folder, Boss!"

    if "open appdata" in lower:
        os.startfile(os.environ.get('APPDATA', ''))
        return "Opening AppData folder, Boss!"

    if "take ownership" in lower or "run as admin" in lower:
        return "I can't elevate permissions directly, Boss. Right-click and select 'Run as administrator' instead!"

    if "empty recycle bin" in lower or "clear recycle bin" in lower:
        try:
            subprocess.run(
                ['PowerShell', '-Command', 'Clear-RecycleBin -Force'],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return "Recycle Bin emptied, Boss!"
        except Exception:
            return "Couldn't empty Recycle Bin, Boss!"

    if "hibernate" in lower:
        os.system("shutdown /h")
        return "Hibernating system, Boss!"

    if "cancel shutdown" in lower or "abort shutdown" in lower or "cancel restart" in lower:
        os.system("shutdown /a")
        return "Shutdown/Restart cancelled, Boss!"

    if "open downloads" in lower:
        os.startfile(str(Path.home() / "Downloads"))
        return "Opening Downloads, Boss!"

    if "open pictures" in lower:
        os.startfile(str(Path.home() / "Pictures"))
        return "Opening Pictures, Boss!"

    if "open music" in lower:
        os.startfile(str(Path.home() / "Music"))
        return "Opening Music, Boss!"

    if "open videos" in lower:
        os.startfile(str(Path.home() / "Videos"))
        return "Opening Videos, Boss!"

    if "open documents" in lower:
        os.startfile(str(Path.home() / "Documents"))
        return "Opening Documents, Boss!"

    if "clean temp" in lower or "clear temp" in lower:
        try:
            temp_dir = os.environ.get('TEMP', '')
            count = 0
            for f in Path(temp_dir).glob('*'):
                try:
                    if f.is_file():
                        f.unlink()
                        count += 1
                except Exception:
                    pass
            return f"Cleared {count} temporary files, Boss! Freed up some space!"
        except Exception:
            return "Couldn't clean temp files, Boss!"

    if "what's my ip" in lower or "my ip address" in lower:
        try:
            result = subprocess.run(
                ['powershell', '-command', '(Invoke-WebRequest -Uri "https://ipinfo.io/ip" -UseBasicParsing).Content'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            ip = result.stdout.strip()
            if ip:
                return f"Your public IP: {ip}, Boss!"
        except Exception:
            pass
        return "Couldn't fetch IP, Boss!"

    if "speed test" in lower or "internet speed" in lower:
        return "Run 'speedtest' in your browser at speedtest.net for accurate results, Boss! I'll open it for you.", webbrowser.open("https://speedtest.net")

    if "open github" in lower:
        webbrowser.open("https://github.com")
        return "Opening GitHub, Boss!"

    if "open chatgpt" in lower or "open ai" in lower:
        webbrowser.open("https://chat.openai.com")
        return "Opening ChatGPT, Boss!"

    if "open gmail" in lower or "open email" in lower:
        webbrowser.open("https://mail.google.com")
        return "Opening Gmail, Boss!"

    if "open maps" in lower:
        webbrowser.open("https://maps.google.com")
        return "Opening Google Maps, Boss!"

    if "open translate" in lower:
        webbrowser.open("https://translate.google.com")
        return "Opening Google Translate, Boss!"

    if "open drive" in lower or "open google drive" in lower:
        webbrowser.open("https://drive.google.com")
        return "Opening Google Drive, Boss!"

    if "open calendar" in lower:
        webbrowser.open("https://calendar.google.com")
        return "Opening Google Calendar, Boss!"

    if "open photos" in lower and "google" in lower:
        webbrowser.open("https://photos.google.com")
        return "Opening Google Photos, Boss!"

    if "open netflix" in lower:
        webbrowser.open("https://netflix.com")
        return "Opening Netflix, Boss!"

    if "open prime" in lower or "open amazon prime" in lower:
        webbrowser.open("https://primevideo.com")
        return "Opening Prime Video, Boss!"

    if "open hotstar" in lower or "open disney" in lower:
        webbrowser.open("https://hotstar.com")
        return "Opening Hotstar, Boss!"

    return None

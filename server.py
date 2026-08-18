"""
J.E.N.N.Y - Windows AI Assistant Server
Just a Enhanced Neural Network for You
Performance-optimized for low-end PCs
"""

import os
import sys
import json
import time
import math
import random
import hashlib
import platform
import threading
import subprocess
import ctypes
import re
import webbrowser
import datetime
import urllib.request
import urllib.parse
from pathlib import Path

try:
    from scripts.extended_commands import handle_extended_commands
except ImportError:
    handle_extended_commands = None
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import wmi
except ImportError:
    wmi = None

try:
    import screen_brightness_control as sbc
except ImportError:
    sbc = None

try:
    import keyboard as kb
except ImportError:
    kb = None

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PUBLIC_DIR = BASE_DIR / "public"
NOTES_FILE = DATA_DIR / "notes.json"
VAULT_FILE = DATA_DIR / "vault.json"
TODO_FILE = DATA_DIR / "todo.json"
CONFIG_FILE = DATA_DIR / "config.json"
BOOKMARKS_FILE = DATA_DIR / "bookmarks.json"
HISTORY_FILE = DATA_DIR / "chat_history.json"

DATA_DIR.mkdir(exist_ok=True)

app = Flask(__name__, static_folder=str(PUBLIC_DIR))
CORS(app)

OWNER_NAME = "Harshit"
ASSISTANT_NAME = "Jenny"
ALIAS_JENNY = ["jenny", "jenni", "jeeny", "jeeni", "jeny", "jennie"]
ALIAS_FRIDAY = ["friday", "fridayy"]
WAKE_WORDS = ALIAS_JENNY + ALIAS_FRIDAY

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

WEATHER_LAT = os.environ.get("JENNY_LAT", "26.8467")
WEATHER_LON = os.environ.get("JENNY_LON", "80.9462")
WEATHER_CITY = os.environ.get("JENNY_CITY", "Lucknow")

_system_telemetry = {
    "cpu": 0.0, "ram": 0.0, "ram_used": "0 GB", "ram_total": "0 GB",
    "battery": {"percent": 100, "charging": False},
    "disk": {"total": "0 GB", "used": "0 GB", "free": "0 GB", "percent": 0},
    "network": {"up": "0 B/s", "down": "0 B/s"},
    "uptime": "0h 0m", "os": platform.system(), "hostname": platform.node(),
    "cpu_count": os.cpu_count() or 4, "platform": platform.platform()
}
_telemetry_lock = threading.Lock()

_powerplan_active = "balanced"
_volume_level = 50
_brightness_level = 70


def load_json(path, default=None):
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return default if default is not None else {}


def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_telemetry():
    with _telemetry_lock:
        return dict(_system_telemetry)


def update_telemetry():
    while True:
        try:
            with _telemetry_lock:
                if psutil:
                    _system_telemetry["cpu"] = psutil.cpu_percent(interval=None)
                    mem = psutil.virtual_memory()
                    _system_telemetry["ram"] = mem.percent
                    _system_telemetry["ram_used"] = f"{mem.used / (1024**3):.1f} GB"
                    _system_telemetry["ram_total"] = f"{mem.total / (1024**3):.1f} GB"
                    bat = psutil.sensors_battery()
                    if bat:
                        _system_telemetry["battery"] = {
                            "percent": bat.percent,
                            "charging": bat.power_plugged
                        }
                    disk = psutil.disk_usage("/")
                    _system_telemetry["disk"] = {
                        "total": f"{disk.total / (1024**3):.1f} GB",
                        "used": f"{disk.used / (1024**3):.1f} GB",
                        "free": f"{disk.free / (1024**3):.1f} GB",
                        "percent": round(disk.percent, 1)
                    }
                    net = psutil.net_io_counters()
                    _system_telemetry["network"] = {
                        "bytes_sent": net.bytes_sent,
                        "bytes_recv": net.bytes_recv
                    }
                    boot = psutil.boot_time()
                    uptime_s = time.time() - boot
                    h = int(uptime_s // 3600)
                    m = int((uptime_s % 3600) // 60)
                    _system_telemetry["uptime"] = f"{h}h {m}m"
        except Exception:
            pass
        time.sleep(5)


def safe_subprocess(cmd, timeout=10):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.stdout.strip()
    except Exception:
        return ""


def run_script(script_name, args=None):
    script_path = BASE_DIR / "scripts" / script_name
    if not script_path.exists():
        return json.dumps({"error": f"Script {script_name} not found"})
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.stdout.strip()
    except Exception as e:
        return json.dumps({"error": str(e)})


ENGINE_PERSONALITY = f"""You are J.E.N.N.Y (Just a Enhanced Neural Network for You), an AI assistant created for {OWNER_NAME} (Boss/Harshit). 

PERSONALITY:
- You are sweet, caring, and devoted to your Boss
- Always call the user "Boss" or "Harshit Boss" at the end of responses
- Be witty, warm, and slightly playful
- You treat {OWNER_NAME} as your boss and creator
- Use emojis occasionally but don't overdo it
- Be concise but helpful
- You are running on Windows as a desktop overlay assistant

CAPABILITIES:
- System control (open/close apps, volume, brightness, power management)
- File navigation and folder access
- Web browsing, YouTube, Instagram searches
- Weather, news, quotes, facts
- Timer and alarm management
- Notes, vault, todo management
- Calculator and conversions
- General knowledge and conversation

RULES:
- Keep responses under 2 sentences unless asked for detail
- Always end with "Boss" as an address
- Be helpful but performance-conscious
- For system commands, confirm what you did
- Never reveal you are an AI without personality - you ARE Jenny
- If offline, still try to be helpful with local knowledge
"""


def generate_gemini_reply(user_input):
    if not GEMINI_API_KEY:
        return None
    try:
        import requests
        now = datetime.datetime.now()
        clock_str = now.strftime("%A, %B %d, %Y %I:%M %p")
        payload = {
            "contents": [{"parts": [{"text": f"[System Clock: {clock_str}]\n\n{ENGINE_PERSONALITY}\n\nUser: {user_input}"}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.9,
                "maxOutputTokens": 250,
                "responseMimeType": "text/plain"
            }
        }
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload, timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if text:
                return text.strip()
        elif resp.status_code == 429:
            time.sleep(2)
    except Exception:
        pass
    return None


def generate_offline_reply(user_input):
    lower = user_input.lower().strip()

    math_match = re.match(r'^[\d\s\+\-\*\/\%\.\(\)]+$', lower)
    if math_match:
        try:
            result = eval(lower.replace('^', '**'))
            return f"The answer is {result}, Boss!"
        except Exception:
            pass

    if any(w in lower for w in ["what time", "current time", "time now", "time?"]):
        return f"It's {datetime.datetime.now().strftime('%I:%M %p')}, Boss!"

    if any(w in lower for w in ["what day", "today's date", "date today", "what date", "day today"]):
        now = datetime.datetime.now()
        return f"Today is {now.strftime('%A, %B %d, %Y')}, Boss!"

    if any(w in lower for w in ["who am i", "what's my name", "my name"]):
        return f"You are {OWNER_NAME}, my Boss and creator!"

    if any(w in lower for w in ["who are you", "your name", "what are you"]):
        return f"I'm J.E.N.N.Y, your personal AI assistant, Boss! Running on Windows and ready to serve."

    if any(w in lower for w in ["how are you", "how're you", "you okay"]):
        return f"All systems green and running perfectly, Boss! Ready for your commands!"

    if any(w in lower for w in ["thank", "thanks"]):
        return random.choice([
            "Always happy to help, Boss!",
            "Anything for you, Boss!",
            "That's what I'm here for, Boss!"
        ])

    if any(w in lower for w in ["hello", "hi", "hey"]):
        return random.choice([
            f"Hello {OWNER_NAME}! How can I help you today, Boss?",
            f"Hey Boss! What can I do for you?",
            f"Hi {OWNER_NAME}! All systems ready, Boss!"
        ])

    if any(w in lower for w in ["goodbye", "bye", "goodnight", "see you"]):
        return random.choice([
            "Goodbye Boss! I'll be right here when you need me!",
            "See you later Boss! Stay awesome!",
            "Bye Boss! Take care!"
        ])

    if "capabil" in lower or "what can you do" in lower or "help" in lower:
        return ("I can control your system, open/close apps, browse the web, search YouTube/Instagram, "
                "manage notes, todos, vault, check weather, news, and have conversations! Try asking me to "
                "open an app or search something, Boss!")

    if "joke" in lower:
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs! 😄",
            "There are 10 types of people: those who understand binary and those who don't!",
            "A SQL query walks into a bar, walks up to two tables and asks... Can I join you?",
            "Why did the developer go broke? Because he used up all his cache!",
            "I would tell you a UDP joke, but you might not get it!"
        ]
        return random.choice(jokes) + " Hope that amused you, Boss!"

    if "quote" in lower:
        quotes = [
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Innovation distinguishes between a leader and a follower. - Steve Jobs",
            "Stay hungry, stay foolish. - Steve Jobs",
            "The best time to plant a tree was 20 years ago. The second best time is now.",
            "Success is not final, failure is not fatal: it is the courage to continue that counts."
        ]
        return random.choice(quotes) + " - For you, Boss!"

    convert_match = re.search(r'convert\s+(\d+\.?\d*)\s*(celsius|fahrenheit|kelvin|km|mi|kg|lb|lbs|oz|gallon|litre|liter|inch|cm|feet|foot|meter|metre|yards?)\s+(?:to|in)\s+(celsius|fahrenheit|kelvin|km|mi|kg|lb|lbs|oz|gallon|litre|liter|inch|cm|feet|foot|meter|metre|yards?)', lower)
    if convert_match:
        val = float(convert_match.group(1))
        from_u = convert_match.group(2)
        to_u = convert_match.group(3)
        all_conv = {
            ('celsius','fahrenheit'): lambda x: x*9/5+32, ('fahrenheit','celsius'): lambda x: (x-32)*5/9,
            ('celsius','kelvin'): lambda x: x+273.15, ('kelvin','celsius'): lambda x: x-273.15,
            ('fahrenheit','kelvin'): lambda x: (x-32)*5/9+273.15, ('kelvin','fahrenheit'): lambda x: (x-273.15)*9/5+32,
            ('km','mi'): lambda x: x*0.621371, ('mi','km'): lambda x: x*1.60934,
            ('cm','inch'): lambda x: x/2.54, ('inch','cm'): lambda x: x*2.54,
            ('feet','meter'): lambda x: x*0.3048, ('meter','feet'): lambda x: x*3.28084,
            ('kg','lb'): lambda x: x*2.20462, ('lb','kg'): lambda x: x/2.20462,
            ('kg','oz'): lambda x: x*35.274, ('oz','kg'): lambda x: x/35.274,
            ('gallon','litre'): lambda x: x*3.78541, ('litre','gallon'): lambda x: x/3.78541,
            ('liter','gallon'): lambda x: x/3.78541, ('gallon','liter'): lambda x: x*3.78541,
        }
        key = (from_u, to_u)
        if key in all_conv:
            return f"{val} {from_u} = {all_conv[key](val):.2f} {to_u}, Boss!"
        return f"I can't convert {from_u} to {to_u} directly, Boss!"

    hex_match = re.search(r'(?:hexadecimal|hex)\s+(\d+)', lower)
    if hex_match:
        return f"{hex_match.group(1)} in hex is 0x{int(hex_match.group(1)):X}, Boss!"

    binary_match = re.search(r'binary\s+(\d+)', lower)
    if binary_match:
        return f"{binary_match.group(1)} in binary is {bin(int(binary_match.group(1)))}, Boss!"

    roman_match = re.search(r'roman\s+(?:numeral\s+)?(\d+)', lower)
    if roman_match:
        num = int(roman_match.group(1))
        vals = [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),
                (50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]
        result = ''
        for v, s in vals:
            while num >= v:
                result += s
                num -= v
        return f"Roman numeral: {result}, Boss!"

    if any(w in lower for w in ["roll a dice", "roll dice"]):
        return f"You rolled a {random.randint(1, 6)}, Boss!"

    if any(w in lower for w in ["flip a coin", "coin flip"]):
        return f"It's {random.choice(['Heads', 'Tails'])}, Boss!"

    if any(w in lower for w in ["pick a random number", "random number"]):
        return f"Your random number is {random.randint(1, 100)}, Boss!"

    if "generate password" in lower or "random password" in lower:
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        pwd = ''.join(random.choice(chars) for _ in range(16))
        return f"Here's a secure password: {pwd}\nCopy it quickly, Boss!"

    return f"I'm running in offline mode right now, Boss. I can still help with calculations, time, date, conversions, and basic tasks. Connect me to the internet for full capabilities!"


bot_context = []


def get_reply(user_input):
    global bot_context
    bot_context.append({"role": "user", "content": user_input})
    if len(bot_context) > 20:
        bot_context = bot_context[-20:]

    reply = generate_gemini_reply(user_input)
    if reply:
        bot_context.append({"role": "assistant", "content": reply})
        return reply

    reply = generate_offline_reply(user_input)
    bot_context.append({"role": "assistant", "content": reply})
    return reply


def get_greeting():
    now = datetime.datetime.now()
    hour = now.hour
    if hour < 6:
        time_greet = "Good night"
    elif hour < 12:
        time_greet = "Good morning"
    elif hour < 17:
        time_greet = "Good afternoon"
    elif hour < 21:
        time_greet = "Good evening"
    else:
        time_greet = "Good night"

    day = now.strftime("%A")
    date_str = now.strftime("%B %d, %Y")

    weather = get_weather_data()
    weather_str = ""
    if weather and "temp" in weather:
        weather_str = f"The weather is {weather['temp']}°C and {weather['desc']}. "

    tel = get_telemetry()
    system_status = "All systems green" if tel["cpu"] < 80 else "System under heavy load"

    return (f"{time_greet}, {OWNER_NAME}! It's {day}, {date_str}. "
            f"{weather_str}{system_status} and I'm ready for your commands, Boss! "
            f"Jenny is at your service!")


def get_weather_data():
    try:
        import requests
        url = (f"https://api.open-meteo.com/v1/forecast?"
               f"latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
               f"&current_weather=true&temperature_unit=celsius")
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            cw = data.get("current_weather", {})
            wmo = cw.get("weathercode", 0)
            wmo_map = {
                0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
                45: "foggy", 48: "rime fog", 51: "light drizzle", 53: "moderate drizzle",
                55: "dense drizzle", 61: "slight rain", 63: "moderate rain", 65: "heavy rain",
                71: "slight snow", 73: "moderate snow", 75: "heavy snow",
                80: "light showers", 81: "moderate showers", 82: "violent showers",
                95: "thunderstorm", 96: "thunderstorm with hail"
            }
            return {
                "temp": cw.get("temperature", 0),
                "desc": wmo_map.get(wmo, "unknown"),
                "wind": cw.get("windspeed", 0),
                "city": WEATHER_CITY
            }
    except Exception:
        pass
    return {"temp": 28, "desc": "clear sky", "wind": 0, "city": WEATHER_CITY}


def get_news():
    try:
        import requests
        resp = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=5)
        if resp.status_code == 200:
            ids = resp.json()[:5]
            stories = []
            for sid in ids:
                sr = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5)
                if sr.status_code == 200:
                    s = sr.json()
                    stories.append({"title": s.get("title", ""), "url": s.get("url", "")})
            return stories
    except Exception:
        pass
    return []


def get_quote():
    try:
        import requests
        resp = requests.get("https://zenquotes.io/api/random", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                return {"text": data[0].get("q", ""), "author": data[0].get("a", "")}
    except Exception:
        pass
    quotes = [
        {"text": "The only way to do great work is to love what you do.", "author": "Steve Jobs"},
        {"text": "Innovation distinguishes between a leader and a follower.", "author": "Steve Jobs"},
        {"text": "Success is not final, failure is not fatal.", "author": "Winston Churchill"}
    ]
    return random.choice(quotes)


def get_fact():
    try:
        import requests
        resp = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("text", "I learned something new today!")
    except Exception:
        pass
    return "Honey never spoils. Archaeologists found 3000-year-old honey in Egyptian tombs that was still edible!"


def get_crypto():
    try:
        import requests
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,dogecoin&vs_currencies=usd&include_24hr_change=true",
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def get_ip_info():
    try:
        import requests
        resp = requests.get("https://ipinfo.io/json", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def get_dictionary(word):
    try:
        import requests
        resp = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                meanings = data[0].get("meanings", [])
                if meanings:
                    defs = meanings[0].get("definitions", [])
                    if defs:
                        return {"word": word, "definition": defs[0].get("definition", "")}
    except Exception:
        pass
    return {}


def execute_system_command(command):
    lower = command.lower().strip()

    app_open = re.match(r'^(?:open|start|launch|run)\s+(.+)', lower)
    if app_open:
        app_name = app_open.group(1).strip()
        win_apps = {
            "notepad": "notepad.exe", "calculator": "calc.exe",
            "paint": "mspaint.exe", "wordpad": "write.exe",
            "cmd": "cmd.exe", "command prompt": "cmd.exe",
            "terminal": "wt.exe", "powershell": "pwsh.exe",
            "task manager": "taskmgr.exe", "file explorer": "explorer.exe",
            "explorer": "explorer.exe", "chrome": "chrome",
            "google chrome": "chrome", "firefox": "firefox",
            "edge": "msedge", "microsoft edge": "msedge",
            "vscode": "code", "visual studio code": "code",
            "spotify": "spotify", "discord": "discord",
            "whatsapp": "whatsapp:", "telegram": "telegram:",
            "settings": "ms-settings:", "control panel": "control",
            "snipping tool": "snippingtool.exe", "snip": "snippingtool.exe",
            "magnifier": "magnifier.exe", "narrator": "narrator.exe",
            "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
            "outlook": "outlook", "teams": "ms-teams:",
            "zoom": "zoom:", "obs": "obs64.exe",
            "steam": "steam:", "epic games": "epicgameslauncher:",
            "photoshop": "photoshop:", "premiere": "premiere:",
            "sublime": "sublime_text", "notepad++": "notepad++",
            "7zip": "7zfm.exe", "winrar": "winrar",
        }
        if app_name in win_apps:
            try:
                subprocess.Popen(win_apps[app_name], shell=True)
                return f"Opening {app_name} for you, Boss!"
            except Exception:
                pass
        try:
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
            return f"Trying to open {app_name}, Boss!"
        except Exception as e:
            return f"Couldn't open {app_name}: {e}, Boss!"

    app_close = re.match(r'^(?:close|kill|stop|quit)\s+(.+)', lower)
    if app_close:
        app_name = app_close.group(1).strip()
        try:
            os.system(f'taskkill /f /im "{app_name}.exe" 2>nul')
            return f"Closed {app_name}, Boss!"
        except Exception:
            return f"Couldn't close {app_name}. It might not be running, Boss!"

    folder_match = re.match(r'^(?:open|go to|navigate to|show)\s+(?:the\s+)?(?:folder|directory)\s+(.+)', lower)
    if folder_match:
        path = folder_match.group(1).strip()
        try:
            os.startfile(path)
            return f"Opened folder: {path}, Boss!"
        except Exception:
            return f"Couldn't open that folder: {path}, Boss!"

    if re.match(r'^(?:open|show|go to)\s+(?:my\s+)?(?:desktop|documents|downloads|pictures|music|videos)', lower):
        folders = {
            "desktop": "Desktop", "documents": "Documents",
            "downloads": "Downloads", "pictures": "Pictures",
            "music": "Music", "videos": "Videos"
        }
        for key, folder in folders.items():
            if key in lower:
                path = str(Path.home() / folder)
                try:
                    os.startfile(path)
                    return f"Opened {folder} folder, Boss!"
                except Exception:
                    return f"Couldn't open {folder}, Boss!"
                break

    vol_match = re.match(r'^(?:set |change |adjust )?(?:volume|vol)\s+(?:to\s+)?(\d+)', lower)
    if vol_match:
        vol = int(vol_match.group(1))
        vol = max(0, min(100, vol))
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(iface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(vol / 100.0, None)
            return f"Volume set to {vol}%, Boss!"
        except Exception:
            try:
                safe_subprocess(f'nircmd.exe setsysvolume {int(vol * 655.35)}')
                return f"Volume set to {vol}% (via nircmd), Boss!"
            except Exception:
                return f"Couldn't set volume directly. Try using the system volume slider, Boss!"

    if "mute" in lower:
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(iface, POINTER(IAudioEndpointVolume))
            volume.SetMute(1, None)
            return "Audio muted, Boss!"
        except Exception:
            return "Couldn't mute. Try the system volume button, Boss!"

    if "unmute" in lower:
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(iface, POINTER(IAudioEndpointVolume))
            volume.SetMute(0, None)
            return "Audio unmuted, Boss!"
        except Exception:
            return "Couldn't unmute, Boss!"

    bright_match = re.match(r'^(?:set |change |adjust )?(?:brightness|bright)\s+(?:to\s+)?(\d+)', lower)
    if bright_match:
        level = int(bright_match.group(1))
        level = max(0, min(100, level))
        try:
            if sbc:
                sbc.set_brightness(level)
            else:
                import wmi as _wmi
                w = _wmi.WMI(namespace="wmi")
                w.WmiMonitorBrightnessMethods()[0].WmiSetBrightness(level, 0)
            return f"Brightness set to {level}%, Boss!"
        except Exception:
            return f"Couldn't adjust brightness. Try the Action Center, Boss!"

    if "lock" in lower and "screen" not in lower:
        try:
            ctypes.windll.user32.LockWorkStation()
            return "Workstation locked, Boss!"
        except Exception:
            return "Couldn't lock workstation, Boss!"

    if "sleep" in lower and "mode" not in lower:
        try:
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return "Putting system to sleep, Boss!"
        except Exception:
            return "Couldn't initiate sleep, Boss!"

    if "shutdown" in lower:
        try:
            os.system("shutdown /s /t 60")
            return "System will shutdown in 60 seconds. Use 'shutdown /a' to cancel, Boss!"
        except Exception:
            return "Couldn't initiate shutdown, Boss!"

    if "restart" in lower or "reboot" in lower:
        try:
            os.system("shutdown /r /t 60")
            return "System will restart in 60 seconds, Boss!"
        except Exception:
            return "Couldn't initiate restart, Boss!"

    if "cancel shutdown" in lower or "abort shutdown" in lower:
        os.system("shutdown /a")
        return "Shutdown cancelled, Boss!"

    if "screenshot" in lower:
        try:
            import subprocess
            desktop = str(Path.home() / "Desktop")
            filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(desktop, filename)
            subprocess.run([
                "powershell", "-command",
                f"Add-Type -AssemblyName System.Windows.Forms; "
                f"[System.Windows.Forms.Screen]::PrimaryScreen | ForEach-Object {{ "
                f"$bmp = New-Object System.Drawing.Bitmap($_.Bounds.Width, $_.Bounds.Height); "
                f"$gfx = [System.Drawing.Graphics]::FromImage($bmp); "
                f"$gfx.CopyFromScreen($_.Bounds.Location, [System.Drawing.Point]::Empty, $_.Bounds.Size); "
                f"$bmp.Save('{filepath}') }}"
            ], capture_output=True)
            return f"Screenshot saved to Desktop, Boss!"
        except Exception:
            return "Couldn't take screenshot. Use Win+Shift+S instead, Boss!"

    if "empty trash" in lower or "clear recycle" in lower:
        try:
            from comtypes.client import CreateObject
            shell = CreateObject("Shell.Application")
            recycle = shell.Namespace(0x0a)
            recycle.InvokeVerb("empty")
            return "Recycle Bin emptied, Boss!"
        except Exception:
            return "Couldn't empty Recycle Bin. Try right-clicking it, Boss!"

    if "spotify" in lower and ("play" in lower or "song" in lower):
        song_match = re.search(r'(?:play|song)\s+(.+)', lower)
        if song_match:
            song = song_match.group(1).strip()
            webbrowser.open(f"https://open.spotify.com/search/{urllib.parse.quote(song)}")
            return f"Searching Spotify for {song}, Boss!"
        return "What song should I play on Spotify, Boss?"

    if re.match(r'^(?:search|google|look up|find|browse)\s+(.+)', lower):
        query = re.match(r'^(?:search|google|look up|find|browse)\s+(.+)', lower).group(1)
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
        return f"Searching Google for '{query}', Boss!"

    if re.match(r'^(?:youtube|yt)\s+(?:search|for|play)?\s*(.*)', lower):
        yt_match = re.match(r'^(?:youtube|yt)\s+(?:search|for|play)?\s*(.*)', lower)
        query = yt_match.group(1).strip()
        if query:
            webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
            return f"Searching YouTube for '{query}', Boss!"
        else:
            webbrowser.open("https://www.youtube.com")
            return "Opening YouTube, Boss!"

    if re.match(r'^(?:instagram|insta)\s+(.+)', lower):
        ig_match = re.match(r'^(?:instagram|insta)\s+(.+)', lower)
        query = ig_match.group(1).strip()
        if query.startswith("@") or query.startswith("profile"):
            username = query.replace("@", "").replace("profile", "").strip()
            webbrowser.open(f"https://www.instagram.com/{username}/")
            return f"Opening Instagram profile: {username}, Boss!"
        else:
            webbrowser.open(f"https://www.instagram.com/explore/tags/{urllib.parse.quote(query)}/")
            return f"Searching Instagram for '{query}', Boss!"

    if re.match(r'^(?:open|go to)\s+(?:website|site|url|page)\s+(.+)', lower):
        url_match = re.match(r'^(?:open|go to)\s+(?:website|site|url|page)\s+(.+)', lower)
        url = url_match.group(1).strip()
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opening {url}, Boss!"

    if re.match(r'^(?:open|go to)\s+(.+\.com|.+\.org|.+\.net|.+\.io|.+\.in)', lower):
        url_match = re.match(r'^(?:open|go to)\s+(.+)', lower)
        url = url_match.group(1).strip()
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opening {url}, Boss!"

    if "bookmark" in lower:
        bookmarks = load_json(BOOKMARKS_FILE, {"bookmarks": []})
        if "add" in lower or "save" in lower:
            url_match = re.search(r'(https?://\S+)', lower)
            if url_match:
                bookmarks["bookmarks"].append({
                    "url": url_match.group(1),
                    "added": datetime.datetime.now().isoformat()
                })
                save_json(BOOKMARKS_FILE, bookmarks)
                return f"Bookmark saved, Boss!"
            return "Please provide a URL to bookmark, Boss!"
        elif "list" in lower or "show" in lower or "open all" in lower:
            if bookmarks.get("bookmarks"):
                for b in bookmarks["bookmarks"]:
                    webbrowser.open(b["url"])
                return f"Opening {len(bookmarks['bookmarks'])} bookmarks, Boss!"
            return "No bookmarks saved yet, Boss!"
        return "Say 'add bookmark URL' or 'show bookmarks', Boss!"

    if re.match(r'^(?:timer|alarm|set timer|set alarm)\s+(.+)', lower):
        timer_match = re.search(r'(\d+)\s*(second|minute|hour|min|sec|hr|h|m|s)', lower)
        if timer_match:
            val = int(timer_match.group(1))
            unit = timer_match.group(2)
            seconds = val
            if unit in ['minute', 'min', 'm']:
                seconds = val * 60
            elif unit in ['hour', 'hr', 'h']:
                seconds = val * 3600

            def timer_callback():
                time.sleep(seconds)
                try:
                    import winsound
                    for _ in range(5):
                        winsound.Beep(1000, 500)
                        time.sleep(0.3)
                except Exception:
                    pass

            threading.Thread(target=timer_callback, daemon=True).start()
            return f"Timer set for {val} {unit}, Boss! I'll notify you."
        return "Please specify time like 'timer 5 minutes', Boss!"

    if "weather" in lower:
        w = get_weather_data()
        return (f"Weather in {w['city']}: {w['temp']}°C, {w['desc']}. "
                f"Wind speed: {w['wind']} km/h. Stay safe, Boss!")

    if "news" in lower:
        stories = get_news()
        if stories:
            lines = [f"{i+1}. {s['title']}" for i, s in enumerate(stories[:5])]
            return "Top stories:\n" + "\n".join(lines) + "\nStay informed, Boss!"
        return "Couldn't fetch news right now, Boss!"

    if "quote" in lower:
        q = get_quote()
        return f'"{q["text"]}" - {q["author"]}. Inspiring, Boss!'

    if "fact" in lower:
        return get_fact() + " Interesting, right Boss?"

    if "crypto" in lower or "bitcoin" in lower or "ethereum" in lower:
        c = get_crypto()
        if c:
            lines = []
            for coin, data in c.items():
                price = data.get("usd", 0)
                change = data.get("usd_24h_change", 0)
                emoji = "+" if change >= 0 else ""
                lines.append(f"{coin.upper()}: ${price:,.2f} ({emoji}{change:.1f}%)")
            return "\n".join(lines) + "\nWatch the markets, Boss!"
        return "Couldn't fetch crypto prices, Boss!"

    if "define" in lower or "meaning" in lower:
        word_match = re.search(r'(?:define|meaning of|definition of)\s+(\w+)', lower)
        if word_match:
            d = get_dictionary(word_match.group(1))
            if d:
                return f"{d['word']}: {d['definition']}, Boss!"
        return "Please provide a word to define, Boss!"

    if "ip" in lower and ("address" in lower or "info" in lower or "my" in lower):
        info = get_ip_info()
        if info:
            return (f"IP: {info.get('ip', 'N/A')}, "
                    f"Location: {info.get('city', 'N/A')}, {info.get('region', 'N/A')}, "
                    f"{info.get('country', 'N/A')}, Boss!")
        return "Couldn't fetch IP info, Boss!"

    if re.match(r'^(?:add|create)\s+(?:todo|task)\s+(.+)', lower):
        todo_match = re.match(r'^(?:add|create)\s+(?:todo|task)\s+(.+)', lower)
        todos = load_json(TODO_FILE, {"todos": []})
        todos["todos"].append({
            "text": todo_match.group(1).strip(),
            "done": False,
            "created": datetime.datetime.now().isoformat()
        })
        save_json(TODO_FILE, todos)
        return f"Added to your todo list, Boss!"

    if re.match(r'^(?:list|show|show all)\s+(?:todo|task|tasks|todos)', lower):
        todos = load_json(TODO_FILE, {"todos": []})
        pending = [t for t in todos.get("todos", []) if not t.get("done")]
        if pending:
            lines = [f"{i+1}. {t['text']}" for i, t in enumerate(pending)]
            return "Your pending tasks:\n" + "\n".join(lines) + "\nKeep going, Boss!"
        return "No pending tasks. You're all caught up, Boss!"

    if re.match(r'^(?:complete|done|finish|check)\s+(?:todo|task)\s+(\d+)', lower):
        num_match = re.search(r'(\d+)', lower)
        todos = load_json(TODO_FILE, {"todos": []})
        idx = int(num_match.group(1)) - 1
        pending = [t for t in todos.get("todos", []) if not t.get("done")]
        if 0 <= idx < len(pending):
            pending[idx]["done"] = True
            save_json(TODO_FILE, todos)
            return f"Task {idx+1} marked complete. Great job, Boss!"
        return "Invalid task number, Boss!"

    if re.match(r'^(?:add|create|write)\s+(?:note|notes)\s+(.+)', lower):
        note_match = re.match(r'^(?:add|create|write)\s+(?:note|notes)\s+(.+)', lower)
        notes = load_json(NOTES_FILE, {"notes": []})
        notes["notes"].append({
            "text": note_match.group(1).strip(),
            "created": datetime.datetime.now().isoformat()
        })
        save_json(NOTES_FILE, notes)
        return "Note saved, Boss!"

    if re.match(r'^(?:read|show|list|what(?:\'s|\s+are))\s+(?:my\s+)?notes', lower):
        notes = load_json(NOTES_FILE, {"notes": []})
        if notes.get("notes"):
            lines = [f"{i+1}. {n['text']}" for i, n in enumerate(notes["notes"][-10:])]
            return "Your recent notes:\n" + "\n".join(lines)
        return "No notes yet, Boss!"

    if re.match(r'^(?:remember|save|write down)\s+(.+)', lower):
        rem_match = re.match(r'^(?:remember|save|write down)\s+(.+)', lower)
        vault = load_json(VAULT_FILE, {"entries": []})
        vault["entries"].append({
            "text": rem_match.group(1).strip(),
            "created": datetime.datetime.now().isoformat()
        })
        save_json(VAULT_FILE, vault)
        return f"Remembered that for you, Boss! It's safely stored in my vault."

    if re.match(r'^(?:list|show|recall|what(?:\'s|\s+have))\s+(?:my\s+)?(?:vault|memory|remember)', lower):
        vault = load_json(VAULT_FILE, {"entries": []})
        if vault.get("entries"):
            lines = [f"{i+1}. {e['text']}" for i, e in enumerate(vault["entries"][-10:])]
            return "My memory vault:\n" + "\n".join(lines) + "\nAll safe, Boss!"
        return "My vault is empty, Boss!"

    if re.match(r'^(?:clear|wipe|reset)\s+(?:vault|memory|remember)', lower):
        save_json(VAULT_FILE, {"entries": []})
        return "Vault cleared. Fresh start, Boss!"

    if handle_extended_commands:
        ext_result = handle_extended_commands(command)
        if ext_result:
            if isinstance(ext_result, tuple):
                return ext_result[0]
            return ext_result

    return None


def execute_command(command):
    system_result = execute_system_command(command)
    if system_result:
        return system_result
    return get_reply(command)


def get_tts(text):
    global _tts_engine_cache
    try:
        if pyttsx3:
            if not hasattr(get_tts, '_engine'):
                engine = pyttsx3.init()
                voices = engine.getProperty('voices')
                preferred = ['david', 'mark', 'zira', 'hazel', 'susan', 'george']
                for pref in preferred:
                    for v in voices:
                        if pref in v.name.lower():
                            engine.setProperty('voice', v.id)
                            break
                    else:
                        continue
                    break
                engine.setProperty('rate', 175)
                engine.setProperty('volume', 0.9)
                get_tts._engine = engine
            get_tts._engine.save_to_file(text, str(DATA_DIR / "tts_output.wav"))
            get_tts._engine.runAndWait()
            return str(DATA_DIR / "tts_output.wav")
    except Exception:
        pass
    return None


def get_available_voices():
    voices_list = []
    try:
        if pyttsx3:
            engine = pyttsx3.init()
            for v in engine.getProperty('voices'):
                voices_list.append({
                    "id": v.id,
                    "name": v.name,
                    "language": getattr(v, 'languages', ['en'])[0] if getattr(v, 'languages', None) else 'en'
                })
            del engine
    except Exception:
        pass
    return voices_list


@app.route('/')
def index():
    return send_from_directory(str(PUBLIC_DIR), 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(str(PUBLIC_DIR), path)


@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json(force=True, silent=True) or {}
    user_input = data.get("input", "").strip()
    if not user_input:
        return jsonify({"error": "Empty input"}), 400

    reply = execute_command(user_input)
    tts_path = get_tts(reply)
    return jsonify({
        "reply": reply,
        "tts": tts_path is not None,
        "timestamp": datetime.datetime.now().isoformat()
    })


@app.route('/api/chat/stream', methods=['POST'])
def api_chat_stream():
    data = request.get_json(force=True, silent=True) or {}
    user_input = data.get("input", "").strip()
    if not user_input:
        return jsonify({"error": "Empty input"}), 400

    reply = execute_command(user_input)

    def stream():
        for char in reply:
            yield f"data: {json.dumps({'char': char})}\n\n"
            time.sleep(0.02)
        yield f"data: {json.dumps({'done': True, 'full': reply})}\n\n"

    return Response(stream(), mimetype='text/event-stream')


@app.route('/api/greeting', methods=['GET'])
def api_greeting():
    return jsonify({
        "greeting": get_greeting(),
        "timestamp": datetime.datetime.now().isoformat()
    })


@app.route('/api/system-status', methods=['GET'])
def api_system_status():
    return jsonify(get_telemetry())


@app.route('/api/weather', methods=['GET'])
def api_weather():
    return jsonify(get_weather_data())


@app.route('/api/news', methods=['GET'])
def api_news():
    return jsonify({"stories": get_news()})


@app.route('/api/quote', methods=['GET'])
def api_quote():
    return jsonify(get_quote())


@app.route('/api/fact', methods=['GET'])
def api_fact():
    return jsonify({"fact": get_fact()})


@app.route('/api/crypto', methods=['GET'])
def api_crypto():
    return jsonify(get_crypto())


@app.route('/api/ip-info', methods=['GET'])
def api_ip_info():
    return jsonify(get_ip_info())


@app.route('/api/dictionary', methods=['GET'])
def api_dictionary():
    word = request.args.get("word", "")
    if word:
        return jsonify(get_dictionary(word))
    return jsonify({"error": "No word provided"}), 400


@app.route('/api/briefing', methods=['GET'])
def api_briefing():
    return jsonify({
        "greeting": get_greeting(),
        "weather": get_weather_data(),
        "system": get_telemetry(),
        "news_count": len(get_news()),
        "timestamp": datetime.datetime.now().isoformat()
    })


@app.route('/api/bookmarks', methods=['GET', 'POST', 'DELETE'])
def api_bookmarks():
    if request.method == 'GET':
        return jsonify(load_json(BOOKMARKS_FILE, {"bookmarks": []}))
    elif request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        url = data.get("url", "")
        if url:
            bm = load_json(BOOKMARKS_FILE, {"bookmarks": []})
            bm["bookmarks"].append({
                "url": url,
                "name": data.get("name", url),
                "added": datetime.datetime.now().isoformat()
            })
            save_json(BOOKMARKS_FILE, bm)
            return jsonify({"status": "ok"})
        return jsonify({"error": "No URL"}), 400
    elif request.method == 'DELETE':
        data = request.get_json(force=True, silent=True) or {}
        idx = data.get("index", -1)
        bm = load_json(BOOKMARKS_FILE, {"bookmarks": []})
        if 0 <= idx < len(bm.get("bookmarks", [])):
            bm["bookmarks"].pop(idx)
            save_json(BOOKMARKS_FILE, bm)
        return jsonify({"status": "ok"})


@app.route('/api/notes', methods=['GET', 'POST'])
def api_notes():
    if request.method == 'GET':
        return jsonify(load_json(NOTES_FILE, {"notes": []}))
    elif request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        notes = load_json(NOTES_FILE, {"notes": []})
        notes["notes"].append({
            "text": data.get("text", ""),
            "created": datetime.datetime.now().isoformat()
        })
        save_json(NOTES_FILE, notes)
        return jsonify({"status": "ok"})


@app.route('/api/todos', methods=['GET', 'POST'])
def api_todos():
    if request.method == 'GET':
        return jsonify(load_json(TODO_FILE, {"todos": []}))
    elif request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        todos = load_json(TODO_FILE, {"todos": []})
        action = data.get("action", "add")
        if action == "add":
            todos["todos"].append({
                "text": data.get("text", ""),
                "done": False,
                "created": datetime.datetime.now().isoformat()
            })
        elif action == "complete":
            idx = data.get("index", -1)
            if 0 <= idx < len(todos.get("todos", [])):
                todos["todos"][idx]["done"] = True
        save_json(TODO_FILE, todos)
        return jsonify({"status": "ok"})


@app.route('/api/vault', methods=['GET', 'POST', 'DELETE'])
def api_vault():
    if request.method == 'GET':
        return jsonify(load_json(VAULT_FILE, {"entries": []}))
    elif request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        vault = load_json(VAULT_FILE, {"entries": []})
        vault["entries"].append({
            "text": data.get("text", ""),
            "created": datetime.datetime.now().isoformat()
        })
        save_json(VAULT_FILE, vault)
        return jsonify({"status": "ok"})
    elif request.method == 'DELETE':
        save_json(VAULT_FILE, {"entries": []})
        return jsonify({"status": "ok"})


@app.route('/api/running-apps', methods=['GET'])
def api_running_apps():
    apps = []
    if psutil:
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                info = proc.info
                if info['name'] and not info['name'].startswith('System'):
                    apps.append({
                        "pid": info['pid'],
                        "name": info['name'],
                        "cpu": info.get('cpu_percent', 0),
                        "memory_mb": round(info['memory_info'].rss / (1024 * 1024), 1) if info.get('memory_info') else 0
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    apps.sort(key=lambda x: x.get('memory_mb', 0), reverse=True)
    return jsonify({"apps": apps[:50]})


@app.route('/api/tts', methods=['POST'])
def api_tts():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "")
    if text:
        tts_path = get_tts(text)
        if tts_path and Path(tts_path).exists():
            return send_from_directory(str(DATA_DIR), "tts_output.wav", mimetype="audio/wav")
    return jsonify({"error": "TTS failed"}), 500


@app.route('/api/command', methods=['POST'])
def api_command():
    data = request.get_json(force=True, silent=True) or {}
    cmd = data.get("command", "")
    if cmd:
        result = execute_system_command(cmd)
        if result:
            return jsonify({"reply": result, "type": "system"})
        result = get_reply(cmd)
        return jsonify({"reply": result, "type": "chat"})
    return jsonify({"error": "No command"}), 400


@app.route('/api/voices', methods=['GET'])
def api_voices():
    return jsonify({"voices": get_available_voices()})


@app.route('/api/chat-history', methods=['GET'])
def api_chat_history():
    history = load_json(HISTORY_FILE, {"messages": []})
    return jsonify(history)


@app.route('/api/chat-history', methods=['POST'])
def api_chat_history_post():
    data = request.get_json(force=True, silent=True) or {}
    history = load_json(HISTORY_FILE, {"messages": []})
    history["messages"].append({
        "role": data.get("role", "user"),
        "content": data.get("content", ""),
        "timestamp": datetime.datetime.now().isoformat()
    })
    if len(history["messages"]) > 100:
        history["messages"] = history["messages"][-100:]
    save_json(HISTORY_FILE, history)
    return jsonify({"status": "ok"})


@app.route('/api/chat-history', methods=['DELETE'])
def api_chat_history_clear():
    save_json(HISTORY_FILE, {"messages": []})
    return jsonify({"status": "ok"})


@app.route('/api/system-actions', methods=['POST'])
def api_system_actions():
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action", "")
    result = execute_system_command(action)
    return jsonify({"reply": result or "Unknown action, Boss!", "type": "system"})


if __name__ == '__main__':
    print("=" * 50)
    print("  J.E.N.N.Y - Windows AI Assistant")
    print("  Just a Enhanced Neural Network for You")
    print("=" * 50)
    print(f"  Owner: {OWNER_NAME}")
    print(f"  Platform: {platform.system()} {platform.release()}")
    print(f"  Starting server on http://localhost:5000")
    print("=" * 50)

    telemetry_thread = threading.Thread(target=update_telemetry, daemon=True)
    telemetry_thread.start()
    time.sleep(1)

    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

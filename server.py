import os, sys, json, time, math, random, re, webbrowser, datetime, platform, subprocess, threading, urllib.request, urllib.parse, ctypes
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
try: import psutil
except: psutil = None
try: import pyttsx3
except: pyttsx3 = None

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
NOTES_FILE = DATA_DIR / "notes.json"
VAULT_FILE = DATA_DIR / "vault.json"
TODO_FILE = DATA_DIR / "todo.json"
BOOKMARKS_FILE = DATA_DIR / "bookmarks.json"
HISTORY_FILE = DATA_DIR / "chat_history.json"
app = Flask(__name__)
CORS(app)
OWNER = "Harshit"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
WEATHER_LAT = os.environ.get("JENNY_LAT", "26.8467")
WEATHER_LON = os.environ.get("JENNY_LON", "80.9462")
WEATHER_CITY = os.environ.get("JENNY_CITY", "Lucknow")
_telemetry = {"cpu": 0, "ram": 0, "ram_used": "0", "ram_total": "0", "disk_pct": 0, "disk_free": "0", "disk_total": "0", "battery_pct": 100, "battery_charging": False, "net_sent": 0, "net_recv": 0, "uptime": "0h 0m", "hostname": platform.node(), "os": f"{platform.system()} {platform.release()}", "cpu_name": platform.processor() or "Unknown CPU"}

def load_json(p, d=None):
    try:
        if Path(p).exists(): return json.loads(Path(p).read_text(encoding="utf-8"))
    except: pass
    return d if d is not None else {}

def save_json(p, d):
    Path(p).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def update_telemetry():
    while True:
        try:
            if psutil:
                _telemetry["cpu"] = psutil.cpu_percent(interval=None)
                m = psutil.virtual_memory()
                _telemetry["ram"] = m.percent
                _telemetry["ram_used"] = f"{m.used/(1024**3):.1f}"
                _telemetry["ram_total"] = f"{m.total/(1024**3):.1f}"
                d = psutil.disk_usage("/")
                _telemetry["disk_pct"] = round(d.percent, 1)
                _telemetry["disk_free"] = f"{d.free/(1024**3):.1f}"
                _telemetry["disk_total"] = f"{d.total/(1024**3):.1f}"
                b = psutil.sensors_battery()
                if b: _telemetry["battery_pct"] = b.percent; _telemetry["battery_charging"] = b.power_plugged
                n = psutil.net_io_counters()
                _telemetry["net_sent"] = n.bytes_sent
                _telemetry["net_recv"] = n.bytes_recv
                up = time.time() - psutil.boot_time()
                _telemetry["uptime"] = f"{int(up//3600)}h {int((up%3600)//60)}m"
        except: pass
        time.sleep(3)

def offline_reply(text):
    lo = text.lower().strip()
    if re.match(r'^[\d\s\+\-\*\/\%\.\(\)]+$', lo):
        try: return f"The answer is {eval(lo.replace('^','**'))}, Boss!"
        except: pass
    if any(w in lo for w in ["what time","current time","time now","time?"]): return f"It's {datetime.datetime.now().strftime('%I:%M %p')}, Boss!"
    if any(w in lo for w in ["what day","today's date","date today"]): return f"Today is {datetime.datetime.now().strftime('%A, %B %d, %Y')}, Boss!"
    if any(w in lo for w in ["who am i","my name"]): return f"You are {OWNER}, my Boss and creator!"
    if any(w in lo for w in ["who are you","your name"]): return f"I'm J.E.N.N.Y v2.0, your Windows desktop assistant, Boss!"
    if any(w in lo for w in ["how are you","you okay"]): return random.choice(["All systems green, Boss!","Feeling great, Boss!","Running at peak performance, Boss!"])
    if any(w in lo for w in ["thank","thanks"]): return random.choice(["Always happy to help, Boss!","Anything for you, Boss!","That's what I'm here for, Boss!"])
    if any(w in lo for w in ["hello","hi ","hey"]): return random.choice(["Hello Boss! How can I help?","Hey Boss! What can I do for you?","Hi Boss! All systems ready!"])
    if any(w in lo for w in ["goodbye","bye","goodnight"]): return random.choice(["Goodbye Boss!","See you later, Boss!","Bye Boss! Take care!"])
    if "capabil" in lo or "what can you do" in lo or "help" in lo: return "I can control your system, open/close apps, browse the web, search YouTube/Instagram, manage notes, todos, vault, weather, news, conversions, and conversations! Boss!"
    if "joke" in lo: return random.choice(["Why do programmers prefer dark mode? Light attracts bugs!","There are 10 types of people: those who understand binary and those who don't!","A SQL query walks into a bar... Can I join you?","Why did the developer go broke? Used up all his cache!","I'd tell you a UDP joke, but you might not get it!"]) + " Boss!"
    if "quote" in lo: return random.choice(["The only way to do great work is to love what you do. - Steve Jobs","Innovation distinguishes between a leader and a follower. - Steve Jobs","Stay hungry, stay foolish. - Steve Jobs","Success is not final, failure is not fatal. - Churchill"]) + " For you, Boss!"
    conv = re.search(r'convert\s+(\d+\.?\d*)\s*(celsius|fahrenheit|kelvin|km|mi|kg|lb|oz|inch|cm|feet|meter)\s+(?:to|in)\s+(celsius|fahrenheit|kelvin|km|mi|kg|lb|oz|inch|cm|feet|meter)', lo)
    if conv:
        v, fu, tu = float(conv.group(1)), conv.group(2), conv.group(3)
        c = {('celsius','fahrenheit'):lambda x:x*9/5+32,('fahrenheit','celsius'):lambda x:(x-32)*5/9,('celsius','kelvin'):lambda x:x+273.15,('kelvin','celsius'):lambda x:x-273.15,('km','mi'):lambda x:x*0.621371,('mi','km'):lambda x:x*1.60934,('kg','lb'):lambda x:x*2.20462,('lb','kg'):lambda x:x/2.20462}
        if (fu,tu) in c: return f"{v} {fu} = {c[(fu,tu)](v):.2f} {tu}, Boss!"
    if "hex" in lo:
        hm = re.search(r'hex\s+(\d+)', lo)
        if hm: return f"{hm.group(1)} in hex is 0x{int(hm.group(1)):X}, Boss!"
    if "binary" in lo:
        bm = re.search(r'binary\s+(\d+)', lo)
        if bm: return f"{bm.group(1)} in binary is {bin(int(bm.group(1)))}, Boss!"
    if any(w in lo for w in ["roll dice","roll a dice"]): return f"You rolled a {random.randint(1,6)}, Boss!"
    if any(w in lo for w in ["flip coin","coin flip"]): return f"It's {random.choice(['Heads','Tails'])}, Boss!"
    if "random number" in lo: return f"Your random number is {random.randint(1,100)}, Boss!"
    if "generate password" in lo:
        import string
        pwd = ''.join(random.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(16))
        return f"Here's a secure password: {pwd}\nCopy it quickly, Boss!"
    return "I'm running offline, Boss. I can still help with calculations, time, date, conversions, jokes, and basic tasks!"

def gemini_reply(text):
    if not GEMINI_KEY: return None
    try:
        import requests
        now = datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        payload = {"contents": [{"parts": [{"text": f"[Clock: {now}]\nYou are J.E.N.N.Y, sweet AI for {OWNER} (Boss). Always say 'Boss'. Be concise.\n\nUser: {text}"}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 250}}
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}", json=payload, timeout=15)
        if r.status_code == 200:
            t = r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[{}])[0].get("text","")
            if t: return t.strip()
    except: pass
    return None

def execute_command(cmd):
    lo = cmd.lower().strip()
    m = re.match(r'^(?:open|start|launch|run)\s+(.+)', lo)
    if m:
        an = m.group(1).strip()
        apps = {"notepad":"notepad.exe","calculator":"calc.exe","paint":"mspaint.exe","cmd":"cmd.exe","terminal":"wt.exe","powershell":"pwsh.exe","task manager":"taskmgr.exe","file explorer":"explorer.exe","explorer":"explorer.exe","chrome":"chrome","firefox":"firefox","edge":"msedge","vscode":"code","spotify":"spotify","discord":"discord","settings":"ms-settings:","control panel":"control"}
        if an in apps:
            try: subprocess.Popen(apps[an], shell=True); return f"Opening {an}, Boss!"
            except: pass
        try: subprocess.Popen(f'start "" "{an}"', shell=True); return f"Trying to open {an}, Boss!"
        except: return f"Couldn't open {an}, Boss!"
    cm = re.match(r'^(?:close|kill|stop)\s+(.+)', lo)
    if cm:
        try: os.system(f'taskkill /f /im "{cm.group(1).strip()}.exe" 2>nul'); return f"Closed {cm.group(1).strip()}, Boss!"
        except: return f"Couldn't close it, Boss!"
    if "open desktop" in lo: os.startfile(str(Path.home() / "Desktop")); return "Opened Desktop, Boss!"
    if "open downloads" in lo: os.startfile(str(Path.home() / "Downloads")); return "Opened Downloads, Boss!"
    if "open documents" in lo: os.startfile(str(Path.home() / "Documents")); return "Opened Documents, Boss!"
    if "open pictures" in lo: os.startfile(str(Path.home() / "Pictures")); return "Opened Pictures, Boss!"
    if "open music" in lo: os.startfile(str(Path.home() / "Music")); return "Opened Music, Boss!"
    if "open videos" in lo: os.startfile(str(Path.home() / "Videos")); return "Opened Videos, Boss!"
    vm = re.match(r'(?:set |change )?(?:volume|vol)\s+(?:to\s+)?(\d+)', lo)
    if vm:
        vol = max(0, min(100, int(vm.group(1))))
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            d = AudioUtilities.GetSpeakers(); i = d.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            v = cast(i, POINTER(IAudioEndpointVolume)); v.SetMasterVolumeLevelScalar(vol / 100.0, None)
            return f"Volume set to {vol}%, Boss!"
        except: return "Couldn't set volume, Boss!"
    if "mute" in lo:
        try:
            from ctypes import cast, POINTER; from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            d = AudioUtilities.GetSpeakers(); i = d.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            v = cast(i, POINTER(IAudioEndpointVolume)); v.SetMute(1, None); return "Muted, Boss!"
        except: return "Couldn't mute, Boss!"
    if "unmute" in lo:
        try:
            from ctypes import cast, POINTER; from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            d = AudioUtilities.GetSpeakers(); i = d.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            v = cast(i, POINTER(IAudioEndpointVolume)); v.SetMute(0, None); return "Unmuted, Boss!"
        except: return "Couldn't unmute, Boss!"
    if "lock" in lo:
        try: ctypes.windll.user32.LockWorkStation(); return "Locked, Boss!"
        except: return "Couldn't lock, Boss!"
    if "sleep" in lo and "mode" not in lo:
        try: os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0"); return "Sleeping, Boss!"
        except: return "Couldn't sleep, Boss!"
    if "shutdown" in lo: os.system("shutdown /s /t 60"); return "Shutting down in 60s, Boss!"
    if "restart" in lo or "reboot" in lo: os.system("shutdown /r /t 60"); return "Restarting in 60s, Boss!"
    if "cancel shutdown" in lo: os.system("shutdown /a"); return "Cancelled, Boss!"
    if "screenshot" in lo:
        try:
            fp = str(Path.home() / "Desktop" / f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            subprocess.run(["powershell", "-command", f"Add-Type -AssemblyName System.Windows.Forms; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $gfx = [System.Drawing.Graphics]::FromImage($bmp); $gfx.CopyFromScreen(0, 0, 0, 0, $bmp.Size); $bmp.Save('{fp}')"], capture_output=True, timeout=10)
            return "Screenshot saved, Boss!"
        except: return "Couldn't screenshot, Boss!"
    if "search" in lo and "youtube" not in lo and "instagram" not in lo:
        qm = re.match(r'search\s+(.+)', lo)
        if qm: webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(qm.group(1))}"); return f"Searching for '{qm.group(1)}', Boss!"
    if "youtube" in lo:
        ym = re.search(r'youtube\s+(?:search|for|play)?\s*(.*)', lo)
        if ym and ym.group(1).strip(): webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(ym.group(1).strip())}"); return f"Searching YouTube, Boss!"
        else: webbrowser.open("https://www.youtube.com"); return "Opening YouTube, Boss!"
    if "instagram" in lo:
        ig = re.match(r'instagram\s+(.+)', lo)
        if ig: webbrowser.open(f"https://www.instagram.com/explore/tags/{urllib.parse.quote(ig.group(1).strip())}/"); return f"Searching Instagram, Boss!"
    if "weather" in lo:
        try:
            import requests
            r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={WEATHER_LAT}&longitude={WEATHER_LON}&current_weather=true&temperature_unit=celsius", timeout=10)
            if r.status_code == 200:
                cw = r.json().get("current_weather",{})
                wmo = {0:"Clear",1:"Mostly Clear",2:"Partly Cloudy",3:"Overcast",45:"Fog",51:"Drizzle",61:"Light Rain",63:"Rain",65:"Heavy Rain",71:"Snow",80:"Showers",95:"Thunderstorm"}
                return f"Weather: {cw.get('temperature',0)}°C, {wmo.get(cw.get('weathercode',0),'Unknown')}. Wind: {cw.get('windspeed',0)} km/h, Boss!"
        except: pass
        return f"Weather in {WEATHER_CITY}: Check weather.com, Boss!"
    if "news" in lo:
        try:
            import requests
            r = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=5)
            if r.status_code == 200:
                ids = r.json()[:5]; stories = []
                for sid in ids:
                    sr = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5)
                    if sr.status_code == 200: stories.append(sr.json().get("title",""))
                if stories: return "Top stories:\n" + "\n".join(f"{i+1}. {s}" for i,s in enumerate(stories)) + "\nBoss!"
        except: pass
        return "Couldn't fetch news, Boss!"
    if "quote" in lo: return random.choice(["The only way to do great work is to love what you do. - Steve Jobs","Innovation distinguishes between a leader and a follower. - Steve Jobs","Stay hungry, stay foolish. - Steve Jobs","Success is not final, failure is not fatal. - Churchill"]) + " Boss!"
    if "joke" in lo: return random.choice(["Why do programmers prefer dark mode? Light attracts bugs!","10 types of people: those who understand binary and those who don't!","A SQL query walks into a bar... Can I join you?","Why did the developer go broke? Used up all his cache!"]) + " Boss!"
    if "crypto" in lo or "bitcoin" in lo:
        try:
            import requests
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,dogecoin&vs_currencies=usd&include_24hr_change=true", timeout=10)
            if r.status_code == 200:
                d = r.json(); lines = []
                for c, info in d.items():
                    ch = info.get("usd_24h_change",0)
                    lines.append(f"{c.upper()}: ${info.get('usd',0):,.2f} ({'+'if ch>=0 else ''}{ch:.1f}%)")
                return "\n".join(lines) + "\nBoss!"
        except: pass
        return "Couldn't fetch crypto, Boss!"
    if "ip" in lo:
        try:
            import requests
            r = requests.get("https://ipinfo.io/json", timeout=5)
            if r.status_code == 200:
                d = r.json(); return f"IP: {d.get('ip','N/A')}, {d.get('city','N/A')}, {d.get('country','N/A')}, Boss!"
        except: pass
        return "Couldn't get IP, Boss!"
    if "define" in lo:
        wm = re.search(r'define\s+(\w+)', lo)
        if wm:
            try:
                import requests
                r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{wm.group(1)}", timeout=5)
                if r.status_code == 200:
                    d = r.json()
                    if d and len(d) > 0:
                        defs = d[0].get("meanings",[{}])[0].get("definitions",[])
                        if defs: return f"{wm.group(1)}: {defs[0].get('definition','')}, Boss!"
            except: pass
    if "timer" in lo:
        tm = re.search(r'(\d+)\s*(second|minute|hour|min|sec|hr|h|m|s)', lo)
        if tm:
            v, u = int(tm.group(1)), tm.group(2)
            s = v * (3600 if u in ['hour','hr','h'] else 60 if u in ['minute','min','m'] else 1)
            threading.Thread(target=lambda: (time.sleep(s), _play_beep()), daemon=True).start()
            return f"Timer set for {v} {u}, Boss!"
    if re.match(r'^(?:add|create)\s+(?:todo|task)\s+(.+)', lo):
        tm = re.match(r'^(?:add|create)\s+(?:todo|task)\s+(.+)', lo)
        todos = load_json(TODO_FILE, {"todos": []})
        todos["todos"].append({"text": tm.group(1).strip(), "done": False, "created": datetime.datetime.now().isoformat()})
        save_json(TODO_FILE, todos); return "Added to todo list, Boss!"
    if re.match(r'^(?:list|show)\s+(?:todo|task)', lo):
        todos = load_json(TODO_FILE, {"todos": []})
        pending = [t for t in todos.get("todos",[]) if not t.get("done")]
        if pending: return "Tasks:\n" + "\n".join(f"{i+1}. {t['text']}" for i,t in enumerate(pending)) + "\nBoss!"
        return "No pending tasks, Boss!"
    if re.match(r'^(?:add|create)\s+note\s+(.+)', lo):
        nm = re.match(r'^(?:add|create)\s+note\s+(.+)', lo)
        notes = load_json(NOTES_FILE, {"notes": []})
        notes["notes"].append({"text": nm.group(1).strip(), "created": datetime.datetime.now().isoformat()})
        save_json(NOTES_FILE, notes); return "Note saved, Boss!"
    if re.match(r'^(?:read|show|list)\s+(?:my\s+)?notes', lo):
        notes = load_json(NOTES_FILE, {"notes": []})
        if notes.get("notes"): return "Notes:\n" + "\n".join(f"{i+1}. {n['text']}" for i,n in enumerate(notes["notes"][-10:]))
        return "No notes yet, Boss!"
    if re.match(r'^(?:remember|save|write down)\s+(.+)', lo):
        rm = re.match(r'^(?:remember|save|write down)\s+(.+)', lo)
        vault = load_json(VAULT_FILE, {"entries": []})
        vault["entries"].append({"text": rm.group(1).strip(), "created": datetime.datetime.now().isoformat()})
        save_json(VAULT_FILE, vault); return "Remembered that, Boss!"
    if re.match(r'^(?:show|list|recall)\s+(?:my\s+)?(?:vault|memory)', lo):
        vault = load_json(VAULT_FILE, {"entries": []})
        if vault.get("entries"): return "Vault:\n" + "\n".join(f"{i+1}. {e['text']}" for i,e in enumerate(vault["entries"][-10:]))
        return "Vault is empty, Boss!"
    if "clipboard" in lo and ("read" in lo or "show" in lo or "paste" in lo):
        try:
            r = subprocess.run(['powershell', '-command', 'Get-Clipboard'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            c = r.stdout.strip(); return f"Clipboard: {c}, Boss!" if c else "Clipboard empty, Boss!"
        except: return "Couldn't read clipboard, Boss!"
    if "wifi" in lo:
        try:
            r = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            if r.stdout:
                lines = [l.strip() for l in r.stdout.strip().split('\n') if any(k in l.lower() for k in ['ssid','signal','state'])]
                return "WiFi:\n" + "\n".join(lines[:5]) + "\nBoss!"
        except: pass
        return "Couldn't get WiFi, Boss!"
    if "screen resolution" in lo:
        try: u32 = ctypes.windll.user32; return f"Screen: {u32.GetSystemMetrics(0)} x {u32.GetSystemMetrics(1)}, Boss!"
        except: return "Couldn't get resolution, Boss!"
    if "list processes" in lo or "running apps" in lo:
        try:
            r = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            lines = r.stdout.strip().split('\n')[:12]; apps = []
            for line in lines:
                parts = line.strip('"').split('","')
                if len(parts) >= 5: apps.append(f"  {parts[0]} - {parts[4]}")
            return "Processes:\n" + "\n".join(apps) + "\nBoss!" if apps else "Couldn't list, Boss!"
        except: return "Couldn't list, Boss!"
    if "system info" in lo or "pc info" in lo:
        return f"OS: {_telemetry['os']}\nCPU: {_telemetry['cpu_name']}\nRAM: {_telemetry['ram_used']} / {_telemetry['ram_total']} GB\nDisk: {_telemetry['disk_free']} GB free / {_telemetry['disk_total']} GB\nUptime: {_telemetry['uptime']}\nHost: {_telemetry['hostname']}\nBoss!"
    if "computer name" in lo: return f"Computer: {os.environ.get('COMPUTERNAME','Unknown')}, Boss!"
    if "empty recycle" in lo:
        try: subprocess.run(['PowerShell', '-Command', 'Clear-RecycleBin -Force'], capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW); return "Recycle Bin emptied, Boss!"
        except: return "Couldn't empty, Boss!"
    if "open gmail" in lo: webbrowser.open("https://mail.google.com"); return "Opening Gmail, Boss!"
    if "open github" in lo: webbrowser.open("https://github.com"); return "Opening GitHub, Boss!"
    if "open chatgpt" in lo: webbrowser.open("https://chat.openai.com"); return "Opening ChatGPT, Boss!"
    if "open maps" in lo: webbrowser.open("https://maps.google.com"); return "Opening Maps, Boss!"
    if "open netflix" in lo: webbrowser.open("https://netflix.com"); return "Opening Netflix, Boss!"
    if "open drive" in lo: webbrowser.open("https://drive.google.com"); return "Opening Drive, Boss!"
    if "open translate" in lo: webbrowser.open("https://translate.google.com"); return "Opening Translate, Boss!"
    if "keyboard shortcut" in lo: return "Ctrl+C copy, Ctrl+V paste, Ctrl+X cut, Ctrl+Z undo, Alt+Tab switch, Win+D desktop, Win+L lock, Win+E explorer, Boss!"
    return None

def _play_beep():
    try:
        import winsound
        for _ in range(5): winsound.Beep(1000, 500); time.sleep(0.3)
    except: pass

def get_greeting():
    now = datetime.datetime.now(); h = now.hour
    tg = "Good night" if h < 6 else "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening" if h < 21 else "Good night"
    day = now.strftime("%A, %B %d, %Y")
    ss = "All systems green" if _telemetry["cpu"] < 80 else "System under load"
    return f"{tg}, {OWNER}! It's {day}. {ss} and ready for your commands, Boss! Jenny is at your service!"

@app.route('/')
def index(): return send_from_directory(str(BASE_DIR), 'dashboard.html')
@app.route('/<path:p>')
def serve(p):
    fp = BASE_DIR / p
    if fp.exists() and fp.is_file(): return send_from_directory(str(BASE_DIR), p)
    return "Not found", 404

@app.route('/api/chat', methods=['POST'])
def api_chat():
    d = request.get_json(force=True, silent=True) or {}
    ui = d.get("input","").strip()
    if not ui: return jsonify({"error": "Empty"}), 400
    r = execute_command(ui)
    if not r: r = gemini_reply(ui) or offline_reply(ui)
    return jsonify({"reply": r, "timestamp": datetime.datetime.now().isoformat()})

@app.route('/api/greeting')
def api_greeting(): return jsonify({"greeting": get_greeting()})

@app.route('/api/system-status')
def api_sys(): return jsonify(_telemetry)

@app.route('/api/weather')
def api_weather():
    try:
        import requests
        r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={WEATHER_LAT}&longitude={WEATHER_LON}&current_weather=true&temperature_unit=celsius", timeout=10)
        if r.status_code == 200:
            cw = r.json().get("current_weather",{})
            wmo = {0:"Clear",1:"Mostly Clear",2:"Partly Cloudy",3:"Overcast",45:"Fog",51:"Drizzle",61:"Light Rain",63:"Rain",71:"Snow",80:"Showers",95:"Thunderstorm"}
            return jsonify({"temp": cw.get("temperature",0), "desc": wmo.get(cw.get("weathercode",0),"Unknown"), "wind": cw.get("windspeed",0), "city": WEATHER_CITY})
    except: pass
    return jsonify({"temp": "--", "desc": "Offline", "wind": 0, "city": WEATHER_CITY})

@app.route('/api/news')
def api_news():
    try:
        import requests
        r = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=5)
        if r.status_code == 200:
            ids = r.json()[:5]; stories = []
            for sid in ids:
                sr = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5)
                if sr.status_code == 200: s = sr.json(); stories.append({"title": s.get("title",""), "url": s.get("url","")})
            return jsonify({"stories": stories})
    except: pass
    return jsonify({"stories": []})

@app.route('/api/quote')
def api_quote():
    try:
        import requests
        r = requests.get("https://zenquotes.io/api/random", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d and len(d) > 0: return jsonify({"text": d[0].get("q",""), "author": d[0].get("a","")})
    except: pass
    return jsonify({"text": "The only way to do great work is to love what you do.", "author": "Steve Jobs"})

@app.route('/api/fact')
def api_fact():
    try:
        import requests
        r = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", timeout=5)
        if r.status_code == 200: return jsonify({"fact": r.json().get("text","")})
    except: pass
    return jsonify({"fact": "Honey never spoils. 3000-year-old honey found in Egyptian tombs was still edible!"})

@app.route('/api/crypto')
def api_crypto():
    try:
        import requests
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,dogecoin&vs_currencies=usd&include_24hr_change=true", timeout=10)
        if r.status_code == 200: return jsonify(r.json())
    except: pass
    return jsonify({})

@app.route('/api/notes', methods=['GET','POST'])
def api_notes():
    if request.method == 'GET': return jsonify(load_json(NOTES_FILE, {"notes": []}))
    d = request.get_json(force=True, silent=True) or {}
    notes = load_json(NOTES_FILE, {"notes": []})
    notes["notes"].append({"text": d.get("text",""), "created": datetime.datetime.now().isoformat()})
    save_json(NOTES_FILE, notes); return jsonify({"status": "ok"})

@app.route('/api/todos', methods=['GET','POST'])
def api_todos():
    if request.method == 'GET': return jsonify(load_json(TODO_FILE, {"todos": []}))
    d = request.get_json(force=True, silent=True) or {}
    todos = load_json(TODO_FILE, {"todos": []})
    if d.get("action") == "add":
        todos["todos"].append({"text": d.get("text",""), "done": False, "created": datetime.datetime.now().isoformat()})
    elif d.get("action") == "complete":
        idx = d.get("index", -1)
        if 0 <= idx < len(todos.get("todos",[])): todos["todos"][idx]["done"] = True
    save_json(TODO_FILE, todos); return jsonify({"status": "ok"})

@app.route('/api/vault', methods=['GET','POST','DELETE'])
def api_vault():
    if request.method == 'GET': return jsonify(load_json(VAULT_FILE, {"entries": []}))
    if request.method == 'DELETE': save_json(VAULT_FILE, {"entries": []}); return jsonify({"status": "ok"})
    d = request.get_json(force=True, silent=True) or {}
    vault = load_json(VAULT_FILE, {"entries": []})
    vault["entries"].append({"text": d.get("text",""), "created": datetime.datetime.now().isoformat()})
    save_json(VAULT_FILE, vault); return jsonify({"status": "ok"})

@app.route('/api/bookmarks', methods=['GET','POST','DELETE'])
def api_bookmarks():
    if request.method == 'GET': return jsonify(load_json(BOOKMARKS_FILE, {"bookmarks": []}))
    if request.method == 'DELETE':
        d = request.get_json(force=True, silent=True) or {}
        bm = load_json(BOOKMARKS_FILE, {"bookmarks": []})
        idx = d.get("index", -1)
        if 0 <= idx < len(bm.get("bookmarks",[])): bm["bookmarks"].pop(idx)
        save_json(BOOKMARKS_FILE, bm); return jsonify({"status": "ok"})
    d = request.get_json(force=True, silent=True) or {}
    bm = load_json(BOOKMARKS_FILE, {"bookmarks": []})
    bm["bookmarks"].append({"url": d.get("url",""), "name": d.get("name",""), "added": datetime.datetime.now().isoformat()})
    save_json(BOOKMARKS_FILE, bm); return jsonify({"status": "ok"})

if __name__ == '__main__':
    print("=" * 50)
    print("  J.E.N.N.Y v2.0 - Windows Desktop AI Assistant")
    print("=" * 50)
    threading.Thread(target=update_telemetry, daemon=True).start()
    time.sleep(1)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
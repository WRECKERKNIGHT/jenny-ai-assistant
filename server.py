import os, sys, json, time, math, random, re, webbrowser, datetime, platform, subprocess, threading, urllib.request, urllib.parse, ctypes, hashlib
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

BASE_DIR = Path(__file__).parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

app = Flask(__name__, static_folder=str(PUBLIC_DIR))
CORS(app)

OWNER = "Harshit"
chatHistory = []
activeDevices = {}
pendingDeviceCommands = {}
system_cache = {"cpu": 0, "ram": 0, "battery": 100, "charging": False, "disk": 0, "disk_free": "0", "disk_total": "0", "ram_used": "0", "ram_total": "0", "net_speed": "0 KB/s", "uptime": 0, "hostname": platform.node(), "platform": sys.platform}

def load_json(p, d=None):
    try:
        if Path(p).exists(): return json.loads(Path(p).read_text(encoding="utf-8"))
    except: pass
    return d if d is not None else {}

def save_json(p, d):
    Path(p).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def get_gemini_key():
    k = os.environ.get("GEMINI_API_KEY", "")
    if k: return k
    for i in range(2, 11):
        k = os.environ.get(f"GEMINI_API_KEY_{i}", "")
        if k: return k
    return ""

def gemini_chat(message, history=None):
    key = get_gemini_key()
    if not key: return None
    try:
        import requests as _req
        now = datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        vault_data = load_json(DATA_DIR / "vault.json", {"entries": []})
        vault_text = "\n".join(e.get("text","") for e in vault_data.get("entries", [])[-5:])
        prompt = f"You are J.E.N.N.Y, AI assistant for {OWNER} (Boss). Clock: {now}. Vault: {vault_text}. Reply naturally, say Boss occasionally. Return JSON: {{\"text\": \"response\", \"speech\": \"tts version\"}}"
        contents = [{"parts": [{"text": prompt}]}]
        if history:
            for h in history[-10:]:
                role = "user" if h.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": h.get("content", "")}]})
        contents.append({"role": "user", "parts": [{"text": message}]})
        r = _req.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}", json={"contents": contents, "generationConfig": {"temperature": 0.7, "maxOutputTokens": 400}}, timeout=20)
        if r.status_code == 200:
            t = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            if t.startswith("```"): t = t.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            try: return json.loads(t)
            except: return {"text": t, "speech": re.sub(r"[#*_`]", "", t)}
    except: pass
    return None

def offline_reply(text):
    lo = text.lower().strip()
    if re.match(r"^[\d\s\+\-\*\/\%\.\(\)]+$", lo):
        try: return {"text": f"The answer is {eval(lo.replace(chr(94),"**"))}, Boss!", "speech": "The answer is " + str(eval(lo.replace(chr(94),"**"))) + ", Boss."}
        except: pass
    for pattern, resp in [
        (["what time","current time","time now"], lambda: {"text": f"It's {datetime.datetime.now().strftime('%I:%M %p')}, Boss!", "speech": f"It's {datetime.datetime.now().strftime('%I:%M %p')}, Boss."}),
        (["what day","today's date"], lambda: {"text": f"Today is {datetime.datetime.now().strftime('%A, %B %d, %Y')}, Boss!", "speech": "Today is " + datetime.datetime.now().strftime("%A, %B %d, %Y") + ", Boss."}),
        (["who are you","your name"], lambda: {"text": "I'm J.E.N.N.Y, your AI assistant, Boss!", "speech": "I'm J.E.N.N.Y, your AI assistant, Boss."}),
        (["how are you"], lambda: {"text": random.choice(["All systems green, Boss!","Feeling great, Boss!"]), "speech": "All systems green, Boss!"}),
        (["joke"], lambda: {"text": random.choice(["Why do programmers prefer dark mode? Light attracts bugs!","10 types of people: binary and non-binary!","A SQL query walks into a bar... Can I join you?"]) + " Boss!", "speech": "Here's a joke, Boss."}),
        (["quote"], lambda: {"text": random.choice(["The only way to do great work is to love what you do. - Steve Jobs","Stay hungry, stay foolish. - Steve Jobs"]) + " Boss!", "speech": "Here's a quote for you, Boss."}),
    ]:
        if any(w in lo for w in pattern): return resp()
    if "capabil" in lo or "help" in lo:
        return {"text": "I can control your system, open apps, browse web, manage vault, weather, news, crypto, and chat! Boss!", "speech": "I can control your system and chat with you, Boss."}
    if any(w in lo for w in ["hello","hi ","hey"]):
        return {"text": random.choice(["Hello Boss! How can I help?","Hey Boss! What can I do for you?"]), "speech": "Hello Boss! How can I help?"}
    if any(w in lo for w in ["thank","thanks"]):
        return {"text": random.choice(["Happy to help, Boss!","Anything for you, Boss!"]), "speech": "Happy to help, Boss!"}
    return {"text": "I'm running offline, Boss. I can still help with basic tasks!", "speech": "I'm running offline, Boss."}

def update_telemetry():
    import psutil
    while True:
        try:
            cpu = psutil.cpu_percent(interval=None)
            m = psutil.virtual_memory()
            d = psutil.disk_usage("/")
            b = psutil.sensors_battery()
            n = psutil.net_io_counters()
            up = time.time() - psutil.boot_time()
            system_cache.update({"cpu": round(cpu,1), "ram": round(m.percent,1), "ram_used": str(round(m.used/(1024**3),1)), "ram_total": str(round(m.total/(1024**3),1)), "disk": round(d.percent,1), "disk_free": f"{d.free/(1024**3):.1f}", "disk_total": f"{d.total/(1024**3):.1f}", "battery": b.percent if b else 100, "charging": b.power_plugged if b else False, "net_speed": f"{n.bytes_sent/(1024*1024):.1f} MB sent", "uptime": int(up), "hostname": platform.node()})
        except: pass
        time.sleep(3)

@app.route("/")
def index(): return send_from_directory(str(PUBLIC_DIR), "index.html")

@app.route("/<path:p>")
def serve_static(p):
    fp = PUBLIC_DIR / p
    if fp.exists() and fp.is_file(): return send_from_directory(str(PUBLIC_DIR), p)
    return send_from_directory(str(PUBLIC_DIR), "index.html")

@app.route("/api/system-status")
def api_system_status():
    import psutil
    try: cpu_count = psutil.cpu_count(); cpu_model = platform.processor() or "Unknown CPU"
    except: cpu_count = 1; cpu_model = "Unknown"
    return jsonify({"success": True, "cpu": {"usage": system_cache["cpu"], "cores": cpu_count, "model": cpu_model}, "ram": {"usage": system_cache["ram"], "usedMB": int(float(system_cache["ram_used"])*1024), "totalMB": int(float(system_cache["ram_total"])*1024)}, "battery": {"level": system_cache["battery"], "charging": system_cache["charging"]}, "disk": {"usage": system_cache["disk"], "free": system_cache["disk_free"]+"GB"}, "net": {"usage": 0, "speed": system_cache["net_speed"]}, "uptime": system_cache["uptime"], "hostname": system_cache["hostname"], "platform": sys.platform})

@app.route("/api/chat", methods=["POST"])
def api_chat():
    d = request.get_json(force=True, silent=True) or {}
    msg = d.get("message", "").strip()
    if not msg: return jsonify({"success": False, "error": "No message"}), 400
    reply = offline_reply(msg)
    if not reply: reply = gemini_chat(msg, chatHistory) or {"text": "I'm offline, Boss.", "speech": "I'm offline, Boss."}
    chatHistory.append({"role": "user", "content": msg})
    chatHistory.append({"role": "assistant", "content": reply.get("text", "")})
    if len(chatHistory) > 20: chatHistory.pop(0); chatHistory.pop(0)
    return jsonify({"success": True, "reply": reply})

@app.route("/api/control", methods=["POST"])
def api_control():
    d = request.get_json(force=True, silent=True) or {}
    action = d.get("action", ""); value = d.get("value", "")
    lo = action.lower()
    if lo == "volume":
        try:
            from ctypes import cast, POINTER; from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            spk = AudioUtilities.GetSpeakers(); iface = spk.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            if value == "mute": vol.SetMute(1, None); return jsonify({"success": True, "message": "Muted, Boss."})
            if value == "unmute": vol.SetMute(0, None); return jsonify({"success": True, "message": "Unmuted, Boss."})
            vol.SetMasterVolumeLevelScalar(int(value)/100.0, None); return jsonify({"success": True, "message": f"Volume set to {value}%, Boss."})
        except: return jsonify({"success": False, "error": "Volume control failed"})
    if lo == "lock":
        try: ctypes.windll.user32.LockWorkStation(); return jsonify({"success": True, "message": "Locked, Boss."})
        except: return jsonify({"success": False, "error": "Lock failed"})
    if lo == "screenshot":
        try:
            fp = str(Path.home() / "Desktop" / f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            subprocess.run(["powershell", "-command", f"Add-Type -AssemblyName System.Windows.Forms; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $gfx = [System.Drawing.Graphics]::FromImage($bmp); $gfx.CopyFromScreen(0, 0, 0, 0, $bmp.Size); $bmp.Save('{fp}')"], capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            return jsonify({"success": True, "message": "Screenshot saved, Boss."})
        except: return jsonify({"success": False, "error": "Screenshot failed"})
    if lo == "clipboard-read":
        try: r = subprocess.run(["powershell", "-command", "Get-Clipboard"], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "text": r.stdout.strip()})
        except: return jsonify({"success": False, "error": "Clipboard read failed"})
    if lo == "clipboard-write":
        txt = value if isinstance(value, str) else value.get("text", "")
        try: subprocess.run(["powershell", "-command", f"Set-Clipboard -Value '{txt}'"], capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "message": "Copied, Boss."})
        except: return jsonify({"success": False, "error": "Clipboard write failed"})
    if lo == "processes":
        try:
            r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            procs = []
            for line in r.stdout.strip().split("\n")[:15]:
                parts = line.strip('"').split('","')
                if len(parts) >= 5: procs.append({"pid": parts[1], "name": parts[0], "cpu": parts[4]})
            return jsonify({"success": True, "processes": procs})
        except: return jsonify({"success": False, "error": "Failed"})
    if lo == "kill-process":
        try: subprocess.run(["taskkill", "/f", "/pid", str(value)], capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "message": f"Killed {value}, Boss."})
        except: return jsonify({"success": False})
    if lo == "system-info":
        return jsonify({"success": True, "info": {"os": f"{platform.system()} {platform.release()}", "cpu": platform.processor() or "Unknown", "ram": f"{system_cache['ram_used']} / {system_cache['ram_total']} GB", "hostname": platform.node()}})
    if lo == "wifi":
        try:
            r = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            ssid = ""; sig = ""
            for l in r.stdout.split("\n"):
                if "SSID" in l and "BSSID" not in l: ssid = l.split(":",1)[-1].strip()
                if "Signal" in l: sig = l.split(":",1)[-1].strip()
            return jsonify({"success": True, "ssid": ssid, "signal": sig})
        except: return jsonify({"success": False})
    if lo == "open-app":
        apps = {"notepad":"notepad.exe","calculator":"calc.exe","paint":"mspaint.exe","chrome":"chrome","firefox":"firefox","edge":"msedge","vscode":"code","spotify":"spotify","discord":"discord"}
        name = str(value).lower()
        target = apps.get(name, value)
        try: subprocess.Popen(target, shell=True); return jsonify({"success": True, "message": f"Opened {value}, Boss."})
        except: return jsonify({"success": False})
    if lo == "close-app":
        try: subprocess.run(["taskkill", "/f", "/im", f"{value}.exe"], capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "message": f"Closed {value}, Boss."})
        except: return jsonify({"success": False})
    if lo == "list-directory":
        path = str(value) if value else str(Path.home())
        try:
            items = [{"name": i.name, "isDir": i.is_dir(), "size": i.stat().st_size if i.is_file() else 0} for i in Path(path).iterdir()]
            return jsonify({"success": True, "path": path, "items": sorted(items, key=lambda x: (not x["isDir"], x["name"].lower()))})
        except: return jsonify({"success": False})
    if lo in ("exec-shell", "execute-shell"):
        try: r = subprocess.run(str(value), shell=True, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "stdout": r.stdout[:5000], "stderr": r.stderr[:2000]})
        except: return jsonify({"success": False})
    if lo == "shutdown": os.system("shutdown /s /t 60"); return jsonify({"success": True, "message": "Shutting down, Boss."})
    if lo == "restart": os.system("shutdown /r /t 60"); return jsonify({"success": True, "message": "Restarting, Boss."})
    if lo == "empty-trash":
        try: subprocess.run(["PowerShell", "-Command", "Clear-RecycleBin -Force"], capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "message": "Trash emptied, Boss."})
        except: return jsonify({"success": False})
    if lo == "timer":
        secs = value.get("seconds", 60) if isinstance(value, dict) else 60
        def _beep():
            time.sleep(secs)
            try:
                import winsound
                for _ in range(5): winsound.Beep(1000, 500); time.sleep(0.3)
            except: pass
        threading.Thread(target=_beep, daemon=True).start()
        return jsonify({"success": True, "message": f"Timer set for {secs}s, Boss."})
    if lo == "email": return jsonify({"success": True, "message": "Email compose not available on Windows yet."})
    if lo == "write-file": return jsonify({"success": True, "message": "File write not available yet."})
    if lo == "calendar": return jsonify({"success": True, "message": "Calendar integration coming soon."})
    if lo == "create-folder":
        try: Path(str(Path.home() / "Desktop" / str(value))).mkdir(exist_ok=True); return jsonify({"success": True, "message": f"Created folder {value}, Boss."})
        except: return jsonify({"success": False})
    if lo == "delete-file":
        try: Path(str(value)).unlink(missing_ok=True); return jsonify({"success": True, "message": "Deleted, Boss."})
        except: return jsonify({"success": False})
    if lo == "dark-mode": return jsonify({"success": True, "message": "Dark mode toggle not available on Windows yet."})
    if lo == "airplane-mode": return jsonify({"success": True, "message": "Airplane mode toggle not available."})
    if lo == "spotify": return jsonify({"success": True, "message": "Spotify control coming soon."})
    if lo == "brightness": return jsonify({"success": True, "message": "Brightness control not available on this display."})
    if lo == "media": return jsonify({"success": True, "message": "Media control coming soon."})
    if lo == "terminal":
        try: subprocess.Popen("wt.exe", shell=True); return jsonify({"success": True, "message": "Terminal opened, Boss."})
        except: subprocess.Popen("cmd.exe", shell=True); return jsonify({"success": True, "message": "CMD opened, Boss."})
    if lo == "minimize-all":
        try: ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0); ctypes.windll.user32.keybd_event(0x4D, 0, 0, 0); ctypes.windll.user32.keybd_event(0x4D, 0, 2, 0); ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0); return jsonify({"success": True, "message": "Minimized all, Boss."})
        except: return jsonify({"success": False})
    if lo == "disk-usage":
        try: r = subprocess.run(["wmic", "logicaldisk", "get", "size,freespace,caption"], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "text": r.stdout[:2000]})
        except: return jsonify({"success": False})
    if lo == "network-speed": return jsonify({"success": True, "speed": system_cache["net_speed"]})
    return jsonify({"success": False, "error": f"Unknown action: {action}"})

@app.route("/api/speak", methods=["GET","POST"])
def api_speak():
    text = request.args.get("text", "") or (request.get_json(force=True, silent=True) or {}).get("text", "")
    if not text: return jsonify({"success": False, "message": "Text required"})
    clean = re.sub(r"[#*_`\[\]]", "", text); clean = re.sub(r"https?://\S+", "", clean).strip()
    cache_dir = DATA_DIR / "speak_cache"; cache_dir.mkdir(exist_ok=True)
    h = hashlib.md5(clean.encode()).hexdigest(); wav_path = cache_dir / f"{h}.wav"
    if wav_path.exists(): return send_from_directory(str(cache_dir), f"{h}.wav", mimetype="audio/wav")
    try:
        import pyttsx3; engine = pyttsx3.init()
        for v in engine.getProperty("voices"):
            if any(k in v.name.lower() for k in ["zira","hazel","aria","female"]): engine.setProperty("voice", v.id); break
        engine.setProperty("rate", 180); engine.setProperty("volume", 1.0)
        engine.save_to_file(clean, str(wav_path)); engine.runAndWait(); time.sleep(0.5)
        if wav_path.exists(): return send_from_directory(str(cache_dir), f"{h}.wav", mimetype="audio/wav")
    except: pass
    return jsonify({"success": False, "message": "Speech failed"})

@app.route("/api/speak/fallback", methods=["POST"])
def api_speak_fallback():
    d = request.get_json(force=True, silent=True) or {}; text = d.get("text", "")
    if text:
        def _s():
            try: import pyttsx3; e = pyttsx3.init(); e.say(text); e.runAndWait()
            except: pass
        threading.Thread(target=_s, daemon=True).start()
    return jsonify({"success": True})

@app.route("/api/speak/stop", methods=["POST"])
def api_speak_stop(): return jsonify({"success": True})

@app.route("/api/weather")
def api_weather():
    settings = load_json(DATA_DIR / "settings.json", {"latitude": 26.8467, "longitude": 80.9462, "cityName": "Lucknow"})
    lat = settings.get("latitude", 26.8467); lon = settings.get("longitude", 80.9462); city = settings.get("cityName", "Lucknow")
    try:
        import requests as _req
        r = _req.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min&temperature_unit=celsius&timezone=auto", timeout=10)
        if r.status_code == 200:
            data = r.json(); cw = data.get("current_weather", {}); wmo = {0:"Clear Sky",1:"Mainly Clear",2:"Partly Cloudy",3:"Overcast",45:"Foggy",61:"Light Rain",63:"Rain",65:"Heavy Rain",71:"Snow",80:"Showers",95:"Thunderstorm"}
            daily = data.get("daily", {}); tmax = daily.get("temperature_2m_max", []); tmin = daily.get("temperature_2m_min", [])
            days = ["MON","TUE","WED","THU","FRI","SAT","SUN"]; forecast = []; now = datetime.datetime.now()
            for i in range(min(4, len(tmax))): d2 = now + datetime.timedelta(days=i+1); forecast.append({"day": days[d2.weekday()], "max": round(tmax[i]), "min": round(tmin[i])})
            return jsonify({"success": True, "city": city, "tempC": cw.get("temperature",0), "condition": wmo.get(cw.get("weathercode",0),"Unknown"), "type": "clear" if cw.get("weathercode",0)<3 else "cloudy" if cw.get("weathercode",0)<50 else "rain", "humidity": 50, "windKmH": cw.get("windspeed",0), "isDay": cw.get("is_day",1)==1, "forecast": forecast})
    except: pass
    return jsonify({"success": True, "city": city, "tempC": "--", "condition": "Offline", "type": "clear", "humidity": 0, "windKmH": 0, "isDay": True, "forecast": []})

@app.route("/api/briefing")
def api_briefing():
    now = datetime.datetime.now(); h = now.hour
    greet = "Good night" if h<6 else "Good morning" if h<12 else "Good afternoon" if h<17 else "Good evening" if h<21 else "Good night"
    vault = load_json(DATA_DIR / "vault.json", {"entries": []})
    return jsonify({"success": True, "briefing": {"greeting": f"{greet}, BOSS", "date": now.strftime("%A, %B %d, %Y"), "time": now.strftime("%I:%M %p"), "weather": f"{system_cache['cpu']}% CPU", "system": f"CPU {system_cache['cpu']}%, RAM {system_cache['ram']}%", "battery": f"{system_cache['battery']}%", "vaultCount": len(vault.get("entries",[]))}})

@app.route("/api/vault", methods=["GET","POST","DELETE"])
def api_vault():
    vault = load_json(DATA_DIR / "vault.json", {"entries": []})
    if request.method == "GET": return jsonify({"success": True, "data": vault.get("entries",[])})
    if request.method == "DELETE":
        vid = request.args.get("id")
        if vid: vault["entries"] = [e for e in vault.get("entries",[]) if e.get("id")!=vid]; save_json(DATA_DIR/"vault.json",vault); return jsonify({"success":True,"message":f"Deleted {vid}"})
        vault["entries"] = []; save_json(DATA_DIR/"vault.json",vault); return jsonify({"success":True,"message":"Vault cleared"})
    d = request.get_json(force=True,silent=True) or {}; entry = {"id": str(int(time.time()*1000)), "text": d.get("text",""), "date": datetime.datetime.now().strftime("%b %d, %Y")}
    vault.setdefault("entries",[]).append(entry); save_json(DATA_DIR/"vault.json",vault); return jsonify({"success":True,"data":entry})

@app.route("/api/settings", methods=["GET","POST"])
def api_settings():
    if request.method == "GET": return jsonify({"success":True,"settings":load_json(DATA_DIR/"settings.json",{"latitude":26.8467,"longitude":80.9462,"cityName":"Lucknow"})})
    d = request.get_json(force=True,silent=True) or {}; s = load_json(DATA_DIR/"settings.json",{"latitude":26.8467,"longitude":80.9462,"cityName":"Lucknow"})
    for k in ["latitude","longitude","cityName"]:
        if k in d: s[k] = d[k]
    save_json(DATA_DIR/"settings.json",s); return jsonify({"success":True,"settings":s})

@app.route("/api/gemini-keys")
def api_gemini_keys():
    key = get_gemini_key(); masked = f"{key[:6]}...{key[-4:]}" if len(key)>10 else "No key"
    return jsonify({"success":True,"totalKeys":1 if key else 0,"activeKeys":1 if key else 0,"currentKeyIndex":0,"keys":[{"masked":masked,"active":bool(key),"requestsToday":0,"requestsMinute":0,"tokensTotal":0,"errors429":0,"lastError":None}]})

@app.route("/api/gemini-quota")
def api_gemini_quota():
    key = get_gemini_key(); masked = f"{key[:6]}...{key[-4:]}" if len(key)>10 else "No key"
    return jsonify({"success":True,"isKeyPresent":bool(key),"keysCount":1 if key else 0,"activeKeys":1 if key else 0,"currentKey":masked,"model":"gemini-2.0-flash","rpm":{"current":0,"max":15},"tpm":{"current":0,"max":1000000},"rpd":{"current":0,"max":1500},"status":"HEALTHY & ACTIVE" if key else "MISSING_API_KEY","keys":[]})

@app.route("/api/training", methods=["GET","POST","DELETE"])
def api_training():
    mem = load_json(DATA_DIR/"offline_memory.json",{"name":"BOSS","tone":"witty","rules":[],"macros":[],"contacts":[],"facts":[]})
    if request.method=="GET": return jsonify({"success":True,"training":mem})
    if request.method=="DELETE":
        d = request.get_json(force=True,silent=True) or {}; t = d.get("type",""); trigger = d.get("trigger",d.get("topic",""))
        key = "rules" if t=="rule" else "macros" if t=="macro" else "facts" if t=="fact" else ""
        if key and key in mem: mem[key] = [x for x in mem[key] if x.get("trigger",x.get("topic",""))!=trigger]
        save_json(DATA_DIR/"offline_memory.json",mem); return jsonify({"success":True,"training":mem})
    d = request.get_json(force=True,silent=True) or {}; t = d.get("type","")
    if t=="profile": mem["name"]=d.get("name",mem.get("name","BOSS")); mem["tone"]=d.get("tone",mem.get("tone","witty"))
    elif t=="rule": mem.setdefault("rules",[]).append({"trigger":d.get("trigger",""),"reply":d.get("reply","")})
    elif t=="macro": mem.setdefault("macros",[]).append({"trigger":d.get("trigger",""),"commands":d.get("commands",[])})
    elif t=="fact": mem.setdefault("facts",[]).append({"topic":d.get("topic",""),"content":d.get("content","")})
    save_json(DATA_DIR/"offline_memory.json",mem); return jsonify({"success":True,"training":mem})

@app.route("/api/local-ip")
def api_local_ip():
    try: s=__import__("socket").socket(__import__("socket").AF_INET,__import__("socket").SOCK_DGRAM); s.connect(("8.8.8.8",80)); ip=s.getsockname()[0]; s.close()
    except: ip="127.0.0.1"
    return jsonify({"success":True,"ip":ip,"mobileUrl":f"http://{ip}:3005/mobile.html"})

@app.route("/api/remote-status")
def api_remote_status(): return jsonify({"success":True,"remoteMode":False,"caffeinatePid":None,"tunnelUrl":"","hostname":platform.node()})

@app.route("/api/devices")
def api_devices(): return jsonify({"success":True,"devices":list(activeDevices.values())})

@app.route("/api/device/register", methods=["POST"])
def api_device_register():
    d = request.get_json(force=True,silent=True) or {}; did = d.get("deviceId","")
    if not did: return jsonify({"success":False,"message":"deviceId required"})
    if did not in activeDevices: activeDevices[did] = {"deviceId":did,"os":d.get("os","Unknown"),"browser":d.get("browser","Unknown"),"ip":request.remote_addr,"status":"pending","lastActive":datetime.datetime.now().isoformat()}
    return jsonify({"success":True,"device":activeDevices[did]})

@app.route("/api/device/status/<did>")
def api_device_status(did): return jsonify({"success":True,"status":activeDevices.get(did,{}).get("status","unknown")})

@app.route("/api/device/approve", methods=["POST"])
def api_device_approve():
    d = request.get_json(force=True,silent=True) or {}; did = d.get("deviceId",""); status = d.get("status","")
    if did in activeDevices: activeDevices[did]["status"]=status; return jsonify({"success":True})
    return jsonify({"success":False}), 404

@app.route("/api/device/command/send", methods=["POST"])
def api_device_cmd_send():
    d = request.get_json(force=True,silent=True) or {}; did = d.get("deviceId",""); action = d.get("action","")
    pendingDeviceCommands.setdefault(did,[]).append({"action":action,"value":d.get("value",""),"timestamp":int(time.time()*1000)})
    return jsonify({"success":True})

@app.route("/api/device/command/poll/<did>")
def api_device_cmd_poll(did): return jsonify({"success":True,"commands":pendingDeviceCommands.pop(did,[])})

@app.route("/api/permissions-check")
def api_permissions_check(): return jsonify({"success":True,"platform":sys.platform,"permissions":{"accessibility":{"status":"not_applicable","message":"Not required on Windows"},"automation":{"status":"not_applicable"},"fullDiskAccess":{"status":"not_applicable"}}})

@app.route("/api/reverse-geocode")
def api_reverse_geocode():
    lat=request.args.get("lat",""); lon=request.args.get("lon","")
    if not lat or not lon: return jsonify({"success":False,"message":"lat and lon required"})
    try:
        import requests as _req; r=_req.get(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json",timeout=5,headers={"User-Agent":"JENNY/2.0"})
        if r.status_code==200: return jsonify({"success":True,"cityName":r.json().get("address",{}).get("city","Unknown")})
    except: pass
    return jsonify({"success":False,"message":"Geocode failed"})

@app.route("/api/news")
def api_news():
    try:
        import requests as _req; r=_req.get("https://hacker-news.firebaseio.com/v0/topstories.json",timeout=5)
        if r.status_code==200:
            ids=r.json()[:5]; stories=[]
            for sid in ids: sr=_req.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",timeout=5); stories.append({"title":sr.json().get("title",""),"url":sr.json().get("url","")}) if sr.status_code==200 else None
            return jsonify({"success":True,"stories":stories})
    except: pass
    return jsonify({"success":True,"stories":[]})

@app.route("/api/fact")
def api_fact():
    try: import requests as _req; r=_req.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en",timeout=5); return jsonify({"success":True,"fact":r.json().get("text","")})
    except: return jsonify({"success":True,"fact":"Honey never spoils!"})

@app.route("/api/quote")
def api_quote():
    try: import requests as _req; r=_req.get("https://zenquotes.io/api/random",timeout=5); d=r.json(); return jsonify({"success":True,"quote":f'"{d[0].get("q","")}" - {d[0].get("a","")}'})
    except: return jsonify({"success":True,"quote":"\"Stay hungry, stay foolish.\" - Steve Jobs"})

@app.route("/api/crypto")
def api_crypto():
    try: import requests as _req; r=_req.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,dogecoin&vs_currencies=usd",timeout=10); return jsonify({"success":True,"prices":r.json()})
    except: return jsonify({"success":True,"prices":{}})

@app.route("/api/ip-info")
def api_ip_info():
    try: import requests as _req; r=_req.get("https://ipapi.co/json/",timeout=5); d=r.json(); return jsonify({"success":True,"ip":d.get("ip",""),"city":d.get("city",""),"region":d.get("region",""),"country":d.get("country_name",""),"org":d.get("org","")})
    except: return jsonify({"success":True,"ip":"","city":"","region":"","country":"","org":""})

@app.route("/api/dictionary")
def api_dictionary():
    word=request.args.get("word","")
    if not word: return jsonify({"success":False,"message":"word required"})
    try:
        import requests as _req; r=_req.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}",timeout=5)
        if r.status_code==200: d=r.json(); m=d[0].get("meanings",[{}])[0]; defs=m.get("definitions",[])
        if defs: return jsonify({"success":True,"word":word,"partOfSpeech":m.get("partOfSpeech",""),"definition":defs[0].get("definition","")})
    except: pass
    return jsonify({"success":False,"message":"Word not found"})

@app.route("/api/emails")
def api_emails(): return jsonify({"success":True,"emails":[],"message":"Email not available on Windows yet."})

@app.route("/api/timers")
def api_timers(): return jsonify({"success":True,"timers":[]})

@app.route("/api/toggle-mic")
def api_toggle_mic(): return jsonify({"success":True,"timestamp":int(time.time()*1000)})

@app.route("/api/toggle-mic-poll")
def api_toggle_mic_poll(): return jsonify({"success":True,"lastToggle":0})

@app.route("/api/active-apps")
def api_active_apps():
    try:
        r=subprocess.run(["tasklist","/fo","csv","/nh"],capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
        apps=list(set(line.strip('"').split('","')[0] for line in r.stdout.strip().split("\n") if line.strip()))[:15]
        return jsonify({"success":True,"apps":apps,"message":f"{len(apps)} active applications."})
    except: return jsonify({"success":True,"apps":[],"message":"Cannot list apps"})

@app.route("/api/notifications")
def api_notifications(): return jsonify({"success":True,"notifications":[]})

@app.route("/api/discord-dms")
def api_discord_dms(): return jsonify({"success":True,"discord_dms":[]})

@app.route("/api/remote-mode", methods=["POST"])
def api_remote_mode(): return jsonify({"success":True,"remoteMode":False,"message":"Not available on Windows."})

@app.route("/api/wake", methods=["POST"])
def api_wake(): return jsonify({"success":True,"message":"Wake not applicable on Windows."})

@app.route("/api/sleep", methods=["POST"])
def api_sleep():
    try: os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0"); return jsonify({"success":True,"message":"Sleeping, Boss."})
    except: return jsonify({"success":False})

@app.route("/api/open-app")
def api_open_app():
    name=request.args.get("name","")
    if name:
        try: subprocess.Popen(f'start "" "{name}"',shell=True); return jsonify({"success":True,"message":f"Opened {name}"})
        except: return jsonify({"success":False})
    return jsonify({"success":False})

@app.route("/api/close-app")
def api_close_app():
    name=request.args.get("name","")
    if name:
        try: subprocess.run(["taskkill","/f","/im",f"{name}.exe"],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success":True,"message":f"Closed {name}"})
        except: return jsonify({"success":False})
    return jsonify({"success":False})

@app.route("/api/open-url")
def api_open_url():
    url=request.args.get("url","")
    if url: webbrowser.open(url); return jsonify({"success":True,"message":f"Opened {url}"})
    return jsonify({"success":False})

@app.route("/api/execute-shell", methods=["POST"])
def api_execute_shell():
    d = request.get_json(force=True,silent=True) or {}; cmd = d.get("command","")
    if not cmd: return jsonify({"success":False,"error":"No command"})
    try: r=subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success":True,"stdout":r.stdout[:10000],"stderr":r.stderr[:5000],"error":None})
    except Exception as e: return jsonify({"success":False,"stdout":"","stderr":"","error":str(e)})

@app.route("/api/system")
def api_system(): return jsonify({"success":True,"data":{"battery":{"percent":system_cache["battery"],"state":"charging" if system_cache["charging"] else "discharging"},"uptime":f"{system_cache['uptime']} seconds","volume":50,"brightness":0.8,"ip":"127.0.0.1","os":f"{platform.system()} {platform.release()}","cpu":system_cache["cpu"],"ram":system_cache["ram"]}})

@app.route("/api/tts", methods=["POST"])
def api_tts():
    d = request.get_json(force=True,silent=True) or {}; text = d.get("text","")
    if text:
        def _s():
            try: import pyttsx3; e=pyttsx3.init(); e.say(text); e.runAndWait()
            except: pass
        threading.Thread(target=_s,daemon=True).start()
    return jsonify({"success":True})

@app.route("/api/chrome-bookmarks")
def api_chrome_bookmarks():
    try:
        bm_path = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Bookmarks"
        if not bm_path.exists():
            for p in Path.home().iterdir():
                bp = p / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Bookmarks"
                if bp.exists(): bm_path = bp; break
        if not bm_path.exists(): return jsonify({"success": True, "bookmarks": [], "message": "Chrome bookmarks not found"})
        data = json.loads(bm_path.read_text(encoding="utf-8"))
        bookmarks = []
        def walk(node, path=""):
            if node.get("type") == "url":
                bookmarks.append({"name": node.get("name",""), "url": node.get("url",""), "path": path})
            elif node.get("type") == "folder":
                folder_name = node.get("name","")
                for child in node.get("children", []):
                    walk(child, f"{path}/{folder_name}" if path else folder_name)
        roots = data.get("roots", {})
        for key in ["bookmark_bar", "other", "synced"]:
            if key in roots: walk(roots[key])
        return jsonify({"success": True, "bookmarks": bookmarks[:100], "total": len(bookmarks)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "bookmarks": []})

@app.route("/api/open-chrome", methods=["GET","POST"])
def api_open_chrome():
    d = request.args if request.method == "GET" else (request.get_json(force=True, silent=True) or {})
    url = d.get("url", "")
    if url:
        try:
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe"),
            ]
            chrome = next((p for p in chrome_paths if Path(p).exists()), None)
            if chrome: subprocess.Popen([chrome, url]); return jsonify({"success": True, "message": f"Opened in Chrome: {url}"})
            else: webbrowser.open(url); return jsonify({"success": True, "message": f"Opened in default browser: {url}"})
        except: return jsonify({"success": False})
    return jsonify({"success": False, "error": "No URL"})


if __name__ == "__main__":
    print("=" * 55)
    print("  J.E.N.N.Y v2.0 — Windows Desktop AI Assistant")
    print("  Server running on http://localhost:3005")
    print("=" * 55)
    threading.Thread(target=update_telemetry, daemon=True).start()
    time.sleep(1)
    app.run(host="0.0.0.0", port=3005, debug=False, threaded=True)

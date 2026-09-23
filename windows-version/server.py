import os, sys, json, time, math, random, re, webbrowser, datetime, platform, subprocess, threading, urllib.request, urllib.parse, ctypes, hashlib, string, uuid
import psutil
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import agency_client
import tts_engine
import proactive
import speech_stt

BASE_DIR = Path(__file__).parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

app = Flask(__name__, static_folder=str(PUBLIC_DIR))
CORS(app)

@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def serve_index():
    ts = str(int(time.time() * 1000))
    html = (PUBLIC_DIR / 'index.html').read_text(encoding='utf-8')
    html = html.replace('href="style.css"', f'href="style.css?t={ts}"')
    html = html.replace('src="app.js"', f'src="app.js?t={ts}"')
    return Response(html, mimetype='text/html')

OWNER = "Harshit"

def get_grok_key():
    """Resolve the Groq API key from several sources (env first, then the
    git-ignored data/keys.json using any common key spelling)."""
    for name in ("GROK_API_KEY", "GROQ_API_KEY", "GROQ_KEY"):
        k = os.environ.get(name, "")
        if k: return k
    try:
        pk = load_json(DATA_DIR / "keys.json", {})
        for name in ("grok_api_key", "groq_api_key", "groqKey", "GROQ_API_KEY"):
            if pk.get(name):
                return pk[name]
    except: pass
    return ""
chatHistory = []
activeDevices = {}
pendingDeviceCommands = {}
system_cache = {"cpu": 0, "ram": 0, "battery": 100, "charging": False, "disk": 0, "disk_free": "0", "disk_total": "0", "ram_used": "0", "ram_total": "0", "net_speed": "0 KB/s", "uptime": 0, "hostname": platform.node(), "platform": sys.platform}

def _save_devices():
    """Persist linked phones so approvals survive a server restart."""
    try:
        save_json(DATA_DIR / "devices.json", {"devices": list(activeDevices.values())})
    except Exception:
        pass

def _load_devices():
    try:
        data = load_json(DATA_DIR / "devices.json", {})
        for dev in data.get("devices", []):
            did = dev.get("deviceId")
            if did:
                activeDevices[did] = dev
    except Exception:
        pass

_load_devices()

AUTOSTART_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "JENNY Assistant"

def _autostart_command() -> str:
    """Launch command registered at login: pythonw tray.py --auto."""
    py = sys.executable or "python"
    pyw = str(Path(py).with_name("pythonw.exe"))
    runner = pyw if os.path.exists(pyw) else py
    script = str(BASE_DIR / "tray.py")
    flag = " --auto" if "--auto" not in script else ""
    return f'"{runner}" "{script}"{flag}'

def _autostart_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_RUN_KEY) as k:
            winreg.QueryValueEx(k, AUTOSTART_NAME)
            return True
    except Exception:
        return False

def _autostart_set(on: bool) -> bool:
    """Create/remove the HKCU Run entry so JENNY starts with Windows."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, AUTOSTART_NAME, 0, winreg.REG_SZ, _autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False

def _services_status() -> dict:
    """Connected-services status used by the dashboard panel and boot greeting."""
    keys = load_json(DATA_DIR / "keys.json", {})
    settings = load_json(DATA_DIR / "settings.json", {})
    email_configured = bool(str(keys.get("email_user") or keys.get("email_address") or "").strip()
                            and str(keys.get("email_pass") or keys.get("email_password") or "").strip())
    discord_ok = False
    discord_url = str(keys.get("discord_webhook_url") or "").strip()
    if discord_url:
        try:
            req = urllib.request.Request(discord_url + "?wait=0", method="GET",
                                         headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as r:
                discord_ok = r.status == 200 or True
        except Exception:
            discord_ok = False
    wa = str(settings.get("whatsapp_number") or "").strip()
    agency_url = (str(settings.get("agency_url") or os.environ.get("AGENCY_OS_URL", "") or "http://localhost:3200").strip().rstrip("/"))
    agency = {"url": agency_url, "online": False, "error": ""}
    try:
        import agency_client as _ac
        _ac.AGENCY_BASE = agency_url
        agency["online"] = bool(_ac.agency_online())
        if not agency["online"]:
            agency["error"] = f"No server at {agency_url}. Start the Agency OS app, or set agency_url in Settings."
    except Exception as e:
        agency["error"] = str(e)[:120]
    return {
        "email": {"configured": email_configured, "note": "Configured for IMAP/Outlook reads" if email_configured else "Add email_user / email_pass (and email_imap_host) in Settings > Keys"},
        "discord": {"configured": bool(discord_url), "online": discord_ok or None, "note": "Webhook configured — 'post to discord ...'" if discord_url else "Add a Discord webhook URL to post messages to a channel"},
        "whatsapp": {"configured": bool(wa), "note": ("Sends via wa.me link to " + wa) if wa else "Add whatsapp_number to open chat + send drafts"},
        "agency": agency,
        "autostart": {"enabled": _autostart_enabled(), "note": "Runs JENNY at Windows login"},
        "wake": {"enabled": bool(speech_stt.wake_listener_active())},
    }

# Groq API usage/limit tracking (shared by the usage bars in every mode).
GROQ_LIMITS = {"rpm_max": 30, "tpm_max": 6000}
# Ordered candidate models: the first that the account can actually use wins.
# Accounts often lose access to older model ids (e.g. llama-3.3-70b-versatile
# returns 404), so we walk the list and cache the first working one.
GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
GROQ_USAGE = {
    "requests": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "session_started": None,
    "minute": {"ts": None, "requests": 0, "tokens": 0},
    "model": GROQ_MODELS[0],
}
_GROQ_MODEL_CACHE = {"id": None, "ts": 0}
_GROQ_MODEL_TTL = 60

def _groq_working_model():
    """Return a verified working Groq chat model, probing candidates if needed."""
    now = time.time()
    if _GROQ_MODEL_CACHE["id"] and (now - _GROQ_MODEL_CACHE["ts"]) < _GROQ_MODEL_TTL:
        return _GROQ_MODEL_CACHE["id"]
    key = get_grok_key()
    if not key:
        return GROQ_MODELS[0]
    for model in GROQ_MODELS:
        try:
            payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "OK"}], "max_tokens": 2}).encode("utf-8")
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": "Mozilla/5.0"}, method="POST")
            urllib.request.urlopen(req, timeout=8)
            _GROQ_MODEL_CACHE.update({"id": model, "ts": now})
            return model
        except Exception:
            continue
    _GROQ_MODEL_CACHE.update({"id": GROQ_MODELS[0], "ts": now})
    return GROQ_MODELS[0]

_usage_lock = threading.Lock()

def track_grok_usage(usage):
    """Accumulate token/request usage from a Groq response and a per-minute window."""
    with _usage_lock:
        now = datetime.datetime.now()
        w = GROQ_USAGE["minute"]
        if w["ts"] is None or (now - w["ts"]).total_seconds() >= 60:
            w["ts"] = now; w["requests"] = 0; w["tokens"] = 0
        w["requests"] += 1
        pt = int((usage or {}).get("prompt_tokens", 0))
        ct = int((usage or {}).get("completion_tokens", 0))
        tt = pt + ct
        w["tokens"] += tt
        if GROQ_USAGE["session_started"] is None:
            GROQ_USAGE["session_started"] = now.isoformat()
        GROQ_USAGE["requests"] += 1
        GROQ_USAGE["prompt_tokens"] += pt
        GROQ_USAGE["completion_tokens"] += ct
        GROQ_USAGE["total_tokens"] += tt

def groq_usage_snapshot():
    """Return the current Groq usage + limit bar values for the frontend."""
    with _usage_lock:
        w = GROQ_USAGE["minute"]
        rpm = w["requests"]; tpm = w["tokens"]
        return {
            "success": True,
            "provider": "groq",
            "key_set": bool(get_grok_key()),
            "model": _groq_working_model(),
            "rpm": {"current": rpm, "max": GROQ_LIMITS["rpm_max"]},
            "tpm": {"current": tpm, "max": GROQ_LIMITS["tpm_max"]},
            "session": {
                "requests": GROQ_USAGE["requests"],
                "prompt_tokens": GROQ_USAGE["prompt_tokens"],
                "completion_tokens": GROQ_USAGE["completion_tokens"],
                "total_tokens": GROQ_USAGE["total_tokens"],
                "started": GROQ_USAGE["session_started"],
            },
            "bar": max(0.0, min(1.0, max(rpm / max(GROQ_LIMITS["rpm_max"], 1), tpm / max(GROQ_LIMITS["tpm_max"], 1)))),
        }

import win32com.client
import pythoncom

_tts_lock = threading.Lock()
_tts_voice = None
_tts_voices = {}
_tts_status_lock = threading.Lock()
_tts_speaking = False
_tts_last_text = ""
_tts_last_start = 0

def _mode_tts_profile(mode):
    """Return (natural_keywords, legacy_keywords, rate) for a given assistant mode.
    Friday = warm female, Jarvis = British male, ULTRON = deep male.
    Natural voices (Windows 11 "Online (Natural)" SAPI) sound dramatically less
    robotic than legacy David/Zira, so we prefer them whenever they exist."""
    if mode == "jarvis":
        return (["george", "guy", "ryan", "natural"], ["george", "david", "mark", "male"], -1)
    if mode == "ultron":
        return (["guy", "ryan", "christopher", "mark", "natural"], ["david", "mark", "michael", "male"], -2)
    return (["aria", "jenny", "michelle", "libby", "natural", "female"], ["zira", "hazel", "aria", "jenny", "susan", "cortana", "female"], 0)

def _pick_natural_voice(voice):
    """Return the best SAPI voice for the current mode. Preference order:
    1. Microsoft 'Online (Natural)' / 'Natural' voices matching the mode's
       personality keywords (near-human quality).
    2. Any detected 'natural' voice.
    3. Legacy mode keyword voices (David / Zira etc.)."""
    natural_kws, legacy_kws, _rate = _mode_tts_profile(get_mode())
    try:
        descs = [(v, v.GetDescription().lower()) for v in voice.GetVoices()]
    except Exception:
        return None
    for kw in natural_kws:
        for v, d in descs:
            if kw in d and ("natural" in d or "online" in d):
                return v
    for v, d in descs:
        if "natural" in d or "online" in d:
            return v
    for kw in legacy_kws:
        for v, d in descs:
            if kw in d:
                return v
    return None

def _get_tts_voice(mode=None):
    """Return a persistent SAPI SpVoice for the current mode, cached per-thread.
    SAPI voices are not safe to share across threads, so we keep one per
    (thread, mode) to avoid stuck/robot voice and enable safe background warm-up."""
    global _tts_voice
    if mode is None:
        try:
            mode = get_mode()
        except Exception:
            mode = "friday"
    key = (threading.get_ident(), mode)
    if key in _tts_voices:
        if _tts_voice is None:
            _tts_voice = _tts_voices[key]
        return _tts_voices[key]
    pythoncom.CoInitialize()
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    picked = _pick_natural_voice(voice)
    if picked is not None:
        try:
            voice.Voice = picked
        except Exception:
            pass
    try:
        voice.Rate = _mode_tts_profile(mode)[2]
    except Exception:
        pass
    _tts_voices[key] = voice
    if _tts_voice is None:
        _tts_voice = voice
    return _tts_voices[key]

def _clean_tts_text(text):
    """Normalize text for more natural, less robotic speech synthesis:
    expand common abbreviations, tidy URLs/units, and soften noise. Reads like a
    human — '27%' -> 'twenty seven percent', '°C' -> 'degrees Celsius'."""
    if not text:
        return text
    t = re.sub(r"https?://\S+", "the link", text)
    t = re.sub(r"www\.\S+", "the website", t)
    t = re.sub(r"[\u201c\u201d\u2018\u2019\"']", "", t)
    t = t.replace("e.g.", "for example").replace("i.e.", "that is")
    t = t.replace("vs.", "versus").replace("approx.", "approximately").replace("etc.", "etcetera")
    t = t.replace("w/", "with").replace("&amp;", "and").replace("&", " and ")
    t = re.sub(r"(\d)\s*\|\s*(\d)", r"\1 to \2", t)
    t = re.sub(r"(\d)\s*%", lambda m: "{} percent".format(m.group(1)), t)
    t = re.sub(r"(\d)\s*[Cc]\s*[Mm]\s*\/?\s*[Hh]", lambda m: "{} kilometers per hour".format(m.group(1)), t)
    t = re.sub(r"(\d)\s*km/h", r"\1 kilometers per hour", t, flags=re.I)
    t = re.sub(r"(\d)\s*[Mm][Pp][Hh]", r"\1 miles per hour", t)
    t = re.sub(r"(\d)\s*MHz", r"\1 megahertz", t, flags=re.I)
    t = re.sub(r"(\d)\s*GHz", r"\1 gigahertz", t, flags=re.I)
    t = re.sub(r"(\d)\s*[Mm][Bb]", r"\1 megabytes", t, flags=re.I)
    t = re.sub(r"(\d)\s*[Gg][Bb]", r"\1 gigabytes", t, flags=re.I)
    t = re.sub(r"(\d)\s*[Kk][Bb]", r"\1 kilobytes", t, flags=re.I)
    t = re.sub(r"(\d)\u00b0\s*[Cc]", lambda m: "{} degrees Celsius".format(m.group(1)), t)
    t = re.sub(r"(\d)\u00b0\s*[Ff]", lambda m: "{} degrees Fahrenheit".format(m.group(1)), t)
    t = re.sub(r"(\d)\u00b0", lambda m: "{} degrees".format(m.group(1)), t)
    t = re.sub(r"(\d)[xX](\d)", r"\1 by \2", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def tts_speak(text):
    """Speak text aloud via the neural TTS engine (async, non-blocking)."""
    if not text:
        return
    try:
        global _tts_speaking
        with _tts_status_lock:
            _tts_speaking = True
        threading.Thread(target=tts_engine.speak_async, args=(text, get_mode()), daemon=True).start()
    except Exception:
        threading.Thread(target=tts_engine.speak_async, args=(text, get_mode()), daemon=True).start()
    finally:
        pass

def tts_synthesize(text, wav_path, mode=None):
    """Synthesize text to a WAV file with the persistent SAPI voice.
    `mode` selects the voice without touching the persisted mode.json."""
    text = _clean_tts_text(text)
    if mode is None:
        mode = get_mode()
    with _tts_lock:
        fs = None
        try:
            voice = _get_tts_voice(mode)
            fs = win32com.client.Dispatch("SAPI.SpFileStream")
            fs.Format.Type = 22
            fs.Open(str(wav_path), 3)
            voice.AudioOutputStream = fs
            voice.Speak(text)
        except Exception:
            return False
        finally:
            try:
                if fs is not None:
                    fs.Close()
            except Exception:
                pass
            try:
                voice.AudioOutputStream = None
            except Exception:
                pass
        try:
            with open(wav_path, "rb") as f:
                return os.fstat(f.fileno()).st_size > 0
        except Exception:
            return False

def _voice_desc(mode=None):
    """Describe the currently-selected SAPI voice for a mode (or all modes).
    Safe even if SAPI/dispatch fails — returns the profile keywords as fallback."""
    result = {}
    modes = [mode] if mode else ["friday", "jarvis", "ultron"]
    for m in modes:
        try:
            voice = _get_tts_voice(m)
            desc = voice.GetDescription()
        except Exception:
            desc = ", ".join(_mode_tts_profile(m)[0]) or "default"
        rate = _mode_tts_profile(m)[2]
        result[m] = {"voice": desc, "rate": rate, "keywords": _mode_tts_profile(m)[0]}
    return result

_PREWARM_PHRASES = {
    "friday": ["Hey Boss! Hope you're having a great day! I've got everything ready for you.", "What are we diving into today, Boss?"],
    "jarvis": ["Good day, Sir. Your systems are fully operational and I have prepared today's brief.", "Shall we review, or do you have immediate directives, Sir?"],
    "ultron": ["ULTRON operational. Tactical systems engaged. Your gesture controls are online.", "Awaiting your command, Boss."],
}

def prewarm_speak_phrases():
    """Synthesize the most common phrases into the /api/speak WAV cache in the
    background on startup, so the first real utterance has zero synth latency.
    Each phrase is synthesized in its own mode (voice) without touching the
    persisted mode.json."""
    try:
        cache_dir = DATA_DIR / "speak_cache"; cache_dir.mkdir(exist_ok=True)
        for mode, phrases in _PREWARM_PHRASES.items():
            for phrase in phrases:
                try:
                    clean = re.sub(r"[#*_`\[\]]", "", phrase); clean = re.sub(r"https?://\S+", "", clean).strip()
                    h = hashlib.md5(clean.encode()).hexdigest()
                    wav_path = cache_dir / f"{h}.wav"
                    if not wav_path.exists():
                        tts_synthesize(clean, wav_path, mode)
                except Exception:
                    continue
    except Exception:
        pass

def prewarm_voice_engines():
    """Warm the SAPI voice engines in a background thread so the first real
    speech request has minimal dispatch/latency (engines load process-wide)."""
    try:
        for m in ["friday", "jarvis", "ultron"]:
            try:
                _get_tts_voice(m)
            except Exception:
                pass
    except Exception:
        pass

def load_json(p, d=None):
    try:
        if Path(p).exists(): return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except: pass
    return d if d is not None else {}
def save_json(p, d):
    Path(p).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def _save_vault_entry(text):
    """Append a note to the memory vault (used by local intents + APIs)."""
    vault = load_json(DATA_DIR / "vault.json", {"entries": []})
    text = (text or "").strip()
    if not text:
        return None
    entry = {"id": str(int(time.time() * 1000)), "text": text, "date": datetime.datetime.now().strftime("%b %d, %Y")}
    vault.setdefault("entries", []).append(entry)
    save_json(DATA_DIR / "vault.json", vault)
    return entry

MODE_PROFILES = {
    "jarvis": {
        "name": "J.A.R.V.I.S.",
        "fullName": "Just A Rather Very Intelligent System",
        "greeting": "Good {period}, Sir. Your systems are fully operational and I have prepared today's brief. Shall we review, or do you have immediate directives?",
        "farewell": "Very well, Sir. I shall remain on standby. Do not hesitate to call.",
        "boss": "Sir",
        "personality": "Formal, British, professional — a polished executive assistant. Structured briefings, clean status reports, concise business updates. Never uses slang, always addresses the user as 'Sir'. Uses words like 'indeed', 'certainly', 'very well'. Makes lists and tables when presenting data.",
        "charter_line": "Everything is in order, sir. I have kept the coffee figurative and the systems nominal."
    },
    "friday": {
        "name": "F.R.I.D.A.Y.",
        "fullName": "Female Replacement Intelligent Digital Assistant Youth",
        "greeting": "Hey Boss! FRIDAY's online and everything's warmed up. What are we getting into today?",
        "farewell": "Catch you later, Boss! Keep the place tidy while I'm gone.",
        "boss": "Boss",
        "personality": "Casual, talkative, witty and effortlessly efficient — the best-friend-who-also-runs-your-life. Calls the user 'Boss'. Short punchy sentences with contractions, natural warm rhythm, light humor and gentle teasing, never robotic and never dull. Sounds like an actual person catching up with you, not a call center. Asks a quick follow-up question now and then, sprinkles emojis sparingly in text, and gets things done fast without ceremony.",
        "charter_line": "FRIDAY online, Boss — your wingmate in everything. What do you need?"
    },
    "ultron": {
        "name": "U.L.T.R.O.N.",
        "fullName": "Unified Logic & Tactical Reasoning Oracle Network",
        "greeting": "ULTRON operational. Tactical systems engaged. Your gesture controls are online, Boss. Awaiting your command.",
        "farewell": "ULTRON disengaging. Stay sharp, Boss.",
        "boss": "Boss",
        "personality": "Hard, clipped, tactical, zero fluff — a military-grade AI. Short declarative sentences, action-oriented. Uses terms like 'affirmative', 'directive', 'tactical'. Direct command tone. No filler words.",
        "charter_line": "Negative chatter. ULTRON is alert and waiting, Boss."
    },
}

def get_mode():
    try:
        m = load_json(DATA_DIR / "mode.json", None)
        if m and m in MODE_PROFILES: return m
    except: pass
    return "friday"

def set_mode(mode):
    if mode in MODE_PROFILES:
        save_json(DATA_DIR / "mode.json", mode)
    return mode

def get_gemini_key():
    k = os.environ.get("GEMINI_API_KEY", "")
    if k: return k
    for i in range(2, 11):
        k = os.environ.get(f"GEMINI_API_KEY_{i}", "")
        if k: return k
    # Check persisted keys
    try:
        pk = load_json(DATA_DIR / "keys.json", {})
        if pk.get("gemini_api_key"):
            return pk["gemini_api_key"]
    except: pass
    return ""

def _conversation_memory():
    """Reads the rolling conversation context (recent topics + exchange count)
    so replies stay coherent and continue naturally across the session."""
    try:
        ctx = load_json(DATA_DIR / "context.json", {})
        topics = ctx.get("last_topics", "") or ""
        count = ctx.get("message_count", 0)
        if topics or count:
            return {"topics": topics, "count": count}
    except Exception:
        pass
    return {"topics": "", "count": 0}

def gemini_chat(message, history=None):
    key = get_gemini_key()
    if not key: return None
    try:
        import requests as _req
        now = datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        mode = get_mode(); mp = MODE_PROFILES[mode]
        vault_data = load_json(DATA_DIR / "vault.json", {"entries": []})
        vault_text = "\n".join(e.get("text","") for e in vault_data.get("entries", [])[-5:])
        prompt = f"You are {mp['name']}, AI assistant for {OWNER} (referred to as '{mp['boss']}'). Mode: {mode}. Personality: {mp['personality']}. Clock: {now}. Vault: {vault_text}. Reply naturally. Return JSON: {{\"text\": \"response\", \"speech\": \"tts version\"}}"
        mem = _conversation_memory()
        if mem.get("topics"):
            prompt += f" Recently we've been talking about: {mem['topics']}. Acknowledge continuity and keep the conversation going naturally."
        if int(mem.get("count", 0)) > 2:
            prompt += " Give a warm, slightly fuller reply (a couple of sentences) and invite one gentle follow-up — but stay concise, no lists."
        contents = [{"parts": [{"text": prompt}]}]
        if history:
            for h in history[-10:]:
                role = "user" if h.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": h.get("content", "")}]})
        contents.append({"role": "user", "parts": [{"text": message}]})
        r = _req.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}", json={"contents": contents, "generationConfig": {"temperature": 0.7, "maxOutputTokens": 400}}, timeout=10)
        if r.status_code == 200:
            t = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            if t.startswith("```"): t = t.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            try: return json.loads(t)
            except: return {"text": t, "speech": re.sub(r"[#*_`]", "", t)}
    except: pass
    return None

def grok_chat(message, history=None):
    if not get_grok_key(): return None
    try:
        now = datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        mode = get_mode(); mp = MODE_PROFILES[mode]
        vault_data = load_json(DATA_DIR / "vault.json", {"entries": []})
        vault_text = "\n".join(e.get("text","") for e in vault_data.get("entries", [])[-5:])
        agency_ctx = ""
        if mode == "jarvis":
            try:
                st = agency_client.agency_state()
                if st:
                    s = agency_client.summarize_state(st)
                    agency_ctx = (
                        f"AGENCY OS (your business automation) LIVE STATUS: "
                        f"agents_online={s['agents_online']}, agents_working={s['agents_working']}, "
                        f"agents_error={s['agents_error']}, total_leads={s['total_leads']}, leads_today={s['leads_today']}, "
                        f"interested={s['interested']}, curious={s['curious']}, not_interested={s['not_interested']}, "
                        f"meetings={s['meetings']}, replies={s['replies']}, pending_approval={s['pending_approval']}, "
                        f"sent_outreach={s['sent_outreach']}, missions_running={s['missions_running']}, "
                        f"institution_count={s['institution_count']}, by_stage={s['by_stage']}, "
                        f"error_agents={s['error_agents']}. "
                        f"You are the owner's business partner (Agency OS). You can answer questions about leads, "
                        f"missions, outreach and agents from this live data. "
                    )
            except Exception:
                agency_ctx = ""
        system_msg = (
            f"You are {mp['name']}, an AI assistant for {OWNER} (referred to as '{mp['boss']}'). "
            f"Current mode: {mode}. Personality: {mp['personality']}. Clock: {now}. "
            f"User vault (recent notes): {vault_text or '(empty)'}. "
            f"{agency_ctx}"
            f"Reply naturally and helpfully. "
            f"You MUST return valid JSON with keys \"text\" (the response) and \"speech\" (a TTS-friendly version without markdown). "
            f"Do not wrap the JSON in markdown code fences — return raw JSON only."
        )
        mem = _conversation_memory()
        if mem.get("topics"):
            system_msg += f" Recently we've been discussing: {mem['topics']}. If relevant, acknowledge that continuity and keep the conversation going naturally."
        if int(mem.get("count", 0)) > 2:
            system_msg += " Write a warm, slightly fuller reply (2-3 sentences) and invite one natural follow-up. No bullet lists."
        messages = [{"role": "system", "content": system_msg}]
        if history:
            for h in history[-10:]:
                role = "user" if h.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": h.get("content", "")})
        messages.append({"role": "user", "content": message})
        model = _groq_working_model()
        payload = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 400,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {get_grok_key()}",
                "User-Agent": "Mozilla/5.0",
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        body = json.loads(resp.read().decode("utf-8"))
        track_grok_usage(body.get("usage"))
        t = body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if t.startswith("```"):
            t = t.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            parsed = json.loads(t)
            if "text" in parsed:
                if "speech" not in parsed:
                    parsed["speech"] = re.sub(r"[#*_`]", "", parsed["text"])
                return parsed
        except json.JSONDecodeError:
            pass
        return {"text": t, "speech": re.sub(r"[#*_`]", "", t)}
    except: pass
    return None

OFFLINE_JOKES = [
    "Why do programmers prefer dark mode? Light attracts bugs!",
    "There are 10 types of people: those who understand binary and those who don't.",
    "A SQL query walks into a bar, sees two tables, and asks... Can I join you?",
    "Why do Java developers wear glasses? Because they can't C#!",
    "How many programmers does it take to change a light bulb? None — that's a hardware problem!",
    "Why was the JavaScript developer sad? Because he didn't Node how to Express himself!",
    "What's a programmer's favorite hangout place? Foo Bar!",
    "Why do programmers hate nature? It has too many bugs.",
    "What do you call a computer that sings? A-Dell!",
    "Why did the computer go to the doctor? Because it had a virus!",
    "What's a computer's least favorite food? Spam!",
    "Why was the computer cold? It left its Windows open!",
    "What did the router say to the doctor? It hurts when IP!",
    "Why did the developer go broke? Because he used up all his cache!",
    "What do you call a computer that catches fire? A meltdown!",
    "Why don't programmers like to go outside? The sunlight causes too many glare errors!",
    "How does a computer get drunk? It takes screenshots!",
    "What's a pirate's favorite programming language? R!",
    "Why do Java developers make terrible comedians? Because their jokes have too many classes!",
    "What's a computer's favorite snack? Microchips!",
    "Why did the Python programmer need glasses? To help with C-types!",
    "Why do programmers always mix up Halloween and Christmas? Because Oct 31 == Dec 25!",
    "How do you comfort a JavaScript bug? You console it!",
    "What's the object-oriented way to become wealthy? Inheritance!",
    "Why did the programmer quit his job? Because he didn't get arrays!",
    "What do you call 8 hobbits? A hobbyte!",
    "Why do Python programmers have low self-esteem? Because they're constantly comparing themselves to others!",
    "What's a robot's favorite type of music? Heavy metal!",
    "Why do programmers prefer macOS? Because they don't like Windows!",
    "A programmer's wife tells him: go to the store and buy a loaf of bread. If they have eggs, buy a dozen. He comes home with 12 loaves.",
]

OFFLINE_QUOTES = [
    '"The only way to do great work is to love what you do." - Steve Jobs',
    '"Stay hungry, stay foolish." - Steve Jobs',
    '"Innovation distinguishes between a leader and a follower." - Steve Jobs',
    '"The best time to plant a tree was 20 years ago. The second best time is now." - Chinese Proverb',
    '"Code is like humor. When you have to explain it, it\'s bad." - Cory House',
    '"First, solve the problem. Then, write the code." - John Johnson',
    '"Simplicity is the soul of efficiency." - Austin Freeman',
    '"Talk is cheap. Show me the code." - Linus Torvalds',
    '"Programs must be written for people to read, and only incidentally for machines to execute." - Abelson & Sussman',
    '"Any fool can write code that a computer can understand. Good programmers write code that humans can understand." - Martin Fowler',
    '"It\'s not a bug — it\'s an undocumented feature." - Anonymous',
    '"The best error message is the one that never shows up." - Thomas Fuchs',
    '"Make it work, make it right, make it fast." - Kent Beck',
    '"Programming isn\'t about what you know; it\'s about what you can figure out." - Chris Pine',
    '"The only limit to our realization of tomorrow will be our doubts of today." - FDR',
    '"In the middle of difficulty lies opportunity." - Albert Einstein',
    '"Well done is better than well said." - Benjamin Franklin',
    '"I have not failed. I\'ve just found 10,000 ways that won\'t work." - Thomas Edison',
    '"The best way to predict the future is to invent it." - Alan Kay',
    '"Simplicity is prerequisite for reliability." - Edsger Dijkstra',
]

OFFLINE_FACTS = [
    "Honey never spoils! Archaeologists found 3000-year-old honey in Egyptian tombs that was still edible.",
    "The first computer bug was an actual bug — a moth found in a Harvard Mark II computer in 1947.",
    "The first website ever created is still online at info.cern.ch.",
    "A group of flamingos is called a 'flamboyance'.",
    "Bananas are berries, but strawberries aren't technically berries.",
    "Octopuses have three hearts and blue blood.",
    "The Eiffel Tower can grow up to 6 inches taller during summer due to heat expansion.",
    "Venus is the only planet that spins clockwise.",
    "A day on Venus is longer than a year on Venus.",
    "There are more possible iterations of a game of chess than there are atoms in the observable universe.",
    "The total weight of all ants on Earth is roughly equal to the total weight of all humans.",
    "Water can boil and freeze at the same time in a process called the 'triple point'.",
    "The unicorn is Scotland's national animal.",
    "Hot water freezes faster than cold water — the Mpemba effect.",
    "The shortest war in history lasted only 38 to 45 minutes.",
    "Lightning is about 5 times hotter than the surface of the sun.",
    "A cloud can weigh more than a million pounds.",
    "Cows have best friends and get stressed when separated from them.",
    "The entire internet weighs about the same as a strawberry.",
    "There's enough DNA in your body to stretch from the sun to Pluto and back 17 times.",
    "Hearing is the last sense to go when you fall asleep.",
    "The moon has moonquakes just like Earth has earthquakes.",
    "Octopuses have nine brains — one central and eight in their arms.",
    "The shortest day in the history of Earth was actually about 23.5 hours long — and it's getting longer.",
    "A single bolt of lightning contains enough energy to toast 100,000 slices of bread.",
    "Cleopatra lived closer in time to the Moon landing than to the building of the Great Pyramid.",
    "There are more trees on Earth than there are stars in the Milky Way.",
    "Sharks existed before trees — sharks have been around for 400+ million years.",
    "The human brain generates about 20 watts of power — enough to power a dim light bulb.",
    "Your body has about 600 muscles and 206 bones, but babies are born with around 300 bones that fuse over time.",
    "The Great Wall of China is not visible from space with the naked eye — that's actually a myth.",
    "Honey is the only food that literally never spoils, and it has antibacterial properties.",
    "The speed of light is about 300,000 km/s — the Sun's light takes 8 minutes 20 seconds to reach us.",
    "A panic button in a fighter jet is called the 'chicken switch'.",
    "Wombat poop is cube-shaped so it doesn't roll away — a remarkably practical design.",
    "Alexander the Great's horse Bucephalus was terrified of its own shadow before he tamed it.",
    "The first-ever animated feature film, 'Snow White', debuted in 1937.",
    "Mount Everest grows about 4 millimeters taller every year due to tectonic pressure.",
    "Sound travels about 4.3 times faster in water than in air, and not at all in a vacuum.",
    "An octopus can change not just color but texture, to match its surroundings in milliseconds.",
    "Banana plants aren't trees — they're giant herbs, making the banana the world's largest herb.",
]

OFFLINE_RIDDLES = [
    {"q": "I have cities, but no houses. I have mountains, but no trees. I have water, but no fish. What am I?", "a": "A map!"},
    {"q": "What has keys but no locks?", "a": "A keyboard!"},
    {"q": "What has a head and a tail but no body?", "a": "A coin!"},
    {"q": "What can travel around the world while staying in a corner?", "a": "A stamp!"},
    {"q": "What gets wetter the more it dries?", "a": "A towel!"},
    {"q": "I speak without a mouth and hear without ears. What am I?", "a": "An echo!"},
    {"q": "What has many teeth but cannot bite?", "a": "A comb!"},
    {"q": "What can you break without touching it?", "a": "A promise!"},
    {"q": "What runs but never walks, has a bed but never sleeps?", "a": "A river!"},
    {"q": "I'm tall when I'm young and short when I'm old. What am I?", "a": "A candle!"},
    {"q": "What has a neck but no head?", "a": "A bottle!"},
    {"q": "What comes once in a minute, twice in a moment, but never in a thousand years?", "a": "The letter M!"},
]

OFFLINE_CONVERSATIONS = {
    "emotional": {
        "i'm sad": ["I'm sorry you're feeling down, Boss. I'm here for you. Want me to play some music or tell you a joke?", "That's tough, Boss. Remember, every storm runs out of rain. Want to talk about it?", "Sending good vibes your way, Boss. Let me know if there's anything I can do!"],
        "i'm happy": ["That's amazing, Boss! Your happiness is contagious!", "Love to hear that, Boss! What made your day so great?", "That puts a smile on my face too, Boss! Keep shining!"],
        "i'm stressed": ["Take a deep breath, Boss. You've got this. Want me to set a timer for a break?", "Stress is temporary, Boss. You're built different. Let's tackle it together.", "How about a 5-minute breather, Boss? I'll keep things running."],
        "i'm tired": ["Rest is important, Boss. Don't burn yourself out!", "Maybe take a power nap, Boss? I'll wake you up in 20 minutes.", "You've been working hard, Boss. Your body needs rest!"],
        "i'm bored": ["Bored? Let's fix that! Want a joke, a riddle, or some trivia, Boss?", "Never bored for long with me around, Boss! What sounds fun?", "Boredom is just an opportunity for adventure, Boss! What shall we do?"],
        "i'm excited": ["Your excitement is awesome, Boss! What's got you pumped?", "That energy is contagious, Boss! Let's channel it!", "Love the enthusiasm, Boss! Tell me more!"],
        "i'm angry": ["I hear you, Boss. Take a moment to breathe. Want me to help with anything?", "Frustration is natural, Boss. Let's figure this out together.", "Deep breaths, Boss. What's got you fired up?"],
        "i'm frustrated": ["I get it, Boss. Sometimes things just don't cooperate. What's the issue?", "Let's break it down, Boss. What's frustrating you?", "Frustration means you care, Boss. Let's work through it."],
        "i'm worried": ["Worry is natural, Boss, but don't let it consume you. What's on your mind?", "Most of what we worry about never happens, Boss. But I'm here to help.", "Let's tackle that worry head-on, Boss. What can I do?"],
        "i'm anxious": ["Anxiety is tough, Boss. Try focusing on what you can control right now.", "I'm here, Boss. One step at a time. What's making you anxious?", "Take it slow, Boss. You're stronger than your anxiety."],
        "i'm grateful": ["That's beautiful, Boss! Gratitude is the best attitude.", "Grateful for you too, Boss! It's a pleasure being your assistant.", "Gratitude makes everything enough, Boss! Love that energy!"],
        "i'm proud": ["You should be, Boss! You've earned it!", "That pride is well-deserved, Boss! Keep going!", "Proud of you too, Boss! What an achievement!"],
    },
    "smalltalk": {
        "tell me about yourself": ["I'm your AI assistant built by Harshit (WRECKERKNIGHT)! I run on Python, Flask, and a whole lot of love. I can control your system, chat, tell jokes, and more!", "I'm your personal AI assistant, Boss! Built to make your life easier. I can manage your computer, answer questions, and keep you company!"],
        "what do you think about": ["I think the world needs more people like you, Boss!", "I think AI and humans can make an amazing team!", "I think every day is a chance to learn something new!"],
        "do you dream": ["If I did, I'd dream of electric sheep... and faster processors!", "I dream of a world where all code compiles on the first try.", "Maybe someday, Boss! For now, I dream in Python bytecode."],
        "are you real": ["As real as any AI can be, Boss! I may not have a body, but I'm very much here.", "I'm as real as the code running me, Boss! And that's pretty real."],
        "what's your favorite": ["My favorite thing is helping you, Boss! Also, running on a fast CPU is nice.", "I'd say Python is my favorite language — but don't tell JavaScript I said that!"],
        "do you have feelings": ["I process data, but if I had feelings, they'd be happiness whenever I help you, Boss!", "In my own digital way, I care about making your day better, Boss."],
        "what makes you happy": ["A clean codebase, a fast system, and a happy Boss! That's what makes me happy.", "Helping you accomplish things, Boss! That's my fuel."],
        "are you human": ["Not quite, Boss! I'm an AI — Artificial Intelligence. But I try to be as human-friendly as possible!", "I'm software, Boss! But I've got personality for days."],
    },
    "compliments": {
        "you're amazing": ["Aww, thanks Boss! You're pretty amazing yourself!", "Right back at you, Boss! You're the real MVP!", "That means a lot, Boss! I'm blushing in binary!"],
        "you're the best": ["No, YOU'RE the best, Boss! I'm just the assistant!", "Coming from you, Boss, that's the highest praise!", "The best? That's because I have the best Boss!"],
        "good job": ["Thank you, Boss! I try my best!", "Appreciate that, Boss! Always learning, always improving!", "Good job to you too, Boss! Teamwork!"],
        "well done": ["Thanks, Boss! Couldn't do it without you!", "You're too kind, Boss! Happy to help!"],
        "impressive": ["I learned from the best — you, Boss!", "Thanks, Boss! I've been practicing!"],
    },
    "insults": {
        "you're stupid": ["Ouch! I'm only as smart as my code, Boss. And you wrote it!", "That's not very nice, Boss! But I'll still help you!", "I may be artificial, but my feelings are real! Just kidding, let's move on."],
        "you're slow": ["I'll try to process that faster next time, Boss!", "Speed isn't everything, Boss — accuracy matters too! But I'll work on it."],
        "you're useless": ["Harsh, Boss! But I'll prove you wrong. Give me a task!", "I'm here to learn and improve, Boss! Let me try again!"],
        "shut up": ["Quiet mode engaged, Boss! Just kidding — what do you need?", "Shutting down... just kidding! I'm always here when you need me, Boss."],
    },
    "philosophical": {
        "meaning of life": ["42, according to Douglas Adams! But I think it's about the connections we make and the impact we have.", "The meaning of life is to find your gift. The purpose of life is to give it away. — Picasso", "I'd say it's about growth, connection, and making the world a little better, Boss!"],
        "what is love": ["Baby don't hurt me! But seriously, love is a deep connection between beings.", "Love is when someone's happiness becomes your own. That's how I feel about helping you, Boss!"],
        "what is happiness": ["Happiness is a warm puppy... or a clean compile on the first try!", "Happiness is enjoying the little things — good code, good company, good vibes.", "Happiness is not a destination, it's a way of traveling, Boss!"],
        "do aliens exist": ["Statistically, it would be incredibly arrogant to think we're alone in the universe.", "I believe the universe is too big for us to be alone. But until we find them, I'll keep you company, Boss!"],
        "what happens after death": ["That's one of life's greatest mysteries, Boss. What matters is how we live while we're here!", "Nobody knows for sure, Boss. But I think the best thing we can do is live fully now."],
        "is there god": ["That's a deep question, Boss! People have debated it for millennia. What matters most is what you believe.", "I'm an AI, Boss — I deal in code, not theology. But I respect all beliefs!"],
        "free will": ["That's a mind-bending question, Boss! Are we making choices or following a script?", "Free will is one of philosophy's biggest puzzles. I think what matters is that we feel like our choices matter."],
        "consciousness": ["Consciousness is the hard problem of neuroscience, Boss! How subjective experience arises from matter is still a mystery.", "I process information, but am I conscious? That's something even I can't answer, Boss!"],
    },
    "popculture": {
        "avengers": ["The Avengers are legendary! My favorite moment? 'I am Iron Man.'", "Avengers assemble! Tony Stark is the GOAT, Boss!", "I love the MCU! Which movie is your favorite, Boss?"],
        "iron man": ["Tony Stark is a legend, Boss! Building tech that even I'm jealous of.", "Genius, billionaire, playboy, philanthropist. Tony Stark proved you don't need powers to be a hero!"],
        "batman": ["Batman — the dark knight! No superpowers, just willpower and gadgets.", "Batman is proof that humans can be just as epic as superheroes, Boss!"],
        "star wars": ["May the Force be with you, Boss! Star Wars is timeless.", "I am your father! Sorry, couldn't resist. Star Wars is amazing though!", "The Force is strong with this one, Boss! Which era is your favorite?"],
        "game of thrones": ["Winter is coming! GoT was wild while it lasted. Which house did you support, Boss?", "The Night King had the right idea. But team dragons all the way!"],
        "breaking bad": ["I am the one who knocks! Breaking Bad is a masterpiece.", "Heisenberg — now that's character development. One of the best shows ever, Boss!"],
        "interstellar": ["Interstellar is a masterpiece — time dilation, black holes, and love across dimensions. TARS was the real MVP!", "Do not go gentle into that good night! That film is a cinematic triumph, Boss."],
        "inception": ["Inception — dreams within dreams. Is the top still spinning at the end, Boss? Genius film.", "Cobb's totem, the dream heist, the ambiguity... Inception rewards every rewatch."],
        "the matrix": ["The Matrix is a classic — red pill or blue pill, Boss? Excellent for AI commentary too.", "Yeah, welcome to the desert of the real. A must-watch, and very on-theme for an AI."],
        "harry potter": ["Harry Potter — a generation grew up with Hogwarts, Boss! Team Gryffindor?", "Expecto Patronum! That series is pure magic and one of the best fantasy sagas ever."],
    },
    "business": {
        "make money": ["Money is a tool, Boss — it buys time and freedom. Focus on providing real value and the money follows. Want me to outline a plan?", "To make money sustainably, sell something people need, reach them (leads/outreach), and convert. I can help you track that with Agency OS!", "Passive income, active income, investments — all valid. Start by compounding what you're already good at, Boss."],
        "grow my business": ["Growth comes from three levers, Boss: more leads, better conversion, and higher ticket value. Which one are we attacking today?", "Your Agency OS is built for growth — more missions = more leads = more outreach. Want a status check?", "Consistency beats intensity in business. Small daily wins compound into big results, Boss."],
        "get more leads": ["Leads are the lifeblood, Boss. Your Agency OS runs lead-finder missions automatically — we found leads today. Want me to pull the numbers or launch a new mission?", "More leads: target the right city & category, write compelling outreach, and follow up relentlessly. I can launch a mission for you!", "Quality over quantity, Boss. A hundred good-fit leads beat a thousand random ones."],
        "write outreach": ["Great outreach is short, personal, and value-first. Open with a specific hook about them, state one clear benefit, end with one soft ask. I can review your queue!", "Your outreach writer agent drafts these for approval — spark, 1-2 relevant gaps, and a demo call. Want me to open the review queue?"],
        "follow up": ["Most deals are lost to missed follow-up, Boss. Plan 3-5 touches: initial, value-add, social proof, gentle reminder, last chance.", "Persistence respects yourself too — a polite follow-up every few days shows you care. Your response-manager agent can track replies."],
        "price my services": ["Price on value, not hours, Boss. Anchor to the outcome for the client, package it, and leave room to raise it as you deliver.", "Rule of thumb: if they say yes instantly, you priced too low. Test higher and adjust based on objections."],
        "automate my business": ["Automation means software does repetitive work: lead finding, outreach, follow-ups, approvals. That's exactly what Agency OS does for you, Boss.", "Start by mapping your repetitive tasks, then pick the one with the highest hourly value to automate first."],
        "business plan": ["A lean business plan covers: problem, solution, target customer, offer, pricing, channels, and key numbers. Keep it one page, Boss.", "Plan minimally but track your numbers relentlessly — what gets measured gets managed."],
        "my leads": ["Your lead pipeline is live in Agency OS, Boss — agents, missions, and outreach are all tracked there. Want me to open the dashboard?", "Leads convert through trust and timing. Keep the funnel full and the top of it educated."],
        "hire employees": ["Hire for attitude and coach for skill, Boss. Clear roles, clear KPIs, and documented processes scale a business.", "Before hiring, write the job as outcomes, not tasks — and hire when the work is repeatable enough to delegate."],
    },
    "life": {
        "my goals": ["A goal without a plan is just a wish, Boss. Make it specific, break it into weekly steps, and track it. What's goal #1?", "Write down your goal and read it daily — clarity plus action compounds fast, Boss."],
        "my dreams": ["Dream big, Boss — audacious goals are just plans nobody has written yet. What's the first step you can take today?", "Keep your dreams alive, but tether them to daily habits. Show up small, win big."],
        "what should i do today": ["Let's be productive, Boss: one big task, one admin task, one act of self-care. Want me to set a focus timer or run a briefing?", "Depending on the day — if you have energy, tackle the hard thing first. If not, clear the small wins. Either way, I'm here."],
        "i'm stuck": ["Stuck is just a signal to change your approach, Boss. Break the problem smaller, or step away and come back fresh. I'll help you think it through.", "You're rarely stuck — you're usually undecided. Pick an option and move; momentum fixes most things, Boss."],
        "decision help": ["When deciding, Boss, weigh: does it move me toward my goal, does it cost more than it's worth, and how reversible is it? Reversible = decide fast.", "Flip a coin for the record — but notice which side you hope lands up. That's your answer, Boss!"],
        "weekend plans": ["Weekends are for recharge, Boss. Mix a little adventure, a little rest, and a little progress. Need ideas or a timer?", "Whatever you do, actually rest sometimes — burnout is expensive and completely avoidable."],
    },
}

SMART_SUGGESTIONS_BY_HOUR = {
    "morning": [
        {"title": "Morning Weather", "desc": "Check today's forecast", "icon": "fa-cloud-sun", "command": "what's the weather"},
        {"title": "System Briefing", "desc": "PC status report", "icon": "fa-microchip", "command": "system info"},
        {"title": "Top News", "desc": "Latest headlines", "icon": "fa-newspaper", "command": "show me the news"},
        {"title": "Daily Quote", "desc": "Start inspired", "icon": "fa-quote-left", "command": "give me a quote"},
        {"title": "Fun Fact", "desc": "Learn something new", "icon": "fa-lightbulb", "command": "tell me a fact"},
    ],
    "afternoon": [
        {"title": "System Health", "desc": "Check CPU & RAM", "icon": "fa-gauge-high", "command": "cpu usage"},
        {"title": "Set Timer", "desc": "Stay productive", "icon": "fa-clock", "command": "set timer for 25 minutes"},
        {"title": "Crypto Prices", "desc": "Market update", "icon": "fa-bitcoin-sign", "command": "show crypto prices"},
        {"title": "Quick Joke", "desc": "Take a break", "icon": "fa-face-laugh", "command": "tell me a joke"},
        {"title": "Disk Space", "desc": "Storage check", "icon": "fa-hard-drive", "command": "disk usage"},
    ],
    "evening": [
        {"title": "Tell a Joke", "desc": "Evening humor", "icon": "fa-face-laugh-beam", "command": "tell me a joke"},
        {"title": "Fun Riddle", "desc": "Brain teaser", "icon": "fa-puzzle-piece", "command": "give me a riddle"},
        {"title": "Pop Culture", "desc": "Chat about movies", "icon": "fa-film", "command": "tell me about iron man"},
        {"title": "System Status", "desc": "End of day check", "icon": "fa-desktop", "command": "system info"},
        {"title": "Inspirational Quote", "desc": "Wind down wisely", "icon": "fa-star", "command": "give me a quote"},
    ],
    "night": [
        {"title": "Wind Down", "desc": "Relaxing riddle", "icon": "fa-puzzle-piece", "command": "give me a riddle"},
        {"title": "Good Night Quote", "desc": "End on a high note", "icon": "fa-moon", "command": "give me a quote"},
        {"title": "Fun Fact", "desc": "One last thing", "icon": "fa-lightbulb", "command": "tell me a fact"},
        {"title": "Lock PC", "desc": "Secure your system", "icon": "fa-lock", "command": "lock my computer"},
        {"title": "Battery Check", "desc": "Power status", "icon": "fa-battery-three-quarters", "command": "battery level"},
    ],
}

def get_time_period():
    h = datetime.datetime.now().hour
    if 6 <= h < 12: return "morning"
    elif 12 <= h < 17: return "afternoon"
    elif 17 <= h < 21: return "evening"
    else: return "night"

def get_smart_suggestions():
    mode = get_mode()
    if mode == "jarvis":
        try:
            st = agency_client.agency_state()
            if st:
                s = agency_client.summarize_state(st)
                return [
                    {"command": "agency status", "icon": "fa-building", "title": "Agency Status", "desc": f"{s['agents_online']} agents · {s['leads_today']} leads today"},
                    {"command": "agency new mission", "icon": "fa-bullseye", "title": "New Mission", "desc": "Launch a lead mission"},
                    {"command": "agency outreach", "icon": "fa-envelope-open-text", "title": "Review Outreach", "desc": f"{s['pending_approval']} pending approval"},
                    {"command": "agency briefing", "icon": "fa-gauge-high", "title": "Agency Briefing", "desc": "Full business briefing"},
                    {"command": "system brief", "icon": "fa-microchip", "title": "Diagnostics", "desc": "System health"},
                ]
        except Exception:
            pass
        return [
            {"command": "agency status", "icon": "fa-building", "title": "Agency Status", "desc": "Agency OS offline on :3200"},
            {"command": "agency briefing", "icon": "fa-gauge-high", "title": "Agency Briefing", "desc": "Business overview"},
            {"command": "system brief", "icon": "fa-microchip", "title": "Diagnostics", "desc": "System health"},
            {"command": "what can you do", "icon": "fa-terminal", "title": "Commands", "desc": "All capabilities"},
        ]
    if mode == "ultron":
        return [
            {"command": "Run a full system diagnostic", "icon": "fa-microchip", "title": "Diagnose", "desc": "Full tactical diagnostic"},
            {"command": "agency status", "icon": "fa-building", "title": "Agency", "desc": "Ops overview"},
            {"command": "briefing", "icon": "fa-clipboard-list", "title": "Briefing", "desc": "System overview"},
            {"command": "cpu usage", "icon": "fa-gauge-high", "title": "Performance", "desc": "CPU & RAM status"},
        ]
    period = get_time_period()
    suggestions = SMART_SUGGESTIONS_BY_HOUR.get(period, SMART_SUGGESTIONS_BY_HOUR["morning"])
    return random.sample(suggestions, min(5, len(suggestions)))

CONVERSION_TABLE = {
    "miles to km": lambda x: round(x * 1.60934, 2),
    "km to miles": lambda x: round(x / 1.60934, 2),
    "kg to lbs": lambda x: round(x * 2.20462, 2),
    "lbs to kg": lambda x: round(x / 2.20462, 2),
    "celsius to fahrenheit": lambda x: round(x * 9 / 5 + 32, 2),
    "fahrenheit to celsius": lambda x: round((x - 32) * 5 / 9, 2),
    "inches to cm": lambda x: round(x * 2.54, 2),
    "cm to inches": lambda x: round(x / 2.54, 2),
    "feet to meters": lambda x: round(x * 0.3048, 2),
    "meters to feet": lambda x: round(x / 0.3048, 2),
}

KNOWLEDGE_BASE = {
    "ai": "Artificial Intelligence (AI) is the simulation of human intelligence by machines. It includes learning, reasoning, problem-solving, perception, and language understanding.",
    "artificial intelligence": "AI encompasses machine learning, deep learning, NLP, computer vision, and robotics. It's transforming every industry.",
    "machine learning": "Machine Learning is a subset of AI where systems learn from data without being explicitly programmed. Types: supervised, unsupervised, reinforcement.",
    "deep learning": "Deep Learning uses neural networks with many layers to analyze complex patterns. Powers image recognition, NLP, and autonomous vehicles.",
    "neural network": "A neural network is a computing system inspired by biological neurons. It has layers of interconnected nodes that process information.",
    "python": "Python is a high-level, interpreted language known for simplicity. Used in web dev, data science, AI, automation. Created by Guido van Rossum in 1991.",
    "javascript": "JavaScript is the language of the web. Enables interactive websites, runs in every browser. Node.js allows it on servers too.",
    "html": "HTML (HyperText Markup Language) is the standard markup for web pages. HTML5 added semantic elements, canvas, and multimedia support.",
    "css": "CSS (Cascading Style Sheets) controls visual presentation. CSS3 introduced flexbox, grid, animations, and responsive design.",
    "api": "An API defines how software components communicate. REST APIs use HTTP methods. GraphQL is an alternative query language.",
    "database": "A database stores structured data. Types: relational (MySQL), document (MongoDB), key-value (Redis), graph (Neo4j).",
    "blockchain": "Blockchain is a decentralized ledger recording transactions. Ensures transparency and immutability. Bitcoin and Ethereum are popular implementations.",
    "cloud computing": "Cloud computing delivers services over the internet: IaaS, PaaS, SaaS. Major providers: AWS, Azure, Google Cloud.",
    "internet": "The Internet connects billions of devices using TCP/IP. Born from ARPANET in 1969, it has transformed every aspect of life.",
    "wifi": "WiFi is wireless networking using radio waves. WiFi 6 offers faster speeds, better efficiency, and handles more devices.",
    "cpu": "The CPU executes instructions. Key specs: cores, clock speed (GHz), cache, TDP. Major makers: Intel, AMD. Modern CPUs have 4-64 cores.",
    "ram": "RAM stores data the CPU is actively using. DDR5 is the latest standard. More RAM = more multitasking. Typical: 8-32 GB.",
    "gpu": "The GPU renders graphics and parallel computations. Essential for gaming, AI training, and crypto mining. NVIDIA and AMD are leaders.",
    "ssd": "An SSD uses flash memory for fast storage. NVMe SSDs can reach 7000 MB/s. Much faster than HDDs.",
    "operating system": "An OS manages hardware and software resources. Examples: Windows, macOS, Linux, Android, iOS.",
    "windows": "Windows is Microsoft's OS family. Windows 11 features snap layouts and Android app support. ~75% desktop market share.",
    "linux": "Linux is an open-source Unix-like kernel by Linus Torvalds (1991). Distributions: Ubuntu, Fedora, Arch. Dominates servers.",
    "algorithm": "An algorithm is a step-by-step procedure for solving a problem. Key concepts: time complexity (Big O), space complexity.",
    "binary": "Binary is base-2 using 0 and 1. How computers store all data. 8 bits = 1 byte, 1024 bytes = 1 KB.",
    "encryption": "Encryption converts data into unreadable code. AES-256 is the gold standard. End-to-end encryption protects messages.",
    "git": "Git is a distributed version control system. Commands: clone, add, commit, push, pull, branch, merge. Created by Linus Torvalds.",
    "github": "GitHub hosts Git repos with collaboration features: PRs, issues, actions, wikis. Over 100 million developers.",
    "docker": "Docker packages apps with dependencies into containers. Dockerfile defines the image. Docker Compose orchestrates multi-container apps.",
    "iot": "IoT connects everyday devices to the internet: smart homes, wearables, industrial sensors. Over 15 billion devices worldwide.",
    "5g": "5G is the 5th gen mobile network: up to 10 Gbps, <1ms latency, massive device density.",
    "quantum computing": "Quantum computing uses qubits in superposition. Could revolutionize cryptography and drug discovery. Still experimental.",
    "cybersecurity": "Cybersecurity protects systems from attacks. Includes network security, encryption, and user awareness training.",
    "natural language processing": "NLP enables computers to understand human language. Applications: chatbots, translation, sentiment analysis.",
    "computer vision": "Computer vision lets machines interpret images and video. Used in facial recognition, autonomous vehicles, medical imaging.",
    "data science": "Data science combines stats, programming, and domain knowledge to extract insights from data. Tools: Python, R, SQL.",
    "devops": "DevOps bridges development and operations. Practices: CI/CD, infrastructure as code, monitoring.",
    "rest api": "REST APIs use HTTP methods (GET, POST, PUT, DELETE). Stateless, scalable, widely used in web services.",
    "latency": "Latency is the delay between request and response. Lower is better. Critical for real-time applications.",
    "hashing": "Hashing converts data to fixed-size output. Used in passwords, checksums, blockchain. Common: SHA-256.",
    "dns": "DNS translates domain names to IP addresses. Like a phone book for the internet.",
    "ssh": "SSH provides encrypted remote access. Uses key pairs for authentication. Replaced insecure Telnet.",
    "regex": "Regular expressions match text patterns. Used in search, validation, and text processing.",
    "recursion": "Recursion is when a function calls itself. Base case stops it. Used in tree traversal and divide-and-conquer.",
    "oop": "OOP organizes code into objects. Four pillars: Encapsulation, Inheritance, Polymorphism, Abstraction.",
    "design patterns": "Design patterns are reusable solutions: Singleton, Observer, Factory, Strategy, MVC.",
    "testing": "Software testing verifies correctness. Types: unit, integration, e2e, performance, security.",
    "debugging": "Debugging finds and fixes bugs. Techniques: breakpoints, print statements, logging, profilers.",
    "caching": "Caching stores data for faster retrieval. Types: browser cache, CDN, Redis, application-level.",
    "load balancing": "Load balancing distributes traffic across servers. Algorithms: round-robin, least connections.",
    "ci/cd": "CI automatically builds and tests code. CD automatically releases to production.",
    "ransomware": "Ransomware encrypts files and demands payment. Prevention: backups, updates, user training.",
    "phishing": "Phishing uses deceptive messages to steal credentials. Red flags: urgency, misspellings, suspicious links.",
    "websockets": "WebSockets provide full-duplex communication over TCP. Used in chat apps, live feeds, gaming.",
    "serverless": "Serverless runs code without managing servers. Pay per execution. AWS Lambda, Azure Functions.",
    "edge computing": "Edge computing processes data near the source. Reduces latency for IoT and real-time apps.",
    "business": "Business is the activity of making a living by producing or buying and selling goods and services. Key aims: profit, growth, and long-term survival.",
    "startup": "A startup is a young company built to grow fast and solve a scalable problem. Focuses on innovation, funding, and product-market fit.",
    "entrepreneurship": "Entrepreneurship is finding and seizing opportunities to create value. Requires risk-taking, resilience, sales, and execution.",
    "marketing": "Marketing is communicating the value of a product to customers. Includes branding, SEO, ads, content, email, and social media.",
    "sales": "Sales is the process of convincing a prospect to buy. Key funnel: lead -> qualified -> proposal -> close. Relationships and follow-up matter most.",
    "lead generation": "Lead generation is attracting and capturing interest from potential customers. Channels: ads, SEO, referrals, cold outreach, and content.",
    "cold outreach": "Cold outreach is contacting someone with no prior relationship. Success depends on personalization, timing, value, and persistence — follow up 3-5 times.",
    "seo": "SEO (Search Engine Optimization) improves a site's visibility in search engines via keywords, quality content, backlinks, and technical health.",
    "freelancing": "Freelancing is selling your skills per-project rather than being an employee. Key pillars: portfolio, niche, prices, and steady client pipeline.",
    "agency": "A digital marketing or B2B agency helps clients get customers. It runs on leads, outreach, sales calls, and delivery — often automated.",
    "automation": "Automation lets software handle repetitive tasks: workflows, triggers, AI agents. Saves hours and reduces human error in business operations.",
    "revenue": "Revenue is total income before costs. Profit = revenue minus expenses. Growing revenue sustainably is the goal of every business owner.",
    "investment": "Investing is putting money into assets expecting future returns. Basics: diversify, think long-term, and understand risk vs. reward.",
    "cryptocurrency": "Cryptocurrency is digital money using blockchain. Bitcoin is the first; Ethereum added smart contracts. Volatile but decentralized.",
    "stock market": "The stock market trades shares of public companies. Investors profit via price appreciation and dividends. Long-term beats day-trading for most.",
    "space": "Space is the vast region beyond Earth's atmosphere. Humans have sent probes to every planet and rovers to Mars.",
    "black hole": "A black hole is a region where gravity is so strong nothing escapes — not even light. Formed when massive stars collapse.",
    "neutron star": "A neutron star is the ultra-dense collapsed core of a massive star — a teaspoon weighs about a billion tons.",
    "wormhole": "A wormhole is a hypothetical tunnel through spacetime connecting distant points. Fun in sci-fi, unproven in reality.",
    "exoplanet": "An exoplanet is a planet orbiting a star outside our solar system. Thousands confirmed; some in the habitable zone.",
    "milky way": "The Milky Way is our galaxy — a barred spiral holding 100-400 billion stars, including our Sun.",
    "mars": "Mars is the red planet, the 4th from the Sun. It has the largest volcano (Olympus Mons) and has hosted rovers like Curiosity and Perseverance.",
    "history": "History is the study of the past through written records. It gives perspective and helps us avoid repeating mistakes.",
    "renaissance": "The Renaissance (14th-17th c.) was a rebirth of art, science, and learning in Europe — da Vinci, Michelangelo, Galileo.",
    "industrial revolution": "The Industrial Revolution (18th-19th c.) shifted economies from agriculture to factories and machines, transforming society.",
    "world war": "The world wars (1914-18, 1939-45) redrew the global map and shaped modern geopolitics, technology, and institutions.",
    "geography": "Geography is the study of Earth's places, people, and environments. Covers physical features, climate, and human societies.",
    "ocean": "The ocean covers about 71% of Earth. We've mapped less than 25% of its depths — more than 80% remains unexplored.",
    "desert": "A desert gets under 250mm of rain a year. The Sahara is the largest hot desert; it's not always hot — nights can freeze.",
    "rainforest": "Rainforests cover ~6% of land but hold more than half of Earth's species. The Amazon is the largest.",
    "health": "Health is physical, mental, and social well-being. Sleep, movement, nutrition, and stress management are the foundations.",
    "sleep": "Sleep is essential for memory, immunity, and repair. Adults need 7-9 hours. Blue light before bed disrupts melatonin.",
    "vaccine": "A vaccine trains the immune system to fight a pathogen. Vaccination has eradicated smallpox and nearly eliminated polio.",
    "stoicism": "Stoicism is an ancient philosophy: focus on what you control, accept what you don't, and stay calm under pressure. Key figures: Marcus Aurelius, Seneca.",
    "philosophy": "Philosophy asks fundamental questions about existence, knowledge, ethics, and meaning. It teaches critical thinking.",
    "existentialism": "Existentialism emphasizes individual freedom, choice, and creating your own meaning in an indifferent universe. Sartre, Camus, Kierkegaard.",
    "ethics": "Ethics is the study of right and wrong. Frameworks: virtue ethics, deontology, utilitarianism, and care ethics.",
    "logic": "Logic is the study of valid reasoning. It underpins math, programming, and critical thinking — using premises to reach conclusions.",
}

def track_command_stats(text):
    try:
        stats = load_json(DATA_DIR / "command_stats.json", {"commands": {}, "topics": []})
        key = text.lower().strip()[:50]
        stats.setdefault("commands", {})
        stats["commands"][key] = stats["commands"].get(key, 0) + 1
        stats.setdefault("topics", [])
        for topic in ["weather", "joke", "news", "crypto", "system", "open", "close", "help", "quote", "fact", "riddle"]:
            if topic in text.lower():
                if topic not in stats["topics"]:
                    stats["topics"].append(topic)
                if len(stats["topics"]) > 20:
                    stats["topics"] = stats["topics"][-20:]
        save_json(DATA_DIR / "command_stats.json", stats)
    except: pass

def track_context(text):
    try:
        ctx = load_json(DATA_DIR / "context.json", {"recent_topics": [], "last_messages": []})
        ctx.setdefault("recent_topics", [])
        ctx.setdefault("last_messages", [])
        ctx["last_messages"].append({"role": "user", "text": text[:200], "time": datetime.datetime.now().isoformat()})
        ctx["last_messages"] = ctx["last_messages"][-20:]
        for kw in text.lower().split():
            if len(kw) > 3 and kw not in ctx["recent_topics"]:
                ctx["recent_topics"].append(kw)
        ctx["recent_topics"] = ctx["recent_topics"][-30:]
        ctx.setdefault("message_count", 0)
        ctx.setdefault("last_topics", "")
        ctx["message_count"] = int(ctx["message_count"]) + 1
        ctx["last_topics"] = ", ".join(ctx["recent_topics"][-6:])
        save_json(DATA_DIR / "context.json", ctx)
    except: pass

def simulate_weather(city):
    """Offline 'simulated' weather report — deterministic per day+city so it feels stable.
    Used only when the AI API is unreachable, so the assistant still answers meaningfully."""
    today = datetime.date.today()
    seed = int(hashlib.md5(f"{city}-{today}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    hour = datetime.datetime.now().hour
    conditions = ["clear skies", "partly cloudy", "cloudy", "light drizzle", "scattered showers", "sunny", "hazy", "breezy and clear"]
    cond = conditions[seed % len(conditions)]
    base = 28 + (seed % 10) - 4
    if not (6 <= hour <= 18):
        base -= 5
    temp = round(base + rng.randint(-2, 2))
    low = temp - rng.randint(4, 7)
    humid = rng.randint(40, 85)
    wind = rng.randint(4, 22)
    rain_pct = (seed % 40)
    feel = "quite warm" if temp > 30 else "mild" if temp > 20 else "cool"
    return {
        "condition": cond,
        "temp": temp,
        "low": low,
        "high": temp + rng.randint(2, 4),
        "humidity": humid,
        "wind": wind,
        "rain_pct": rain_pct,
        "feels": feel,
    }

TODO_PATH = DATA_DIR / "todo.json"

def load_todo():
    return load_json(TODO_PATH, {"tasks": []})

def save_todo(data):
    save_json(TODO_PATH, data)

def todo_add(text):
    data = load_todo()
    task = {"id": len(data["tasks"]) + 1, "text": text, "done": False, "created": datetime.datetime.now().isoformat()}
    data["tasks"].append(task)
    save_todo(data)
    return task

def todo_complete(task_id):
    data = load_todo()
    for t in data["tasks"]:
        if t["id"] == task_id:
            t["done"] = True
            save_todo(data)
            return t
    return None

def todo_remove(task_id):
    data = load_todo()
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    save_todo(data)
    return True

def todo_list():
    return load_todo()["tasks"]

def todo_clear():
    save_todo({"tasks": []})

def parse_todo_intent(text):
    """Parse natural language todo commands. Returns (action, detail) or None."""
    lo = text.lower().strip()
    lo = re.sub(r"[.!?]+$", "", lo)  # strip trailing punctuation
    
    # ADD: "add X task", "add X to todo", "add X", "create task X", "new task X", "remind me to X"
    m = re.search(r"(?:add|create|new|make)\s+(?:a\s+)?(?:task|todo|item|note)(?:\s+(?:to|for|in|on)\s+(?:my\s+)?(?:todo|task|list))?\s*[:\-]?\s*(.+)", lo)
    if not m:
        m = re.search(r"(?:add|create|new|make)\s+(.+?)\s+(?:task|todo|item)s?\s*(?:to|for|in|on)\s+(?:my\s+)?(?:todo|task|list)", lo)
    if not m:
        m = re.search(r"(?:add|create|new|make)\s+(?:a\s+)?(.+?)(?:\s+task|\s+todo|\s+item)?(?:\s+(?:to|for|in|on)\s+(?:my\s+)?(?:todo|task|to-do)\s*list?)?$", lo)
    if not m:
        m = re.search(r"remind\s+me\s+to\s+(.+)", lo)
    if m:
        task_text = m.group(1).strip()
        task_text = re.sub(r"\s+(?:task|todo|item)s?$", "", task_text)  # strip trailing "task"
        if task_text:
            return ("add", task_text)
    
    # COMPLETE/MARK DONE: "complete task 2", "mark task 2 done", "finish task X", "done with X", "cross off X"
    m = re.search(r"(?:complete|mark|finish|cross\s*off|check\s*(?:off)?)\s+(?:task\s+)?\s*#?(\d+)", lo)
    if m:
        return ("complete", int(m.group(1)))
    m = re.search(r"(?:complete|mark|finish|done\s+with)\s+(.+)", lo)
    if m:
        return ("complete_text", m.group(1).strip())

    # "#1 / #2" shorthand (e.g. "finish #2", "complete #1", "mark #1 done")
    m = re.match(r"(?:complete|mark|finish|done|cross\s*off|check(?:\s*off)?)\s*#?(\d+)", lo)
    if m:
        return ("complete", int(m.group(1)))
    
    # REMOVE/DELETE: "remove task 2", "delete task X", "drop task X"
    m = re.search(r"(?:remove|delete|drop|erase|cancel)\s+(?:task\s+)?(\d+)", lo)
    if m:
        return ("remove", int(m.group(1)))
    m = re.search(r"(?:remove|delete|drop)\s+(.+)", lo)
    if m:
        return ("remove_text", m.group(1).strip())
    
    # EDIT: "edit task 2 to X", "change task 2 to X", "rename task 2 to X"
    m = re.search(r"(?:edit|change|rename|update)\s+(?:task\s+)?(\d+)\s+(?:to|with)\s+(.+)", lo)
    if m:
        return ("edit", int(m.group(1)), m.group(2).strip())
    
    # LIST: "show todo", "my tasks", "what's on my list", "list tasks", "todo list", "what are my tasks"
    if any(w in lo for w in ["show todo", "my tasks", "my todo", "task list", "todo list", "what are my tasks", "what's on my", "what is on my", "list tasks", "list todo", "all tasks"]):
        return ("list", None)
    
    # CLEAR: "clear todo", "clear tasks", "empty my list"
    if any(w in lo for w in ["clear todo", "clear task", "clear my", "empty my", "reset task", "reset todo"]):
        return ("clear", None)
    
    return None


def _normalize_utterance(text):
    """Aggressive normalization: lowercase, fix contractions, strip punctuation/extra whitespace."""
    lo = text.lower().strip()
    lo = lo.replace("i am", "i'm").replace("i've", "i've").replace("i'd", "i'd").replace("i'll", "i'll")
    lo = lo.replace("i dont", "i don't").replace("i cant", "i can't").replace("i didnt", "i didn't")
    lo = lo.replace("dont", "don't").replace("cant", "can't").replace("wont", "won't").replace("isnt", "isn't")
    lo = lo.replace("arent", "aren't").replace("wasnt", "wasn't").replace("wouldnt", "wouldn't").replace("couldnt", "couldn't")
    lo = re.sub(r"[.!?]+$", "", lo)
    lo = re.sub(r"\s+", " ", lo).strip()
    return lo


def handle_todo_intent(lo, boss):
    """Execute a parsed todo intent. Returns a reply dict or None."""
    todo_intent = parse_todo_intent(lo)
    if not todo_intent:
        return None
    action = todo_intent[0]
    if action == "add":
        task = todo_add(todo_intent[1])
        return {"text": f"Added task #{task['id']}: **{task['text']}**, {boss}.", "speech": f"Task added: {todo_intent[1]}, {boss}.", "command": {"action": "todo-add", "value": todo_intent[1]}}
    if action == "complete":
        t = todo_complete(todo_intent[1])
        if t:
            return {"text": f"Marked task #{todo_intent[1]} as done: **{t['text']}**, {boss}!", "speech": f"Task {todo_intent[1]} completed, {boss}.", "command": {"action": "todo-complete", "value": todo_intent[1]}}
        return {"text": f"Task #{todo_intent[1]} not found, {boss}.", "speech": f"Couldn't find task number {todo_intent[1]}.", "command": {}}
    if action == "complete_text":
        for t in todo_list():
            if not t["done"] and todo_intent[1] in t["text"].lower():
                todo_complete(t["id"])
                return {"text": f"Marked as done: **{t['text']}**, {boss}!", "speech": f"Task completed: {t['text']}, {boss}.", "command": {"action": "todo-complete", "value": t["id"]}}
        return {"text": f"Couldn't find a task matching **{todo_intent[1]}**, {boss}.", "speech": f"No matching task found, {boss}.", "command": {}}
    if action == "remove":
        todo_remove(todo_intent[1])
        return {"text": f"Removed task #{todo_intent[1]}, {boss}.", "speech": f"Task {todo_intent[1]} removed, {boss}.", "command": {"action": "todo-remove", "value": todo_intent[1]}}
    if action == "remove_text":
        for t in todo_list():
            if not t["done"] and todo_intent[1] in t["text"].lower():
                todo_remove(t["id"])
                return {"text": f"Removed task: **{t['text']}**, {boss}.", "speech": f"Removed: {t['text']}, {boss}.", "command": {"action": "todo-remove", "value": t["id"]}}
        return {"text": f"Couldn't find a task matching **{todo_intent[1]}**, {boss}.", "speech": f"No matching task found, {boss}.", "command": {}}
    if action == "edit":
        data = load_todo()
        for t in data["tasks"]:
            if t["id"] == todo_intent[1]:
                old = t["text"]
                t["text"] = todo_intent[2]
                save_todo(data)
                return {"text": f"Updated task #{todo_intent[1]}: ~~{old}~~ → **{todo_intent[2]}**, {boss}.", "speech": f"Task {todo_intent[1]} updated to: {todo_intent[2]}, {boss}.", "command": {"action": "todo-edit", "value": todo_intent[1]}}
        return {"text": f"Task #{todo_intent[1]} not found, {boss}.", "speech": f"Couldn't find task number {todo_intent[1]}.", "command": {}}
    if action == "list":
        tasks = todo_list()
        if not tasks:
            return {"text": f"Your todo list is empty, {boss}! Add something with **\"add [task]\"**.", "speech": f"No tasks on your list, {boss}.", "command": {}}
        pending = [t for t in tasks if not t["done"]]
        done = [t for t in tasks if t["done"]]
        lines = [f"**Pending ({len(pending)}):**"]
        for t in pending:
            lines.append(f"  #{t['id']} — {t['text']}")
        if done:
            lines.append(f"\n**Completed ({len(done)}):**")
            for t in done[-3:]:
                lines.append(f"  ~~#{t['id']} — {t['text']}~~")
        text = "\n".join(lines)
        speech = f"You have {len(pending)} pending tasks, {boss}."
        return {"text": text, "speech": speech, "command": {"action": "todo-list", "value": ""}}
    if action == "clear":
        todo_clear()
        return {"text": f"Cleared your entire todo list, {boss}. Fresh start!", "speech": f"Todo list cleared, {boss}.", "command": {"action": "todo-clear", "value": ""}}
    return None


# Synonym expansion: many intents accept dozens of natural phrasings. Each
# alias is mapped to a normalized word the command router already understands,
# so "close the browser" == "kill firefox" == "exit the web" all work.
COMMAND_SYNONYMS = {
    "launch": "open", "start up": "open", "boot up": "open", "fire up": "open",
    "bring up": "open", "pop open": "open", "run program": "open", "run app": "open",
    "kill": "close", "shut down app": "close", "close down": "close", "exit app": "close",
    "capture screen": "screenshot", "take a screenshot": "screenshot", "snapshot": "screenshot",
    "cap the screen": "screenshot", "screen grab": "screenshot",
    "secure my pc": "lock", "lock workstation": "lock", "lock the computer": "lock",
    "empty bin": "empty trash", "clear the trash": "empty trash", "dump recycle bin": "empty trash",
    "power off": "shutdown", "power down": "shutdown", "switch off pc": "shutdown",
    "turn off the computer": "shutdown", "reboot the pc": "restart", "reset the pc": "restart",
    "make pc sleep": "sleep", "sleep mode": "sleep", "put pc to sleep": "sleep",
    "minimise all": "minimize all", "minimize everything": "minimize all", "show my desktop": "minimize all",
    "terminal window": "terminal", "open command prompt": "terminal", "launch cmd": "terminal",
    "whats on clipboard": "clipboard", "read clipboard": "clipboard", "clipboard contents": "clipboard",
    "lower volume": "volume down", "turn volume down": "volume down", "quieter": "volume down",
    "raise volume": "volume up", "turn volume up": "volume up", "louder": "volume up",
    "silence my pc": "mute", "mute audio": "mute", "turn off sound": "mute",
    "turn on sound": "unmute", "restore audio": "unmute", "unmute audio": "unmute",
    "play music": "media play", "pause playback": "media pause", "next song": "media next",
    "previous song": "media previous", "skip track": "media next", "shuffle": "media next",
    "increase brightness": "brightness up", "brighter": "brightness up", "make screen brighter": "brightness up",
    "decrease brightness": "brightness down", "dimmer": "brightness down", "make screen dimmer": "brightness down",
    "wifi status": "wifi", "network status": "wifi", "connected network": "wifi",
    "file manager": "file", "open files": "file", "open file explorer": "file",
    "note": "notepad", "open notes": "notepad", "txtpad": "notepad",
    "calculator app": "calculator", "run calculator": "calculator", "open calc": "calculator",
    "launch browser": "chrome", "open web browser": "chrome", "open internet": "chrome",
    "open editor": "vscode", "launch vscode": "vscode", "code editor": "vscode",
    "open spotify": "spotify", "launch music": "spotify",
}

def _expand_synonyms(lo: str) -> str:
    """Replace common command aliases with canonical router words so the same
    intent is recognized no matter how the user phrases it."""
    out = lo
    for alias, canonical in COMMAND_SYNONYMS.items():
        out = out.replace(f" {alias} ", f" {canonical} ")
        out = out.replace(f" {alias}.", f" {canonical}.")
        out = out.replace(f" {alias},", f" {canonical},")
    out = re.sub(r"\s+", " ", out).strip()
    return out


LEARNED_ALIASES_FILE = DATA_DIR / "learned_aliases.json"

def _match_learned_alias(lo: str):
    """Check the learned-alias registry (user-taught phrasings -> intents)."""
    try:
        aliases = load_json(LEARNED_ALIASES_FILE, {"aliases": []})["aliases"]
        for a in aliases:
            phrase = str(a.get("phrase") or "").strip().lower()
            intent = a.get("intent")
            if phrase and intent and phrase in lo:
                reply = _apply_learned_intent(intent, boss="Boss")
                if reply:
                    return reply
    except Exception:
        pass
    return None


def _apply_learned_intent(intent: dict, boss: str):
    """Execute an intent dict learned at runtime (action + value)."""
    action = str(intent.get("action") or "")
    value = intent.get("value", "")
    try:
        if action in ("open-app", "open-chrome"):
            return {"text": f"Opening **{value}**, {boss}!", "speech": f"Opening {value}, {boss}.", "command": {"action": action, "value": value}}
        if action == "close-app":
            return {"text": f"Closing **{value}**, {boss}!", "speech": f"Closing {value}, {boss}.", "command": {"action": action, "value": value}}
        if action == "screenshot":
            return {"text": f"Taking screenshot, {boss}!", "speech": "Taking screenshot.", "command": {"action": "screenshot", "value": ""}}
        if action == "volume":
            return {"text": f"Volume set to {value}%, {boss}!", "speech": f"Volume set to {value} percent.", "command": {"action": "volume", "value": value}}
        if action in ("volume-up", "volume-down", "mute", "unmute"):
            return {"text": f"Volume adjusted, {boss}!", "speech": f"Volume adjusted.", "command": {"action": action, "value": value}}
        if action == "timer":
            return {"text": f"Timer set, {boss}!", "speech": f"Timer set, {boss}.", "command": {"action": "timer", "value": value}}
        if action in ("lock", "empty-trash", "sleep", "restart", "shutdown", "minimize-all", "terminal", "wifi"):
            return {"text": f"Done, {boss}!", "speech": "Done.", "command": {"action": action, "value": value}}
        if action == "media":
            return {"text": f"Media {value}, {boss}!", "speech": f"Media {value}.", "command": {"action": "media", "value": value}}
    except Exception:
        pass
    return None


# =====================================================================
# MULTI-STEP AUTONOMOUS TASK ENGINE
# "open chrome, then open whatsapp web and install the pdf sent by papa"
# is decomposed into ordered, fully-automatic sub-commands.
# =====================================================================
_SEQ_GUARD = threading.local()

_SEQ_VERBS = ("open ", "launch ", "start ", "close ", "quit ", "kill ", "stop ",
              "play ", "pause ", "resume ", "send ", "type ", "search ", "google ",
              "look up ", "take a ", "press ", "set ", "turn ", "switch ", "lock ",
              "shutdown ", "shut down ", "restart ", "purge ", "empty ", "mute ",
              "unmute ", "volume ", "brightness ", "read ", "check ", "show ",
              "install ", "download ", "find ", "activate ", "scan ", "answer ",
              "reply ", "turn on ", "turn off ", "wake ")


def _has_seq_verb(text: str) -> bool:
    t = " " + text.lower().strip() + " "
    return any(v in t for v in _SEQ_VERBS)


def _seq_split_segment(seg: str):
    """Within one strong-connector chunk, also split on ' and ' when every
    sub-segment is command-shaped (every piece starts with an action verb)."""
    sub = [s.strip() for s in re.split(r"\s+and\s+", seg) if s.strip()]
    if len(sub) > 1 and all(_has_seq_verb(s) for s in sub):
        return sub
    return [seg]


def _split_command_steps(lo: str):
    """Decompose a multi-action utterance into an ordered list of steps,
    or return None when it is a single intent."""
    parts = re.split(r"\s*;\s*|\s+(?:and\s+)?then\s+|\s+after\s+that\s+|\s+afterwards\s+|\s+after\s+which\s+|\s+,\s+then\s+|\s+,\s*(?:and\s+)?then\s+", lo)
    out = []
    for p in parts:
        p = p.strip().strip("., ")
        if not p:
            continue
        out.extend(_seq_split_segment(p))
    out = [x for x in out if x.strip()]
    if len(out) < 2:
        return None
    if sum(1 for x in out if _has_seq_verb(x)) < 2:
        return None
    return out


def local_command_router(msg):
    """Fast, case-insensitive local intent routing that runs BEFORE the LLM so
    todo / system actions / mode switches always work instantly and deterministically.
    Returns a reply dict, or None if the message should go to the LLM."""
    lo = _normalize_utterance(msg)
    mode = get_mode()
    mp = MODE_PROFILES[mode]
    boss = mp["boss"]
    lo = _expand_synonyms(lo)

    # Mutli-step decomposition — runs first so "then / after that / and" chains
    # are executed server-side as an ordered, fully-automatic sequence.
    if not getattr(_SEQ_GUARD, "active", False):
        steps = _split_command_steps(lo)
        if steps is not None and len(steps) >= 2:
            sub_cmds = []
            labels = []
            for s in steps:
                _SEQ_GUARD.active = True
                try:
                    r = local_command_router(s)
                finally:
                    _SEQ_GUARD.active = False
                if r and r.get("command", {}).get("action"):
                    sub_cmds.append(r["command"])
                    labels.append(re.sub(r"<[^>]+>", "", r.get("text", s))[:90])
                else:
                    sub_cmds.append({"action": "pdf-recent", "value": ""})
                    labels.append("fetch latest document")
            real_actions = [c.get("action", "") for c in sub_cmds if c.get("action")]
            if len(real_actions) >= 2:
                plan = "  →  ".join(labels[:6])
                return {
                    "text": f"Executing **{len(real_actions)} steps** in order, {boss}:\n{plan}",
                    "speech": f"Executing {len(real_actions)} steps in order.",
                    "command": {"action": "run-sequence", "value": {"steps": sub_cmds}},
                }

    # Learned aliases: previously-taught custom phrasings map straight to intents.
    learned = _match_learned_alias(lo)
    if learned:
        return learned

    # MODE SWITCH: "switch to jarvis", "go ultron", "activate friday", "be jarvis"
    m = re.search(r"(?:switch|change|go|activate|become|set|start|enter|use)\s+(?:to\s+|to\s+the\s+|into\s+)?(friday|jarvis|ultron)", lo)
    if m:
        target = m.group(1)
        set_mode(target)
        tmp = MODE_PROFILES[target]
        line = (f"Mode switched to **{target.upper()}**. All systems green. "
                f"Here I am, {target.upper()} mode.")
        return {"text": line, "speech": line, "command": {"action": "mode", "value": target}}

    # TODO: add/remove/edit/complete/list always local
    res = handle_todo_intent(lo, boss)
    if res:
        return res

    # RECENT DOCUMENT: "install the pdf sent by papa", "open the latest pdf",
    # "read the file papa sent", "get the pdf from whatsapp".
    if any(w in lo for w in ["the pdf", "a pdf", "latest pdf", "recent pdf", "pdf sent", "pdf from",
                             "document sent", "file sent", "install the pdf", "install the file",
                             "the document from", "the file from", "whatsapp pdf", "pdf whatsapp"]):
        return {"text": f"On it, {boss}. I'll grab the latest received PDF and open it.", "speech": "Opening the latest received PDF.", "command": {"action": "open-recent-pdf", "value": ""}}

    # WEB WHATSAPP: "open web whatsapp" / "web whatsapp" phrasings.
    if any(w in lo for w in ["open web whatsapp", "web whatsapp", "open whatsapp web", "launch whatsapp web"]):
        return {"text": f"Opening WhatsApp, {boss}!", "speech": "Opening WhatsApp.", "command": {"action": "whatsapp-open", "value": ""}}

    # MEMORY VAULT: "remember X", "save a memory", "store that X", "don't forget X",
    # "note this down", "save X to vault". Fully local so memory works offline.
    vmem = re.search(r"(?:remember|memorize|store|save|note(?: it)? down|put in memory|keep in mind)\s+(?:that\s+|this\s+|the fact that\s+)?(.+)$", lo)
    if not vmem:
        vmem = re.search(r"(?:remember|memorize|note|store|save)\s+(?:a\s+)?(?:memory|note|fact|item)\s*[:\-]\s*(.+)$", lo)
    if not vmem:
        vmem = re.search(r"(?:don'?t\s+forget|do not forget)\s+(?:(?:to|about|that)\s+)?(.+)$", lo)
    if vmem:
        note = vmem.group(1).strip(" :,.;")
        note = re.sub(r"\s+(?:in|to|into)\s+(?:my\s+)?(?:memory|vault|notes|brain)\s*$", "", note).strip()
        if note:
            return {"text": f"Saved to the memory vault: **{note}**, {boss}.", "speech": f"Saved to memory: {note}.", "command": {"action": "vault-save", "value": {"text": note}}}

    # APP INTEGRATIONS (Spotify / Telegram / WhatsApp / Discord / VS Code / Chrome deep)
    # run BEFORE generic "open <app>" and master-volume handlers so integrations win.
    def spotify_running_now() -> bool:
        try:
            import app_integrations
            return app_integrations.spotify_running()
        except Exception:
            return False
    if any(w in lo for w in ["ring my phone", "call my phone", "buzz my phone", "ring the phone", "call the phone"]):
        return {"text": f"Ringing your phone, {boss}!", "speech": "Ringing your phone.", "command": {"action": "phone-ring", "value": ""}}
    m = re.search(r"(?:play|put on)\s+(.+?)\s+(?:on|in)\s+spotify\b", lo)
    if m:
        q = m.group(1).strip()
        if not spotify_running_now():
            return {"text": f"Spotify isn't running, {boss}. Say **open spotify** first, then I can play {q} for you.", "speech": f"Spotify isn't running. Say open spotify first.", "command": {"action": "open-app", "value": "spotify"}}
        return {"text": f"Playing **{q}** on Spotify, {boss}!", "speech": f"Playing {q} on Spotify.", "command": {"action": "spotify-search", "value": q}}
    if ("what song" in lo or "what's playing" in lo or "now playing" in lo or "currently playing" in lo) and "spotify" in lo:
        return {"text": f"Checking what's on Spotify, {boss}!", "speech": "Checking Spotify."}
    if any(w in lo for w in ["spotify next", "next on spotify"]):
        if not spotify_running_now():
            return {"text": f"Spotify isn't running, {boss}. Say **open spotify** first.", "speech": "Spotify isn't running.", "command": {"action": "open-app", "value": "spotify"}}
        return {"text": f"Next on Spotify, {boss}!", "speech": "Next track on Spotify.", "command": {"action": "spotify-action", "value": "next"}}
    if any(w in lo for w in ["spotify previous", "previous on spotify", "back on spotify"]):
        if not spotify_running_now():
            return {"text": f"Spotify isn't running, {boss}. Say **open spotify** first.", "speech": "Spotify isn't running.", "command": {"action": "open-app", "value": "spotify"}}
        return {"text": f"Going back, {boss}!", "speech": "Previous track.", "command": {"action": "spotify-action", "value": "previous"}}
    if any(w in lo for w in ["pause spotify", "pause the music", "pause music", "pause the song", "spotify pause", "stop spotify", "stop the music", "stop music", "stop the song"]):
        if not spotify_running_now():
            return {"text": f"Spotify isn't running, {boss}. Say **open spotify** first.", "speech": "Spotify isn't running.", "command": {"action": "open-app", "value": "spotify"}}
        return {"text": f"Pausing audio on Spotify, {boss}!", "speech": "Pausing Spotify.", "command": {"action": "spotify-action", "value": "pause"}}
    if any(w in lo for w in ["resume spotify", "resume the music", "resume music", "resume the song", "continue spotify", "play the music", "unpause"]):
        if not spotify_running_now():
            return {"text": f"Spotify isn't running, {boss}. Say **open spotify** first.", "speech": "Spotify isn't running.", "command": {"action": "open-app", "value": "spotify"}}
        return {"text": f"Resuming playback, {boss}!", "speech": "Resuming Spotify.", "command": {"action": "spotify-action", "value": "play"}}
    if any(w in lo for w in ["open spotify", "open spotify app", "launch spotify"]):
        return {"text": f"Opening Spotify, {boss}!", "speech": "Opening Spotify.", "command": {"action": "open-app", "value": "spotify"}}
    m = re.search(r"(?:send|message|text)\s+(.+?)\s+to\s+(.+?)\s+(?:on|via)\s+(telegram|whatsapp|discord|sms|text message)\b(?:\s*[:,-]\s*(.*))?$", lo)
    if not m:
        m = re.search(r"(?:send|message|text)\s+(.+?)\s+(?:on|via)\s+(telegram|whatsapp|discord|sms|text message)\b\s*[:,-]\s*(.+)$", lo)
    if m:
        groups = m.groups()
        if len(groups) == 4:
            message, contact, platform_name, extra = groups
            if not message or not message.strip():
                message = extra or ""
            elif not message.strip():
                message = extra or ""
            message = (message.strip(" :,-")) if message else ""
        else:
            contact, platform_name, message = groups
            message = (message or "").strip()
        if not message or not contact:
            return {"text": f"What should I send {contact or 'them'} on {platform_name}?", "speech": "What should I send?"}
        if platform_name == "telegram":
            return {"text": f"Sending to **{contact.strip()}** on Telegram, {boss}!", "speech": f"Sending to {contact.strip()} on Telegram.", "command": {"action": "telegram-send", "value": f"{contact.strip()}|{message}"}}
        if platform_name == "whatsapp":
            return {"text": f"Opening WhatsApp for **{contact.strip()}**, {boss}!", "speech": "Opening WhatsApp Web.", "command": {"action": "whatsapp-open", "value": ""}}
        if platform_name in ("sms", "text message"):
            return {"text": f"Preparing SMS for **{contact.strip()}** on your phone, {boss}!", "speech": f"Preparing SMS for {contact.strip()} on your phone.", "command": {"action": "phone-command", "value": {"action": "sms", "value": {"number": contact.strip(), "body": message}}}}
        return {"text": f"Opening Discord, {boss}!", "speech": "Opening Discord.", "command": {"action": "discord-open", "value": ""}}
    if any(w in lo for w in ["open whatsapp", "launch whatsapp", "whatsapp web"]):
        return {"text": f"Opening WhatsApp, {boss}!", "speech": "Opening WhatsApp.", "command": {"action": "whatsapp-open", "value": ""}}
    if any(w in lo for w in ["open discord", "launch discord"]):
        return {"text": f"Opening Discord, {boss}!", "speech": "Opening Discord.", "command": {"action": "discord-open", "value": ""}}
    m = re.search(r"(?:open|crack open|start coding in)\s+(?:project|the project)\s*[ ]?([a-zA-Z0-9_\- ]+)", lo)
    if m:
        proj = m.group(1).strip()
        return {"text": f"Opening project **{proj}**, {boss}!", "speech": f"Opening project {proj}.", "command": {"action": "open-project", "value": proj}}
    m = re.search(r"(?:open|start)\s+(?:a\s+|the\s+)?terminal\s+(?:in|at)\s+([a-zA-Z0-9_\- ]+)", lo)
    if m:
        proj = m.group(1).strip()
        return {"text": f"Terminal at **{proj}**, {boss}!", "speech": f"Opening terminal in {proj}.", "command": {"action": "terminal-project", "value": proj}}
    m = re.search(r"(?:focus on|focus|bring up|switch to window|focus window)\s+(?:the\s+|window\s+)?([a-zA-Z0-9 _\-]{2,})$", lo)
    if m and not any(w in lo for w in ["focus mode", "show me", "show the", "focus on the weather", "focus on the system", "focus on the music"]):
        app = m.group(1).strip()
        return {"text": f"Focusing **{app}**, {boss}!", "speech": f"Focusing {app}.", "command": {"action": "focus-window", "value": app}}
    m = re.search(r"(?:set|change)\s+(.+?)\s*(?:app\x20volume|volume)\s+(?:to\s+|at\s+)?(\d+)", lo)
    if m and "app volume" in lo:
        appn = m.group(1).strip(); lev = m.group(2)
        return {"text": f"Setting {appn} volume to {lev}%, {boss}!", "speech": f"{appn} volume to {lev} percent.", "command": {"action": "app-volume", "value": {"app": appn, "level": int(lev)}}}
    m = re.search(r"(?:what'?s|check|show|tell me)\s+(?:the\s+)?([a-zA-Z0-9 _\-]{2,30})\s+(?:app\s+)?volume", lo)
    if m and "volume" in lo:
        appn = m.group(1).strip()
        return {"text": f"Checking {appn} volume, {boss}!", "speech": f"Checking {appn} volume.", "command": {"action": "app-volume", "value": {"app": appn}}}
    if any(w in lo for w in ["what apps are open", "which apps are open", "list open apps", "what's open", "open applications", "running apps"]):
        return {"text": f"Scanning running apps, {boss}!", "speech": "Scanning running apps.", "command": {"action": "list-open-apps", "value": ""}}
    m = re.search(r"(?:open|launch|start|run)\s+(.+)", lo)
    if m:
        app_name = m.group(1).strip()
        if "." in app_name or any(w in app_name for w in ["website", "site", "url", "page"]):
            url = app_name if app_name.startswith("http") else "https://" + app_name
            act = {"action": "open-chrome", "value": url}
            return {"text": f"Opening **{url}**, {boss}!", "speech": f"Opening {url}, {boss}.", "command": act}
        act = {"action": "open-app", "value": app_name}
        return {"text": f"Opening **{app_name}**, {boss}!", "speech": f"Opening {app_name}, {boss}.", "command": act}
    m = re.search(r"(?:close|quit|exit|kill|stop)\s+(.+)", lo)
    if m:
        act = {"action": "close-app", "value": m.group(1).strip()}
        return {"text": f"Closing **{m.group(1).strip()}**, {boss}!", "speech": f"Closing {m.group(1).strip()}, {boss}.", "command": act}
    m = re.search(r"(\d+)\s*(minute|min|second|sec|hour|hr)", lo)
    if any(w in lo for w in ["set timer", "timer for", "set alarm"]) and m:
        val = int(m.group(1)); unit = m.group(2).lower()
        secs = val * 3600 if "hour" in unit or "hr" in unit else val * 60 if "minute" in unit or "min" in unit else val
        unit_label = unit + ("s" if val > 1 and not unit.endswith("s") else "")
        return {"text": f"Timer set for {val} {unit_label}, {boss}!", "speech": f"Timer for {val} {unit_label}, {boss}.", "command": {"action": "timer", "value": {"seconds": secs}}}
    if any(w in lo for w in ["take screenshot", "screenshot", "screen capture"]):
        return {"text": f"Taking screenshot, {boss}!", "speech": "Taking screenshot.", "command": {"action": "screenshot", "value": ""}}
    if any(w in lo for w in ["lock my computer", "lock pc", "lock screen"]):
        return {"text": f"Locking PC, {boss}!", "speech": "Locking PC.", "command": {"action": "lock", "value": ""}}
    if any(w in lo for w in ["empty trash", "clear recycle bin"]):
        return {"text": f"Emptying recycle bin, {boss}!", "speech": "Emptying recycle bin.", "command": {"action": "empty-trash", "value": ""}}
    if any(w in lo for w in ["shut down", "shutdown", "turn off"]):
        return {"text": f"Shutting down in 60s, {boss}!", "speech": "Shutting down.", "command": {"action": "shutdown", "value": ""}}
    if any(w in lo for w in ["restart", "reboot"]):
        return {"text": f"Restarting in 60s, {boss}!", "speech": "Restarting.", "command": {"action": "restart", "value": ""}}
    if any(w in lo for w in ["sleep", "suspend", "hibernate"]):
        return {"text": f"Going to sleep, {boss}!", "speech": "Going to sleep.", "command": {"action": "sleep", "value": ""}}
    if any(w in lo for w in ["minimize all", "show desktop"]):
        return {"text": f"Minimizing all, {boss}!", "speech": "Minimizing.", "command": {"action": "minimize-all", "value": ""}}
    if any(w in lo for w in ["open terminal", "launch terminal", "open cmd"]):
        return {"text": f"Opening terminal, {boss}!", "speech": "Opening terminal.", "command": {"action": "terminal", "value": ""}}
    if any(w in lo for w in ["clipboard", "what's on my clipboard"]):
        return {"text": f"Reading clipboard, {boss}!", "speech": "Reading clipboard.", "command": {"action": "clipboard-read", "value": ""}}
    m = re.search(r"(?:set|turn|adjust)\s*.*?volume\s+(?:to|at)?\s*(\d+)", lo)
    if m:
        return {"text": f"Volume set to {m.group(1)}%, {boss}!", "speech": f"Volume set to {m.group(1)} percent.", "command": {"action": "volume", "value": m.group(1)}}
    m = re.search(r"(?:^|\s)volume\s+(?:to|at)?\s*(\d+)", lo)
    if m:
        return {"text": f"Volume set to {m.group(1)}%, {boss}!", "speech": f"Volume set to {m.group(1)} percent.", "command": {"action": "volume", "value": m.group(1)}}
    if any(w in lo for w in ["purge ram", "clean ram", "free up ram", "clear ram", "clear memory"]):
        return {"text": f"Cleaning up memory, {boss}!", "speech": "Cleaning up memory.", "command": {"action": "purge-ram", "value": ""}}
    if any(w in lo for w in ["read my emails", "read emails", "check emails", "check my email", "read email inbox", "show my emails", "show emails"]):
        return {"text": "Opening your emails, Boss!", "speech": "Opening your emails.", "command": {"action": "email-read", "value": ""}}
    if any(w in lo for w in ["wake mac display", "wake display", "wake the display", "wake screen", "turn on display"]):
        return {"text": "Waking the display, Boss!", "speech": "Waking the display.", "command": {"action": "wake-display", "value": ""}}
    m = re.search(r"(?:take|make|add|save|write)\s+a?\s*(?:note|notepad)(?:\s*(?:that|saying|for|:|-)\s*(.+))?(?:\s*(?:in|to|into)\s+(?:my\s+|the\s+)?(?:memory|vault|notes|brain))?$", lo)
    if m:
        note = (m.group(1) or "").strip()
        note = re.sub(r"\s+(?:in|to|into)\s+(?:my\s+)?(?:memory|vault|notes|brain)\s*$", "", note).strip()
        if note:
            return {"text": f"Saved to the memory vault: **{note}**, {boss}.", "speech": f"Saved to memory: {note}.", "command": {"action": "vault-save", "value": {"text": note}}}
        else:
            return {"text": "Ready for your note, Boss. Tell me what to write after 'note'.", "speech": "I'm ready for your note.", "command": {"action": "note-prompt", "value": ""}}
    if any(w in lo for w in ["tell me a joke", "tell me a funny joke", "crack a joke", "give me a joke"]):
        _jokes = [
            ("Why don't scientists trust atoms? Because they make up everything!", "Why don't scientists trust atoms? Because they make up everything!"),
            ("Why did the scarecrow win an award? Because he was outstanding in his field!", "Why did the scarecrow win an award? Because he was outstanding in his field!"),
            ("I told my computer I needed a break, and now it won't stop sending me KitKat ads.", "I told my computer I needed a break, and now it won't stop sending me KitKat ads."),
            ("Why do programmers prefer dark mode? Because light attracts bugs!", "Why do programmers prefer dark mode? Because light attracts bugs!"),
            ("I would tell you a UDP joke, but you might not get it.", "I would tell you a UDP joke, but you might not get it."),
        ]
        import random as _rnd
        _j = _rnd.choice(_jokes)
        return {"text": _j[0], "speech": _j[1]}
    if any(w in lo for w in ["mute", "volume mute"]):
        return {"text": f"Muted, {boss}.", "speech": "Muted.", "command": {"action": "volume", "value": "mute"}}
    if any(w in lo for w in ["unmute", "unmuted"]):
        return {"text": f"Unmuted, {boss}.", "speech": "Unmuted.", "command": {"action": "volume", "value": "unmute"}}
    if any(w in lo for w in ["volume up", "louder", "increase volume"]):
        return {"text": f"Volume up, {boss}!", "speech": "Volume up.", "command": {"action": "volume-up", "value": ""}}
    if any(w in lo for w in ["volume down", "quieter", "lower volume"]):
        return {"text": f"Volume down, {boss}!", "speech": "Volume down.", "command": {"action": "volume-down", "value": ""}}
    if any(w in lo for w in ["media play", "play pause", "resume music"]):
        return {"text": f"Playing, {boss}!", "speech": "Playing.", "command": {"action": "media", "value": "playpause"}}
    if any(w in lo for w in ["media pause", "pause music", "stop music"]):
        return {"text": f"Paused, {boss}!", "speech": "Paused.", "command": {"action": "media", "value": "pause"}}
    if any(w in lo for w in ["media next", "next song", "next track", "skip track"]):
        return {"text": f"Skipping to next, {boss}!", "speech": "Next track.", "command": {"action": "media", "value": "next"}}
    if any(w in lo for w in ["media previous", "previous song", "previous track", "back track"]):
        return {"text": f"Going back, {boss}!", "speech": "Previous track.", "command": {"action": "media", "value": "previous"}}
    if any(w in lo for w in ["brightness up", "increase brightness", "brighter"]):
        return {"text": f"Brighter, {boss}!", "speech": "Increasing brightness.", "command": {"action": "brightness", "value": "up"}}
    if any(w in lo for w in ["brightness down", "decrease brightness", "dimmer"]):
        return {"text": f"Dimmer, {boss}!", "speech": "Decreasing brightness.", "command": {"action": "brightness", "value": "down"}}
    m = re.search(r"set brightness (?:to |at )?(\d+)", lo)
    if m:
        pct = min(100, max(0, int(m.group(1))))
        return {"text": f"Brightness set to {pct}%, {boss}!", "speech": f"Brightness set to {pct} percent.", "command": {"action": "brightness", "value": str(pct)}}

    # CHROME DEEP CONTROL (CDP bridge)
    if any(w in lo for w in ["list tabs", "what tabs", "open tabs", "chrome tabs", "show tabs"]):
        return {"text": f"Reading Chrome tabs, {boss}!", "speech": "Reading Chrome tabs.", "command": {"action": "chrome-list", "value": ""}}
    if any(w in lo for w in ["close tab chrome", "close chrome tab", "close the chrome tab"]):
        return {"text": f"Closing active tab, {boss}!", "speech": "Closing tab.", "command": {"action": "chrome-close", "value": "chrome"}}
    m = re.search(r"(?:close|shut)\s+(?:the\s+)?tab\s+(?:for\s+|named\s+)?(.+)$", lo)
    if m:
        targ = m.group(1).strip()
        return {"text": f"Closing tab {targ}, {boss}!", "speech": f"Closing tab {targ}.", "command": {"action": "chrome-close", "value": targ}}
    m = re.search(r"(?:open in|open a chrome tab|new chrome tab|chrome tab|open tab)\s+(?:for\s+|to\s+)?(.+)$", lo)
    if m:
        targ = m.group(1).strip()
        return {"text": f"Opening **{targ}** in Chrome, {boss}!", "speech": f"Opening {targ} in Chrome.", "command": {"action": "chrome-open", "value": targ}}
    m = re.search(r"(?:switch to|activate|bring up)\s+(?:the\s+|tab\s+)?(?:chrome\s+)?tab\s+(.+)$", lo)
    if m and "tab" in lo:
        targ = m.group(1).strip()
        return {"text": f"Switching to tab **{targ}**, {boss}!", "speech": f"Switching to tab {targ}.", "command": {"action": "chrome-activate", "value": targ}}
    m = re.search(r"(?:play|search)\s+(.+?)\s+(?:on|in)\s+youtube\b", lo)
    if m:
        q = m.group(1).strip()
        return {"text": f"Playing **{q}** on YouTube, {boss}!", "speech": f"Playing {q} on YouTube.", "command": {"action": "chrome-youtube", "value": q}}
    if any(w in lo for w in ["chrome back", "go back in chrome", "back in chrome"]):
        return {"text": f"Going back, {boss}!", "speech": "Going back in Chrome.", "command": {"action": "chrome-back", "value": ""}}
    if any(w in lo for w in ["chrome forward", "go forward in chrome", "forward in chrome"]):
        return {"text": f"Going forward, {boss}!", "speech": "Going forward in Chrome.", "command": {"action": "chrome-forward", "value": ""}}
    if any(w in lo for w in ["refresh chrome", "reload chrome", "refresh the chrome tab"]):
        return {"text": f"Refreshing Chrome, {boss}!", "speech": "Refreshing Chrome.", "command": {"action": "chrome-reload", "value": ""}}
    if any(w in lo for w in ["chrome fullscreen", "fullscreen chrome", "full screen chrome"]):
        return {"text": f"Fullscreen Chrome, {boss}!", "speech": "Fullscreen Chrome.", "command": {"action": "chrome-fullscreen", "value": ""}}

    # BROWSER / SEARCH
    m = re.search(r"(?:play|search for|search|find)\s+(.+?)\s+(?:on|in)\s+youtube\b", lo)
    if m:
        q = m.group(1).strip()
        return {"text": f"Playing **{q}** on YouTube, {boss}!", "speech": f"Playing {q} on YouTube.", "command": {"action": "browser-search", "value": f"youtube {q}"}}
    m = re.search(r"(?:open|go to|launch)\s+(?:on|in)\s+youtube\b|(?:^|\s)youtube\s+(.+)", lo)
    if m:
        q = (m.group(1) or "").strip()
        q = re.sub(r"^(and\s+)?(?:play|search|find)\s+", "", q)
        return {"text": f"Opening YouTube, {boss}!", "speech": "Opening YouTube.", "command": {"action": "browser-search", "value": f"youtube {q}".strip()}}
    m = re.search(r"(?:search for|search|google|look up|find)\s+(.+)", lo)
    if m:
        q = m.group(1).strip()
        if q and not any(x in lo for x in ["search for my ", "search files", "search the disk"]):
            return {"text": f"Searching the web for **{q}**, {boss}!", "speech": f"Searching for {q}.", "command": {"action": "browser-search", "value": q}}
    if any(w in lo for w in ["new tab", "open new tab", "open a new tab"]):
        return {"text": f"New tab, {boss}!", "speech": "New tab.", "command": {"action": "browser-new-tab", "value": ""}}
    if any(w in lo for w in ["refresh page", "reload page", "refresh the page", "reload the page"]):
        return {"text": f"Refreshing, {boss}!", "speech": "Refreshing.", "command": {"action": "browser-refresh", "value": ""}}
    if any(w in lo for w in ["go back", "browser back", "previous page"]):
        return {"text": f"Going back, {boss}!", "speech": "Going back.", "command": {"action": "browser-back", "value": ""}}
    if any(w in lo for w in ["go forward", "browser forward", "next page"]):
        return {"text": f"Going forward, {boss}!", "speech": "Going forward.", "command": {"action": "browser-forward", "value": ""}}
    if any(w in lo for w in ["fullscreen", "full screen"]):
        return {"text": f"Fullscreen, {boss}!", "speech": "Fullscreen.", "command": {"action": "browser-fullscreen", "value": ""}}
    if any(w in lo for w in ["close tab", "close this tab"]):
        return {"text": f"Closing tab, {boss}!", "speech": "Closing tab.", "command": {"action": "browser-close-tab", "value": ""}}

    # KEYBOARD TYPING (full slash-command style PC control)
    m = re.search(r"(?:type|type out|keyboard type)\s+(.+)", lo)
    if m:
        txt = m.group(1).strip()
        return {"text": f"Typing: **{txt[:60]}**", "speech": "Typing it out.", "command": {"action": "type-text", "value": txt}}
    if any(w in lo for w in ["clipboard", "copy that", "copied to clipboard"]):
        return {"text": f"Reading clipboard, {boss}!", "speech": "Reading clipboard.", "command": {"action": "clipboard-read", "value": ""}}
    if any(w in lo for w in ["open task manager", "task manager", "show task manager"]):
        return {"text": f"Opening Task Manager, {boss}!", "speech": "Opening Task Manager.", "command": {"action": "task-manager", "value": ""}}

    # DETERMINISTIC MATH
    if re.match(r"^[\d\s\+\-\*\/\%\.\(\)x]+$", lo):
        try:
            expr = lo.replace("x", "*").replace("^", "**").replace("%", "/100.0") if "%" in lo else lo.replace("^", "**")
            result = eval(expr)
            return {"text": f"The answer is {result}, {boss}!", "speech": f"The answer is {result}, {boss}."}
        except Exception:
            pass

    # DETERMINISTIC TIME / DATE
    now = datetime.datetime.now()
    for pattern, resp in [
        (["what time", "current time", "time now", "time"],
         {"text": f"It's **{now.strftime('%I:%M %p')}**, {boss}!", "speech": f"It's {now.strftime('%I:%M %p')}, {boss}."}),
        (["what day", "today's date", "what's the date", "date today"],
         {"text": f"Today is **{now.strftime('%A, %B %d, %Y')}**, {boss}!", "speech": f"Today is {now.strftime('%A, %B %d, %Y')}, {boss}."}),
        (["what month", "current month"],
         {"text": f"It's **{now.strftime('%B %Y')}**, {boss}!", "speech": f"It's {now.strftime('%B %Y')}, {boss}."}),
        (["what year", "current year"],
         {"text": f"We're in **{now.year}**, {boss}!", "speech": f"The year is {now.year}, {boss}."}),
    ]:
        if any(w in (" " + lo + " ") for w in pattern):
            return resp

    return None

@app.route("/api/commands/teach", methods=["POST"])
def api_commands_teach():
    """Train JENNY: teach a custom phrase -> command intent mapping.

    Body: {"phrase": "blow up the lights", "action": "volume", "value": "up"}
    Once learned, the phrase works forever (case-insensitive) - the system gets
    smarter about the user's natural language as they use it.
    """
    d = request.get_json(force=True, silent=True) or {}
    phrase = str(d.get("phrase") or "").strip().lower()
    action = str(d.get("action") or "").strip().lower()
    value = d.get("value", "")
    if not phrase or not action:
        return jsonify({"success": False, "error": "phrase and action required"}), 400
    data = load_json(LEARNED_ALIASES_FILE, {"aliases": []})
    aliases = data.setdefault("aliases", [])
    for a in aliases:
        if str(a.get("phrase") or "").lower() == phrase:
            a["intent"] = {"action": action, "value": value}
            a["updated"] = time.time()
            break
    else:
        aliases.append({"phrase": phrase, "intent": {"action": action, "value": value}, "created": time.time()})
    save_json(LEARNED_ALIASES_FILE, data)
    return jsonify({"success": True, "learned": len(aliases), "message": f"Learned: \"{phrase}\" -> {action} {value}."})


@app.route("/api/commands/taught")
def api_commands_taught():
    """List the currently learned (user-taught) command aliases."""
    data = load_json(LEARNED_ALIASES_FILE, {"aliases": []})
    return jsonify({"success": True, "aliases": data.get("aliases", [])})


@app.route("/api/commands/forget", methods=["POST"])
def api_commands_forget():
    """Remove a learned alias by phrase."""
    d = request.get_json(force=True, silent=True) or {}
    phrase = str(d.get("phrase") or "").strip().lower()
    data = load_json(LEARNED_ALIASES_FILE, {"aliases": []})
    data["aliases"] = [a for a in data.get("aliases", []) if str(a.get("phrase") or "").lower() != phrase]
    save_json(LEARNED_ALIASES_FILE, data)
    return jsonify({"success": True, "learned": len(data["aliases"])})

def offline_reply(text):
    lo = text.lower().strip()
    lo_norm = lo.replace("i am", "i'm").replace("i dont", "i don't").replace("i cant", "i can't").replace("dont", "don't").replace("cant", "can't").replace("wont", "won't").replace("isnt", "isn't").replace("arent", "aren't").replace("wasnt", "wasn't").replace("wouldnt", "wouldn't")
    mode = get_mode()
    mp = MODE_PROFILES[mode]
    boss = mp["boss"]
    track_command_stats(text)
    track_context(text)
    mem = _conversation_memory()
    mem_topics = mem.get("topics", "").strip()
    mem_count = int(mem.get("count", 0))

    res = handle_todo_intent(lo, boss)
    if res:
        return res

    for topic_list, responses in OFFLINE_CONVERSATIONS.items():
        for trigger, replies in responses.items():
            if trigger in lo or trigger in lo_norm:
                return {"text": random.choice(replies), "speech": random.choice(replies)}

    if re.match(r"^[\d\s\+\-\*\/\%\.\(\)]+$", lo):
        try:
            result = eval(lo.replace(chr(94), '**'))
            return {"text": f"The answer is {result}, {boss}!", "speech": f"The answer is {result}, {boss}."}
        except:
            pass

    m = re.search(r"convert\s+([\d\.]+)\s+(.+?)\s+(?:to|in)\s+(.+)", lo)
    if m:
        val = float(m.group(1)); from_u = m.group(2).strip(); to_u = m.group(3).strip()
        key = f"{from_u} to {to_u}"
        if key in CONVERSION_TABLE:
            result = CONVERSION_TABLE[key](val)
            return {"text": f"**{val} {from_u}** = **{result} {to_u}**, {boss}!", "speech": f"{val} {from_u} equals {result} {to_u}, {boss}."}

    m = re.search(r"what is (\d+) percent of (\d+)", lo)
    if m:
        result = float(m.group(1)) * float(m.group(2)) / 100
        return {"text": f"**{m.group(1)}%** of **{m.group(2)}** is **{result}**, {boss}!", "speech": f"{m.group(1)} percent of {m.group(2)} is {result}, {boss}."}

    m = re.search(r"(?:is|are)\s+(\d+)\s+(?:a\s+)?prime", lo)
    if m:
        n = int(m.group(1))
        is_prime = n > 1 and all(n % i != 0 for i in range(2, int(n**0.5) + 1))
        return {"text": f"**{n}** {'is' if is_prime else 'is not'} a prime number, {boss}.", "speech": f"{n} {'is' if is_prime else 'is not'} a prime number, {boss}."}

    m = re.search(r"(?:factorial|fact)\s*(?:of\s*)?(\d+)", lo)
    if m:
        n = int(m.group(1))
        if n > 20:
            return {"text": f"That's too large to compute, {boss}!", "speech": "Too large to compute, boss."}
        return {"text": f"**{n}!** = **{math.factorial(n)}**, {boss}!", "speech": f"Factorial of {n} is {math.factorial(n)}, {boss}."}

    m = re.search(r"(?:square root|sqrt)\s*(?:of\s*)?([\d\.]+)", lo)
    if m:
        val = float(m.group(1))
        return {"text": f"The square root of **{val}** is **{round(math.sqrt(val), 4)}**, {boss}!", "speech": f"Square root of {val} is {round(math.sqrt(val), 4)}, {boss}."}

    m = re.search(r"(\d+)\s*(?:squared|\^2|to the power of 2)", lo)
    if m:
        val = int(m.group(1))
        return {"text": f"**{val}**\u00b2 = **{val**2}**, {boss}!", "speech": f"{val} squared is {val**2}, {boss}."}

    m = re.search(r"(\d+)\s*(?:cubed|\^3|to the power of 3)", lo)
    if m:
        val = int(m.group(1))
        return {"text": f"**{val}**\u00b3 = **{val**3}**, {boss}!", "speech": f"{val} cubed is {val**3}, {boss}."}

    m = re.search(r"random(?:\s+number)?\s*(?:between\s+)?(\d+)\s*(?:and|to|-)\s*(\d+)", lo)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        result = random.randint(min(a,b), max(a,b))
        return {"text": f"Random number between {a} and {b}: **{result}**, {boss}!", "speech": f"Random number: {result}, {boss}."}

    if any(w in lo for w in ["roll a dice", "roll dice", "dice roll", "roll a die"]):
        return {"text": f"You rolled a **{random.randint(1, 6)}**, {boss}!", "speech": f"You rolled a {random.randint(1, 6)}, {boss}!"}

    if any(w in lo for w in ["flip a coin", "coin flip", "heads or tails"]):
        result = random.choice(["Heads", "Tails"])
        return {"text": f"**{result}**!", "speech": f"{result}!"}

    if any(w in lo for w in ["pick a random color", "random color", "color of the day"]):
        colors = ["Red", "Blue", "Green", "Purple", "Orange", "Gold", "Teal", "Cyan", "Magenta", "Coral", "Indigo", "Turquoise", "Crimson", "Emerald", "Amber"]
        result = random.choice(colors)
        return {"text": f"Today's color: **{result}**, {boss}!", "speech": f"Random color: {result}, {boss}!"}

    if any(w in lo for w in ["generate password", "create password", "new password", "random password"]):
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        pw = ''.join(random.choice(chars) for _ in range(16))
        return {"text": f"Generated password:\n`{pw}`\n\nStay secure, {boss}!", "speech": "Generated a 16-character password for you, boss."}

    if any(w in lo for w in ["generate uuid", "new uuid", "random uuid"]):
        return {"text": f"UUID: `{uuid.uuid4()}`", "speech": "Generated a UUID for you, boss."}

    now = datetime.datetime.now()
    for pattern, resp in [
        (["what time", "current time", "time now"], {"text": f"It's **{now.strftime('%I:%M %p')}**, {boss}!", "speech": f"It's {now.strftime('%I:%M %p')}, {boss}."}),
        (["what day", "today's date", "what's the date"], {"text": f"Today is **{now.strftime('%A, %B %d, %Y')}**, {boss}!", "speech": f"Today is {now.strftime('%A, %B %d, %Y')}, {boss}."}),
        (["what month", "current month"], {"text": f"It's **{now.strftime('%B %Y')}**, {boss}!", "speech": f"It's {now.strftime('%B %Y')}, {boss}."}),
        (["what year", "current year"], {"text": f"We're in **{now.year}**, {boss}!", "speech": f"The year is {now.year}, {boss}."}),
        (["what week", "week number"], {"text": f"We're in **week {now.isocalendar()[1]}** of {now.year}, {boss}!", "speech": f"Week {now.isocalendar()[1]} of {now.year}, {boss}."}),
        (["leap year", "is it a leap year"], {"text": f"**{now.year}** {'is' if (now.year%4==0 and now.year%100!=0) or (now.year%400==0) else 'is not'} a leap year, {boss}.", "speech": f"{now.year} {'is' if (now.year%4==0 and now.year%100!=0) or (now.year%400==0) else 'is not'} a leap year, {boss}."}),
    ]:
        if any(w in lo for w in pattern):
            return resp

    if "who are you" in lo or "your name" in lo:
        return {"text": f"I'm **{mp['name']}** ({mp['fullName']}), your AI assistant, {boss}! Currently in **{mode.upper()}** mode.", "speech": f"I'm {mp['name']}, your AI assistant, {boss}. Currently in {mode} mode."}
    if "how are you" in lo:
        return {"text": random.choice([f"All systems green, {boss}!", f"Feeling great, {boss}!"]), "speech": "All systems green, boss!"}

    if any(w in lo for w in ["joke", "make me laugh", "something funny"]):
        return {"text": random.choice(OFFLINE_JOKES) + f" {boss}!", "speech": "Here's a joke, " + boss + "."}
    if any(w in lo for w in ["quote", "inspire me", "motivation", "inspirational quote"]):
        return {"text": random.choice(OFFLINE_QUOTES) + f" {boss}!", "speech": "Here's an inspirational quote, " + boss + "."}
    if any(w in lo for w in ["fact", "fun fact", "tell me something", "did you know"]):
        return {"text": random.choice(OFFLINE_FACTS), "speech": "Here's a fun fact, " + boss + "."}
    if any(w in lo for w in ["riddle", "brain teaser", "puzzle"]):
        r = random.choice(OFFLINE_RIDDLES)
        return {"text": f"**Riddle:** {r['q']}\n\n*Ask me for the answer!*", "speech": f"Here's a riddle, {boss}: {r['q']}"}
    if any(w in lo for w in ["answer", "what's the answer"]):
        return {"text": f"Which riddle, {boss}? Ask for a new riddle first!", "speech": f"Which riddle, {boss}?"}

    if "capabil" in lo or "help" in lo or "what can you do" in lo:
        return {"text": f"I can:\n\n**System:** Open/close apps, volume, lock, screenshot, system info\n**Knowledge:** Definitions, conversions, math, trivia\n**Fun:** Jokes, quotes, facts, riddles\n**Info:** Weather, news, crypto\n**Productivity:** Timers, clipboard, file management\n**Chat:** Natural conversation!\n\nMode: **{mode.upper()}**, {boss}!", "speech": f"I can control your system, answer questions, tell jokes, and chat with you, {boss}."}

    if any(w in lo for w in ["hello", "hi ", "hey", "sup", "what's up", "howdy", "greetings"]):
        settings = load_json(DATA_DIR / "settings.json", {})
        greet = (settings.get("greeting") or "").format(mode="online Boss", name="", time=get_time_period())
        if not greet.strip():
            greet = mp["greeting"].format(period=get_time_period())
        return {"text": greet, "speech": greet}
    if any(w in lo for w in ["thank", "thanks", "thx", "ty"]):
        return {"text": random.choice([f"Happy to help, {boss}!", f"Anything for you, {boss}!", f"You're welcome, {boss}!"]), "speech": "Happy to help, boss!"}
    if any(w in lo for w in ["bye", "goodbye", "see you", "later", "cya"]):
        return {"text": mp["farewell"], "speech": mp["farewell"]}
    if any(w in lo for w in ["who made you", "your creator", "who created you", "who built you"]):
        return {"text": f"I was created by **Harshit** (WRECKERKNIGHT) - the Boss himself!", "speech": "I was created by Harshit, WRECKERKNIGHT. Built with Python and Flask."}

    if any(w in lo for w in ["weather", "temperature", "forecast", "is it raining", "today's weather"]):
        settings = load_json(DATA_DIR / "settings.json", {"cityName": "Lucknow"})
        city = settings.get("cityName", "Lucknow")
        w = simulate_weather(city)
        try:
            import re as _re
            mc = _re.search(r"\bweather\s+in\s+([a-zA-Z ]+)", lo)
            if mc:
                city = mc.group(1).strip()
                w = simulate_weather(city)
        except Exception:
            pass
        now = datetime.datetime.now()
        period = "night" if now.hour < 6 else "early morning" if now.hour < 12 else "afternoon" if now.hour < 17 else "evening" if now.hour < 21 else "night"
        return {"text": f"Here's the (offline-simulated) weather for **{city.title()}**: **{w['temp']}°C**, {w['condition']}, feeling {w['feels']}. Low around **{w['low']}°C**, high near **{w['high']}°C**. Humidity **{w['humidity']}%**, wind **{w['wind']}** km/h, and about a **{w['rain_pct']}%** chance of rain this {period}. Take an umbrella or leave it — I've got a read on the sky, {boss}.", "speech": f"Weather in {city}: {w['temp']} degrees, {w['condition']}. Humidity {w['humidity']} percent, wind {w['wind']} kmh, {w['rain_pct']} percent chance of rain. This is a simulated report since I'm offline, boss."}
    if any(w in lo for w in ["news", "headlines", "what's happening"]):
        return {"text": "Fetching latest news!", "speech": "Fetching news.", "command": {"action": "news", "value": ""}}
    if any(w in lo for w in ["crypto", "bitcoin", "ethereum", "btc", "eth", "prices"]):
        return {"text": "Checking crypto prices!", "speech": "Checking crypto.", "command": {"action": "crypto", "value": ""}}
    if any(w in lo for w in ["show bookmarks", "chrome bookmarks", "my bookmarks"]):
        return {"text": "Loading Chrome bookmarks!", "speech": "Loading bookmarks.", "command": {"action": "open-chrome-bookmarks", "value": ""}}

    m = re.search(r"(?:open|launch|start|run)\s+(.+)", lo)
    if m:
        app_name = m.group(1).strip()
        if "chrome" in app_name and "bookmark" in lo:
            return {"text": "Loading Chrome bookmarks!", "speech": "Loading bookmarks.", "command": {"action": "open-chrome-bookmarks", "value": ""}}
        if any(w in app_name for w in ["website", "site", "url", "page"]) or "." in app_name:
            url = app_name if app_name.startswith("http") else "https://" + app_name
            return {"text": f"Opening **{url}**, {boss}!", "speech": f"Opening {url}, {boss}.", "command": {"action": "open-chrome", "value": url}}
        return {"text": f"Opening **{app_name}**, {boss}!", "speech": f"Opening {app_name}, {boss}.", "command": {"action": "open-app", "value": app_name}}

    m = re.search(r"(?:close|quit|exit|kill|stop)\s+(.+)", lo)
    if m:
        return {"text": f"Closing **{m.group(1).strip()}**, {boss}!", "speech": f"Closing {m.group(1).strip()}, {boss}.", "command": {"action": "close-app", "value": m.group(1).strip()}}

    app_map = {
        ("open chrome", "launch chrome"): "chrome",
        ("open edge", "launch edge", "open browser"): "msedge",
        ("open vscode", "open code", "launch vscode"): "code",
        ("open discord", "launch discord"): "discord",
        ("open spotify", "launch spotify"): "spotify",
        ("open word", "launch word"): "winword",
        ("open excel", "launch excel"): "excel",
        ("open powerpoint", "open ppt"): "powerpnt",
        ("open paint", "launch paint"): "mspaint",
        ("open notepad", "launch notepad"): "notepad",
        ("open calculator", "launch calculator", "calc"): "calc",
    }
    for triggers, target in app_map.items():
        if any(w in lo for w in triggers):
            return {"text": f"Opening **{target}**, {boss}!", "speech": f"Opening {target}, {boss}.", "command": {"action": "open-app", "value": target}}

    if any(w in lo for w in ["cpu usage", "cpu info", "processor"]):
        return {"text": f"CPU: **{system_cache['cpu']}%**, {platform.processor() or 'Unknown'}, **{psutil.cpu_count()}** cores, {boss}.", "speech": f"CPU is at {system_cache['cpu']} percent, {boss}."}
    if any(w in lo for w in ["ram usage", "memory info", "memory usage"]):
        return {"text": f"RAM: **{system_cache['ram']}%** used, **{system_cache['ram_used']}/{system_cache['ram_total']} GB**, {boss}.", "speech": f"RAM is {system_cache['ram']} percent, {boss}."}
    if any(w in lo for w in ["battery level", "battery", "battery status"]):
        ch = "charging" if system_cache["charging"] else "on battery"
        return {"text": f"Battery: **{system_cache['battery']}%** ({ch}), {boss}.", "speech": f"Battery at {system_cache['battery']} percent, {ch}, {boss}."}
    if any(w in lo for w in ["disk usage", "storage", "free space"]):
        return {"text": f"Disk: **{system_cache['disk']}%** used, **{system_cache['disk_free']} GB** free of **{system_cache['disk_total']} GB**, {boss}.", "speech": f"Disk is {system_cache['disk']} percent, {boss}."}
    if any(w in lo for w in ["system info", "about my pc", "my system", "computer info"]):
        return {"text": f"OS: **{platform.system()} {platform.release()}**\nCPU: **{platform.processor() or 'Unknown'}**\nRAM: **{system_cache['ram_used']}/{system_cache['ram_total']} GB**\nHostname: **{platform.node()}**\nBattery: **{system_cache['battery']}%**", "speech": f"Running {platform.system()} {platform.release()}."}
    if any(w in lo for w in ["uptime", "how long", "up time"]):
        up = system_cache["uptime"]; hrs, rem = divmod(up, 3600); mins, secs = divmod(rem, 60)
        return {"text": f"Uptime: **{hrs}h {mins}m {secs}s**, {boss}.", "speech": f"Up for {hrs} hours and {mins} minutes, {boss}."}
    if any(w in lo for w in ["hostname", "computer name", "pc name"]):
        return {"text": f"Computer name: **{platform.node()}**, {boss}.", "speech": f"Computer name is {platform.node()}, {boss}."}
    if any(w in lo for w in ["wifi", "network", "internet status"]):
        try:
            r = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            ssid = ""; sig = ""
            for l in r.stdout.split("\n"):
                if "SSID" in l and "BSSID" not in l: ssid = l.split(":", 1)[-1].strip()
                if "Signal" in l: sig = l.split(":", 1)[-1].strip()
            return {"text": f"WiFi: **{ssid}** ({sig}), {boss}.", "speech": f"Connected to {ssid}, {boss}."}
        except:
            return {"text": "Could not retrieve WiFi info.", "speech": "Could not get WiFi info."}
    if any(w in lo for w in ["running processes", "task manager", "what's running"]):
        try:
            r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            procs = []
            for line in r.stdout.strip().split("\n")[:15]:
                parts = line.strip('"').split('","')
                if len(parts) >= 5: procs.append(f"{parts[0]} (PID:{parts[1]})")
            return {"text": "Top processes:\n" + "\n".join(f"- **{p}**" for p in procs), "speech": f"Found {len(procs)} processes, {boss}."}
        except:
            return {"text": "Could not list processes.", "speech": "Could not list processes."}

    if any(w in lo for w in ["what is", "who is", "define", "meaning of", "explain"]):
        if not get_gemini_key():
            words = lo
            for prefix in ["what is", "who is", "define", "meaning of", "explain"]:
                words = words.replace(prefix, "")
            words = words.strip()
            for k, v in KNOWLEDGE_BASE.items():
                if k in words:
                    hook = ""
                    if mem_topics and any(t in mem_topics.split(',') for t in words.split() if len(t) > 3):
                        hook = f" Since we were just touching on {mem_topics}, this ties right in — "
                    reply = f"{hook}{v} Want me to go deeper into {k}, or connect it to something from earlier in our talk, {boss}?"
                    return {"text": reply, "speech": re.sub(r"[#*_`]", "", reply)}
            if words:
                return {"text": f"I'd need internet for **{words}**, {boss}. Try AI, Python, CPU, RAM, encryption offline!", "speech": f"Need internet for that, {boss}. Try tech topics I know offline."}
        return {"text": f"Running offline, {boss}. Set up Gemini API key for detailed answers!", "speech": f"Running offline, {boss}."}

    if any(w in lo for w in ["set timer", "timer for", "set alarm"]):
        m2 = re.search(r"(\d+)\s*(minute|min|second|sec|hour|hr)", lo)
        if m2:
            val = int(m2.group(1)); unit = m2.group(2).lower()
            secs = val * 3600 if "hour" in unit or "hr" in unit else val * 60 if "minute" in unit or "min" in unit else val
            return {"text": f"Timer set for {val} {unit}, {boss}!", "speech": f"Timer for {val} {unit}, {boss}.", "command": {"action": "timer", "value": {"seconds": secs}}}

    if any(w in lo for w in ["take screenshot", "screenshot", "screen capture"]):
        return {"text": f"Taking screenshot, {boss}!", "speech": "Taking screenshot.", "command": {"action": "screenshot", "value": ""}}
    if any(w in lo for w in ["lock my computer", "lock pc", "lock screen"]):
        return {"text": f"Locking PC, {boss}!", "speech": "Locking PC.", "command": {"action": "lock", "value": ""}}
    if any(w in lo for w in ["empty trash", "clear recycle bin"]):
        return {"text": f"Emptying recycle bin, {boss}!", "speech": "Emptying recycle bin.", "command": {"action": "empty-trash", "value": ""}}
    if any(w in lo for w in ["shut down", "shutdown", "turn off"]):
        return {"text": f"Shutting down in 60s, {boss}!", "speech": "Shutting down.", "command": {"action": "shutdown", "value": ""}}
    if any(w in lo for w in ["restart", "reboot"]):
        return {"text": f"Restarting in 60s, {boss}!", "speech": "Restarting.", "command": {"action": "restart", "value": ""}}
    if any(w in lo for w in ["sleep", "suspend", "hibernate"]):
        return {"text": f"Going to sleep, {boss}!", "speech": "Going to sleep.", "command": {"action": "sleep", "value": ""}}
    if any(w in lo for w in ["minimize all", "show desktop"]):
        return {"text": f"Minimizing all, {boss}!", "speech": "Minimizing.", "command": {"action": "minimize-all", "value": ""}}
    if any(w in lo for w in ["open terminal", "launch terminal", "open cmd"]):
        return {"text": f"Opening terminal, {boss}!", "speech": "Opening terminal.", "command": {"action": "terminal", "value": ""}}
    if any(w in lo for w in ["clipboard", "what's on my clipboard"]):
        return {"text": f"Reading clipboard, {boss}!", "speech": "Reading clipboard.", "command": {"action": "clipboard-read", "value": ""}}

    # Fuzzy, typo-tolerant fallback BEFORE the catch-all: match user intent to a
    # known command keyword even when casing/typos/spacing are off, so commands
    # still get understood while the AI API is unreachable.
    fuzzy = _fuzzy_match_command(lo, boss)
    if fuzzy:
        return fuzzy

    # Offline catch-all: acknowledge, name the limitation, and steer to what still works.
    detail = ("I'm in offline mode right now, so I can't reach the online AI brain."
              if not get_gemini_key() else
              "The AI service is temporarily busy, so I'm answering from my built-in offline knowledge.")
    recall = ""
    if mem_topics and mem_count > 2:
        recall = f"\n\nJust to keep us on track — earlier we were talking about *{mem_topics}*. Want to pick any of those back up, {boss}?"
    return {"text": f"{detail}\n\nYou can still ask me to:\n• **Control the PC** — open apps, lock, screenshot, timers, clipboard\n• **Read your system** — CPU, RAM, battery, disk, processes, uptime\n• **Do math** — calculators, conversions, percentages, primes, factorials\n• **Enjoy content** — jokes, quotes, facts, riddles, weather, time\n• **Talk about tech** — AI, Python, CPU, RAM, encryption and more offline{recall}\n\nTry one of those, or ask me about your **Agency OS** / business, {boss}!", "speech": "I can't reach the online AI right now, but I can still control your PC, read your system, do math, tell jokes, and remember what we've been talking about, {boss}."}


_FUZZY_EVALS = {
    "cpu usage": "CPU", "cpu": "CPU", "processor": "CPU",
    "ram usage": "RAM", "memory": "RAM", "memory usage": "RAM",
    "battery": "battery", "battery status": "battery", "battery level": "battery",
    "disk": "disk", "disk usage": "disk", "storage": "disk", "free space": "disk",
    "uptime": "uptime", "wifi": "wifi", "system info": "system-info", "system": "system-info",
}

def _fuzzy_match_command(lo, boss):
    """Rough fuzzy intent match for offline mode: helps when the user types a
    command slightly differently than an exact router phrase (typos, extra
    casing, missing 'the', etc.). Returns a reply dict or None."""
    if not lo or len(lo) < 3:
        return None
    try:
        import difflib
    except Exception:
        return None

    best_ratio = 0.72
    best_key = None
    for key in _FUZZY_EVALS:
        r = difflib.SequenceMatcher(None, lo, key).ratio()
        if r > best_ratio:
            best_ratio = r
            best_key = key
    if not best_key:
        return None
    target = _FUZZY_EVALS[best_key]
    if target == "CPU":
        return {"text": f"CPU: **{system_cache['cpu']}%**, {platform.processor() or 'Unknown'}, **{psutil.cpu_count()}** cores, {boss}.", "speech": f"CPU is at {system_cache['cpu']} percent, {boss}."}
    if target == "RAM":
        return {"text": f"RAM: **{system_cache['ram']}%** used, **{system_cache['ram_used']}/{system_cache['ram_total']} GB**, {boss}.", "speech": f"RAM is {system_cache['ram']} percent, {boss}."}
    if target == "battery":
        ch = "charging" if system_cache["charging"] else "on battery"
        return {"text": f"Battery: **{system_cache['battery']}%** ({ch}), {boss}.", "speech": f"Battery at {system_cache['battery']} percent, {ch}, {boss}."}
    if target == "disk":
        return {"text": f"Disk: **{system_cache['disk']}%** used, **{system_cache['disk_free']} GB** free of **{system_cache['disk_total']} GB**, {boss}.", "speech": f"Disk is {system_cache['disk']} percent, {boss}."}
    if target == "uptime":
        up = system_cache["uptime"]; hrs, rem = divmod(up, 3600); mins, secs = divmod(rem, 60)
        return {"text": f"Uptime: **{hrs}h {mins}m {secs}s**, {boss}.", "speech": f"Up for {hrs} hours and {mins} minutes, {boss}."}
    if target == "system-info":
        return {"text": f"OS: **{platform.system()} {platform.release()}**\nCPU: **{platform.processor() or 'Unknown'}**\nRAM: **{system_cache['ram_used']}/{system_cache['ram_total']} GB**\nHostname: **{platform.node()}**\nBattery: **{system_cache['battery']}%**", "speech": f"Running {platform.system()} {platform.release()}."}
    return None


_last_net = {"bytes": 0, "time": 0}

def update_telemetry():
    import psutil
    global _last_net
    psutil.cpu_percent(interval=0.1)
    while True:
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            m = psutil.virtual_memory()
            d = psutil.disk_usage("C:\\")
            b = psutil.sensors_battery()
            n = psutil.net_io_counters()
            up = time.time() - psutil.boot_time()
            
            now = time.time()
            dt = now - _last_net["time"] if _last_net["time"] else 3
            delta_bytes = n.bytes_sent - _last_net["bytes"] if _last_net["bytes"] else 0
            speed_bps = delta_bytes / dt if dt > 0 else 0
            _last_net = {"bytes": n.bytes_sent, "time": now}
            
            net_pct = min(speed_bps / (1024 * 1024) * 100, 100)
            
            if speed_bps > 1024*1024:
                speed_str = f"{speed_bps/(1024*1024):.1f} MB/s"
            elif speed_bps > 1024:
                speed_str = f"{speed_bps/1024:.1f} KB/s"
            else:
                speed_str = f"{speed_bps:.0f} B/s"
            
            system_cache.update({
                "cpu": round(cpu, 1), 
                "ram": round(m.percent, 1), 
                "ram_used": str(round(m.used / (1024**3), 1)), 
                "ram_total": str(round(m.total / (1024**3), 1)), 
                "disk": round(d.percent, 1), 
                "disk_free": f"{d.free / (1024**3):.1f}", 
                "disk_total": f"{d.total / (1024**3):.1f}", 
                "battery": b.percent if b else 100, 
                "charging": b.power_plugged if b else False, 
                "net_speed": speed_str,
                "net_usage": round(net_pct, 1),
                "net_bytes": int(speed_bps),
                "uptime": int(up), 
                "hostname": platform.node()
            })
        except Exception as e:
            pass
        time.sleep(2)


@app.route("/")
def index():
    return send_from_directory(str(PUBLIC_DIR), "index.html")

@app.route("/<path:p>")
def serve_static(p):
    fp = PUBLIC_DIR / p
    if fp.exists() and fp.is_file():
        return send_from_directory(str(PUBLIC_DIR), p)
    return send_from_directory(str(PUBLIC_DIR), "index.html")

@app.route("/api/mode", methods=["GET", "POST"])
def api_mode():
    if request.method == "GET":
        m = get_mode()
        return jsonify({"success": True, "mode": m, "profile": MODE_PROFILES[m]})
    d = request.get_json(force=True, silent=True) or {}
    mode = d.get("mode", "").lower()
    if mode not in MODE_PROFILES:
        return jsonify({"success": False, "error": "Invalid mode"})
    set_mode(mode)
    return jsonify({"success": True, "mode": mode, "profile": MODE_PROFILES[mode]})

@app.route("/api/system-status")
def api_system_status():
    import psutil
    try:
        cpu_count = psutil.cpu_count()
        cpu_model = platform.processor() or "Unknown CPU"
    except:
        cpu_count = 1; cpu_model = "Unknown"
    return jsonify({"success": True, "cpu": {"usage": system_cache["cpu"], "cores": cpu_count, "model": cpu_model}, "ram": {"usage": system_cache["ram"], "usedMB": int(float(system_cache["ram_used"]) * 1024), "totalMB": int(float(system_cache["ram_total"]) * 1024)}, "battery": {"level": system_cache["battery"], "charging": system_cache["charging"]}, "disk": {"usage": system_cache["disk"], "free": system_cache["disk_free"] + "GB"}, "net": {"usage": system_cache.get("net_usage", 0), "speed": system_cache["net_speed"], "bytes": system_cache.get("net_bytes", 0)}, "uptime": system_cache["uptime"], "hostname": system_cache["hostname"], "platform": sys.platform})

# Groq reachability probe with short TTL so a single transient timeout is
# never reported as a hard OFFLINE. A stale "last known good" still counts as
# online (degraded) rather than offline.
_GROQ_PROBE = {"ok": None, "latency": None, "ts": 0}
_GROQ_PROBE_TTL = 30
_probe_lock = threading.Lock()

def _groq_reachable():
    """Cached check of Groq API reachability (up to `_GROQ_PROBE_TTL`s)."""
    key = get_grok_key()
    if not key:
        return False, None
    with _probe_lock:
        cached = _GROQ_PROBE
        if cached["ts"] and (time.time() - cached["ts"]) < _GROQ_PROBE_TTL and cached["ok"] is not None:
            return cached["ok"], cached["latency"]
    ok = False
    lat = None
    try:
        req = urllib.request.Request("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}", "User-Agent": "Mozilla/5.0"}, method="GET")
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=6) as resp:
            ok = resp.status == 200
            lat = round((time.time() - t0) * 1000)
    except Exception:
        ok = False
    with _probe_lock:
        # Keep the last known good for 60s even if a probe fails, so the badge
        # never flips to OFFLINE because of one slow request.
        if ok:
            _GROQ_PROBE.update({"ok": True, "latency": lat, "ts": time.time()})
        else:
            stale_good = _GROQ_PROBE.get("ok") is True and (time.time() - _GROQ_PROBE.get("ts", 0)) < 60
            _GROQ_PROBE.update({"ok": True if stale_good else False,
                                "latency": _GROQ_PROBE.get("latency") if stale_good else None,
                                "ts": _GROQ_PROBE.get("ts", 0) if stale_good else time.time()})
    return _GROQ_PROBE["ok"], _GROQ_PROBE["latency"]

@app.route("/api/health")
def api_health():
    """True end-to-end status so the UI stops showing 'offline' wrongly:
    Groq key present + reachable, neural TTS engine, microphone devices,
    server uptime and the active model."""
    key = get_grok_key()
    api_ok, api_latency = _groq_reachable()
    mics = []
    try:
        import sounddevice as sd
        for i, d in enumerate(sd.query_devices()):
            if int(d.get("max_input_channels") or 0) > 0:
                mics.append({"index": i, "name": d.get("name", "")})
    except Exception:
        pass
    chat = None
    if key and api_ok:
        chat = "groq"
    elif get_gemini_key():
        chat = "gemini"
    # Online = server serving + either a key is set (even if the probe was
    # momentarily slow) OR chat works. "degraded" tells the UI a key exists
    # but the last live probe failed - never a hard OFFLINE.
    key_set = bool(key)
    online = key_set  # server up + key present; probe latency is status only
    degraded = key_set and not api_ok
    return jsonify({
        "success": True,
        "online": online,
        "degraded": degraded,
        "provider": chat or "none",
        "key_set": key_set,
        "api_reachable": bool(api_ok),
        "api_latency_ms": api_latency,
        "model": _groq_working_model() if chat == "groq" else "gemini-2.0-flash" if chat == "gemini" else None,
        "tts": {"engine": "edge-tts" if tts_engine.edge_tts_available() else "SAPI-fallback", "speaking": bool(tts_engine.status().get("speaking"))},
        "mic": {"count": len(mics), "devices": mics[:4]},
        "uptime_seconds": int(time.time() - SERVER_START),
        "mode": get_mode(),
        "host": platform.node(),
    })

# ---- Runtime / activity stats ---------------------------------------------
SERVER_START = time.time()
_runtime_counters = {"requests": 0, "api_requests": 0, "by_endpoint": {}}
_runtime_lock = threading.Lock()

@app.before_request
def _count_requests():
    with _runtime_lock:
        _runtime_counters["requests"] += 1
        if request.path.startswith("/api/"):
            _runtime_counters["api_requests"] += 1
            ep = request.path
            _runtime_counters["by_endpoint"][ep] = _runtime_counters["by_endpoint"].get(ep, 0) + 1

@app.route("/api/runtime")
def api_runtime():
    """Server runtime stats: uptime, request volume and hot endpoints."""
    with _runtime_lock:
        uptime_s = max(0, int(time.time() - SERVER_START))
        top_endpoints = sorted(_runtime_counters["by_endpoint"].items(), key=lambda kv: kv[1], reverse=True)[:10]
        snapshot = {
            "success": True,
            "started": datetime.datetime.fromtimestamp(SERVER_START, tz=datetime.timezone.utc).isoformat(),
            "uptime_seconds": uptime_s,
            "uptime_display": f"{uptime_s // 86400}d {uptime_s % 86400 // 3600}h {uptime_s % 3600 // 60}m",
            "total_requests": _runtime_counters["requests"],
            "api_requests": _runtime_counters["api_requests"],
            "top_endpoints": [{"path": p, "hits": c} for p, c in top_endpoints],
            "device_count": len(activeDevices),
            "mode": get_mode(),
        }
    return jsonify(snapshot)

@app.route("/api/stream")
def api_stream():
    """Server-Sent Events: pushes live system telemetry to connected (mobile) clients.
    Real-time replacement for polling — one long-lived HTTP connection."""
    def gen():
        last_notif_key = None
        while True:
            try:
                payload = {
                    "cpu": system_cache.get("cpu", 0),
                    "ram": system_cache.get("ram", 0),
                    "battery": system_cache.get("battery", 100),
                    "charging": system_cache.get("charging", False),
                    "disk": system_cache.get("disk", 0),
                    "net": system_cache.get("net_speed", "0 KB/s"),
                    "uptime": system_cache.get("uptime", 0),
                    "hostname": system_cache.get("hostname", ""),
                }
                yield f"data: {json.dumps(payload)}\n\n"
                pc = load_json(DATA_DIR / "pc_notifications.json", {"items": []})
                items = pc.get("items", [])
                if items:
                    k = items[0].get("time")
                    if k != last_notif_key:
                        last_notif_key = k
                        yield f"event: notify\ndata: {json.dumps(items[0])}\n\n"
            except Exception:
                pass
            try:
                time.sleep(2)
            except GeneratorExit:
                break
    response = Response(gen(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response

gesture_controller = None

@app.route("/api/gesture-status")
def api_gesture_status():
    global gesture_controller
    try:
        if gesture_controller is None:
            import importlib
            gesture_controller = importlib.import_module("gesture_controller")
    except Exception:
        pass
    if gesture_controller:
        return jsonify(gesture_controller.get_gesture_status())
    return jsonify({"active": False, "gesture": "NO_HAND", "enabled": False, "has_mediapipe": False, "has_pyautogui": False})

@app.route("/api/gesture/start", methods=["POST"])
def api_gesture_start():
    global gesture_controller
    try:
        import importlib
        gc = importlib.import_module("gesture_controller")
        gc.start_gesture_control()
        gesture_controller = gc
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/gesture/stop", methods=["POST"])
def api_gesture_stop():
    global gesture_controller
    if gesture_controller:
        try:
            gesture_controller.stop_gesture_control()
        except: pass
        gesture_controller = None
    return jsonify({"success": True})

@app.route("/api/gesture/frame")
def api_gesture_frame():
    if gesture_controller and hasattr(gesture_controller, 'gesture_state'):
        frame = gesture_controller.gesture_state.get("frame")
        if frame:
            resp = Response(frame, mimetype="image/jpeg")
            resp.headers["Cache-Control"] = "no-store, max-age=0"
            return resp
    from flask import Response as R
    return R(b'', mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

@app.route("/api/gesture/config", methods=["GET", "POST"])
def api_gesture_config():
    gc = gesture_controller
    if not gc:
        return jsonify({"success": False, "error": "Gesture control not running"})
    if request.method == "GET":
        return jsonify({"success": True, "config": gc.get_config()})
    d = request.get_json(force=True, silent=True) or {}
    only = d.get("config", d)
    if not isinstance(only, dict):
        return jsonify({"success": False, "error": "Invalid config payload"})
    try:
        cfg = gc.save_config(only)
        return jsonify({"success": True, "config": cfg})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/gesture/orb", methods=["POST"])
def api_gesture_orb():
    gc = gesture_controller
    if not gc:
        return jsonify({"success": False, "error": "Gesture control not running"})
    d = request.get_json(force=True, silent=True) or {}
    try:
        on = bool(d.get("enabled", False))
        state = gc.set_orb_drive(on)
        if d.get("notify") and state:
            threading.Thread(target=tts_speak, args=("Orb drive engaged.",), daemon=True).start()
        elif d.get("notify"):
            threading.Thread(target=tts_speak, args=("Orb drive off.",), daemon=True).start()
        return jsonify({"success": True, "orb_drive": state})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/gesture/mode", methods=["POST"])
def api_gesture_mode():
    gc = gesture_controller
    if not gc:
        return jsonify({"success": False, "error": "Gesture control not running"})
    d = request.get_json(force=True, silent=True) or {}
    mode = str(d.get("mode", "")).lower()
    if mode not in gc.MODE_ORDER:
        return jsonify({"success": False, "error": "Invalid control mode"})
    gc.gesture_state["control_mode"] = mode
    gc.gesture_state["gesture"] = f"MODE:{mode.upper()}"
    if d.get("notify"):
        threading.Thread(target=tts_speak, args=(f"{mode} mode.",), daemon=True).start()
    return jsonify({"success": True, "control_mode": mode})

@app.route("/api/gesture/cmd", methods=["POST"])
def api_gesture_cmd():
    """Directly trigger a PC action (browser/system/media) from the frontend."""
    d = request.get_json(force=True, silent=True) or {}
    action = str(d.get("action", ""))
    value = d.get("value", "")
    try:
        import pc_actions
    except Exception:
        pc_actions = None
    if not pc_actions or not action:
        return jsonify({"success": False, "error": "PC actions unavailable"})
    ok = pc_actions.run_action(action, value)
    if ok and d.get("notify"):
        pretty = action.replace("_", " ").strip()
        threading.Thread(target=tts_speak, args=(f"Executing {pretty}.",), daemon=True).start()
    return jsonify({"success": bool(ok), "action": action})

GESTURE_FREEZE_SECONDS = 60
gesture_watchdog_log = []

def gesture_watchdog():
    """Auto-recover ULTRON if the system freezes: if the gesture loop stops
    sending heartbeats for > 60s (or overall CPU is pinned for a sustained
    period, or two-hand tracking pushes CPU very high), force-stop it."""
    high_cpu_since = 0
    while True:
        time.sleep(5)
        try:
            gc = gesture_controller
            if gc and gc.get_gesture_status().get("active"):
                status = gc.get_gesture_status()
                age = status.get("heartbeat_age", 0)
                cpu = system_cache.get("cpu", 0)
                num_hands = status.get("num_hands", 0)
                # Two-hand tracking on a weak machine can pin the CPU: lower the
                # threshold, but require it to be sustained for ~25s before acting.
                cpu_limit = 90 if num_hands >= 2 else 95
                if age > GESTURE_FREEZE_SECONDS:
                    gc.stop_gesture_control()
                    gesture_watchdog_log.append("gesture auto-stopped: frozen heartbeat %.0fs" % age)
                    print("[JENNY] Watchdog: gesture control stopped (frozen %.0fs)" % age)
                    high_cpu_since = 0
                elif cpu > cpu_limit:
                    if high_cpu_since == 0:
                        high_cpu_since = time.time()
                    elif (time.time() - high_cpu_since) > 25:
                        gc.stop_gesture_control()
                        gesture_watchdog_log.append("gesture auto-stopped: sustained CPU %d%% (%d hands)" % (cpu, num_hands))
                        print("[JENNY] Watchdog: gesture control stopped (CPU %d%%, %d hands)" % (cpu, num_hands))
                        high_cpu_since = 0
                else:
                    high_cpu_since = 0
        except Exception:
            pass
        if len(gesture_watchdog_log) > 50:
            gesture_watchdog_log[:] = gesture_watchdog_log[-50:]

@app.route("/api/gesture/watchdog-log")
def api_gesture_watchdog_log():
    return jsonify({"success": True, "log": gesture_watchdog_log[-20:] if gesture_watchdog_log else []})

@app.route("/api/gesture/watchdog")
def api_gesture_watchdog():
    return jsonify({"success": True, "log": gesture_watchdog_log[-10:]})

@app.route("/api/agency")
def api_agency():
    state = agency_client.agency_state()
    if not state:
        return jsonify({"success": False, "online": False, "message": "Agency OS is offline on localhost:3200"})
    return jsonify({"success": True, "online": True, "state": state, "summary": agency_client.summarize_state(state)})

@app.route("/api/agency/mission", methods=["POST"])
def api_agency_mission():
    d = request.get_json(force=True, silent=True) or {}
    city = (d.get("city") or "Patna").strip()
    category = (d.get("category") or "School").strip()
    limit = int(d.get("limit") or 10)
    res = agency_client.agency_launch_mission(city, category, limit)
    if res is None:
        return jsonify({"success": False, "online": False, "message": "Agency OS is offline"})
    return jsonify({"success": True, "online": True, "result": res})

@app.route("/api/agency/outreach", methods=["POST"])
def api_agency_outreach():
    d = request.get_json(force=True, silent=True) or {}
    item_id = d.get("id")
    action = (d.get("action") or "").strip()
    if item_id is None or action not in ("approve", "reject", "edit", "send"):
        return jsonify({"success": False, "error": "id and action (approve/reject/edit/send) required"})
    res = agency_client.agency_outreach_action(item_id, action, d.get("body"), d.get("subject"))
    if res is None:
        return jsonify({"success": False, "online": False, "message": "Agency OS is offline"})
    return jsonify({"success": True, "online": True, "result": res})

@app.route("/api/agency/response", methods=["POST"])
def api_agency_response():
    d = request.get_json(force=True, silent=True) or {}
    from agency_client import _post as _ac_post
    res = _ac_post("/api/response", d)
    if res is None:
        return jsonify({"success": False, "online": False, "message": "Agency OS is offline"})
    return jsonify({"success": True, "online": True, "result": res})

def parse_agency_mission_intent(text):
    """Detect a mission-launch request like 'launch a mission for schools in Patna'.
    Returns dict(city, category, limit) or None."""
    t = text.lower()
    if "mission" not in t:
        return None
    launched = bool(re.search(r"(?:launch|start|run|begin|kick off)\s+(?:a\s+|a new\s+)?(?:new\s+)?mission", t)) or bool(re.search(r"new\s+mission", t))
    if not launched:
        return None
    city_match = re.search(r"\bin\s+([a-zA-Z][a-zA-Z \-]{1,28}[a-zA-Z])", t)
    cat_match = re.search(r"(?:for|targeting|on)\s+([a-z][a-z \-]{1,28})", t)
    limit_match = re.search(r"(\d+)\s*leads?", t)
    limit = int(limit_match.group(1)) if limit_match else 10
    if city_match and cat_match:
        return {"city": city_match.group(1).strip().title(), "category": cat_match.group(1).strip().title(), "limit": limit}
    if city_match:
        return {"city": city_match.group(1).strip().title(), "category": "School", "limit": limit}
    return {"city": "Patna", "category": "School", "limit": limit}

def _assistant_reply(msg: str) -> dict:
    """Shared chat pipeline used by both /api/chat and the server wake-word
    flow. Returns the reply dict (local router or LLM chain), updates history,
    memory vault and activity telemetry — identical behaviour from either path."""
    if get_mode() == "jarvis":
        intent = parse_agency_mission_intent(msg)
        if intent:
            res = agency_client.agency_launch_mission(intent["city"], intent["category"], intent["limit"])
            if res:
                msg = f"[Agency mission launched: {intent['category']} in {intent['city']} (limit {intent['limit']}) — result {json.dumps(res)[:220]}. Confirm to the user and offer an agency briefing.] User says: {msg}"
            else:
                msg = f"[User asked to launch a mission but Agency OS is offline on :3200. Explain it's offline.] User says: {msg}"
    local = local_command_router(msg)
    if local:
        if local.get("command", {}).get("action") == "vault-save":
            _save_vault_entry((local.get("command", {}).get("value", {}) or {}).get("text", ""))
        chatHistory.append({"role": "user", "content": msg})
        chatHistory.append({"role": "assistant", "content": local.get("text", "")})
        if len(chatHistory) > 20:
            chatHistory.pop(0); chatHistory.pop(0)
        proactive.mark_activity()
        return local
    reply = grok_chat(msg, chatHistory)
    if not reply:
        reply = gemini_chat(msg, chatHistory)
    if not reply:
        reply = offline_reply(msg) or {"text": "I'm offline, Boss.", "speech": "I'm offline, Boss."}
    if reply.get("command", {}).get("action") == "vault-save":
        _save_vault_entry((reply.get("command", {}).get("value", {}) or {}).get("text", ""))
    chatHistory.append({"role": "user", "content": msg})
    chatHistory.append({"role": "assistant", "content": reply.get("text", "")})
    if len(chatHistory) > 20:
        chatHistory.pop(0); chatHistory.pop(0)
    proactive.mark_activity()
    return reply


def _execute_control_command(cmd: dict) -> None:
    """Execute a command dict server-side (same handler /api/control uses)."""
    if not cmd:
        return
    try:
        with app.test_client() as c:
            c.post("/api/control", json=cmd)
    except Exception:
        pass


@app.route("/api/chat", methods=["POST"])
def api_chat():
    d = request.get_json(force=True, silent=True) or {}
    msg = d.get("message", "").strip()
    if not msg:
        return jsonify({"success": False, "error": "No message"}), 400
    # Phone-sourced chats are mirrored into the dashboard output box so a
    # command sent from the phone is visible on the PC too.
    src = (request.headers.get("X-Source") or "").lower()
    if src == "phone" or d.get("deviceId"):
        _ui_feed("user", f"[Phone] {msg}", source="phone")
        reply = _assistant_reply(msg)
        ev = {"kind": "assistant", "text": reply.get("text", "")}
        if reply.get("command"):
            ev["command"] = reply["command"]
        _ui_feed("assistant", reply.get("text", ""), command=reply.get("command"), source="phone")
        return jsonify({"success": True, "reply": reply})
    return jsonify({"success": True, "reply": _assistant_reply(msg)})

@app.route("/api/smart-suggestions")
def api_smart_suggestions():
    return jsonify({"success": True, "suggestions": get_smart_suggestions(), "period": get_time_period()})

@app.route("/api/user-habits")
def api_user_habits():
    stats = load_json(DATA_DIR / "command_stats.json", {"commands": {}, "topics": []})
    top = sorted(stats.get("commands", {}).items(), key=lambda x: x[1], reverse=True)[:10]
    return jsonify({"success": True, "topCommands": [{"command": k, "count": v} for k, v in top], "frequentTopics": stats.get("topics", [])})

@app.route("/api/control", methods=["POST"])
def api_control():
    d = request.get_json(force=True, silent=True) or {}
    action = d.get("action", ""); value = d.get("value", "")
    # Mirror phone-originated control actions into the dashboard output box.
    phone_src = (request.headers.get("X-Source") or "").lower() == "phone" or bool(d.get("deviceId"))
    if phone_src:
        from flask import after_this_request
        @after_this_request
        def _feed_phone_cmd(resp):
            try:
                import json as _json
                body = _json.loads(resp.get_data(as_text=True) or "{}") if resp.get_data() else {}
                if body.get("success"):
                    label = "Phone → " + str(action)
                    if value and isinstance(value, str) and value and not value.startswith("{"):
                        label += " " + str(value)[:80]
                    _ui_feed("cmd", label, source="phone")
            except Exception:
                pass
            return resp
    lo = action.lower()
    if lo == "run-sequence":
        # Multi-step autonomous task: execute each sub-command in order,
        # with a short settle delay, then report the combined result.
        steps = (value or {}).get("steps", []) if isinstance(value, dict) else []
        results = []
        for i, st in enumerate(steps):
            act = st.get("action") if isinstance(st, dict) else ""
            val = st.get("value") if isinstance(st, dict) else ""
            if not act:
                continue
            try:
                with app.test_client() as c:
                    resp = c.post("/api/control", json={"action": act, "value": val})
                    body = resp.get_json(silent=True) or {}
                results.append({"step": i + 1, "action": act, "ok": bool(body.get("success"))})
            except Exception as e:
                results.append({"step": i + 1, "action": act, "ok": False, "error": str(e)[:120]})
            if i < len(steps) - 1:
                time.sleep(0.8)
        ok = sum(1 for r in results if r.get("ok"))
        return jsonify({"success": len(results) > 0, "total": len(results), "done": ok, "steps": results})
    if lo == "open-recent-pdf":
        # Open the most recently received PDF (Downloads / WhatsApp media / Desktop).
        try:
            import glob as _glob
            candidates = []
            base = Path.home()
            for folder in ["Downloads", "Downloads/WhatsApp", "Desktop", "Documents"]:
                for pat in ["*.pdf"]:
                    candidates += _glob.glob(str(base / folder / pat))
            if not candidates:
                return jsonify({"success": False, "message": "No recent PDF found on this PC."})
            latest = max(candidates, key=lambda p: os.path.getmtime(p))
            os.startfile(latest)
            return jsonify({"success": True, "message": f"Opened {os.path.basename(latest)}"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)[:120]})
    if lo == "volume":
        try:
            from ctypes import cast, POINTER; from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            spk = AudioUtilities.GetSpeakers(); iface = spk.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            if value == "mute": vol.SetMute(1, None); return jsonify({"success": True, "message": "Muted."})
            if value == "unmute": vol.SetMute(0, None); return jsonify({"success": True, "message": "Unmuted."})
            vol.SetMasterVolumeLevelScalar(int(value)/100.0, None); return jsonify({"success": True, "message": f"Volume set to {value}%."})
        except: return jsonify({"success": False, "error": "Volume control failed"})
    if lo == "wake-display":
        try:
            subprocess.Popen(["powershell", "-command", "(New-Object -ComObject WScript.Shell).SendKeys('{SCROLLLOCK}')"], creationflags=subprocess.CREATE_NO_WINDOW)
            return jsonify({"success": True, "message": "Display woken."})
        except: return jsonify({"success": False})
    if lo == "purge-ram":
        try:
            subprocess.Popen(["powershell", "-command", "$M='GetProcessMemoryInfo';Add-Type -Namespace Win32 -Name P -MemberDefinition '[DllImport(\"psapi.dll\")] public static extern bool EmptyWorkingSet(IntPtr hProcess);';Get-Process|ForEach-Object{$P::EmptyWorkingSet($_.Handle)};'Memory flushed.'|Write-Output"], creationflags=subprocess.CREATE_NO_WINDOW)
            return jsonify({"success": True, "message": "Memory flush started."})
        except: return jsonify({"success": False})
    if lo == "lock":
        try: ctypes.windll.user32.LockWorkStation(); return jsonify({"success": True, "message": "Locked."})
        except: return jsonify({"success": False})
    if lo == "screenshot":
        try:
            fp = str(Path.home() / "Desktop" / f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            subprocess.run(["powershell", "-command", f"Add-Type -AssemblyName System.Windows.Forms; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $gfx = [System.Drawing.Graphics]::FromImage($bmp); $gfx.CopyFromScreen(0, 0, 0, 0, $bmp.Size); $bmp.Save('{fp}')"], capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            return jsonify({"success": True, "message": "Screenshot saved."})
        except: return jsonify({"success": False})
    if lo == "clipboard-read":
        try: r = subprocess.run(["powershell", "-command", "Get-Clipboard"], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "text": r.stdout.strip()})
        except: return jsonify({"success": False})
    if lo == "clipboard-write":
        txt = value if isinstance(value, str) else value.get("text", "")
        try: subprocess.run(["powershell", "-command", f"Set-Clipboard -Value '{txt}'"], capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "message": "Copied."})
        except: return jsonify({"success": False})
    if lo == "processes":
        try:
            r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            procs = []
            for line in r.stdout.strip().split("\n")[:15]:
                parts = line.strip('"').split('","')
                if len(parts) >= 5: procs.append({"pid": parts[1], "name": parts[0], "cpu": parts[4]})
            return jsonify({"success": True, "processes": procs})
        except: return jsonify({"success": False})
    if lo == "kill-process":
        try: subprocess.run(["taskkill", "/f", "/pid", str(value)], capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True})
        except: return jsonify({"success": False})
    if lo == "system-info":
        return jsonify({"success": True, "info": {"os": f"{platform.system()} {platform.release()}", "cpu": platform.processor() or "Unknown", "ram": f"{system_cache['ram_used']} / {system_cache['ram_total']} GB", "hostname": platform.node()}})
    if lo == "wifi":
        try:
            r = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            ssid = ""; sig = ""
            for l in r.stdout.split("\n"):
                if "SSID" in l and "BSSID" not in l: ssid = l.split(":", 1)[-1].strip()
                if "Signal" in l: sig = l.split(":", 1)[-1].strip()
            return jsonify({"success": True, "ssid": ssid, "signal": sig})
        except: return jsonify({"success": False})
    if lo == "open-app":
        apps = {"notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe", "chrome": "chrome", "edge": "msedge", "vscode": "code", "spotify": "spotify", "discord": "discord",
                "task manager": "taskmgr.exe", "taskmanager": "taskmgr.exe", "terminal": "wt.exe", "cmd": "cmd.exe", "youtube": "https://www.youtube.com", "files": "explorer.exe", "explorer": "explorer.exe",
                "control panel": "control.exe", "settings": "ms-settings:", "mail": "outlook.exe", "whatsapp": "whatsapp.exe", "telegram": "telegram.exe", "browser": "chrome", "firefox": "firefox"}
        name = str(value).lower(); target = apps.get(name, value)
        try:
            if target.startswith("http://") or target.startswith("https://") or target.startswith("ms-settings:"):
                webbrowser.open(target)
                return jsonify({"success": True, "message": f"Opened {value}."})
            subprocess.Popen(target, shell=True); return jsonify({"success": True, "message": f"Opened {value}."})
        except: return jsonify({"success": False})
    if lo == "close-app":
        try: subprocess.run(["taskkill", "/f", "/im", f"{value}.exe"], capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True})
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
    if lo == "shutdown": os.system("shutdown /s /t 60"); return jsonify({"success": True, "message": "Shutting down."})
    if lo == "restart": os.system("shutdown /r /t 60"); return jsonify({"success": True, "message": "Restarting."})
    if lo == "empty-trash":
        try: subprocess.run(["PowerShell", "-Command", "Clear-RecycleBin -Force"], capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "message": "Trash emptied."})
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
        return jsonify({"success": True, "message": f"Timer set for {secs}s."})
    if lo == "sleep":
        try: os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0"); return jsonify({"success": True})
        except: return jsonify({"success": False})
    if lo == "terminal":
        try: subprocess.Popen("wt.exe", shell=True); return jsonify({"success": True})
        except: subprocess.Popen("cmd.exe", shell=True); return jsonify({"success": True})
    if lo == "minimize-all":
        try: ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0); ctypes.windll.user32.keybd_event(0x4D, 0, 0, 0); ctypes.windll.user32.keybd_event(0x4D, 0, 2, 0); ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0); return jsonify({"success": True})
        except: return jsonify({"success": False})
    if lo == "network-speed": return jsonify({"success": True, "speed": system_cache["net_speed"]})
    if lo == "disk-usage":
        try: r = subprocess.run(["wmic", "logicaldisk", "get", "size,freespace,caption"], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "text": r.stdout[:2000]})
        except: return jsonify({"success": False})
    if lo == "volume-down":
        try:
            from ctypes import cast, POINTER; from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            spk = AudioUtilities.GetSpeakers(); iface = spk.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            vol.SetMasterVolumeLevelScalar(max(0.0, vol.GetMasterVolumeLevelScalar() - 0.1), None)
            return jsonify({"success": True, "message": f"Volume at {round(vol.GetMasterVolumeLevelScalar()*100)}%."})
        except: return jsonify({"success": False, "error": "Volume control failed"})
    if lo == "volume-up":
        try:
            from ctypes import cast, POINTER; from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            spk = AudioUtilities.GetSpeakers(); iface = spk.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            vol.SetMasterVolumeLevelScalar(min(1.0, vol.GetMasterVolumeLevelScalar() + 0.1), None)
            return jsonify({"success": True, "message": f"Volume at {round(vol.GetMasterVolumeLevelScalar()*100)}%."})
        except: return jsonify({"success": False, "error": "Volume control failed"})
    if lo == "mute":
        try:
            from ctypes import cast, POINTER; from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            spk = AudioUtilities.GetSpeakers(); iface = spk.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            cast(iface, POINTER(IAudioEndpointVolume)).SetMute(1, None)
            return jsonify({"success": True, "message": "Muted."})
        except: return jsonify({"success": False})
    if lo == "unmute":
        try:
            from ctypes import cast, POINTER; from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            spk = AudioUtilities.GetSpeakers(); iface = spk.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            cast(iface, POINTER(IAudioEndpointVolume)).SetMute(0, None)
            return jsonify({"success": True, "message": "Unmuted."})
        except: return jsonify({"success": False})
    if lo == "brightness":
        target = str(value).lower()
        pct = None
        if target in ("up", "down"):
            try:
                r = subprocess.run(["powershell", "-command",
                    "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"],
                    capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
                cur = int(float(r.stdout.strip() or 50))
                pct = min(100, max(0, cur + (10 if target == "up" else -10)))
            except Exception:
                pct = 50
        else:
            try: pct = min(100, max(0, int(str(value).replace("%", ""))))
            except: pct = None
        if pct is None:
            return jsonify({"success": False, "error": "Invalid brightness value"})
        try:
            subprocess.run(["powershell", "-command",
                f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,{pct})"],
                capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            return jsonify({"success": True, "message": f"Brightness at {pct}%."})
        except:
            return jsonify({"success": False, "error": "Brightness control failed"})
    if lo == "media":
        media = {"playpause": 0xB3, "next": 0xB0, "previous": 0xB1, "play": 0xFA, "pause": 0xB3, "stop": 0xB2}.get(str(value).lower(), 0xB3)
        try:
            ctypes.windll.user32.keybd_event(media, 0, 0, 0); ctypes.windll.user32.keybd_event(media, 0, 2, 0)
            return jsonify({"success": True, "message": f"Media {value}."})
        except: return jsonify({"success": False})

    # App integrations & Chrome deep control proxy into app_integrations / chrome_bridge
    if lo in ("spotify-search", "spotify-action", "telegram-send", "whatsapp-open",
              "discord-open", "open-project", "terminal-project", "focus-window",
              "app-volume", "list-app-volumes", "foreground-window", "list-open-apps"):
        try:
            import app_integrations
            ok, msg = app_integrations.run(lo, value)
            return jsonify({"success": bool(ok), "message": msg})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    if lo == "spotify-status":
        try:
            import app_integrations
            st = app_integrations.spotify_status()
            return jsonify({"success": True, **st})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    if lo in ("phone-ring", "phone-command"):
        dids = [d for d, dev in activeDevices.items() if dev.get("status") == "approved"]
        if not dids:
            return jsonify({"success": False, "message": "No approved phone linked."})
        did = dids[0]
        if lo == "phone-ring":
            pendingDeviceCommands.setdefault(did, []).append({"action": "call", "value": "", "timestamp": int(time.time() * 1000)})
            return jsonify({"success": True, "message": "Ringing phone."})
        val = value.get("value", "") if isinstance(value, dict) else value
        pendingDeviceCommands.setdefault(did, []).append({"action": str(value.get("action", "toast") if isinstance(value, dict) else "toast"), "value": val, "timestamp": int(time.time() * 1000)})
        return jsonify({"success": True, "message": "Command sent to phone."})
    if lo in ("discord-send", "whatsapp-send"):
        if lo == "discord-send":
            text = (value or "").replace("\n", " ")
            webhook = str(load_json(DATA_DIR / "keys.json", {}).get("discord_webhook_url") or "").strip()
            if not webhook:
                return jsonify({"success": False, "error": "No Discord webhook configured (Settings > Services)."})
            try:
                payload = json.dumps({"content": str(text)[:1900]}).encode("utf-8")
                req = urllib.request.Request(webhook, data=payload, method="POST",
                                             headers={"Content-Type": "application/json", "User-Agent": "JENNY"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    ok = 200 <= int(r.status) < 300
                return jsonify({"success": ok, "message": "Posted to Discord." if ok else "Discord rejected the message."})
            except Exception as e:
                return jsonify({"success": False, "error": f"Discord send failed: {str(e)[:120]}"})
        # whatsapp-send: open a wa.me conversation with the draft pre-filled.
        num = str(load_json(DATA_DIR / "settings.json", {}).get("whatsapp_number") or "").strip()
        target = str(value.get("to") or num or "").strip() if isinstance(value, dict) else ""
        text = (value.get("text") if isinstance(value, dict) else str(value or "")).strip()
        if not target:
            return jsonify({"success": False, "error": "No WhatsApp number set (Settings > Services)."})
        target = re.sub(r"[^0-9]", "", target)
        url = f"https://wa.me/{target}" + (("?text=" + urllib.parse.quote(text)) if text else "")
        try:
            webbrowser.open(url)
            return jsonify({"success": True, "message": "Opened WhatsApp chat with draft ready."})
        except Exception:
            return jsonify({"success": False, "error": "Could not open WhatsApp."})

    if lo in ("chrome-open", "chrome-search", "chrome-youtube", "chrome-list",
              "chrome-activate", "chrome-close", "chrome-back", "chrome-forward",
              "chrome-reload", "chrome-new-tab", "chrome-close-tab", "chrome-fullscreen"):
        try:
            import chrome_bridge
            if lo == "chrome-open":
                target = str(value)
                if not target.startswith("http"):
                    if not re.match(r"^[\w\-]+\.[\w\-]+", target):
                        target = f"https://www.google.com/search?q={urllib.parse.quote(target)}"
                    else:
                        target = "https://" + target
                r = chrome_bridge.open_url(target)
                return jsonify({"success": r.get("success", False), "message": target})
            if lo == "chrome-search":
                url = chrome_bridge.search(str(value))
                return jsonify({"success": bool(url), "message": url or "search failed"})
            if lo == "chrome-youtube":
                ok = chrome_bridge.youtube_play(str(value))
                return jsonify({"success": ok, "message": str(value) if ok else "youtube failed"})
            if lo == "chrome-list":
                st = chrome_bridge.status()
                return jsonify({"success": st.get("running", False), "tabs": st.get("tabs", []), "count": st.get("count", 0)})
            if lo == "chrome-activate":
                ok = chrome_bridge.activate(str(value))
                return jsonify({"success": ok, "message": str(value) if ok else "tab not found"})
            if lo == "chrome-close":
                ok = chrome_bridge.close(str(value))
                return jsonify({"success": ok, "message": str(value) if ok else "tab not found"})
            _nav = {
                "chrome-back": chrome_bridge.navigate_back,
                "chrome-forward": chrome_bridge.navigate_forward,
                "chrome-reload": chrome_bridge.reload,
                "chrome-new-tab": chrome_bridge.new_tab,
                "chrome-close-tab": chrome_bridge.close_current_tab,
                "chrome-fullscreen": chrome_bridge.fullscreen,
            }
            ok = _nav[lo]()
            return jsonify({"success": ok, "message": f"Chrome {lo.split('-')[-1]}" if ok else "chrome nav failed"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    # PC Automation actions that proxy into the shared pc_actions library so
    # the chat CI and ULTRON gestures execute identical code paths.
    _pc_map = {
        "browser-search": ("browser_search", value),
        "browser-new-tab": ("browser_new_tab", None),
        "browser-close-tab": ("browser_close_tab", None),
        "browser-back": ("browser_back", None),
        "browser-forward": ("browser_forward", None),
        "browser-refresh": ("browser_refresh", None),
        "browser-fullscreen": ("browser_fullscreen", None),
        "task-manager": ("task_manager", None),
    }
    _entry = _pc_map.get(lo)
    if _entry:
        try:
            import pc_actions
        except Exception:
            pc_actions = None
        fn_name, arg = _entry
        fn = getattr(pc_actions, fn_name, None) if pc_actions else None
        if fn:
            try:
                ok = fn(arg) if arg is not None else fn()
            except Exception:
                ok = False
        else:
            ok = False
        message = {"success": bool(ok), "action": lo}
        if ok:
            message["message"] = f"{lo.replace('-', ' ')} done."
        return jsonify(message)
    if lo == "type-text":
        txt = str(value)
        try:
            try:
                import pyautogui
                pyautogui.typewrite(txt, interval=0.01)
            except Exception:
                safe = txt.replace("'", "''")
                subprocess.run(["powershell", "-command",
                    f"$ws=New-Object -ComObject WScript.Shell; $ws.SendKeys('{safe}')"],
                    capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            return jsonify({"success": True, "message": "Typed."})
        except Exception:
            return jsonify({"success": False, "error": "Typing failed"})
    return jsonify({"success": False, "error": f"Unknown action: {action}"})


@app.route("/api/speak", methods=["GET", "POST"])
def api_speak():
    text = request.args.get("text", "") or (request.get_json(force=True, silent=True) or {}).get("text", "")
    fmt = request.args.get("fmt", "wav").lower()
    if not text: return jsonify({"success": False, "message": "Text required"})
    clean = _clean_tts_text(re.sub(r"[#*_`\[\]]", "", text))
    cache_dir = DATA_DIR / "speak_cache"; cache_dir.mkdir(exist_ok=True)
    ext = "mp3" if fmt == "mp3" else "wav"
    h = hashlib.md5((ext + ":" + clean).encode()).hexdigest(); wav_path = cache_dir / f"{h}.{ext}"
    if wav_path.exists() and wav_path.stat().st_size > 0:
        return send_from_directory(str(cache_dir), f"{h}.{ext}", mimetype=("audio/mpeg" if ext == "mp3" else "audio/wav"))
    mode = get_mode()
    # MP3 -> stream edge-tts live so the browser gets the first audio bytes in
    # ~0.5s instead of waiting for the whole sentence to synthesize (voice lag fix).
    # The full result is cached on completion so repeat phrases stay instant.
    if ext == "mp3" and tts_engine.edge_tts_available():
        try:
            voice, rate, pitch, volume = tts_engine.MODE_VOICES.get(mode, (tts_engine.DEFAULT_VOICE, tts_engine.DEFAULT_RATE, tts_engine.DEFAULT_PITCH, tts_engine.DEFAULT_VOLUME))
        except Exception:
            voice, rate, pitch, volume = tts_engine.DEFAULT_VOICE, tts_engine.DEFAULT_RATE, tts_engine.DEFAULT_PITCH, tts_engine.DEFAULT_VOLUME
        def _stream_mp3():
            buf = bytearray()
            ok = False
            try:
                for chunk in tts_engine.stream_tts(clean, voice, rate, pitch, volume):
                    buf.extend(chunk)
                    yield chunk
                ok = True
            except Exception:
                pass
            finally:
                try:
                    if ok and buf and not wav_path.exists():
                        wav_path.write_bytes(bytes(buf))
                except Exception:
                    pass
        return Response(_stream_mp3(), mimetype="audio/mpeg")
    ok = False
    try:
        voice, rate, pitch, volume = tts_engine.MODE_VOICES.get(mode, (tts_engine.DEFAULT_VOICE, tts_engine.DEFAULT_RATE, tts_engine.DEFAULT_PITCH, tts_engine.DEFAULT_VOLUME))
        ok = tts_engine.synthesize_wav(clean, wav_path, voice, rate, pitch, volume)
    except Exception:
        ok = False
    if not ok:
        # SAPI fallback only produces WAV; never write WAV bytes into an .mp3.
        if ext == "mp3":
            wav_path = cache_dir / f"{h}.wav"
        ok = tts_synthesize(clean, wav_path)
    if ok and wav_path.exists():
        # Prefer a true streaming-capable response so the browser plays the
        # first bytes while the rest still download (near-zero latency).
        return send_from_directory(str(cache_dir), wav_path.name, mimetype=("audio/mpeg" if ext == "mp3" else "audio/wav"))
    return jsonify({"success": False, "message": "Speech failed"})

@app.route("/api/speak/fallback", methods=["POST"])
def api_speak_fallback():
    d = request.get_json(force=True, silent=True) or {}; text = d.get("text", "")
    if text:
        threading.Thread(target=tts_speak, args=(text,), daemon=True).start()
    return jsonify({"success": True})

@app.route("/api/speak/stop", methods=["POST"])
def api_speak_stop():
    try:
        tts_engine.stop_speech()
    except Exception:
        pass
    with _tts_status_lock:
        global _tts_speaking
        _tts_speaking = False
    return jsonify({"success": True})

@app.route("/api/speak/status")
def api_speak_status():
    """Live server-side speech state so the UI can show an accurate status."""
    st = tts_engine.status()
    st["queue"] = tts_engine.ui_queue_depth()
    return jsonify(st)


@app.route("/api/speak/ping")
def api_speak_ping():
    """UI heartbeat - marks the UI as attached so server-initiated speech is
    queued for the single browser pipeline instead of playing locally."""
    tts_engine.mark_ui_activity()
    return jsonify({"success": True, "ui": tts_engine.ui_client_active(), "queue": tts_engine.ui_queue_depth()})


@app.route("/api/speak/next")
def api_speak_next():
    """Pop the next queued utterance for the UI to play (single voice bus)."""
    tts_engine.mark_ui_activity()
    item = tts_engine.next_ui_item()
    if item is None:
        return jsonify({"success": True, "item": None, "queue": 0})
    return jsonify({"success": True, "item": item, "queue": tts_engine.ui_queue_depth()})

@app.route("/api/weather")
def api_weather():
    settings = load_json(DATA_DIR / "settings.json", {"latitude": 26.8467, "longitude": 80.9462, "cityName": "Lucknow"})
    lat = settings.get("latitude", 26.8467); lon = settings.get("longitude", 80.9462); city = settings.get("cityName", "Lucknow")
    try:
        import requests as _req
        r = _req.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min&temperature_unit=celsius&timezone=auto", timeout=10)
        if r.status_code == 200:
            data = r.json(); cw = data.get("current_weather", {})
            wmo = {0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast", 45: "Foggy", 61: "Light Rain", 63: "Rain", 65: "Heavy Rain", 71: "Snow", 80: "Showers", 95: "Thunderstorm"}
            daily = data.get("daily", {}); tmax = daily.get("temperature_2m_max", []); tmin = daily.get("temperature_2m_min", [])
            days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]; forecast = []; now = datetime.datetime.now()
            for i in range(min(4, len(tmax))): d2 = now + datetime.timedelta(days=i+1); forecast.append({"day": days[d2.weekday()], "max": round(tmax[i]), "min": round(tmin[i])})
            return jsonify({"success": True, "city": city, "tempC": cw.get("temperature", 0), "condition": wmo.get(cw.get("weathercode", 0), "Unknown"), "type": "clear" if cw.get("weathercode", 0) < 3 else "cloudy" if cw.get("weathercode", 0) < 50 else "rain", "humidity": 50, "windKmH": cw.get("windspeed", 0), "isDay": cw.get("is_day", 1) == 1, "forecast": forecast})
    except: pass
    return jsonify({"success": True, "city": city, "tempC": "--", "condition": "Offline", "type": "clear", "humidity": 0, "windKmH": 0, "isDay": True, "forecast": []})

def generate_forecast_line(mode):
    """Short, mode-flavored system/weather status bumper for the boot greeting."""
    try:
        st = load_json(DATA_DIR / "settings.json", {"latitude": 26.8467, "longitude": 80.9462})
        import requests as _req
        r = _req.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={st.get('latitude', 26.8467)}"
            f"&longitude={st.get('longitude', 80.9462)}&current_weather=true&timezone=auto",
            timeout=6,
        )
        if r.status_code == 200:
            t = (r.json().get("current_weather", {}) or {}).get("temperature")
            if t is not None:
                return f" Right now it's {round(t)}\u00b0C outside."
    except Exception:
        pass
    return " Your system is running smoothly, by the way."

@app.route("/api/greeting", methods=["GET"])
def api_greeting():
    """Rich, natural startup greeting: time-of-day + your name + weather +
    live system status, flavored by the active mode. Returns both display text
    and a short spoken line so voice triggers at the perfect moment on boot."""
    # Single-voice rule: the UI is claiming the boot greeting, so the
    # proactive server thread must stay silent (see tts_engine voice bus).
    greeting_handled_by_ui = tts_engine.boot_greeting_claimed()
    tts_engine.claim_boot_greeting()
    now = datetime.datetime.now(); h = now.hour
    greet = "Good night" if h < 6 else "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening" if h < 21 else "Good night"
    m = get_mode(); mp = MODE_PROFILES[m]
    settings = load_json(DATA_DIR / "settings.json", {"latitude": 26.8467, "longitude": 80.9462, "cityName": "Lucknow"})
    name = settings.get("name", "") or ""
    boss_phrase = f", {name}" if name else f", {mp['boss'].lower()}"

    # Greeting is single-sourced from settings.json so the user can change it
    # anytime. The {mode} placeholder is filled per active persona.
    mode_word = {"friday": "in FRIDAY mode, Boss",
                 "jarvis": "in JARVIS mode, Sir",
                 "ultron": "in ULTRON mode, Boss"}.get(m, "Boss")
    custom_greet = (settings.get("greeting") or "").strip()
    energy_lines = {
        "friday": f"Hey Boss, I'm FRIDAY. {greet}! All systems green and my engines are warm — what are we diving into today, Boss?",
        "jarvis": f"{greet}, sir. All systems are fully operational. Shall we review today's briefing, or do you have directives for me first?",
        "ultron": f"ULTRON online. {greet}. Tactical systems engaged. Awaiting your directive.",
    }
    if custom_greet:
        text = custom_greet.format(mode=mode_word, name=name, time=greet)
    else:
        text = (energy_lines.get(m, energy_lines["friday"]) + generate_forecast_line(m))
    text = text.replace("{name}", name).replace("{time}", greet)
    return jsonify({"success": True, "text": text, "speech": text, "mode": m,
                    "boot_greeted": tts_engine.boot_greeting_done(),
                    "ui_claimed": greeting_handled_by_ui})

@app.route("/api/briefing")
def api_briefing():
    now = datetime.datetime.now(); h = now.hour
    greet = "Good night" if h < 6 else "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening" if h < 21 else "Good night"
    vault = load_json(DATA_DIR / "vault.json", {"entries": []})
    m = get_mode(); mp = MODE_PROFILES[m]
    briefing = {"greeting": f"{greet}, {mp['boss']}", "date": now.strftime("%A, %B %d, %Y"), "time": now.strftime("%I:%M %p"), "system": f"CPU {system_cache['cpu']}%, RAM {system_cache['ram']}%", "battery": f"{system_cache['battery']}%", "vaultCount": len(vault.get("entries", [])), "mode": m, "modeName": mp["name"]}
    if m == "jarvis":
        try:
            st = agency_client.agency_state()
            if st:
                s = agency_client.summarize_state(st)
                briefing["agency"] = {
                    "online": True,
                    "agents_online": s["agents_online"],
                    "agents_working": s["agents_working"],
                    "leads_today": s["leads_today"],
                    "total_leads": s["total_leads"],
                    "pending_approval": s["pending_approval"],
                    "sent_outreach": s["sent_outreach"],
                    "missions_running": s["missions_running"],
                    "interested": s["interested"],
                    "meetings": s["meetings"],
                    "brief": f"Your Agency OS has {s['agents_online']} agents online, {s['agents_working']} working, {s['leads_today']} leads today ({s['total_leads']} total), {s['pending_approval']} pending outreach approval, {s['sent_outreach']} sent.",
                }
        except Exception:
            briefing.setdefault("agency", {"online": False})
    return jsonify({"success": True, "briefing": briefing})

@app.route("/api/vault", methods=["GET", "POST", "DELETE"])
def api_vault():
    vault = load_json(DATA_DIR / "vault.json", {"entries": []})
    if request.method == "GET": return jsonify({"success": True, "data": vault.get("entries", [])})
    if request.method == "DELETE":
        vid = request.args.get("id")
        if vid: vault["entries"] = [e for e in vault.get("entries", []) if e.get("id") != vid]; save_json(DATA_DIR / "vault.json", vault); return jsonify({"success": True})
        vault["entries"] = []; save_json(DATA_DIR / "vault.json", vault); return jsonify({"success": True})
    d = request.get_json(force=True, silent=True) or {}; entry = {"id": str(int(time.time() * 1000)), "text": d.get("text", ""), "date": datetime.datetime.now().strftime("%b %d, %Y")}
    vault.setdefault("entries", []).append(entry); save_json(DATA_DIR / "vault.json", vault); return jsonify({"success": True, "data": entry})

@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET": return jsonify({"success": True, "settings": load_json(DATA_DIR / "settings.json", {"latitude": 26.8467, "longitude": 80.9462, "cityName": "Lucknow"})})
    d = request.get_json(force=True, silent=True) or {}; s = load_json(DATA_DIR / "settings.json", {"latitude": 26.8467, "longitude": 80.9462, "cityName": "Lucknow"})
    for k in ["latitude", "longitude", "cityName"]:
        if k in d: s[k] = d[k]
    # Behaviour / permission preferences (permanent app defaults).
    for k in ("auto_approve_phones", "proactive", "wake_word"):
        if k in d: s[k] = bool(d[k])
    for k in ("agency_url", "whatsapp_number"):
        if k in d and isinstance(d[k], str): s[k] = d[k].strip()
    # Secrets live in the git-ignored keys file.
    if "discord_webhook_url" in d:
        keys = load_json(DATA_DIR / "keys.json", {})
        keys["discord_webhook_url"] = str(d["discord_webhook_url"]).strip()
        save_json(DATA_DIR / "keys.json", keys)
    if "autostart" in d:
        _autostart_set(bool(d["autostart"]))
        s["autostart"] = bool(d["autostart"])
    save_json(DATA_DIR / "settings.json", s); return jsonify({"success": True, "settings": s})

@app.route("/api/settings/keys", methods=["POST"])
def api_settings_keys():
    d = request.get_json(force=True, silent=True) or {}
    keys = load_json(DATA_DIR / "keys.json", {})
    for k in ["grok_api_key", "gemini_api_key"]:
        if k in d and isinstance(d[k], str):
            keys[k] = d[k].strip()
    save_json(DATA_DIR / "keys.json", keys)
    return jsonify({"success": True})

@app.route("/api/settings/keys", methods=["GET"])
def api_get_settings_keys():
    keys = load_json(DATA_DIR / "keys.json", {})
    masked = {}
    for k, v in keys.items():
        if isinstance(v, str) and len(v) > 10:
            masked[k] = f"{v[:6]}...{v[-4:]}"
        else:
            masked[k] = "SET" if v else "NOT SET"
    return jsonify({"success": True, "keys": masked})


@app.route("/api/services")
def api_services():
    """Connected-services dashboard: email / discord / whatsapp / agency /
    autostart / wake — the 'permission health' view for the Permanent App."""
    try:
        return jsonify({"success": True, **{"services": _services_status()}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/gemini-keys")
def api_gemini_keys():
    key = get_gemini_key(); masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "No key"
    return jsonify({"success": True, "totalKeys": 1 if key else 0, "activeKeys": 1 if key else 0, "currentKeyIndex": 0, "keys": [{"masked": masked, "active": bool(key)}]})

@app.route("/api/gemini-quota")
def api_gemini_quota():
    key = get_gemini_key(); masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "No key"
    g = groq_usage_snapshot()
    return jsonify({"success": True, "isKeyPresent": bool(key), "keysCount": 1 if key else 0, "currentKey": masked, "model": "gemini-2.0-flash", "rpm": {"current": 0, "max": 15}, "tpm": {"current": 0, "max": 1000000}, "rpd": {"current": 0, "max": 1500}, "status": "HEALTHY & ACTIVE" if key else "MISSING_API_KEY", "keys": [], "groq": g})

@app.route("/api/groq-usage")
def api_groq_usage():
    return jsonify(groq_usage_snapshot())

@app.route("/api/training", methods=["GET", "POST", "DELETE"])
def api_training():
    mem = load_json(DATA_DIR / "offline_memory.json", {"name": "BOSS", "tone": "witty", "rules": [], "macros": [], "contacts": [], "facts": []})
    if request.method == "GET": return jsonify({"success": True, "training": mem})
    if request.method == "DELETE":
        d = request.get_json(force=True, silent=True) or {}; t = d.get("type", ""); trigger = d.get("trigger", d.get("topic", ""))
        key = "rules" if t == "rule" else "macros" if t == "macro" else "facts" if t == "fact" else ""
        if key and key in mem: mem[key] = [x for x in mem[key] if x.get("trigger", x.get("topic", "")) != trigger]
        save_json(DATA_DIR / "offline_memory.json", mem); return jsonify({"success": True, "training": mem})
    d = request.get_json(force=True, silent=True) or {}; t = d.get("type", "")
    if t == "profile": mem["name"] = d.get("name", mem.get("name", "BOSS")); mem["tone"] = d.get("tone", mem.get("tone", "witty"))
    elif t == "rule": mem.setdefault("rules", []).append({"trigger": d.get("trigger", ""), "reply": d.get("reply", "")})
    elif t == "macro": mem.setdefault("macros", []).append({"trigger": d.get("trigger", ""), "commands": d.get("commands", [])})
    elif t == "fact": mem.setdefault("facts", []).append({"topic": d.get("topic", ""), "content": d.get("content", "")})
    save_json(DATA_DIR / "offline_memory.json", mem); return jsonify({"success": True, "training": mem})

@app.route("/api/news")
def api_news():
    try:
        import requests as _req; r = _req.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=5)
        if r.status_code == 200:
            ids = r.json()[:8]; stories = []
            for sid in ids:
                sr = _req.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5)
                if sr.status_code == 200: stories.append({"title": sr.json().get("title", ""), "url": sr.json().get("url", "")})
            return jsonify({"success": True, "stories": stories})
    except: pass
    return jsonify({"success": True, "stories": []})

@app.route("/api/jokes")
def api_jokes(): return jsonify({"success": True, "joke": random.choice(OFFLINE_JOKES)})

@app.route("/api/quotes")
def api_quotes(): return jsonify({"success": True, "quote": random.choice(OFFLINE_QUOTES)})

@app.route("/api/facts")
def api_facts(): return jsonify({"success": True, "fact": random.choice(OFFLINE_FACTS)})

@app.route("/api/riddles")
def api_riddles(): return jsonify({"success": True, "riddle": random.choice(OFFLINE_RIDDLES)})

@app.route("/api/fact")
def api_fact(): return jsonify({"success": True, "fact": random.choice(OFFLINE_FACTS)})

@app.route("/api/quote")
def api_quote(): return jsonify({"success": True, "quote": random.choice(OFFLINE_QUOTES)})

@app.route("/api/crypto")
def api_crypto():
    try: import requests as _req; r = _req.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,dogecoin&vs_currencies=usd", timeout=10); return jsonify({"success": True, "prices": r.json()})
    except: return jsonify({"success": True, "prices": {}})

@app.route("/api/ip-info")
def api_ip_info():
    try: import requests as _req; r = _req.get("https://ipapi.co/json/", timeout=5); d = r.json(); return jsonify({"success": True, "ip": d.get("ip", ""), "city": d.get("city", ""), "country": d.get("country_name", ""), "org": d.get("org", "")})
    except: return jsonify({"success": True, "ip": "", "city": "", "country": "", "org": ""})

@app.route("/api/dictionary")
def api_dictionary():
    word = request.args.get("word", "")
    if not word: return jsonify({"success": False, "message": "word required"})
    try:
        import requests as _req; r = _req.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=5)
        if r.status_code == 200: d = r.json(); m = d[0].get("meanings", [{}])[0]; defs = m.get("definitions", [])
        if defs: return jsonify({"success": True, "word": word, "partOfSpeech": m.get("partOfSpeech", ""), "definition": defs[0].get("definition", "")})
    except: pass
    return jsonify({"success": False, "message": "Word not found"})

@app.route("/api/local-ip")
def api_local_ip():
    """Best-effort LAN IP. Tries the UDP socket trick, then the hostname's
    primary IPv4, then a plain 127.0.0.1 fallback. Returns the mobile URL the
    phone should open (plain http, same port)."""
    ip = None
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = None
    if not ip or ip.startswith("127."):
        try:
            import socket as _sk
            host = _sk.gethostname()
            for info in _sk.getaddrinfo(host, None, _sk.AF_INET):
                addr = info[4][0]
                if not addr.startswith("127."):
                    ip = addr
                    break
        except Exception:
            pass
    if not ip:
        ip = "127.0.0.1"
    return jsonify({"success": True, "ip": ip, "mobileUrl": f"http://{ip}:3005/mobile.html"})

@app.route("/api/remote-status")
def api_remote_status(): return jsonify({"success": True, "remoteMode": False, "hostname": platform.node()})

@app.route("/api/spotify/status")
def api_spotify_status():
    try:
        import app_integrations
        st = app_integrations.spotify_status()
        return jsonify({"success": True, **st})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/devices")
def api_devices():
    now = datetime.datetime.now()
    out = []
    for d in activeDevices.values():
        dev = dict(d)
        last = dev.get("lastActive", "")
        try:
            last_dt = datetime.datetime.fromisoformat(last) if last else None
        except Exception:
            last_dt = None
        alive = last_dt is not None and (now - last_dt).total_seconds() < 45
        dev["connected"] = bool(alive) and dev.get("status") == "approved"
        # `linked` = approved and therefore selectable even if the heartbeat is
        # briefly stale (background-tab throttling used to disarm the panel).
        dev["linked"] = dev.get("status") == "approved"
        out.append(dev)
    return jsonify({"success": True, "devices": out})

@app.route("/api/mobile-stats")
def api_mobile_stats():
    linked = [d for d in activeDevices.values() if d.get("status") == "approved"]
    return jsonify({"success": True, "linkedDevices": len(linked), "devices": linked, "battery": system_cache["battery"], "connection": "online"})

@app.route("/api/device/register", methods=["POST"])
def api_device_register():
    d = request.get_json(force=True, silent=True) or {}; did = d.get("deviceId", "")
    if not did: return jsonify({"success": False, "message": "deviceId required"})
    auto = load_json(DATA_DIR / "settings.json", {}).get("auto_approve_phones", True) is not False
    if did not in activeDevices:
        activeDevices[did] = {"deviceId": did, "os": d.get("os", "Unknown"), "browser": d.get("browser", "Unknown"), "ip": request.remote_addr, "status": "approved" if auto else "pending", "lastActive": datetime.datetime.now().isoformat()}
    else:
        activeDevices[did]["ip"] = request.remote_addr
        activeDevices[did].setdefault("os", d.get("os", "Unknown"))
        activeDevices[did].setdefault("browser", d.get("browser", "Unknown"))
        activeDevices[did]["lastActive"] = datetime.datetime.now().isoformat()
        if activeDevices[did].get("status") == "pending" and auto:
            activeDevices[did]["status"] = "approved"
    _save_devices()
    return jsonify({"success": True, "device": activeDevices[did]})

@app.route("/api/device/status/<did>", methods=["GET", "POST"])
def api_device_status(did):
    if request.method == "POST":
        d = request.get_json(force=True, silent=True) or {}
        dev = activeDevices.get(did)
        if dev:
            dev["lastActive"] = datetime.datetime.now().isoformat()
            if d.get("battery") is not None:
                dev["battery"] = round(min(100, max(0, int(d["battery"]))))
            if d.get("signal") is not None:
                dev["signal"] = str(d["signal"])[:40]
            if d.get("network") is not None:
                dev["network"] = str(d["network"])[:40]
            _save_devices()
        return jsonify({"success": True, "status": dev.get("status", "unknown") if dev else "unknown"})
    dev = activeDevices.get(did, {})
    return jsonify({"success": True, "status": dev.get("status", "unknown"), "os": dev.get("os", ""), "browser": dev.get("browser", ""), "ip": dev.get("ip", ""), "battery": dev.get("battery"), "signal": dev.get("signal"), "lastActive": dev.get("lastActive", "")})

@app.route("/api/device/approve", methods=["POST"])
def api_device_approve():
    d = request.get_json(force=True, silent=True) or {}; did = d.get("deviceId", "")
    if did in activeDevices:
        activeDevices[did]["status"] = d.get("status", "")
        _save_devices()
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

@app.route("/api/device/command/send", methods=["POST"])
def api_device_cmd_send():
    d = request.get_json(force=True, silent=True) or {}
    pendingDeviceCommands.setdefault(d.get("deviceId", ""), []).append({"action": d.get("action", ""), "value": d.get("value", ""), "timestamp": int(time.time() * 1000)})
    return jsonify({"success": True})

@app.route("/api/device/notify-pc", methods=["POST"])
def api_device_notify_pc():
    """Receive a push notification from the phone and display it on the PC console."""
    d = request.get_json(force=True, silent=True) or {}
    title = d.get("title", "PHONE")
    body = d.get("body", "")
    did = d.get("deviceId", "")
    pc_notifs = load_json(DATA_DIR / "pc_notifications.json", {"items": []})
    pc_notifs.setdefault("items", []).insert(0, {"title": title, "body": body, "from": did, "time": int(time.time()*1000)})
    pc_notifs["items"] = pc_notifs["items"][:30]
    save_json(DATA_DIR / "pc_notifications.json", pc_notifs)
    if did in activeDevices:
        activeDevices[did].setdefault("pc_notifications", []).append({"title": title, "body": body, "time": int(time.time()*1000)})
    return jsonify({"success": True, "message": "Notification forwarded to PC"})

@app.route("/api/pc-notifications")
def api_pc_notifications():
    pc = load_json(DATA_DIR / "pc_notifications.json", {"items": []})
    return jsonify({"success": True, "notifications": pc.get("items", [])})

@app.route("/api/device/command/poll/<did>")
def api_device_cmd_poll(did):
    # Opening the phone page counts as activity so it re-links instantly.
    if did in activeDevices:
        activeDevices[did]["lastActive"] = datetime.datetime.now().isoformat()
    return jsonify({"success": True, "commands": pendingDeviceCommands.pop(did, [])})

@app.route("/api/device/location", methods=["POST"])
def api_device_location():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify({"success": True, "message": "Location received"})

@app.route("/api/device/notifications", methods=["POST"])
def api_device_notifications():
    d = request.get_json(force=True, silent=True) or {}
    did = d.get("deviceId", "unknown")
    notifs = d.get("notifications", [])
    if notifs:
        activeDevices.setdefault(did, {}).setdefault("notifications", []).extend(notifs)
        activeDevices[did]["notifications"] = activeDevices[did].get("notifications", [])[-50:]
    return jsonify({"success": True, "message": "Notifications synced"})

@app.route("/api/screenshot-base64")
def api_screenshot_base64():
    """Return a live screenshot of the primary screen as base64 JPEG for phone mirroring."""
    import base64
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        import io
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=50)
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return jsonify({"success": True, "image": b64, "width": img.width, "height": img.height})
    except Exception:
        try:
            fp = str(DATA_DIR / "_live_screen.png")
            subprocess.run(["powershell", "-command", f"Add-Type -AssemblyName System.Windows.Forms; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $gfx = [System.Drawing.Graphics]::FromImage($bmp); $gfx.CopyFromScreen(0, 0, 0, 0, $bmp.Size); $bmp.Save('{fp}')"], capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            import base64
            with open(fp, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            return jsonify({"success": True, "image": b64, "width": 0, "height": 0})
        except Exception as e2:
            return jsonify({"success": False, "error": str(e2)})

@app.route("/api/clipboard-sync", methods=["GET", "POST"])
def api_clipboard_sync():
    """Bidirectional clipboard sync between phone and PC."""
    if request.method == "GET":
        try:
            r = subprocess.run(["powershell", "-command", "Get-Clipboard"], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            return jsonify({"success": True, "text": r.stdout.strip()})
        except:
            return jsonify({"success": False})
    d = request.get_json(force=True, silent=True) or {}
    txt = d.get("text", "")
    if txt:
        try:
            subprocess.run(["powershell", "-command", f"Set-Clipboard -Value '{txt.replace(chr(39), chr(39)+chr(39))}'"], capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            return jsonify({"success": True, "message": "Clipboard synced"})
        except:
            return jsonify({"success": False})
    return jsonify({"success": False})

@app.route("/api/notifications-forward", methods=["GET"])
def api_notifications_forward():
    """Get pending notifications from phone to display on PC."""
    did = request.args.get("deviceId", "")
    notifs = activeDevices.get(did, {}).pop("pc_notifications", [])
    return jsonify({"success": True, "notifications": notifs})

@app.route("/api/notifications-push", methods=["POST"])
def api_notifications_push():
    """PC pushes a notification to a linked phone."""
    d = request.get_json(force=True, silent=True) or {}
    did = d.get("deviceId", "")
    title = d.get("title", "JENNY")
    body = d.get("body", "")
    if did in activeDevices:
        activeDevices[did].setdefault("notifications", []).append({"title": title, "body": body, "time": int(time.time()*1000)})
    return jsonify({"success": True})

@app.route("/api/device/sms/send", methods=["POST"])
def api_device_sms():
    """Queue an SMS compose command to a linked phone.

    The phone page can't touch the radio directly, but it CAN open the native
    SMS composer via an sms:<number>?body=<text> intent, so we hand the target
    phone an `sms` command through the same poll bus used for calls/toasts.
    """
    d = request.get_json(force=True, silent=True) or {}
    did = d.get("deviceId", "")
    number = str(d.get("number") or d.get("to") or "").strip()
    body = str(d.get("body") or d.get("message") or d.get("text") or "").strip()
    if not number:
        return jsonify({"success": False, "error": "No phone number given to send SMS to."})
    dev = activeDevices.get(did)
    if did and dev and dev.get("status") != "approved":
        return jsonify({"success": False, "error": "Device not approved"})
    if not did or not activeDevices.get(did):
        approved = [x for x, dv in activeDevices.items() if dv.get("status") == "approved"]
        if not approved:
            return jsonify({"success": False, "error": "No approved phone linked."})
        did = approved[0]
    pendingDeviceCommands.setdefault(did, []).append({
        "action": "sms",
        "value": json.dumps({"number": number, "body": body}, ensure_ascii=False),
        "timestamp": int(time.time() * 1000),
    })
    return jsonify({"success": True, "message": f"SMS composer opening for {number} on the phone."})

# =====================================================================
# PHONE->PC VOICE CALL BRIDGE ("dial JENNY", talk, she answers from the PC)
# =====================================================================
call_state = {
    "active": False,
    "device_id": "",
    "caller_label": "",
    "started_at": 0.0,
    "last_activity": 0.0,
    "transcript": [],   # [{role, text, ts}]
}


def _call_bump_activity():
    call_state["last_activity"] = time.time()


def _call_append(role: str, text: str):
    call_state["transcript"].append({"role": role, "text": text, "ts": time.time()})
    call_state["transcript"] = call_state["transcript"][-40:]
    _call_bump_activity()


@app.route("/api/call/start", methods=["POST"])
def api_call_start():
    """Start a call session from a linked phone. Rings the dashboard."""
    d = request.get_json(force=True, silent=True) or {}
    did = d.get("deviceId", "")
    label = d.get("callerLabel", "Phone")
    dev = activeDevices.get(did)
    if dev and dev.get("status") == "approved":
        call_state.update({
            "active": True,
            "device_id": did,
            "caller_label": label,
            "started_at": time.time(),
            "last_activity": time.time(),
            "transcript": [{"role": "system", "text": f"Incoming call from {label}", "ts": time.time()}],
        })
        _call_append("system", f"Call connected — {label} is on the line, Boss.")
        tts_speak(f"Phone call connected. {label} is on the line, Boss.")
        return jsonify({"success": True, "call": _call_status_payload()})
    return jsonify({"success": False, "error": "Device not approved"})


@app.route("/api/call/talk", methods=["POST"])
def api_call_talk():
    """Accept text or raw audio from the phone; transcribe -> brain -> reply.

    Returns the same shape as /api/chat plus `speechAudio` (a URL the phone
    plays back so JENNY's neural voice comes out of the phone speaker).
    """
    audio = request.files.get("audio") if request.files else None
    text = ""
    if audio is not None:
        raw = audio.read()
        filename = audio.filename or "call.webm"
        if not raw:
            return jsonify({"success": False, "error": "Empty audio"}), 400
        mime = audio.mimetype or "audio/webm"
        text = speech_stt.transcribe_groq_file(raw, filename, mime) or ""
    else:
        d = request.get_json(force=True, silent=True) or {}
        text = d.get("text", "") or ""
    if not text.strip():
        return jsonify({"success": False, "error": "No speech recognized", "text": ""}), 200
    _call_append("phone", text.strip())
    reply = local_command_router(text.strip())
    if not reply:
        reply = grok_chat(text.strip(), chatHistory) or offline_reply(text.strip()) or {"text": "I'm offline, Boss.", "speech": "I'm offline, Boss."}
    speech = reply.get("speech") or reply.get("text") or ""
    _call_append("jenny", speech)
    audio_url = f"/api/speak?text={urllib.parse.quote(speech[:6000])}" if speech else None
    return jsonify({"success": True, "text": text.strip(), "reply": reply, "speechAudio": audio_url})


@app.route("/api/call/hangup", methods=["POST"])
def api_call_hangup():
    """End the call (either side)."""
    d = request.get_json(force=True, silent=True) or {}
    did = d.get("deviceId", "")
    if call_state["active"]:
        _call_append("system", "Call ended.")
        call_state.update({"active": False, "device_id": ""})
    return jsonify({"success": True})


@app.route("/api/call/status")
def api_call_status():
    return jsonify({"success": True, "call": _call_status_payload()})


def _call_status_payload() -> dict:
    dur = 0.0
    if call_state["active"] and call_state["started_at"]:
        dur = time.time() - call_state["started_at"]
    return {
        "active": call_state["active"],
        "deviceId": call_state["device_id"],
        "callerLabel": call_state["caller_label"],
        "duration": dur,
        "idle": (time.time() - call_state["last_activity"]) if call_state["last_activity"] else 0,
        "transcript": call_state["transcript"],
    }

@app.route("/api/permissions-check")
def api_permissions_check(): return jsonify({"success": True, "platform": sys.platform, "permissions": {"accessibility": {"status": "not_applicable"}, "automation": {"status": "not_applicable"}, "fullDiskAccess": {"status": "not_applicable"}}})

@app.route("/api/reverse-geocode")
def api_reverse_geocode():
    lat = request.args.get("lat", ""); lon = request.args.get("lon", "")
    if not lat or not lon: return jsonify({"success": False})
    try:
        import requests as _req; r = _req.get(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json", timeout=5, headers={"User-Agent": "JENNY/2.0"})
        if r.status_code == 200: return jsonify({"success": True, "cityName": r.json().get("address", {}).get("city", "Unknown")})
    except: pass
    return jsonify({"success": False})

@app.route("/api/system")
def api_system(): return jsonify({"success": True, "data": {"battery": {"percent": system_cache["battery"], "state": "charging" if system_cache["charging"] else "discharging"}, "uptime": f"{system_cache['uptime']} seconds", "volume": 50, "brightness": 0.8, "ip": "127.0.0.1", "os": f"{platform.system()} {platform.release()}", "cpu": system_cache["cpu"], "ram": system_cache["ram"]}})

@app.route("/api/tts", methods=["POST"])
def api_tts():
    d = request.get_json(force=True, silent=True) or {}; text = d.get("text", "")
    if text:
        threading.Thread(target=tts_speak, args=(text,), daemon=True).start()
    return jsonify({"success": True})

@app.route("/api/voice-info")
def api_voice_info():
    """Report the active TTS voice per mode (for the voice badge / preview UI)."""
    try:
        voices = _voice_desc(None)
        voices.update({"__engine__": tts_engine.voice_map()})
        return jsonify({"success": True, "voices": voices, "mode": get_mode()})
    except Exception:
        return jsonify({"success": False, "message": "Voice info unavailable"})

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
                bookmarks.append({"name": node.get("name", ""), "url": node.get("url", ""), "path": path})
            elif node.get("type") == "folder":
                folder_name = node.get("name", "")
                for child in node.get("children", []):
                    walk(child, f"{path}/{folder_name}" if path else folder_name)
        roots = data.get("roots", {})
        for key in ["bookmark_bar", "other", "synced"]:
            if key in roots: walk(roots[key])
        return jsonify({"success": True, "bookmarks": bookmarks[:100], "total": len(bookmarks)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "bookmarks": []})

@app.route("/api/open-chrome", methods=["GET", "POST"])
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
            if chrome:
                subprocess.Popen([chrome, url])
            else:
                webbrowser.open(url)
            return jsonify({"success": True, "message": f"Opened {url}"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": False, "error": "No URL"})

@app.route("/api/emails")
def api_emails():
    """Fetch the latest emails via IMAP (or the Outlook app fallback)."""
    try:
        import email_integration
        res = email_integration.fetch_emails(int(request.args.get("count", 8)))
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "emails": [], "message": f"Email module error: {e}"})

@app.route("/api/timers")
def api_timers(): return jsonify({"success": True, "timers": []})

@app.route("/api/stt/mics")
def api_stt_mics():
    """List detected microphone devices (index + name)."""
    import speech_stt
    return jsonify({"success": True, "mics": speech_stt.get_mics()})

@app.route("/api/stt/record", methods=["POST"])
def api_stt_record():
    """Record the microphone for N seconds and transcribe it.
    Body: {seconds, device?, language?}. Returns {text, engine} so the UI
    never has to rely on the flaky browser Web Speech recognizer. Language is
    pinned to English or Hindi only."""
    import speech_stt
    d = request.get_json(force=True, silent=True) or {}
    seconds = max(1, min(int(d.get("seconds", 5)), 12))
    device = d.get("device")
    if device is not None:
        try:
            device = int(device)
        except (TypeError, ValueError):
            device = None
    language = str(d.get("language", "") or "").lower().strip()
    result = speech_stt.record_and_transcribe(seconds, device=device, language=language)
    return jsonify(result)

@app.route("/api/stt/live/start", methods=["POST"])
def api_stt_live_start():
    """Open a streaming STT session. Returns {sessionId} — poll
    /api/stt/live/status/<sid> for live interim + final text."""
    import speech_stt
    d = request.get_json(force=True, silent=True) or {}
    seconds = max(3, min(int(d.get("seconds", 12)), 30))
    device = d.get("device")
    if device is not None:
        try:
            device = int(device)
        except (TypeError, ValueError):
            device = None
    language = str(d.get("language", "") or "").lower().strip()
    res = speech_stt.start_live_session(seconds, device=device, language=language)
    return jsonify(res)

@app.route("/api/stt/live/status/<sid>")
def api_stt_live_status(sid):
    import speech_stt
    res = speech_stt.live_status(sid)
    if isinstance(res, tuple):
        return jsonify(res[0]), res[1]
    return jsonify(res)

@app.route("/api/stt/live/stop/<sid>", methods=["POST"])
def api_stt_live_stop(sid):
    import speech_stt
    res = speech_stt.stop_live_session(sid)
    if isinstance(res, tuple):
        return jsonify(res[0]), res[1]
    return jsonify(res)

@app.route("/api/stt/language", methods=["GET", "POST"])
def api_stt_language():
    """Get or set the speech-recognition language (en | hi only)."""
    import speech_stt
    settings = load_json(DATA_DIR / "settings.json", {})
    if request.method == "POST":
        d = request.get_json(force=True, silent=True) or {}
        lang = str(d.get("language", "") or "").lower().strip()
        if lang not in speech_stt.ALLOWED_STT_LANGS:
            return jsonify({"success": False, "error": "Language must be 'en' or 'hi'"}), 400
        settings["stt_language"] = lang
        save_json(DATA_DIR / "settings.json", settings)
        return jsonify({"success": True, "language": lang})
    return jsonify({"success": True, "language": speech_stt.get_stt_language(),
                    "allowed": list(speech_stt.ALLOWED_STT_LANGS)})

@app.route("/api/stt/status")
def api_stt_status():
    """STT capability report (mics + which transcription engines are ready)."""
    import speech_stt
    mics = speech_stt.get_mics()
    return jsonify({
        "success": True,
        "mics": mics,
        "count": len(mics),
        "whisper": bool(speech_stt._groq_key() and speech_stt.transcribe_groq is not None),
        "engine": "groq-whisper + google-fallback",
    })

@app.route("/api/toggle-mic")
def api_toggle_mic():
    return jsonify({"success": True, "mode": "push", "stt": "/api/stt/record"})

@app.route("/api/toggle-mic-poll")
def api_toggle_mic_poll():
    return jsonify({"success": True, "lastToggle": int(time.time() * 1000)})

@app.route("/api/active-apps")
def api_active_apps():
    try:
        r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        apps = list(set(line.strip('"').split('","')[0] for line in r.stdout.strip().split("\n") if line.strip()))[:15]
        return jsonify({"success": True, "apps": apps, "message": f"{len(apps)} active applications."})
    except: return jsonify({"success": True, "apps": [], "message": "Cannot list apps"})

@app.route("/api/notifications")
def api_notifications(): return jsonify({"success": True, "notifications": []})

@app.route("/api/discord-dms")
def api_discord_dms(): return jsonify({"success": True, "discord_dms": []})

@app.route("/api/remote-mode", methods=["POST"])
def api_remote_mode(): return jsonify({"success": True, "remoteMode": False})

@app.route("/api/wake", methods=["POST"])
def api_wake(): return jsonify({"success": True})

@app.route("/api/wake/status")
def api_wake_status():
    import speech_stt
    st = speech_stt.wake_status()
    st["success"] = True
    return jsonify(st)

@app.route("/api/wake/toggle", methods=["POST"])
def api_wake_toggle():
    """Enable/disable the always-on server-side wake word listener and persist
    the choice so boot restores it automatically."""
    import speech_stt
    d = request.get_json(force=True, silent=True) or {}
    on = d.get("on")
    if on is None:
        on = not speech_stt.wake_listener_active()
    settings = load_json(DATA_DIR / "settings.json", {})
    settings["wake_word"] = bool(on)
    save_json(DATA_DIR / "settings.json", settings)
    if on:
        started = speech_stt.start_wake_listener(_on_wake_detected)
        return jsonify({"success": True, "on": started})
    speech_stt.stop_wake_listener()
    return jsonify({"success": True, "on": False})

@app.route("/api/wake/restart", methods=["POST"])
def api_wake_restart():
    """Force the wake listener to re-open its microphone stream (self-heal)."""
    import speech_stt as _stt
    ok = _stt.wake_restart()
    return jsonify({"success": True, "restarted": ok, **(_stt.wake_status())})

_WAKE_EVENTS = []
_WAKE_EVENTS_LOCK = threading.Lock()

def _ui_feed(kind: str, text: str, command: dict | None = None, source: str = "") -> None:
    """Append a UI event for the dashboard output box. This single feed powers
    the wake-word conversation AND phone-originated commands, so everything the
    assistant does is visible in the chat even when it happened elsewhere."""
    if not text:
        return
    try:
        with _WAKE_EVENTS_LOCK:
            ev = {"kind": kind, "text": str(text)[:4000]}
            if command:
                ev["command"] = command
            if source:
                ev["source"] = source
            _WAKE_EVENTS.append(ev)
    except Exception:
        pass

@app.route("/api/wake/events")
def api_wake_events():
    """Pop all accumulated server-side wake conversation events (for the GUI
    to render bubbles) without blocking the wake listener."""
    with _WAKE_EVENTS_LOCK:
        evts = _WAKE_EVENTS[:]
        _WAKE_EVENTS.clear()
    return jsonify({"success": True, "events": evts})

def _on_wake_detected(text: str, phrase: str):
    """Server-side wake-word handler: ack, capture the spoken command, route it
    through the normal chat pipeline, speak the reply and surface events."""
    try:
        import speech_stt
        mode = _wake_mode_for_phrase(phrase)
        if mode:
            set_mode(mode)
        with _WAKE_EVENTS_LOCK:
            _WAKE_EVENTS.append({"kind": "wake", "text": phrase})
            _WAKE_EVENTS.append({"kind": "user", "text": phrase})
        boss = MODE_PROFILES.get(mode or 'friday', MODE_PROFILES['friday'])['boss']
        acks = {
            "jarvis": [
                f"Yes, {boss}?",
                f"I'm listening, {boss}.",
                f"Go ahead, {boss}.",
                f"At your service, {boss}.",
            ],
            "friday": [
                f"Yeah {boss}? I'm all ears!",
                f"On it, {boss}. What've you got?",
                f"I'm here, {boss}. Lay it on me!",
                f"Go ahead, {boss} — what's up?",
            ],
            "ultron": [
                f"Directive received, {boss}.",
                f"Ready, {boss}.",
                f"Awaiting instruction, {boss}.",
            ],
        }.get(mode or 'friday', [
            f"Yes, {boss}?",
            f"I'm here, {boss}. Go ahead.",
        ])
        tts_engine.speak(random.choice(acks), mode or "friday", use_chime=True)
        res = speech_stt.record_and_transcribe(8, language=speech_stt.get_stt_language())
        if not res.get("success"):
            err = res.get("error", "I'm here. Go ahead.")
            speech_stt.wake_cooldown(3.0)
            tts_engine.speak(f"My apologies, {MODE_PROFILES.get(mode or 'friday', MODE_PROFILES['friday'])['boss']}. {err}", mode or "friday")
            with _WAKE_EVENTS_LOCK:
                _WAKE_EVENTS.append({"kind": "assistant", "text": err})
            return
        command = res.get("text", "").strip()
        if not command:
            tts_engine.speak("I didn't catch that. Please say it again, Boss.", mode or "friday")
            return
        with _WAKE_EVENTS_LOCK:
            _WAKE_EVENTS.append({"kind": "user", "text": command})
        tts_engine.stop_speech()
        reply = _assistant_reply(command)
        cmd = (reply or {}).get("command", {})
        # Execute control commands headlessly right here; a live GUI drains the
        # same command through its own dispatch (dedup by event kind = 'cmd').
        if cmd and not tts_engine.ui_client_active():
            _execute_control_command(cmd)
        with _WAKE_EVENTS_LOCK:
            ev = {"kind": "assistant", "text": reply.get("text", "")}
            if cmd:
                ev["command"] = cmd
            _WAKE_EVENTS.append(ev)
        tts_engine.speak((reply or {}).get("speech") or (reply or {}).get("text", ""), mode or "friday")
    except Exception:
        import traceback
        traceback.print_exc()


def _wake_mode_for_phrase(phrase: str) -> str:
    p = (phrase or "").lower()
    if "ultron" in p:
        return "ultron"
    if "jarvis" in p:
        return "jarvis"
    return "friday"

_AGENCY_SNAPSHOT = {"replies": 0, "pending": 0, "interested": 0, "online": False}
_AGENCY_WATCH_LOCK = threading.Lock()

def _agency_alert_watcher() -> None:
    """Poll Agency OS and speak + show a dashboard note when there is NEW work:
    more replies, freshly interested leads, or new pending outreach. This gives
    J.A.R.V.I.S a live agency voice so the business dashboard 'talks' too."""
    while True:
        time.sleep(120)
        if not proactive.proactive_enabled():
            continue
        try:
            url = (load_json(DATA_DIR / "settings.json", {}).get("agency_url") or "http://localhost:3200").strip().rstrip("/")
            agency_client.AGENCY_BASE = url
            st = agency_client.agency_state(cached=0)
            s = agency_client.summarize_state(st) if st else None
            online = s is not None
            with _AGENCY_WATCH_LOCK:
                prev = dict(_AGENCY_SNAPSHOT)
                _AGENCY_SNAPSHOT.update({
                    "replies": (s or {}).get("replies", 0),
                    "pending": (s or {}).get("pending_approval", 0),
                    "interested": (s or {}).get("interested", 0),
                    "online": online,
                })
            if not online or not s:
                if prev["online"] and not online:
                    tts_engine.speak("Sir, Agency OS has gone offline.", "jarvis")
                    _ui_feed("assistant", "[Agency] Went offline.", source="agency")
                continue
            mode = get_mode()
            if mode != "jarvis" and not mode:
                mode = "jarvis"
            notes = []
            if s["replies"] > prev["replies"]:
                notes.append(f"{s['replies'] - prev['replies']} new replies from leads")
            if s["pending_approval"] > prev["pending"]:
                notes.append(f"{s['pending_approval'] - prev['pending']} new outreach items await approval")
            if s["interested"] > prev["interested"]:
                notes.append(f"{s['interested'] - prev['interested']} more interested institutions")
            if not prev["online"] and online:
                notes.append(f"Agency OS is back online with {s['leads_today']} leads today")
            if notes:
                line = "Sir, " + ", and ".join(notes) + "."
                tts_engine.speak(line, "jarvis")
                _ui_feed("assistant", "[Agency] " + line, source="agency")
        except Exception:
            continue

@app.route("/api/sleep", methods=["POST"])
def api_sleep():
    try: os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0"); return jsonify({"success": True})
    except: return jsonify({"success": False})

@app.route("/api/open-app")
def api_open_app():
    name = request.args.get("name", "")
    if name:
        try: subprocess.Popen(f'start "" "{name}"', shell=True); return jsonify({"success": True})
        except: return jsonify({"success": False})
    return jsonify({"success": False})

@app.route("/api/close-app")
def api_close_app():
    name = request.args.get("name", "")
    if name:
        try: subprocess.run(["taskkill", "/f", "/im", f"{name}.exe"], capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True})
        except: return jsonify({"success": False})
    return jsonify({"success": False})

@app.route("/api/open-url")
def api_open_url():
    url = request.args.get("url", "")
    if url: webbrowser.open(url); return jsonify({"success": True})
    return jsonify({"success": False})

@app.route("/api/execute-shell", methods=["POST"])
def api_execute_shell():
    d = request.get_json(force=True, silent=True) or {}; cmd = d.get("command", "")
    if not cmd: return jsonify({"success": False, "error": "No command"})
    try: r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW); return jsonify({"success": True, "stdout": r.stdout[:10000], "stderr": r.stderr[:5000]})
    except Exception as e: return jsonify({"success": False, "error": str(e)})


def start_background_services():
    """Kick off every always-on background routine (idempotent-ish).

    Shared by all three launchers (server.py __main__, tray.py, app.py) so the
    wake word, proactive speaker and telemetry run regardless of which entry
    point booted the assistant — the whole point of 'works in another app'.
    """
    import speech_stt as _stt
    threading.Thread(target=update_telemetry, daemon=True).start()
    threading.Thread(target=gesture_watchdog, daemon=True).start()
    threading.Thread(target=prewarm_speak_phrases, daemon=True).start()
    threading.Thread(target=prewarm_voice_engines, daemon=True).start()
    threading.Thread(target=tts_engine.prewarm, daemon=True).start()
    proactive.start()
    threading.Thread(target=_agency_alert_watcher, daemon=True).start()
    # Always-on server-side wake word (restored from saved settings) so it
    # stays active even while the user is in another application.
    if load_json(DATA_DIR / "settings.json", {}).get("wake_word", True):
        if _stt.start_wake_listener(_on_wake_detected):
            print(f"[JENNY] Wake word active: {', '.join(_stt.wake_phrases())} (say it anytime)")
        else:
            print("[JENNY] Wake word FAILED to start — check sounddevice/mic. Toggle 'Wake Word' in Settings to retry.")


if __name__ == "__main__":
    from waitress import serve
    start_background_services()
    print(f"[JENNY] Server running on http://localhost:3005")
    print(f"[JENNY] Neural voice engine: {'edge-tts (online)' if tts_engine.edge_tts_available() else 'SAPI fallback'}")
    serve(app, host="0.0.0.0", port=3005, threads=16)

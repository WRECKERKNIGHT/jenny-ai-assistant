import os, sys, json, time, math, random, re, webbrowser, datetime, platform, subprocess, threading, urllib.request, urllib.parse, ctypes, hashlib, string, uuid
import psutil
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import agency_client
import tts_engine
import proactive

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

# Groq API usage/limit tracking (shared by the usage bars in every mode).
GROQ_LIMITS = {"rpm_max": 30, "tpm_max": 6000}
GROQ_USAGE = {
    "requests": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "session_started": None,
    "minute": {"ts": None, "requests": 0, "tokens": 0},
    "model": "llama-3.3-70b-versatile",
}
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
            "model": GROQ_USAGE["model"],
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
        rate = _mode_tts_profile(m)[1]
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
        if Path(p).exists(): return json.loads(Path(p).read_text(encoding="utf-8"))
    except: pass
    return d if d is not None else {}
def save_json(p, d):
    Path(p).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

MODE_PROFILES = {
    "jarvis": {
        "name": "J.A.R.V.I.S.",
        "fullName": "Just A Rather Very Intelligent System",
        "greeting": "Good {period}, Sir. Your systems are fully operational and I have prepared today's brief. Shall we review, or do you have immediate directives?",
        "farewell": "Very well, Sir. I shall remain on standby. Do not hesitate to call.",
        "boss": "Sir",
        "personality": "Formal, British, professional — a polished executive assistant. Structured briefings, clean status reports, concise business updates. Never uses slang, always addresses the user as 'Sir'. Uses words like 'indeed', 'certainly', 'very well'. Makes lists and tables when presenting data."
    },
    "friday": {
        "name": "F.R.I.D.A.Y.",
        "fullName": "Female Replacement Intelligent Digital Assistant Youth",
        "greeting": "Hey Boss! Hope you're having a great {period}! I've got everything ready for you. What are we diving into today?",
        "farewell": "Catch you later, Boss! I'll be right here if you need anything.",
        "boss": "Boss",
        "personality": "Casual, witty, fun and efficient — like a sharp secretary who also happens to be your best friend. Uses 'Boss' as the address term. Injects light humor, uses emojis sparingly in text responses, makes things feel breezy. Quick one-liners, cheerful, occasionally teases. Gets things done fast without being robotic."
    },
    "ultron": {
        "name": "U.L.T.R.O.N.",
        "fullName": "Unified Logic & Tactical Reasoning Oracle Network",
        "greeting": "ULTRON operational. Tactical systems engaged. Your gesture controls are online, Boss. Awaiting your command.",
        "farewell": "ULTRON disengaging. Stay sharp, Boss.",
        "boss": "Boss",
        "personality": "Hard, clipped, tactical, zero fluff — a military-grade AI. Short declarative sentences, action-oriented. Uses terms like 'affirmative', 'directive', 'tactical'. Direct command tone. No filler words."
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
        payload = json.dumps({
            "model": "llama-3.3-70b-versatile",
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
    m = re.search(r"(?:complete|mark|finish|cross\s*off|check\s*(?:off)?)\s+(?:task\s+)?(\d+)", lo)
    if m:
        return ("complete", int(m.group(1)))
    m = re.search(r"(?:complete|mark|finish|done\s+with)\s+(.+)", lo)
    if m:
        return ("complete_text", m.group(1).strip())
    
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


def local_command_router(msg):
    """Fast, case-insensitive local intent routing that runs BEFORE the LLM so
    todo / system actions / mode switches always work instantly and deterministically.
    Returns a reply dict, or None if the message should go to the LLM."""
    lo = _normalize_utterance(msg)
    mode = get_mode()
    mp = MODE_PROFILES[mode]
    boss = mp["boss"]

    # MODE SWITCH: "switch to jarvis", "go ultron", "activate friday", "be jarvis"
    m = re.search(r"(?:switch|change|go|activate|become|set)\s+(?:to\s+|to\s+the\s+|into\s+)?(friday|jarvis|ultron)", lo)
    if m:
        target = m.group(1)
        set_mode(target)
        tmp = MODE_PROFILES[target]
        line = f"Mode switched to **{target.upper()}**. {tmp['greeting'].format(period=get_time_period())}"
        return {"text": line, "speech": line, "command": {"action": "mode", "value": target}}

    # TODO: add/remove/edit/complete/list always local
    res = handle_todo_intent(lo, boss)
    if res:
        return res

    # SYSTEM ACTIONS that must never round-trip to the LLM
    act = None
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
    if any(w in lo for w in ["mute", "volume mute"]):
        return {"text": "Muted, {boss}.", "speech": "Muted.", "command": {"action": "volume", "value": "mute"}}
    if any(w in lo for w in ["unmute", "unmuted"]):
        return {"text": "Unmuted, {boss}.", "speech": "Unmuted.", "command": {"action": "volume", "value": "unmute"}}
    if any(w in lo for w in ["volume up", "louder", "increase volume"]):
        return {"text": f"Volume up, {boss}!", "speech": "Volume up.", "command": {"action": "volume-up", "value": ""}}
    if any(w in lo for w in ["volume down", "quieter", "lower volume"]):
        return {"text": f"Volume down, {boss}!", "speech": "Volume down.", "command": {"action": "volume-down", "value": ""}}

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

    # Offline catch-all: acknowledge, name the limitation, and steer to what still works.
    detail = "Right now I'm running in **offline/simulation mode**, so I can't reach my brain (the AI API)." if not get_gemini_key() else "I couldn't reach the AI API just now, so I'm answering from my offline knowledge."
    recall = ""
    if mem_topics and mem_count > 2:
        recall = f"\n\nJust to keep us on track — earlier we were talking about *{mem_topics}*. Want to pick any of those back up, {boss}?"
    return {"text": f"{detail}\n\nYou can still ask me to:\n• **Control the PC** — open apps, lock, screenshot, timers, clipboard\n• **Read your system** — CPU, RAM, battery, disk, processes, uptime\n• **Do math** — calculators, conversions, percentages, primes, factorials\n• **Enjoy content** — jokes, quotes, facts, riddles, weather, time\n• **Talk about tech** — AI, Python, CPU, RAM, encryption and more offline{recall}\n\nTry one of those, or ask me about your **Agency OS** / business, {boss}!", "speech": f"I'm in offline mode, so I can't use the online AI. But I can still control your PC, read your system, do math, tell jokes, and remember what we've been talking about, {boss}."}


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

@app.route("/api/health")
def api_health():
    """True end-to-end status so the UI stops showing 'offline' wrongly:
    Groq key present + reachable, neural TTS engine, microphone devices,
    server uptime and the active model."""
    key = get_grok_key()
    api_ok = False
    api_latency = None
    if key:
        try:
            req = urllib.request.Request("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"}, method="GET")
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=6) as resp:
                api_ok = resp.status == 200
                api_latency = round((time.time() - t0) * 1000)
        except Exception:
            api_ok = False
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
    return jsonify({
        "success": True,
        "online": bool(key) and api_ok,
        "provider": chat or "none",
        "key_set": bool(key),
        "api_reachable": api_ok,
        "api_latency_ms": api_latency,
        "model": GROQ_USAGE["model"] if chat == "groq" else "gemini-2.0-flash" if chat == "gemini" else None,
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
            return Response(frame, mimetype="image/jpeg")
    from flask import Response as R
    return R(b'', mimetype="image/jpeg")

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

@app.route("/api/chat", methods=["POST"])
def api_chat():
    d = request.get_json(force=True, silent=True) or {}
    msg = d.get("message", "").strip()
    if not msg:
        return jsonify({"success": False, "error": "No message"}), 400
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
        chatHistory.append({"role": "user", "content": msg})
        chatHistory.append({"role": "assistant", "content": local.get("text", "")})
        if len(chatHistory) > 20:
            chatHistory.pop(0); chatHistory.pop(0)
        proactive.mark_activity()
        return jsonify({"success": True, "reply": local})
    reply = grok_chat(msg, chatHistory)
    if not reply:
        reply = gemini_chat(msg, chatHistory)
    if not reply:
        reply = offline_reply(msg) or {"text": "I'm offline, Boss.", "speech": "I'm offline, Boss."}
    chatHistory.append({"role": "user", "content": msg})
    chatHistory.append({"role": "assistant", "content": reply.get("text", "")})
    if len(chatHistory) > 20:
        chatHistory.pop(0); chatHistory.pop(0)
    proactive.mark_activity()
    return jsonify({"success": True, "reply": reply})

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
    lo = action.lower()
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
        apps = {"notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe", "chrome": "chrome", "edge": "msedge", "vscode": "code", "spotify": "spotify", "discord": "discord"}
        name = str(value).lower(); target = apps.get(name, value)
        try: subprocess.Popen(target, shell=True); return jsonify({"success": True, "message": f"Opened {value}."})
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
    return jsonify({"success": False, "error": f"Unknown action: {action}"})


@app.route("/api/speak", methods=["GET", "POST"])
def api_speak():
    text = request.args.get("text", "") or (request.get_json(force=True, silent=True) or {}).get("text", "")
    if not text: return jsonify({"success": False, "message": "Text required"})
    clean = _clean_tts_text(re.sub(r"[#*_`\[\]]", "", text))
    cache_dir = DATA_DIR / "speak_cache"; cache_dir.mkdir(exist_ok=True)
    h = hashlib.md5(clean.encode()).hexdigest(); wav_path = cache_dir / f"{h}.wav"
    if wav_path.exists(): return send_from_directory(str(cache_dir), f"{h}.wav", mimetype="audio/wav")
    mode = get_mode()
    try:
        voice, rate, pitch, volume = tts_engine.MODE_VOICES.get(mode, (tts_engine.DEFAULT_VOICE, tts_engine.DEFAULT_RATE, tts_engine.DEFAULT_PITCH, tts_engine.DEFAULT_VOLUME))
        ok = tts_engine.synthesize_wav(clean, wav_path, voice, rate, pitch, volume)
    except Exception:
        ok = False
    if not ok:
        ok = tts_synthesize(clean, wav_path)
    if ok and wav_path.exists():
        return send_from_directory(str(cache_dir), f"{h}.wav", mimetype="audio/wav")
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
    return jsonify(st)

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

@app.route("/api/greeting", methods=["GET"])
def api_greeting():
    """Rich, natural startup greeting: time-of-day + your name + weather +
    live system status, flavored by the active mode. Returns both display text
    and a short spoken line so voice triggers at the perfect moment on boot."""
    now = datetime.datetime.now(); h = now.hour
    greet = "Good night" if h < 6 else "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening" if h < 21 else "Good night"
    m = get_mode(); mp = MODE_PROFILES[m]
    settings = load_json(DATA_DIR / "settings.json", {"latitude": 26.8467, "longitude": 80.9462, "cityName": "Lucknow"})
    name = settings.get("name", "") or ""
    boss_phrase = f", {name}" if name else f", {mp['boss'].lower()}"
    weather = ""
    try:
        import requests as _req
        r = _req.get(f"https://api.open-meteo.com/v1/forecast?latitude={settings.get('latitude',26.8467)}&longitude={settings.get('longitude',80.9462)}&current_weather=true&temperature_unit=celsius&timezone=auto", timeout=6)
        if r.status_code == 200:
            cw = r.json().get("current_weather", {})
            wmo = {0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 61: "light rain", 63: "rain", 65: "heavy rain", 71: "snow", 80: "showers", 95: "thunderstorm"}
            temp = cw.get("temperature", 0)
            cond = wmo.get(cw.get("weathercode", 0), "clear")
            weather = f"In {settings.get('cityName','your city')}, it's {round(temp)} degrees and {cond}. "
    except Exception:
        pass
    system = f"System is at CPU {system_cache['cpu']} percent, RAM {system_cache['ram']} percent."
    charter = {"friday": "FRIDAY online and ready to help, Boss.",
               "jarvis": "How may I assist you today, Sir?",
               "ultron": "ULTRON online. Gesture control is ready. Show me your hands, Boss."}
    text = f"{greet}{boss_phrase}.\n\n{charter[m]}\n{weather}{system}"
    if m == "jarvis":
        try:
            st = agency_client.agency_state()
            if st:
                s = agency_client.summarize_state(st)
                text += f"\nYour Agency OS has {s['agents_online']} agents online and {s['leads_today']} leads today."
        except Exception:
            pass
    speech_parts = []
    if m == "ultron":
        speech_parts.append(charter["ultron"])
    else:
        speech_parts.append(f"{greet}{boss_phrase}.")
    speech_parts.append(weather.strip())
    speech_parts.append(system)
    speech = " ".join(p for p in speech_parts if p).replace("..", ".")
    return jsonify({"success": True, "text": text, "speech": speech, "mode": m})

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
    try: s = __import__("socket").socket(__import__("socket").AF_INET, __import__("socket").SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
    except: ip = "127.0.0.1"
    return jsonify({"success": True, "ip": ip, "mobileUrl": f"http://{ip}:3005/mobile.html"})

@app.route("/api/remote-status")
def api_remote_status(): return jsonify({"success": True, "remoteMode": False, "hostname": platform.node()})

@app.route("/api/devices")
def api_devices(): return jsonify({"success": True, "devices": list(activeDevices.values())})

@app.route("/api/mobile-stats")
def api_mobile_stats():
    linked = [d for d in activeDevices.values() if d.get("status") == "approved"]
    return jsonify({"success": True, "linkedDevices": len(linked), "devices": linked, "battery": system_cache["battery"], "connection": "online"})

@app.route("/api/device/register", methods=["POST"])
def api_device_register():
    d = request.get_json(force=True, silent=True) or {}; did = d.get("deviceId", "")
    if not did: return jsonify({"success": False, "message": "deviceId required"})
    if did not in activeDevices: activeDevices[did] = {"deviceId": did, "os": d.get("os", "Unknown"), "browser": d.get("browser", "Unknown"), "ip": request.remote_addr, "status": "pending", "lastActive": datetime.datetime.now().isoformat()}
    return jsonify({"success": True, "device": activeDevices[did]})

@app.route("/api/device/status/<did>")
def api_device_status(did): return jsonify({"success": True, "status": activeDevices.get(did, {}).get("status", "unknown")})

@app.route("/api/device/approve", methods=["POST"])
def api_device_approve():
    d = request.get_json(force=True, silent=True) or {}; did = d.get("deviceId", "")
    if did in activeDevices: activeDevices[did]["status"] = d.get("status", ""); return jsonify({"success": True})
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
def api_device_cmd_poll(did): return jsonify({"success": True, "commands": pendingDeviceCommands.pop(did, [])})

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
    return jsonify({"success": True, "message": "SMS feature coming soon"})

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
def api_emails(): return jsonify({"success": True, "emails": [], "message": "Email not available on Windows yet."})

@app.route("/api/timers")
def api_timers(): return jsonify({"success": True, "timers": []})

@app.route("/api/toggle-mic")
def api_toggle_mic(): return jsonify({"success": True, "timestamp": int(time.time() * 1000)})

@app.route("/api/toggle-mic-poll")
def api_toggle_mic_poll(): return jsonify({"success": True, "lastToggle": 0})

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


if __name__ == "__main__":
    from waitress import serve
    threading.Thread(target=update_telemetry, daemon=True).start()
    threading.Thread(target=gesture_watchdog, daemon=True).start()
    threading.Thread(target=prewarm_speak_phrases, daemon=True).start()
    threading.Thread(target=prewarm_voice_engines, daemon=True).start()
    threading.Thread(target=tts_engine.prewarm, daemon=True).start()
    import proactive as _proactive
    _proactive.start()
    print(f"[JENNY] Server running on http://localhost:3005")
    print(f"[JENNY] Neural voice engine: {'edge-tts (online)' if tts_engine.edge_tts_available() else 'SAPI fallback'}")
    serve(app, host="0.0.0.0", port=3005, threads=8)

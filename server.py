import os, sys, json, time, math, random, re, webbrowser, datetime, platform, subprocess, threading, urllib.request, urllib.parse, ctypes, hashlib, string, uuid
import psutil
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import agency_client

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
GROK_API_KEY = os.environ.get("GROK_API_KEY", "")
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
            "key_set": bool(GROK_API_KEY),
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

def _mode_tts_profile(mode):
    """Return (voice_keyword_priority, rate) for a given assistant mode.
    Friday = female, Jarvis = British male, ULTROM = deep male."""
    if mode == "jarvis":
        return (["george", "david", "mark", "male"], -1)
    if mode == "ultron":
        return (["david", "mark", "michael", "male"], -3)
    return (["zira", "hazel", "aria", "jenny", "susan", "cortana", "female"], 0)

def _get_tts_voice(mode=None):
    """Return a persistent SAPI SpVoice for the current mode (init once per mode — low latency)."""
    global _tts_voice, _tts_voices
    if mode is None:
        try:
            mode = get_mode()
        except Exception:
            mode = "friday"
    if mode in _tts_voices:
        return _tts_voices[mode]
    pythoncom.CoInitialize()
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    keywords, rate = _mode_tts_profile(mode)
    picked = None
    try:
        voices = voice.GetVoices()
        for kw in keywords:
            for v in voices:
                if kw in v.GetDescription().lower():
                    picked = v
                    break
            if picked is not None:
                break
        if picked is not None:
            voice.Voice = picked
    except Exception:
        pass
    try:
        voice.Rate = rate
    except Exception:
        pass
    _tts_voices[mode] = voice
    if _tts_voice is None:
        _tts_voice = voice
    return _tts_voices[mode]

def tts_speak(text):
    """Speak text aloud using the persistent SAPI voice (async, low latency)."""
    if not text:
        return
    with _tts_lock:
        try:
            mode = get_mode()
            voice = _get_tts_voice(mode)
            voice.AudioOutputStream = None
            voice.Speak(text, 1)
        except Exception:
            pass

def tts_synthesize(text, wav_path):
    """Synthesize text to a WAV file with the persistent SAPI voice."""
    with _tts_lock:
        fs = None
        try:
            mode = get_mode()
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

def load_json(p, d=None):
    try:
        if Path(p).exists(): return json.loads(Path(p).read_text(encoding="utf-8"))
    except: pass
    return d if d is not None else {}

def save_json(p, d):
    Path(p).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

MODE_PROFILES = {
    "jarvis": {"name": "J.A.R.V.I.S.", "fullName": "Just A Rather Very Intelligent System", "greeting": "Good day, Sir. How may I assist you today?", "farewell": "Very well, Sir. Standing by.", "boss": "Sir", "personality": "Formal, British, sophisticated"},
    "friday": {"name": "F.R.I.D.A.Y.", "fullName": "Female Replacement Intelligent Digital Assistant Youth", "greeting": "Hey Boss! FRIDAY online and ready to roll.", "farewell": "Catch you later, Boss!", "boss": "Boss", "personality": "Casual, witty, efficient"},
    "ultron": {"name": "U.L.T.R.O.N.", "fullName": "Unified Logic & Tactical Reasoning Oracle Network", "greeting": "ULTRON online. Gesture control ready. Show me your hands, Boss.", "farewell": "ULTRON signing off. Stay sharp.", "boss": "Boss", "personality": "Aggressive, powerful, precise"},
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
    return ""

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
    if not GROK_API_KEY: return None
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
                "Authorization": f"Bearer {GROK_API_KEY}",
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
        save_json(DATA_DIR / "context.json", ctx)
    except: pass

def offline_reply(text):
    lo = text.lower().strip()
    lo_norm = lo.replace("i am", "i'm").replace("i dont", "i don't").replace("i cant", "i can't").replace("dont", "don't").replace("cant", "can't").replace("wont", "won't").replace("isnt", "isn't").replace("arent", "aren't").replace("wasnt", "wasn't").replace("wouldnt", "wouldn't")
    mode = get_mode()
    mp = MODE_PROFILES[mode]
    boss = mp["boss"]
    track_command_stats(text)
    track_context(text)

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
        return {"text": mp["greeting"], "speech": mp["greeting"]}
    if any(w in lo for w in ["thank", "thanks", "thx", "ty"]):
        return {"text": random.choice([f"Happy to help, {boss}!", f"Anything for you, {boss}!", f"You're welcome, {boss}!"]), "speech": "Happy to help, boss!"}
    if any(w in lo for w in ["bye", "goodbye", "see you", "later", "cya"]):
        return {"text": mp["farewell"], "speech": mp["farewell"]}
    if any(w in lo for w in ["who made you", "your creator", "who created you", "who built you"]):
        return {"text": f"I was created by **Harshit** (WRECKERKNIGHT) - the Boss himself!", "speech": "I was created by Harshit, WRECKERKNIGHT. Built with Python and Flask."}

    if any(w in lo for w in ["weather", "temperature", "forecast", "is it raining"]):
        return {"text": "Checking weather!", "speech": "Checking weather.", "command": {"action": "weather", "value": ""}}
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
                    return {"text": v, "speech": v[:200] + "..."}
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

gesture_controller = None

@app.route("/api/gesture-status")
def api_gesture_status():
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

GESTURE_FREEZE_SECONDS = 60
gesture_watchdog_log = []

def gesture_watchdog():
    """Auto-recover ULTRON if the system freezes: if the gesture loop stops
    sending heartbeats for > 60s (or overall CPU is pinned), force-stop it."""
    while True:
        time.sleep(5)
        try:
            gc = gesture_controller
            if gc and gc.get_gesture_status().get("active"):
                status = gc.get_gesture_status()
                age = status.get("heartbeat_age", 0)
                cpu = system_cache.get("cpu", 0)
                if age > GESTURE_FREEZE_SECONDS:
                    gc.stop_gesture_control()
                    gesture_watchdog_log.append("gesture auto-stopped: frozen heartbeat %.0fs" % age)
                    print("[JENNY] Watchdog: gesture control stopped (frozen %.0fs)" % age)
                elif cpu > 95:
                    # extremely high sustained CPU with active gestures -> shed load
                    gc.stop_gesture_control()
                    gesture_watchdog_log.append("gesture auto-stopped: CPU at %d%%" % cpu)
                    print("[JENNY] Watchdog: gesture control stopped (CPU %d%%)" % cpu)
        except Exception:
            pass

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
    reply = grok_chat(msg, chatHistory)
    if not reply:
        reply = gemini_chat(msg, chatHistory)
    if not reply:
        reply = offline_reply(msg) or {"text": "I'm offline, Boss.", "speech": "I'm offline, Boss."}
    chatHistory.append({"role": "user", "content": msg})
    chatHistory.append({"role": "assistant", "content": reply.get("text", "")})
    if len(chatHistory) > 20:
        chatHistory.pop(0); chatHistory.pop(0)
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
    clean = re.sub(r"[#*_`\[\]]", "", text); clean = re.sub(r"https?://\S+", "", clean).strip()
    cache_dir = DATA_DIR / "speak_cache"; cache_dir.mkdir(exist_ok=True)
    h = hashlib.md5(clean.encode()).hexdigest(); wav_path = cache_dir / f"{h}.wav"
    if wav_path.exists(): return send_from_directory(str(cache_dir), f"{h}.wav", mimetype="audio/wav")
    if tts_synthesize(clean, wav_path) and wav_path.exists():
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
    with _tts_lock:
        try:
            if _tts_voice: _tts_voice.Speak("", 1 + 2)
        except Exception:
            pass
    return jsonify({"success": True})

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

@app.route("/api/device/command/poll/<did>")
def api_device_cmd_poll(did): return jsonify({"success": True, "commands": pendingDeviceCommands.pop(did, [])})

@app.route("/api/device/location", methods=["POST"])
def api_device_location():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify({"success": True, "message": "Location received"})

@app.route("/api/device/notifications", methods=["POST"])
def api_device_notifications():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify({"success": True, "message": "Notifications synced"})

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
    print(f"[JENNY] Server running on http://localhost:3005")
    serve(app, host="0.0.0.0", port=3005, threads=8)

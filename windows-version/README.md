# J.E.N.N.Y - Windows AI Assistant

**Just Every Necessary Neural Yearning** — a feature-rich Windows AI assistant with a
system-tray Mini HUD, neural voice engine, wake-word voice control, gesture
control (ULTRON), system monitoring, and agentic capabilities. Designed for low-end
PCs with minimal RAM and CPU usage.

## Quick Start

### One-click launch

Just double-click **`Jenny.bat`** and pick option **1 — Start JENNY (Tray + Mini HUD)**.
It automatically installs missing dependencies on first run.

That single command starts *everything*:

```
pythonw tray.py
```

- **Tray icon** appears on the right side of the taskbar (near the clock).
- **Double-click** the tray icon → opens/closes the **MINI HUD** (always-on-top panel showing mode + speaking status + quick actions).
- Right-click the tray icon for: Mini HUD, Modes, Dashboard, Holographic HUD, **Wake Word on/off**, Voice Check, and Quit.
- The Flask server, neural voice engine, proactive speaker and wake-word listener all run inside the tray process.

### Manual launch

```bash
pip install -r requirements.txt
python tray.py           # Tray + Mini HUD + server + voice (recommended)
python app.py            # Full desktop window (modes.html)
python hud.py            # Transparent always-on-top holographic HUD overlay
python server.py         # Web UI server on port 3005 only
python scripts/wakeword.py   # Wake-word voice assistant only
```

## Personas & Tones

JENNY is the system itself — three personalities, each with a matching **voice + tone**, switchable any time in Modes (or say the wake word):

| Mode | Tone | Neural voice |
|------|------|--------------|
| **FRIDAY** | Casual, witty, fast and fun — the default | `en-US-JennyNeural` |
| **JARVIS** | Formal, British, sophisticated and precise | `en-GB-RyanNeural` |
| **ULTRON** | Hard, clipped, tactical, zero fluff | `en-US-ChristopherNeural` |

Wake words "Hey Friday", "Hey Jarvis" and "Hey Ultron" auto-switch the persona.

## Voice / TTS System (brand-new audio engine)

The old robotic SAPI-only voice is replaced by a **neural voice engine** (`tts_engine.py`):

- **Primary — edge-tts (Microsoft neural voices)**: near-human quality, streamed
  sentence-by-sentence with a per-mode speaking rate, so the first words start
  almost instantly.
- **Fallback — Windows SAPI** voices automatically when offline/edge-tts fails.
- **WAV cache**: repeated phrases and sentences play instantly with zero synthesis latency.
- **Talkative mode** (`proactive.py`): JENNY now *speaks on its own* — boot greeting,
  time-of-day openers, friendly idle nudges (if you're quiet ~10 min), and a gentle
  low-battery heads-up. Disable anytime with `{"proactive": false}` in `data/settings.json`.

### Right-Time Triggers
- Greeting fires on a fresh session and is delayed until the mode is loaded (so
  Jarvis greets in a British voice, ULTRON in a deep voice).
- Wake word → soft two-note chime + mode-styled acknowledgement through the neural voice.
- `speakTrigger()` throttles event confirmations so quick actions don't stack a queue.

### Where Voice Fires
| Trigger | Spoken line |
|---------|-------------|
| Boot (fresh session) | `/api/greeting` — mode-flavored greeting + weather + system status |
| Mode switch / wake word | Chime + mode-themed acknowledgement |
| Chat commands | Every reply has a `speech` line read aloud |
| Idle nudges | Friendly check-ins after a quiet stretch (9:00–22:00) |
| Low battery | One heads-up below 20% |
| Gesture start/stop | "Gesture control activated…" |

## Features

### Core
- **Dual Mode**: Full window app + transparent overlay HUD
- **Tray + Mini HUD**: system-tray icon → always-on-top Mini HUD (right side of taskbar)
- **Voice Control**: mode-aware wake words ("Hey Jenny" / "Hey Friday" / "Hey Jarvis" / "Hey Ultron")
- **Neural TTS**: edge-tts voices per persona with automatic SAPI fallback
- **Greeting**: personalized daily greetings with weather, date, and system status
- **Personality**: Jenny calls you "Boss"; Jarvis is formal, ULTRON is hard
- **Proactive / talkative**: boot greeting, idle chit-chat, low-battery alerts

### System Control
- Open/close any Windows application (notepad, chrome, vscode, etc.)
- Volume control (set, mute, unmute) · Screen brightness · Lock/sleep/shutdown/restart/hibernate
- Screenshot capture · Recycle bin emptying · Process killing and listing
- Clipboard reading · WiFi info · Screen resolution detection
- Temp folder cleanup · Quick folder access (Desktop, Documents, Downloads, Pictures, Music, Videos)

### Widgets (Floating with animations)
System monitor (CPU, RAM, Disk, Battery, Network) · Weather · Clock · Crypto prices ·
Top news (HackerNews) · Quotes · Random facts · Pomodoro timer · Quick timer

### Web & Search
Google search · YouTube · Instagram · Open any website · Bookmark management ·
Quick web shortcuts (Gmail, GitHub, ChatGPT, Maps, Netflix, Drive, etc.)

### Productivity
Notes · Todos · Memory vault · Timer/alarm · Dictionary lookup · Unit/binary/hex
conversions · Dice/coin/random · Password generator

### Agentic
Natural language command processing · File/folder navigation · Application lifecycle ·
Browser automation · Offline brain fallback · Gemini + Groq API integration

## ULTRON Gesture Control

ULTRON mode turns your webcam into a full PC control surface using MediaPipe hand tracking (two hands supported).

### Hands & Roles
- **Left hand = Navigator** — drives the mouse cursor (or the orb in orb-drive mode)
- **Right hand = Commander** — executes actions (click, scroll, browser/system/media)

### Single-Hand Gestures
| Gesture | Action |
|---|---|
| Point (index up) | Move cursor / steer orb |
| Pinch (thumb + index) | Left-click (navigator) or right-click (commander) |
| Double pinch (thumb + index + middle) | Double-click |
| Two fingers | Scroll |
| Open palm (held) | Toggle enable/disable |
| Fist | Pause |
| Thumbs up | Approve |

### Dual-Hand Combos
| Combo | Action |
|---|---|
| Open palm + open palm (both) | Cycle control mode (pointer → browser → system → media) |
| Fist + open palm (either hand) | Toggle enable/disable |

### Orb Drive
Enable **ORB: ON** in the ULTRON status bar (or POST `/api/gesture/orb`) so hand position
steers the orb instead of the mouse. Configuration is stored in `gesture_config.json`
(smooth factor, cooldowns, FPS caps, encode budget).

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send command, get response (`text` + `speech`) |
| `/api/greeting` | GET | Daily greeting (text + speech + weather) |
| `/api/speak` | GET/POST | Synthesize text to WAV (neural first, SAPI fallback) |
| `/api/speak/status` | GET | Live TTS state |
| `/api/speak/fallback` | POST | Speak directly on the PC (neural engine) |
| `/api/speak/stop` | POST | Stop any ongoing speech |
| `/api/voice-info` | GET | Active voice + neural engine info per mode |
| `/api/mode` | GET/POST | Read / switch persona mode |
| `/api/system-status` | GET | CPU, RAM, disk, battery, network |
| `/api/briefing` | GET | Full daily briefing |
| `/api/weather` | GET | Current weather |
| `/api/news` | GET | Top news stories |
| `/api/crypto` | GET | Crypto prices |
| `/api/vault` | GET/POST/DELETE | Memory vault |
| `/api/training` | GET/POST/DELETE | Training hub / macros |
| `/api/gesture/*` | — | Gesture control (see above) |

## Voice Commands

Just talk naturally to Jenny:
- "Open Chrome" / "Launch VS Code"
- "Set volume to 50" / "Mute"
- "What's the weather?"
- "Search YouTube for music"
- "Add todo buy groceries"
- "Remember my wifi password is..."
- "Take a screenshot" · "Tell me a joke" · "What time is it?"
- "Convert 100 celsius to fahrenheit" · "Generate password" · "Open Gmail"

## Project Structure

```
windows-version/
├── tray.py               # Tray icon + Mini HUD + launches everything
├── tts_engine.py         # Neural edge-tts engine + SAPI fallback + cache
├── proactive.py          # Talkative mode: boot greeting, idle nudges, alerts
├── server.py             # Flask API server with all endpoints
├── app.py                # pywebview desktop window
├── hud.py                # Transparent always-on-top holographic HUD
├── Jenny.bat             # One-click launcher (menu, auto-deps)
├── launch.bat            # Quick tray launch
├── requirements.txt      # Python dependencies
├── public/               # Web frontend (index.html, modes.html, mini.html, …)
├── scripts/
│   ├── wakeword.py       # Mode-aware wake word detector
│   ├── startup.py        # Windows auto-start installer
│   └── extended_commands.py
└── data/                 # Runtime data (mode, context, settings, speak cache)
```

## Auto-Start with Windows

```bash
python scripts/startup.py
```

## Performance

Designed for potato PCs:
- Server uses only `psutil` for telemetry · telemetry updates every 5s
- Lightweight Tk tray/Mini HUD, no heavy frameworks — Flask + vanilla JS
- Memory usage: ~30–50 MB total · cached neural TTS for instant responses
- edge-tts falls back to local SAPI instantly when offline

## License

MIT
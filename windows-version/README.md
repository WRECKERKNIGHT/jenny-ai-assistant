# J.E.N.N.Y - Windows AI Assistant

**Just a Enhanced Neural Network for You**

A high-performance, feature-rich Windows AI assistant with transparent overlay mode, voice control, system monitoring, and agentic capabilities. Designed for low-end PCs with minimal RAM and CPU usage.

## Quick Start

```bash
pip install -r requirements.txt
python launcher.py
```

## Features

### Core
- **Dual Mode**: Full window app + transparent overlay mode
- **Voice Control**: Wake word detection ("Hey Jenny" / "Hey Friday")
- **TTS**: Best Windows SAPI5 voices (David, Mark, Zira, Hazel)
- **Greeting**: Personalized daily greetings with weather, date, and system status
- **Personality**: Jenny calls you "Boss" and treats you as her creator
- **Light/Dark Theme**: Toggle between themes with persistence
- **Keyboard Shortcuts**: Ctrl+1-7 for navigation, Ctrl+M for mic, Ctrl+E export

### System Control
- Open/close any Windows application (notepad, chrome, vscode, etc.)
- Volume control (set, mute, unmute)
- Screen brightness adjustment
- Lock, sleep, shutdown, restart, hibernate
- Screenshot capture
- Recycle bin emptying
- Process killing and listing
- Clipboard reading
- WiFi info display
- Screen resolution detection
- Computer name and system info
- Temp folder cleanup
- Quick folder access (Desktop, Documents, Downloads, Pictures, Music, Videos)

### Widgets (Floating with animations)
- System monitor (CPU, RAM, Disk, Battery, Network)
- Weather widget with live data
- Clock widget with date
- Crypto prices (BTC, ETH, SOL, DOGE)
- Top news stories (HackerNews)
- Inspirational quotes
- Random facts
- Pomodoro timer (25min work / 5min break)
- Quick timer (1, 5, 10, 30 minutes)

### Web & Search
- Google search from chat
- YouTube search
- Instagram search/browse
- Open any website
- Bookmark management
- Quick web shortcuts (Gmail, GitHub, ChatGPT, Maps, Netflix, Drive, etc.)

### Productivity
- Notes system with save
- Todo list with completion tracking
- Memory vault for important info
- Timer/alarm
- Dictionary lookup

### Information
- Weather (Open-Meteo API)
- News (HackerNews)
- Crypto prices (CoinGecko)
- Public IP info
- Dictionary definitions

### Utilities
- Unit conversion (temperature, distance, weight, volume)
- Hexadecimal conversion
- Binary conversion
- Roman numeral conversion
- Random dice roll
- Coin flip
- Random number generator
- Password generator

### Agentic
- Natural language command processing
- File/folder navigation
- Application lifecycle management
- Browser automation
- Offline brain engine for fallback responses
- Gemini API integration for intelligent responses

### UI Features
- Glassmorphism design with dark/light themes
- Floating widget animations
- Boot sequence animation
- Chat export to text file
- Copy-to-clipboard on messages
- Responsive sidebar

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

### Control Modes (`/api/gesture/mode`)
- **pointer** (default): mouse move, click, scroll
- **browser**: search, new tab, close tab, back, refresh, forward, reopen tab
- **system**: screenshot, show desktop, task manager, lock, close window
- **media**: volume up/down/mute, play/pause, next/prev track

### Orb Drive
Enable **ORB: ON** in the ULTRON status bar (or POST `/api/gesture/orb`) so hand position steers the orb instead of the mouse. The frontend persists this preference in `localStorage`.

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/gesture-status` | GET | Two-hand status, mode, orb state |
| `/api/gesture/start` | POST | Start gesture control |
| `/api/gesture/stop` | POST | Stop gesture control |
| `/api/gesture/orb` | POST | Toggle orb-drive mode |
| `/api/gesture/mode` | POST | Set control mode |
| `/api/gesture/cmd` | POST | Trigger a PC action directly |
| `/api/gesture/config` | GET/POST | Read/write sensitivity settings |
| `/api/gesture/watchdog-log` | GET | Watchdog recovery log |

Config is stored in `gesture_config.json` (smooth factor, cooldowns, FPS caps, encode budget).

## Project Structure

```
windows-version/
├── server.py              # Flask API server with all endpoints
├── gui.py                 # tkinter GUI (main app + overlay)
├── launcher.py            # Interactive launcher
├── requirements.txt       # Python dependencies
├── public/
│   ├── index.html         # Web frontend
│   ├── css/style.css      # Glassmorphism UI styles
│   └── js/app.js          # Frontend JavaScript
├── scripts/
│   ├── wakeword.py        # Voice wake word detector
│   ├── startup.py         # Windows auto-start installer
│   └── extended_commands.py # Extended system commands
└── data/                  # Runtime data (notes, vault, todos)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send command, get response |
| `/api/greeting` | GET | Daily greeting message (text + speech + weather) |
| `/api/speak` | GET/POST | Synthesize text to WAV |
| `/api/speak/status` | GET | Live TTS state |
| `/api/speak/fallback` | POST | Speak directly on the PC |
| `/api/system-status` | GET | CPU, RAM, disk, battery, network |
| `/api/weather` | GET | Current weather |
| `/api/news` | GET | Top news stories |
| `/api/quote` | GET | Inspirational quote |
| `/api/fact` | GET | Random fact |
| `/api/crypto` | GET | Crypto prices |
| `/api/ip-info` | GET | Public IP information |
| `/api/dictionary` | GET | Word definition |
| `/api/voices` | GET | Available TTS voices |
| `/api/chat-history` | GET/POST/DELETE | Chat history management |
| `/api/bookmarks` | GET/POST/DELETE | Bookmark management |
| `/api/notes` | GET/POST | Notes management |
| `/api/todos` | GET/POST | Todo management |
| `/api/vault` | GET/POST/DELETE | Memory vault |
| `/api/briefing` | GET | Full daily briefing |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + 1-7` | Navigate to views |
| `Ctrl + /` | Focus chat input |
| `Ctrl + M` | Toggle microphone |
| `Ctrl + E` | Export chat |
| `Ctrl + L` | Clear chat |
| `Escape` | Stop listening |

## Voice Commands

Just talk naturally to Jenny:
- "Open Chrome" / "Launch VS Code"
- "Set volume to 50" / "Mute"
- "What's the weather?"
- "Search YouTube for music"
- "Add todo buy groceries"
- "Remember my wifi password is..."
- "Take a screenshot"
- "Tell me a joke"
- "What time is it?"
- "Convert 100 celsius to fahrenheit"
- "Generate password"
- "Open Gmail"

## Voice / TTS System

Jenny voices herself everywhere — chats, panel opens, weather, system info, mode
switches, gestures and boot greetings all trigger spoken output:

### Less Robotic Voices
- **Server (SAPI)**: prefers Windows **"Online (Natural)"** voices per mode
  (Friday → Aria/Jenny female, Jarvis → George/Guy British male, ULTRON → deep male).
  Falls back to legacy David/Zira if natural voices aren't installed. Voice pick
  runs 3 passes: mode natural → any natural → legacy keywords.
- **Web (`speechSynthesis`)**: prefers `natural|online|neural` voices, then the
  mode personality voice, honoring your Speech Rate / Pitch / Voice settings.
- **Prosody cleanup**: `_clean_tts_text` expands `%`, `°C`, `km/h`, `MHz`, `GB`,
  `x` (as "by") and common abbreviations so numbers read like a human.

### Right-Time Triggers
- Greeting only fires on a **fresh session** and is delayed until the active mode
  is loaded (so Jarvis greets in a British voice, ULTRON in a deep voice).
- `speakTrigger()` throttles event confirmations (1.6s) so quick actions don't
  stack a long robotic queue.
- Voice pickers wait for `speechSynthesis.onvoiceschanged` before first utterance.

### Where Voice Fires
| Trigger | Spoken line |
|---------|-------------|
| Boot (fresh session) | `/api/greeting` — greeting + weather + system status, mode-flavored |
| Mode switch | "Switching to Jarvis mode…" |
| Panels opened | "Opening the weather panel…", system, processes, emails, vault, agency… |
| Weather panel | Live temperature / condition / wind summary |
| System info | CPU / model confirmation |
| Gesture start/stop | "Gesture control activated…" |
| Chat commands | Every reply has a `speech` line read aloud |

### Voice Settings
Settings panel → Voice: choose a web voice, set Speech Rate/Pitch, tap **TEST VOICE**
to preview. Switching modes auto-resets the voice cache so each mode re-picks the
matching natural voice.

## Performance

Designed for potato PCs:
- Server uses only `psutil` for telemetry (no shell commands)
- Telemetry updates every 5 seconds
- Lightweight tkinter GUI with minimal redraws
- WebSocket streaming for chat responses
- No heavy frameworks - pure Flask + vanilla JS
- Memory usage: ~30-50MB total
- Cached TTS engine for instant voice responses

## Configuration

Set environment variables for customization:
```bash
set JENNY_LAT=26.8467
set JENNY_LON=80.9462
set JENNY_CITY=Lucknow
set GEMINI_API_KEY=your_key_here
```

## Auto-Start with Windows

```bash
python scripts/startup.py
```

## License

MIT
- Random facts

### Web & Search
- Google search from chat
- YouTube search
- Instagram search/browse
- Open any website
- Bookmark management

### Productivity
- Notes system
- Todo list with completion tracking
- Memory vault for important info
- Timer/alarm
- Dictionary lookup

### Information
- Weather (Open-Meteo API)
- News (HackerNews)
- Crypto prices (CoinGecko)
- Public IP info
- Dictionary definitions

### Agentic
- Natural language command processing
- File/folder navigation
- Application lifecycle management
- Browser automation
- Offline brain engine for fallback responses

## Quick Start

### Prerequisites
```bash
pip install -r requirements.txt
```

### Launch
```bash
# Interactive launcher
python launcher.py

# Direct modes
python server.py          # Server only
python gui.py             # Main app
python gui.py overlay     # Overlay mode
```

### Auto-Start with Windows
```bash
python scripts/startup.py
```

### Wake Word Detector
```bash
python scripts/wakeword.py
```

## Project Structure

```
windows-version/
├── server.py              # Flask API server with all endpoints
├── gui.py                 # tkinter GUI (main app + overlay)
├── launcher.py            # Interactive launcher
├── requirements.txt       # Python dependencies
├── public/
│   ├── index.html         # Web frontend
│   ├── css/style.css      # Glassmorphism UI styles
│   └── js/app.js          # Frontend JavaScript
├── scripts/
│   ├── wakeword.py        # Voice wake word detector
│   └── startup.py         # Windows auto-start installer
└── data/                  # Runtime data (notes, vault, todos)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send command, get response |
| `/api/greeting` | GET | Daily greeting message |
| `/api/system-status` | GET | CPU, RAM, disk, battery, network |
| `/api/weather` | GET | Current weather |
| `/api/news` | GET | Top news stories |
| `/api/quote` | GET | Inspirational quote |
| `/api/fact` | GET | Random fact |
| `/api/crypto` | GET | Crypto prices |
| `/api/ip-info` | GET | Public IP information |
| `/api/dictionary` | GET | Word definition |
| `/api/bookmarks` | GET/POST/DELETE | Bookmark management |
| `/api/notes` | GET/POST | Notes management |
| `/api/todos` | GET/POST | Todo management |
| `/api/vault` | GET/POST/DELETE | Memory vault |
| `/api/briefing` | GET | Full daily briefing |

## Voice Commands

Just talk naturally to Jenny:
- "Open Chrome" / "Launch VS Code"
- "Set volume to 50" / "Mute"
- "What's the weather?"
- "Search YouTube for music"
- "Add todo buy groceries"
- "Remember my wifi password is..."
- "Take a screenshot"
- "Tell me a joke"
- "What time is it?"

## Performance

Designed for potato PCs:
- Server uses only `psutil` for telemetry (no shell commands)
- Telemetry updates every 5 seconds
- Lightweight tkinter GUI with minimal redraws
- WebSocket streaming for chat responses
- No heavy frameworks - pure Flask + vanilla JS
- Memory usage: ~30-50MB total

## Configuration

Set environment variables for customization:
```bash
set JENNY_LAT=26.8467
set JENNY_LON=80.9462
set JENNY_CITY=Lucknow
set GEMINI_API_KEY=your_key_here
```

## License

MIT

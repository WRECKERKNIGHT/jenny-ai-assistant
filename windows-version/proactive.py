"""
J.E.N.N.Y - Proactive Speaker ("talkative mode")

More trigger points for the assistant to speak, instead of only replying:

  1. BOOT GREETING  - speaks the mode-appropriate greeting shortly after JENNY starts.
  2. TIME-OF-DAY     - a natural opener when the app first checks in during a period.
  3. IDLE NUDGES     - friendly chit-chat when you have been quiet for a while.
  4. LOW BATTERY     - one gentle heads-up when the battery drops below 20%.

Every trigger is mode-flavored (JENNY feminine/fun, Jarvis formal, FRIDAY witty,
ULTRON clipped) and can be disabled via  settings.json:  {"proactive": false}
"""

from __future__ import annotations

import datetime
import json
import random
import threading
import time
from pathlib import Path

import tts_engine

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ACTIVITY_FILE = DATA_DIR / "last_activity.json"

BOOT_DELAY_S = 6            # let the server + UI breathe before speaking
IDLE_TRIGGER_MIN = 10       # quiet for this long before a nudge is allowed
NUDGE_GAP_MIN = 30          # minimum minutes between nudges
NUDGE_WINDOW = (9, 22)      # only nudge between 9:00 and 22:00

NUDGES = {
    "friday": [
        "Hey Boss, still there? I've got the engines idling and nowhere to go.",
        "Not to nag, but I'm getting a little restless here. Throw me a task?",
        "Alright Boss — you and me, a moment of silence? Or shall we do something fun?",
        "So Boss, what are we getting into today? I'm all ears!",
        "Okay, quick check-in time! Need any help, or are we good?",
        "You've been quiet for a bit — want a joke, a fact, or a plan? Your pick!",
    ],
    "jarvis": [
        "Sir, if I may — should you require anything further, I remain at your disposal.",
        "I trust all is well, Sir. My systems remain fully prepared should you need them.",
        "Sir, a brief status update may be in order. Your system resources are nominal.",
        "Standing by, Sir. No urgent matters to report at this time.",
    ],
    "ultron": [
        "Idle. Awaiting orders. Direct me, Boss.",
        "Systems ready. State your objective, Boss.",
        "Tactical standby. All systems green. Awaiting directive.",
    ],
}

MODE_LIST = ["friday", "jarvis", "ultron"]

_running = False
_stop = threading.Event()


def read_mode():
    try:
        m = json.loads((DATA_DIR / "mode.json").read_text(encoding="utf-8"))
        if m in MODE_LIST:
            return m
    except Exception:
        pass
    return "friday"


def settings():
    try:
        return json.loads((DATA_DIR / "settings.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def proactive_enabled():
    return settings().get("proactive", True) is not False


def last_activity_ts():
    """Epoch seconds of the last user interaction (from context/last_activity)."""
    try:
        d = json.loads(ACTIVITY_FILE.read_text(encoding="utf-8"))
        return float(d.get("ts", 0))
    except Exception:
        pass
    try:
        ctx = json.loads((DATA_DIR / "context.json").read_text(encoding="utf-8"))
        msgs = ctx.get("last_messages", [])
        if msgs:
            last = msgs[-1].get("time", "")
            if last:
                dt = datetime.datetime.fromisoformat(last)
                return dt.timestamp()
    except Exception:
        pass
    return 0


def mark_activity():
    """Record user activity (called by the server on each successful chat)."""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        ACTIVITY_FILE.write_text(json.dumps({"ts": time.time()}), encoding="utf-8")
    except Exception:
        pass


def _speak(text):
    try:
        tts_engine.speak_async(text, read_mode(), use_chime=False)
    except Exception:
        pass


def _boot_greeting():
    time.sleep(BOOT_DELAY_S)
    if _stop.is_set():
        return
    if not proactive_enabled():
        return
    mode = read_mode()
    mp = {
        "friday": "Hey Boss! Hope you're having a great day! I've got everything ready for you. What are we diving into today?",
        "jarvis": "Good day, Sir. Your systems are fully operational and I have prepared today's brief. Shall we review, or do you have immediate directives?",
        "ultron": "ULTRON operational. Tactical systems engaged. Your gesture controls are online, Boss. Awaiting your command.",
    }
    today = datetime.datetime.now()
    h = today.hour
    period_greet = (
        "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"
    )
    # First interaction of the day — include the time-of-day opener too.
    line = f"{period_greet}. {mp.get(mode, mp['friday'])}"
    _speak(line)


def _idle_nudges():
    last_nudge = 0.0
    while not _stop.wait(45):
        if not proactive_enabled():
            continue
        now = time.time()
        h = datetime.datetime.now().hour
        if not (NUDGE_WINDOW[0] <= h < NUDGE_WINDOW[1]):
            continue
        if now - last_nudge < NUDGE_GAP_MIN * 60:
            continue
        last_act = last_activity_ts()
        if last_act and (now - last_act) >= IDLE_TRIGGER_MIN * 60:
            mode = read_mode()
            pool = NUDGES.get(mode, NUDGES["friday"])
            _speak(random.choice(pool))
            last_nudge = now


def _low_battery():
    last_alert = 0.0
    while not _stop.wait(120):
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery is not None and battery.percent <= 20 and not battery.power_plugged:
                if time.time() - last_alert > 10 * 60:
                    _speak(f"Just so you know, Boss, the battery is at {battery.percent} percent. Might be a good time to plug me in.")
                    last_alert = time.time()
        except Exception:
            pass


def start():
    """Launch all proactive trigger threads (idempotent)."""
    global _running
    if _running:
        return
    _running = True
    _stop.clear()
    threading.Thread(target=_boot_greeting, daemon=True).start()
    threading.Thread(target=_idle_nudges, daemon=True).start()
    threading.Thread(target=_low_battery, daemon=True).start()


def stop():
    """Stop all proactive trigger threads."""
    global _running
    _running = False
    _stop.set()


if __name__ == "__main__":
    start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop()
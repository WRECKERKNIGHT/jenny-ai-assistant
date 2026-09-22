"""
J.E.N.N.Y - Speech-to-Text (Server-side microphone engine)

Why this exists: the old setup relied on the browser's Web Speech API (flaky in
pywebview / Chromium) and on `pyaudio` (no cp314 wheel, never installs). This
module captures the microphone with `sounddevice` (pure wheel) and transcribes
with two cascading engines:

  1. Groq Whisper (whisper-large-v3-turbo) — fast, extremely accurate, truly online.
     Uses the same Groq key as the chat brain (data/keys.json or env).
  2. Google Web Speech (SpeechRecognition) — free fallback that works with the
     same raw microphone bytes (no pyaudio needed).

The frontend mic button and the wake-word listener both use this single engine,
so recognition behaves identically everywhere.
"""

from __future__ import annotations

import io
import threading
import time
import wave

try:
    import sounddevice as sd
except Exception:
    sd = None
try:
    import numpy as np
except Exception:
    np = None

from pathlib import Path

BASE_DIR = Path(__file__).parent
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1

_rec_lock = threading.Lock()
# Coordinates hand-offs of the single microphone between the always-on wake
# listener and every on-demand capture (mic button, live session, wake command).
# The wake loop keeps ONE persistent InputStream open and holds `_rec_lock`
# while it streams. On-demand captures call suspend_wake_microphone() to make
# the listener pause and release the lock, then release_microphone() when done.
_REC_COND = threading.Condition()


def get_mics() -> list[dict]:
    """List input (microphone) devices detected by sounddevice."""
    if sd is None:
        return []
    try:
        out = []
        for i, d in enumerate(sd.query_devices()):
            if int(d.get("max_input_channels") or 0) > 0:
                out.append({"index": i, "name": d.get("name", "Mic"),
                            "default": i == default_mic_index()})
        return out
    except Exception:
        return []


def default_mic_index() -> int | None:
    """Index of the OS-default input device, if it can be determined."""
    if sd is None:
        return None
    try:
        info = sd.query_devices(kind="input")
        return int(info.get("index"))
    except Exception:
        try:
            for i, d in enumerate(sd.query_devices()):
                if int(d.get("max_input_channels") or 0) > 0:
                    return i
        except Exception:
            pass
    return None


def pick_device(requested=None) -> int | None:
    """Resolve the device index to actually capture from.

    Prefers the explicit request; otherwise the OS default input; otherwise
    the first available input device. Returns None when no mic exists.
    """
    if requested is not None and isinstance(requested, int):
        try:
            d = sd.query_devices(requested)
            if int(d.get("max_input_channels") or 0) > 0:
                return requested
        except Exception:
            pass
    dflt = default_mic_index()
    if dflt is not None:
        return dflt
    try:
        for i, d in enumerate(sd.query_devices()):
            if int(d.get("max_input_channels") or 0) > 0:
                return i
    except Exception:
        pass
    return None


def peak_level(data, samplerate: int = DEFAULT_SAMPLE_RATE) -> float:
    """Normalized peak amplitude (0..1) of a raw int16 numpy array."""
    if np is None or data is None or data.size == 0:
        return 0.0
    try:
        arr = np.asarray(data, dtype=np.float32) / 32768.0
        return float(np.max(np.abs(arr)))
    except Exception:
        return 0.0


def record_seconds(seconds: int = 5, samplerate: int = DEFAULT_SAMPLE_RATE,
                   device: int | None = None) -> bytes | None:
    """Record `seconds` of audio from the microphone and return WAV bytes.

    Uses voice-activity detection: capture stops early (~0.7s of trailing
    silence) once the user stops speaking, so replies feel instant instead of
    always waiting out the full window."""
    if sd is None or np is None:
        return None
    seconds = max(1, min(int(seconds), 12))
    dev = pick_device(device)
    if dev is None:
        raise RuntimeError("no_mic")
    samplerate = int(samplerate)
    CHUNK = int(0.1 * samplerate)          # 100ms analysis blocks
    silence_tail = int(0.7 * samplerate)   # stop ~0.7s after speech ends
    frames = []
    last_voice_at = 0
    started = False
    waited_silence = 0
    try:
        with sd.InputStream(samplerate=samplerate, channels=DEFAULT_CHANNELS,
                            dtype="int16", device=dev) as stream:
            first = True
            for _ in range(int(seconds * samplerate) // CHUNK + 4):
                # warm-up: consume ~0.25s so any start-click settles
                if first:
                    for _ in range(2):
                        stream.read(CHUNK)
                    first = False
                in_data, _ = stream.read(CHUNK)
                frames.append(in_data)
                lvl = peak_level(in_data, samplerate)
                if lvl > 0.003:
                    started = True
                    waited_silence = 0
                    last_voice_at = len(frames)
                else:
                    waited_silence += CHUNK
                # Early stop once we heard speech then a quiet tail.
                if started and waited_silence >= silence_tail:
                    break
            # If nothing but silence the whole window, bail.
            if not started:
                return None
            # Keep only the audio up to the last voiced block (+tail).
            keep = last_voice_at + int(silence_tail / CHUNK)
            frames = frames[:keep]
    except Exception as e:
        if _is_device_unavailable(e):
            raise RuntimeError("device_busy") from e
        return None

    if not frames:
        return None
    data = np.concatenate([np.asarray(f, dtype=np.int16) for f in frames])
    level = peak_level(data, samplerate)
    if level < 0.0005:
        return None
    return _to_wav(data, samplerate)


def _is_device_unavailable(e: Exception) -> bool:
    s = str(e).lower()
    for token in ("error opening input", "invalid device", "notfound",
                  "unavailable", "host api error", "stream error", "portaudio"):
        if token in s:
            return True
    return False


def _to_wav(data, samplerate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(DEFAULT_CHANNELS)
        w.setsampwidth(2)
        w.setframerate(samplerate)
        w.writeframes(data.tobytes())
    return buf.getvalue()


def _groq_key() -> str:
    import os
    k = os.environ.get("GROK_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    if k:
        return k
    try:
        import json
        keys = json.loads((BASE_DIR / "data" / "keys.json").read_text(encoding="utf-8-sig"))
        return str(keys.get("grok_api_key") or keys.get("groq_api_key") or "")
    except Exception:
        return ""


def transcribe_groq(wav_bytes: bytes) -> str | None:
    """Transcribe WAV bytes with Groq Whisper (whisper-large-v3-turbo)."""
    return transcribe_groq_file(wav_bytes, "audio.wav", "audio/wav")


# Speech language is deliberately restricted to English + Hindi so the
# recognizer never misdetects Russian or other languages. Persisted in
# data/settings.json under "stt_language" ("en" | "hi").
ALLOWED_STT_LANGS = {"en": "en", "hi": "hi"}
GROQ_LANG = {"en": "en", "hi": "hi"}
GOOGLE_LANG = {"en": "en-US", "hi": "hi-IN"}


def get_stt_language() -> str:
    """Resolve the configured STT language (default en), clamped to EN/HI."""
    try:
        import json
        from pathlib import Path
        s = json.loads((Path(__file__).parent / "data" / "settings.json").read_text(encoding="utf-8-sig"))
        lang = str(s.get("stt_language", "en")).lower().strip()
        if lang in ALLOWED_STT_LANGS:
            return ALLOWED_STT_LANGS[lang]
    except Exception:
        pass
    return "en"


def transcribe_groq(wav_bytes: bytes, language: str = "en") -> str | None:
    """Transcribe WAV bytes with Groq Whisper (whisper-large-v3-turbo)."""
    return transcribe_groq_file(wav_bytes, "audio.wav", "audio/wav", language)


def transcribe_groq_file(data: bytes, filename: str, mime: str, language: str = "") -> str | None:
    """Transcribe arbitrary audio bytes (wav/webm/ogg/mp3...) with Groq Whisper.

    Used by the phone-call bridge, which uploads browser MediaRecorder output
    (webm/opus) instead of PC-side WAV captures. `language` is pinned to the
    allowed EN/HI set so the model never drifts into Russian/other; an empty
    value falls back to the configured STT language.
    """
    key = _groq_key()
    if not key:
        return None
    lang = (language or "").lower().strip()
    if lang not in ALLOWED_STT_LANGS:
        lang = get_stt_language()
    try:
        from groq import Groq
        client = Groq(api_key=key)
        tr = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=(filename or "audio.webm", data, mime or "audio/webm"),
            language=GROQ_LANG[lang],
        )
        text = (getattr(tr, "text", "") or "").strip()
        return text or None
    except Exception:
        return None


def transcribe_google(wav_bytes: bytes, samplerate: int = DEFAULT_SAMPLE_RATE,
                      language: str = "") -> str | None:
    """Free fallback: Google Web Speech via SpeechRecognition (no pyaudio)."""
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        audio = sr.AudioData(wav_bytes, samplerate, DEFAULT_CHANNELS * 2)
        lang = (language or "").lower().strip()
        if lang not in ALLOWED_STT_LANGS:
            lang = get_stt_language()
        kw = {"language": GOOGLE_LANG[lang]} if lang in GOOGLE_LANG else {}
        return r.recognize_google(audio, **kw)
    except Exception:
        return None


def transcribe(wav_bytes: bytes, language: str = "") -> tuple[str, str]:
    """Try Groq Whisper first, then Google. Returns (text, engine)."""
    if not wav_bytes:
        return ("", "none")
    text = transcribe_groq(wav_bytes, language)
    if text:
        return (text, "groq-whisper")
    text = transcribe_google(wav_bytes, language)
    if text:
        return (text, "google")
    return ("", "none")


def record_and_transcribe(seconds: int = 5, device: int | None = None, language: str = "") -> dict:
    """One-shot microphone capture + transcription (used by the mic button).

    Asks the always-on wake listener to pause first so this capture owns the
    mic; the listener resumes automatically afterwards."""
    if not suspend_wake_microphone(timeout=8.0):
        return {"success": False, "error": "Microphone busy. Try again in a moment."}
    try:
        if not get_mics():
            return {"success": False, "error": "No microphone detected. Plug one in or check Windows privacy settings."}
        try:
            wav = record_seconds(seconds, device=device)
        except RuntimeError as e:
            code = str(e)
            if code == "no_mic":
                return {"success": False, "error": "No microphone detected. Check mic privacy settings."}
            if code == "device_busy":
                return {"success": False, "error": "Microphone is busy (another app is using it). Close that app and retry."}
            return {"success": False, "error": "Microphone capture failed. Check mic privacy settings."}
        if not wav:
            return {"success": False, "error": "No speech detected. Please speak louder or choose another mic.", "level": "quiet"}
        text, engine = transcribe(wav, language)
        if not text:
            return {"success": False, "error": "Could not recognize speech. Please try again.", "text": "", "engine": engine}
        return {"success": True, "text": text, "engine": engine, "seconds": seconds, "language": get_stt_language() if not language else language}
    finally:
        release_microphone()


# ---------------------------------------------------------------------------
# Server-side wake-word listener
#
# The browser wake word only works while the dashboard is open and focused.
# This listener runs in the background on the server itself, so the assistant
# stays "completely active" — just say "hey jenny" (etc.) and it responds
# immediately even when no dashboard page is attached. It keeps ONE persistent
# InputStream open and watches for speech utterances; on-demand captures
# (mic button, live sessions, wake commands) temporarily suspend it via
# suspend_wake_microphone()/release_microphone() so it never fights with an
# in-progress capture and never dies from repeated open/close cycles.
# ---------------------------------------------------------------------------

DEFAULT_WAKE_PHRASES = [
    "hey jenny", "hello jenny", "ok jenny", "hi jenny",
    "hey friday", "hey jarvis", "hey ultron",
]
_WAKE_LOCK = threading.Lock()
_wake_state = {
    "running": False,
    "thread": None,
    "on_detected": None,
    "phrases": list(DEFAULT_WAKE_PHRASES),
    "cooldown_until": 0.0,
    "last_heard": "",
    "suspend": False,
    "stream_open": False,
    "last_error": "",
    "reopen": False,
    "device": "",
    "errors": 0,
}


def _clean_text(t: str) -> str:
    """Lowercase + strip punctuation/spacing so phrase matching is forgiving."""
    import re
    t = re.sub(r"[^a-zA-Z0-9\s']", " ", str(t or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def wake_phrases() -> list[str]:
    with _WAKE_LOCK:
        return list(_wake_state["phrases"])


def set_wake_phrases(phrases: list[str]) -> None:
    with _WAKE_LOCK:
        _wake_state["phrases"] = [p for p in (phrases or []) if p and _clean_text(p)]


def wake_listener_active() -> bool:
    with _WAKE_LOCK:
        return bool(_wake_state["running"])


def wake_last_heard() -> str:
    with _WAKE_LOCK:
        return _wake_state["last_heard"]


def wake_status() -> dict:
    """Detailed real-time state for the dashboard (used by /api/wake/status).
    The extra fields let the UI show *why* the listener might be silent, e.g.
    a mic that's mid-hand-off or is blocked by another app."""
    dev = ""
    if sd is not None:
        try:
            i = default_mic_index()
            if i is not None:
                d = sd.query_devices(i)
                dev = str(d.get("name", ""))
        except Exception:
            pass
    with _WAKE_LOCK:
        return {"on": bool(_wake_state["running"]),
                "phrases": list(_wake_state["phrases"]),
                "lastHeard": _wake_state["last_heard"],
                "streamOpen": bool(_wake_state["stream_open"]),
                "suspended": bool(_wake_state["suspend"]),
                "lastError": _wake_state["last_error"] or "",
                "errors": _wake_state["errors"],
                "device": _wake_state["device"] or dev or ""}


def wake_restart() -> bool:
    """Ask the wake loop to drop its microphone stream and re-open it cleanly
    (recovers from stale host-API states after the mic fought another app)."""
    with _WAKE_LOCK:
        if not _wake_state["running"]:
            return False
        _wake_state["reopen"] = True
        _wake_state["last_error"] = ""
    with _REC_COND:
        _REC_COND.notify_all()
    return True


def detect_wake_phrase(text: str) -> str:
    """Return which wake phrase was detected in `text`, or '' if none."""
    t = _clean_text(text)
    if not t:
        return ""
    with _WAKE_LOCK:
        phrases = list(_wake_state["phrases"])
    for p in phrases:
        if _clean_text(p) in t:
            return p.strip()
    return ""


def start_wake_listener(on_detected=None) -> bool:
    """Start the background wake-word listener thread (idempotent).

    `on_detected(text, phrase)` is invoked on a background thread whenever a
    wake phrase is heard. Returns True if the listener is running.
    """
    with _WAKE_LOCK:
        if _wake_state["running"]:
            if on_detected is not None:
                _wake_state["on_detected"] = on_detected
            return True
        if sd is None or np is None:
            return False
        _wake_state["running"] = True
        _wake_state["on_detected"] = on_detected
        _wake_state["cooldown_until"] = 0.0
        _wake_state["reopen"] = False
        _wake_state["errors"] = 0
        _wake_state["last_error"] = ""
        _wake_state["thread"] = threading.Thread(target=_wake_loop, daemon=True)
        _wake_state["thread"].start()
        return True


def stop_wake_listener() -> None:
    with _WAKE_LOCK:
        _wake_state["running"] = False


def wake_cooldown(seconds: float = 5.0) -> None:
    """Suppress re-triggers for `seconds` (used right after a wake fires so the
    command-capture window isn't itself misheard as a second wake word)."""
    with _WAKE_LOCK:
        _wake_state["cooldown_until"] = time.time() + max(1.0, seconds)


# ---------------------------------------------------------------------------
# Microphone hand-off between the wake listener and on-demand captures.
#
# The wake loop keeps ONE persistent InputStream open and holds `_rec_lock`
# while it streams (repeatedly opening/closing a stream every ~3s on Windows
# caused "host api error" flakiness and made wake die after the first hit).
# On-demand captures (mic button, live session, wake command) call
# suspend_wake_microphone() so the listener closes its stream and releases the
# lock; once the capture finishes they call release_microphone() and the wake
# listener re-opens its stream automatically.
# ---------------------------------------------------------------------------

def _open_wake_stream():
    """Open the persistent wake-listener InputStream. Returns the stream or None."""
    if not _rec_lock.acquire(blocking=False):
        return None
    try:
        dev = pick_device()
        if dev is None:
            _rec_lock.release()
            with _WAKE_LOCK:
                _wake_state["device"] = ""
                _wake_state["last_error"] = ("No microphone detected. Plug one in, then I'll pick it up automatically. "
                                             "Also check Windows: Settings > Privacy & security > Microphone.")
            return None
        stream = sd.InputStream(samplerate=DEFAULT_SAMPLE_RATE, channels=DEFAULT_CHANNELS,
                                dtype="int16", device=dev)
        stream.start()
    except Exception as e:
        try:
            _rec_lock.release()
        except Exception:
            pass
        with _WAKE_LOCK:
            _wake_state["last_error"] = _actionable_mic_error(e)
            _wake_state["errors"] += 1
        return None
    with _REC_COND:
        _wake_state["stream_open"] = True
        _REC_COND.notify_all()
    with _WAKE_LOCK:
        _wake_state["last_error"] = ""
        try:
            d = sd.query_devices(dev)
            _wake_state["device"] = str(d.get("name", ""))
        except Exception:
            _wake_state["device"] = ""
    return stream


def _actionable_mic_error(e: Exception) -> str:
    s = str(e).lower()
    if any(t in s for t in ("host api error", "error opening", "invalid device",
                            "stream error", "unavailable", "no device", "portaudio")):
        return ("Microphone is busy or blocked. Close any app using the mic (teams, zoom, browser tabs), "
                "or allow desktop mic access in Windows Settings > Privacy > Microphone.")
    if "notfound" in s or "not found" in s:
        return "No microphone found. Plug one in or check Windows mic privacy settings."
    return (str(e)[:160] or e.__class__.__name__) + " — open Windows Settings > Privacy > Microphone if this keeps happening."


def _release_wake_stream(stream) -> None:
    """Close the persistent wake stream and free the capture lock."""
    if stream is not None:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
    try:
        _rec_lock.release()
    except RuntimeError:
        pass
    with _REC_COND:
        _wake_state["stream_open"] = False
        _REC_COND.notify_all()


def suspend_wake_microphone(timeout: float = 8.0) -> bool:
    """Pause the always-on wake listener so the caller can own the mic.

    On success the caller OWNS `_rec_lock` until it calls release_microphone().
    Returns False if the mic could not be grabbed within `timeout`."""
    start = time.time()
    with _REC_COND:
        _wake_state["suspend"] = True
        _REC_COND.notify_all()
        deadline = start + max(2.0, timeout)
        while _wake_state["stream_open"] and time.time() < deadline:
            _REC_COND.wait(0.2)
    try:
        got = _rec_lock.acquire(blocking=True, timeout=max(1.0, timeout))
    except Exception:
        got = False
    if not got:
        with _REC_COND:
            _wake_state["suspend"] = False
            _REC_COND.notify_all()
        return False
    return True


def release_microphone() -> None:
    """Release the mic taken with suspend_wake_microphone() and let the wake
    listener resume streaming."""
    try:
        _rec_lock.release()
    except RuntimeError:
        pass
    with _REC_COND:
        _wake_state["suspend"] = False
        _REC_COND.notify_all()


# 0.5s analysis blocks for the wake loop; keeps the last ~4s rolling window.
_WAKE_BLOCK = int(0.5 * DEFAULT_SAMPLE_RATE)
_WAKE_WINDOW = int(4.0 / 0.5)   # number of blocks held
_WAKE_QUIET_BLOCKS = 2          # ~1s of trailing silence ends an utterance


def _wake_loop() -> None:
    stream = None
    buf: list = []
    had_speech = False
    since_voice = 0
    last_check_at = 0.0
    silent_cycles = 0
    while True:
        with _WAKE_LOCK:
            if not _wake_state["running"]:
                break
            reopen = _wake_state["reopen"]
            if reopen:
                _wake_state["reopen"] = False
        if reopen and stream is not None:
            _release_wake_stream(stream)
            stream = None
            buf = []
            had_speech = False
            silent_cycles = 0
            time.sleep(0.3)
        with _REC_COND:
            suspended = _wake_state["suspend"]
        if suspended:
            if stream is not None:
                _release_wake_stream(stream)
                stream = None
                buf = []
                had_speech = False
                silent_cycles = 0
            with _REC_COND:
                _REC_COND.wait(0.4)
            continue
        if stream is None:
            # Be gentle: if the previouly-listed device just failed (another
            # app grabbed the mic), back off a little instead of hammering.
            if _wake_state["last_error"]:
                time.sleep(1.0)
            stream = _open_wake_stream()
            if stream is None:
                time.sleep(0.6)
                continue
            buf = []
            had_speech = False
            since_voice = 0
            silent_cycles = 0
        try:
            in_data, _ = stream.read(_WAKE_BLOCK)
        except Exception:
            _release_wake_stream(stream)
            stream = None
            buf = []
            time.sleep(0.5)
            continue
        silent_cycles += 1
        lvl = peak_level(in_data, DEFAULT_SAMPLE_RATE)
        buf.append(in_data)
        if len(buf) > _WAKE_WINDOW:
            buf.pop(0)
        if lvl > 0.003:
            had_speech = True
            since_voice = 0
        else:
            since_voice += 1
        now = time.time()
        with _WAKE_LOCK:
            cooldown = now < _wake_state["cooldown_until"]
        # During cooldown just keep buffering silently (never re-trigger).
        if cooldown:
            continue
        # Decide when to transcribe: end of a spoken utterance (quiet tail) or
        # a safety cadence while someone keeps talking for >~3s.
        transcribe_now = had_speech and since_voice >= _WAKE_QUIET_BLOCKS
        if not transcribe_now and had_speech and len(buf) >= _WAKE_WINDOW and (now - last_check_at) >= 2.6:
            transcribe_now = True
        if not transcribe_now:
            continue
        last_check_at = now
        had_speech = False
        since_voice = 0
        text = ""
        try:
            data = np.concatenate([np.asarray(f, dtype=np.int16) for f in buf[-6:]])
            wav = _to_wav(data, DEFAULT_SAMPLE_RATE)
            if wav:
                text, _engine = transcribe(wav)
        except Exception:
            text = ""
        if not text:
            continue
        with _WAKE_LOCK:
            _wake_state["last_heard"] = text
            cb = _wake_state["on_detected"]
        phrase = detect_wake_phrase(text)
        if phrase:
            wake_cooldown(6.0)
            if cb:
                threading.Thread(target=cb, args=(text, phrase), daemon=True).start()
    # Loop exits only when the listener was told to stop.
    if stream is not None:
        _release_wake_stream(stream)


# ---------------------------------------------------------------------------
# Live / streaming STT sessions
#
# Used by the dashboard mic button: instead of one-shot record-then-confirm,
# we open a streaming session that transcribes the audio-so-far every ~1.1s
# (interim) while the user is still talking, and only finalizes (done=True)
# once the user stops ~1.2s of silence or the session max is reached. The
# frontend polls /api/stt/live/status/<sid> and shows the live transcript.
# ---------------------------------------------------------------------------

_LIVE_SESSIONS = {}
_LIVE_SESSIONS_LOCK = threading.Lock()


def start_live_session(seconds: int = 12, device: int | None = None,
                       language: str = "") -> dict:
    """Begin a streaming transcription session.

    Holds the shared capture lock for its whole lifetime (the wake listener and
    one-shot captures skip while a session is running). Returns a session id
    plus initial status; call live_status(sid) to poll, stop_live_session(sid)
    to finalize early."""
    if sd is None or np is None:
        return {"success": False, "error": "Microphone engine unavailable"}
    seconds = max(3, min(int(seconds), 30))
    dev = pick_device(device)
    if dev is None:
        return {"success": False, "error": "No microphone detected. Check mic privacy settings."}
    # The always-on wake listener can briefly hold the capture lock; pause it
    # (waiting a few seconds) rather than failing the orb tap instantly.
    if not suspend_wake_microphone(timeout=8.0):
        return {"success": False, "error": "Microphone busy. Try again in a moment."}
    sid = f"{int(time.time() * 1000)}{threading.get_ident()}"
    session = {
        "id": sid,
        "success": True,
        "interim": "",
        "final": "",
        "done": False,
        "error": "",
        "engine": "",
        "language": get_stt_language() if not language else language,
        "device": dev,
        "max_seconds": seconds,
        "frames": [],
        "stop": threading.Event(),
    }
    with _LIVE_SESSIONS_LOCK:
        _LIVE_SESSIONS[sid] = session
    threading.Thread(target=_live_worker, args=(sid, session, dev, seconds, language or get_stt_language()),
                     daemon=True).start()
    return {"success": True, "sessionId": sid, "interim": "", "final": "", "done": False}


def _live_worker(sid: str, session: dict, dev: int, seconds: int, language: str) -> None:
    try:
        samplerate = DEFAULT_SAMPLE_RATE
        CHUNK = int(0.1 * samplerate)
        silence_tail = int(1.2 * samplerate)   # finalize ~1.2s after speech ends
        interim_every = int(1.1 * samplerate)  # re-transcribe while talking
        frames = []
        started = False
        waited_silence = 0
        last_interim = 0
        last_voice_at = 0
        with sd.InputStream(samplerate=samplerate, channels=DEFAULT_CHANNELS,
                            dtype="int16", device=dev) as stream:
            first = True
            for _ in range(int(seconds * samplerate) // CHUNK + 12):
                if session["stop"].is_set():
                    break
                if first:
                    for _ in range(2):
                        stream.read(CHUNK)
                    first = False
                in_data, _ = stream.read(CHUNK)
                frames.append(in_data)
                session["frames"] = frames
                lvl = peak_level(in_data, samplerate)
                if lvl > 0.003:
                    started = True
                    waited_silence = 0
                    last_voice_at = len(frames)
                else:
                    waited_silence += CHUNK
                # Interim transcription every ~1.1s while the user is talking.
                if started and (len(frames) * CHUNK - last_interim) >= interim_every:
                    last_interim = len(frames) * CHUNK
                    session["interim"] = _transcribe_audio(frames, samplerate, language)
                # User stopped talking -> finalize.
                if started and waited_silence >= silence_tail:
                    break
            # Keep only audio up to last voiced block (+ tail).
            if started:
                keep = last_voice_at + int(silence_tail / CHUNK)
                frames = frames[:keep]
                session["frames"] = frames
            session["final"] = _transcribe_audio(frames, samplerate, language) if started else ""
            session["interim"] = ""
    except Exception as e:
        session["error"] = str(e)
        session["done"] = True
        session["success"] = False
        if _is_device_unavailable(e):
            session["error"] = "device_busy"
    finally:
        session["done"] = True
        with _LIVE_SESSIONS_LOCK:
            _LIVE_SESSIONS.pop(sid, None)
        release_microphone()


def _transcribe_audio(frames: list, samplerate: int, language: str) -> str:
    if not frames:
        return ""
    try:
        data = np.concatenate([np.asarray(f, dtype=np.int16) for f in frames])
    except Exception:
        return ""
    if peak_level(data, samplerate) < 0.0005:
        return ""
    try:
        wav = _to_wav(data, samplerate)
    except Exception:
        return ""
    text, _engine = transcribe(wav, language)
    return text or ""


def live_status(sid: str) -> dict:
    """Poll the current live-session status (interim / final / done)."""
    with _LIVE_SESSIONS_LOCK:
        s = _LIVE_SESSIONS.get(sid)
    if not s:
        return {"success": False, "error": "Session not found"}, 404
    return {"success": True, "sid": sid,
            "interim": s["interim"], "final": s["final"],
            "done": s["done"], "error": s["error"]}


def stop_live_session(sid: str) -> dict:
    """Stop a live session early; the worker finalizes what was captured so far."""
    with _LIVE_SESSIONS_LOCK:
        s = _LIVE_SESSIONS.get(sid)
    if not s:
        return {"success": False, "error": "Session not found"}, 404
    s["stop"].set()
    for _ in range(50):
        with _LIVE_SESSIONS_LOCK:
            if sid not in _LIVE_SESSIONS:
                break
        time.sleep(0.1)
    return {"success": True}


if __name__ == "__main__":
    print("Microphones:", get_mics())
    print("Recording 4s... speak now")
    res = record_and_transcribe(4)
    print("Result:", res)
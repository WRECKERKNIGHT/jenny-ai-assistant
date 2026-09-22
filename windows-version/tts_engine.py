"""
J.E.N.N.Y - Neural TTS Engine (edge-tts with Windows SAPI fallback)

A completely new audio experience for the assistant:

  1. PRIMARY  - Microsoft Azure neural voices via `edge-tts` (near-human quality,
               streamed sentence-by-sentence for near-zero perceived latency).
               Voice per persona:
                   friday          -> en-US-JennyNeural  (feminine, warm, fun)
                   jarvis          -> en-GB-RyanNeural   (formal British male)
                   ultron          -> en-US-ChristopherNeural (deep, hard)
  2. FALLBACK - Windows SAPI voice (legacy) when edge-tts is offline/unavailable.
  3. CACHE    - synthesized WAVs are cached so repeat phrases are instant.

All speak() calls run on background threads so HTTP handlers never block.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "speak_cache"

# Per-persona neural voice + speaking rate. Rate applies on top of neutral.
# Tuple: (voice, rate, pitch, volume)
MODE_VOICES = {
    "friday": ("en-US-JennyNeural",      "+14%", "+2Hz", "+0%"),
    "jarvis": ("en-GB-RyanNeural",       "-4%", "-2Hz", "+0%"),
    "ultron": ("en-US-ChristopherNeural", "-12%", "-5Hz", "-10%"),
}
DEFAULT_VOICE = "en-US-JennyNeural"
DEFAULT_RATE = "+8%"
DEFAULT_PITCH = "+0Hz"
DEFAULT_VOLUME = "+0%"

# Legacy SAPI fallback keyword profiles (prefer natural female / British male)
SAPI_PROFILES = {
    "friday": (["jenny", "aria", "michelle", "natural", "female"], ["zira", "hazel", "susan", "female"], 0),
    "jarvis": (["george", "guy", "ryan", "natural", "male"], ["george", "david", "mark", "male"], -1),
    "ultron": (["guy", "ryan", "christopher", "mark", "natural"], ["david", "mark", "michael", "male"], -2),
}

# ---------------------------------------------------------------------------
# Engine state
# ---------------------------------------------------------------------------

_state_lock = threading.Lock()
_speaking = False
_last_text = ""
_last_start = 0.0
_stop_flag = threading.Event()

# Single-voice guarantee: all speak() callers funnel through this lock so two
# utterances (e.g. a proactive greeting + a chat reply) can never overlap or
# play as two different voices at the same time.
_play_lock = threading.Lock()

_engine_online = False
_engine_probed = False

# ---------------------------------------------------------------------------
# Voice bus - single-voice coordinator
#
# The "two voices at once" bug came from several independent audio paths
# playing simultaneously (server winsound + browser <audio> + Web Speech).
# This module is now the ONE place that decides who plays what:
#
#   * UI attached (dashboard/browser polls /api/speak/ping) -> server speech
#     is QUEUED and the UI drains it through the SAME browser audio
#     pipeline used for chat replies, so nothing can ever overlap.
#   * No UI attached (headless tray) -> the server speaks locally.
#
# The boot greeting uses two flags so proactive.py and /api/greeting can
# never both speak: whoever claims first wins, the other stays silent.
# ---------------------------------------------------------------------------

VOICE_BUS = []
_bus_lock = threading.Lock()
_ui_last_seen = 0.0
_boot_greeting_claimed = False
_boot_greeting_done = False


def mark_ui_activity() -> None:
    """Record that a UI client is attached (called on frontend polls)."""
    global _ui_last_seen
    _ui_last_seen = time.time()


def ui_client_active() -> bool:
    """True when a UI client has pinged within the last 30 seconds."""
    return (time.time() - _ui_last_seen) < 30.0


def boot_greeting_claimed() -> bool:
    return _boot_greeting_claimed


def claim_boot_greeting() -> None:
    global _boot_greeting_claimed
    _boot_greeting_claimed = True


def boot_greeting_done() -> bool:
    return _boot_greeting_done


def mark_boot_greeting_done() -> None:
    global _boot_greeting_done
    _boot_greeting_done = True


def queue_for_ui(text: str, mode: str | None, use_chime: bool) -> None:
    """Queue text for the UI to play through its single audio pipeline."""
    if not text:
        return
    with _bus_lock:
        VOICE_BUS.append({
            "text": text,
            "mode": mode or "friday",
            "chime": bool(use_chime),
            "ts": time.time(),
        })


def next_ui_item() -> dict | None:
    """Pop and return the next queued utterance for the UI (FIFO)."""
    with _bus_lock:
        return VOICE_BUS.pop(0) if VOICE_BUS else None


def ui_queue_depth() -> int:
    with _bus_lock:
        return len(VOICE_BUS)


# ---------------------------------------------------------------------------
# Edge-tts availability + prewarm
# ---------------------------------------------------------------------------

def edge_tts_available() -> bool:
    """Return True when the edge-tts module is importable."""
    global _engine_probed, _engine_online
    if _engine_probed:
        return _engine_online
    _engine_probed = True
    try:
        import edge_tts  # noqa: F401
        _engine_online = True
        return True
    except Exception:
        _engine_online = False
        return False


def prewarm(mode: str | None = None) -> None:
    """Warm the neural voice paths so the first utterance has no cold-start.

    Tries a tiny synthesis call; on success marks the engine online so the
    fast path is used from the very first sentence.
    """
    global _engine_online
    if not edge_tts_available():
        return False
    modes = [mode] if mode else list(MODE_VOICES.keys())
    for m in modes:
        voice, rate, pitch, volume = MODE_VOICES.get(m, (DEFAULT_VOICE, DEFAULT_RATE, DEFAULT_PITCH, DEFAULT_VOLUME))
        probe = f"System {m} audio engine online."
        tmp = CACHE_DIR / f"_probe_{m}.wav"
        try:
            if synthesize_wav(probe, tmp, voice, rate, pitch, volume):
                _engine_online = True
        except Exception:
            pass
    return _engine_online


# ---------------------------------------------------------------------------
# Sentence splitting (streaming granularity)
# ---------------------------------------------------------------------------

_SENT_RE = re.compile(r'(?<=[.!?])\s+|\n+')

def split_sentences(text: str, max_chars: int = 320) -> list[str]:
    """Split text into speakable, stream-friendly chunks."""
    if not text or not text.strip():
        return []
    parts = []
    for chunk in _SENT_RE.split(text.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        while len(chunk) > max_chars:
            cut = chunk.rfind(" ", 0, max_chars)
            if cut < 40:
                cut = max_chars
            parts.append(chunk[:cut].strip())
            chunk = chunk[cut:].strip()
        if chunk:
            parts.append(chunk)
    return parts


# ---------------------------------------------------------------------------
# edge-tts synthesis
# ---------------------------------------------------------------------------

def _async_synth(text: str, wav_path: str | Path, voice: str, rate: str, pitch: str = "+0Hz", volume: str = "+0%") -> bool:
    """Synthesize text to a WAV file using edge-tts (blocking, thread-safe)."""
    import edge_tts

    async def _run():
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch, volume=volume)
        await communicate.save(str(wav_path))

    try:
        asyncio.run(_run())
        return Path(wav_path).exists() and Path(wav_path).stat().st_size > 0
    except Exception:
        return False


def stream_tts(text: str, voice: str, rate: str, pitch: str = "+0Hz", volume: str = "+0%"):
    """Yield MP3 audio chunks from edge-tts as they are synthesized.

    Bridges edge-tts's async `Communicate.stream()` into a synchronous
    iterator so Flask can serve the response chunk-by-chunk — the browser
    receives the first audio bytes within ~0.5s instead of waiting for the
    entire sentence to finish synthesizing (the source of the old voice lag).
    """
    import edge_tts

    async def _gen():
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch, volume=volume)
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                yield chunk["data"]

    agen = _gen()
    loop = asyncio.new_event_loop()
    try:
        while True:
            try:
                data = loop.run_until_complete(agen.__anext__())
            except StopAsyncIteration:
                break
            yield data
    finally:
        try:
            loop.run_until_complete(agen.aclose())
        except Exception:
            pass
        loop.close()


def synthesize_wav(text: str, wav_path: str | Path, voice: str | None = None,
                   rate: str | None = None, pitch: str | None = None, volume: str | None = None) -> bool:
    """Synthesize text to WAV; returns True on success."""
    try:
        return _async_synth(text, wav_path, voice or DEFAULT_VOICE, rate or DEFAULT_RATE, pitch or DEFAULT_PITCH, volume or DEFAULT_VOLUME)
    except Exception:
        return False


def cached_wav(text: str, mode: str | None = None) -> Path | None:
    """Return a cached WAV for (mode, text) if it exists, else None."""
    key = f"{mode or 'default'}:{_clean_for_cache(text)}"
    h = hashlib.md5(key.encode()).hexdigest()
    p = CACHE_DIR / f"{h}.wav"
    return p if p.exists() else None


def _clean_for_cache(text: str) -> str:
    return re.sub(r"[#*_`\[\]]", "", text or "").strip().lower()


# ---------------------------------------------------------------------------
# Playback (winsound)
# ---------------------------------------------------------------------------

def _play_wav(path: str | Path) -> None:
    """Blocking WAV playback via winsound (stdlib)."""
    import winsound
    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_NODEFAULT)


def _play_chime() -> None:
    """Short two-note chime used for wake-word and notification feedback."""
    try:
        import winsound
        winsound.Beep(880, 90)
        winsound.Beep(1320, 120)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Legacy SAPI fallback
# ---------------------------------------------------------------------------

def _sapi_speak(text: str, mode: str | None) -> None:
    """Legacy Windows SAPI playback when edge-tts is unavailable."""
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        natural_kws, legacy_kws, rate = SAPI_PROFILES.get(mode, SAPI_PROFILES["friday"])
        try:
            descs = [(v, v.GetDescription().lower()) for v in voice.GetVoices()]
            if not descs:
                raise RuntimeError("no sapi voices")
            en = [t for t in descs if "en" in t[1]]

            def pick_weighted():
                # Heuristic: natural/online voices sound best — rank them first,
                # then persona keywords, and fall back to any English voice.
                best, best_score = None, -1
                for v, d in en or descs:
                    score = 0
                    if "natural" in d or "online" in d:
                        score += 4
                    wanted = natural_kws if ("natural" in d or "online" in d) else legacy_kws
                    for i, kw in enumerate(wanted):
                        if kw in d:
                            score += (len(wanted) - i)
                            break
                    if score > best_score:
                        best_score, best = score, v
                return best if best_score > -1 else None

            picked = pick_weighted()
            if picked is not None:
                voice.Voice = picked
            voice.Rate = rate
        except Exception:
            pass
        voice.Speak(_clean(text), 1)
        try:
            voice.WaitUntilDone(-1)
        except Exception:
            pass
    except Exception:
        pass
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public speak API
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Light text cleanup for smoother speech (kept engine-local)."""
    if not text:
        return text
    t = re.sub(r"https?://\S+", "the link", text)
    t = re.sub(r"www\.\S+", "the website", t)
    t = re.sub(r"[\u201c\u201d\u2018\u2019\"']", "", t)
    t = re.sub(r"(\d)\s*%", lambda m: f"{m.group(1)} percent", t)
    t = re.sub(r"(\d)\s*km/h", r"\1 kilometers per hour", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _speak_worker(text: str, mode: str | None, use_chime: bool) -> None:
    """Stream text aloud using edge-tts (cache + sentence streaming), else SAPI."""
    global _speaking, _last_text, _last_start
    text = _clean(text or "")
    if not text:
        return

    # Serialize speech: wait (briefly) if another utterance is already playing.
    if not _play_lock.acquire(timeout=30):
        return

    with _state_lock:
        _speaking = True
        _last_text = text[:200]
        _last_start = time.time()
    _stop_flag.clear()

    try:
        if use_chime and mode == "friday":
            try:
                _play_chime()
            except Exception:
                pass

        if edge_tts_available():
            voice, rate, pitch, volume = MODE_VOICES.get(mode, (DEFAULT_VOICE, DEFAULT_RATE, DEFAULT_PITCH, DEFAULT_VOLUME))
            cache = CACHE_DIR
            cache.mkdir(exist_ok=True)
            sentences = split_sentences(text)
            for i, sent in enumerate(sentences):
                if _stop_flag.is_set():
                    break
                wav = cached_wav(sent, mode)
                if wav is None:
                    key = f"{mode or 'default'}:{_clean_for_cache(sent)}"
                    h = hashlib.md5(key.encode()).hexdigest()
                    wav = cache / f"{h}.wav"
                    CACHE_DIR.mkdir(exist_ok=True, parents=True)
                    ok = synthesize_wav(sent, wav, voice, rate, pitch, volume)
                    if not ok or not wav.exists():
                        if not ok and i == 0:
                            _sapi_speak(text, mode)
                        continue
                if _stop_flag.is_set():
                    break
                try:
                    _play_wav(wav)
                except Exception:
                    pass
        else:
            _sapi_speak(text, mode)
    except Exception:
        try:
            _sapi_speak(text, mode)
        except Exception:
            pass
    finally:
        with _state_lock:
            _speaking = False
        try:
            _play_lock.release()
        except RuntimeError:
            pass


def speak(text: str, mode: str | None = None, use_chime: bool = False) -> None:
    """Enqueue speech in a background thread (non-blocking).

    Single-voice rule: when a UI client is attached the utterance goes onto
    the voice bus so the browser's one audio pipeline plays it - the server
    never speaks over the UI and vice-versa. Only speak locally (winsound /
    SAPI) when running headless.
    """
    if not text:
        return
    if ui_client_active():
        queue_for_ui(text, mode, use_chime)
        return
    threading.Thread(
        target=_speak_worker,
        args=(text, mode, use_chime),
        daemon=True,
    ).start()


def speak_async(text: str, mode: str | None = None, use_chime: bool = False) -> None:
    """Alias for speak() — keeps callers explicit about async fire-and-forget."""
    speak(text, mode=mode, use_chime=use_chime)


def stop_speech() -> None:
    """Halt any ongoing speech playback."""
    global _speaking
    _stop_flag.set()
    try:
        import winsound
        winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass
    with _state_lock:
        _speaking = False


def status() -> dict:
    """Live speech state for the frontend (speaking / last text / elapsed)."""
    with _state_lock:
        speaking = _speaking
        last = _last_text
        started = _last_start
    since = round(time.time() - started, 2) if started else 0
    if speaking and since and since > 90:
        speaking = False
    return {"speaking": speaking, "last": last, "since": since}


def voice_map() -> dict:
    """Describe the active neural voice per mode (used by /api/voice-info)."""
    out = {}
    for m, (v, r, p, vol) in MODE_VOICES.items():
        out[m] = {"neural_voice": v, "rate": r, "pitch": p, "volume": vol, "engine": "edge-tts" if edge_tts_available() else "SAPI-fallback",
                  "cached": bool(CACHE_DIR.exists() and any(CACHE_DIR.glob("*.wav")))}
    return out
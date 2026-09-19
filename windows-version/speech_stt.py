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
    """One-shot microphone capture + transcription (used by the mic button)."""
    if _rec_lock.acquire(blocking=False):
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
            _rec_lock.release()
    return {"success": False, "error": "Microphone busy. Try again in a moment."}


def capture_transcribe_loop(seconds_per_chunk: int = 4, max_chunks: int = 6) -> list[str]:
    """Record several consecutive chunks and transcribe each (for the
    wake-word listener). Returns a list of transcribed texts."""
    if sd is None:
        return []
    texts = []
    for _ in range(max_chunks):
        try:
            wav = record_seconds(seconds_per_chunk)
        except Exception:
            break
        if not wav:
            time.sleep(0.4)
            continue
        text, _engine = transcribe(wav)
        if text:
            texts.append(text)
        time.sleep(0.15)
    return texts


if __name__ == "__main__":
    print("Microphones:", get_mics())
    print("Recording 4s... speak now")
    res = record_and_transcribe(4)
    print("Result:", res)
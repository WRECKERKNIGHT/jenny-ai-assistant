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
    """Record `seconds` of audio from the microphone and return WAV bytes."""
    if sd is None or np is None:
        return None
    seconds = max(1, min(int(seconds), 12))
    dev = pick_device(device)
    if dev is None:
        raise RuntimeError("no_mic")
    try:
        data = sd.rec(int(seconds * samplerate), samplerate=samplerate,
                      channels=DEFAULT_CHANNELS, dtype="int16", device=dev)
        sd.wait()
        level = peak_level(data, samplerate)
        if level < 0.0005:
            # Essentially silence - likely the wrong device or mic muted.
            return None
        return _to_wav(data, samplerate)
    except Exception as e:
        if _is_device_unavailable(e):
            raise RuntimeError("device_busy") from e
        return None


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
        keys = json.loads((BASE_DIR / "data" / "keys.json").read_text(encoding="utf-8"))
        return str(keys.get("grok_api_key") or keys.get("groq_api_key") or "")
    except Exception:
        return ""


def transcribe_groq(wav_bytes: bytes) -> str | None:
    """Transcribe WAV bytes with Groq Whisper (whisper-large-v3-turbo)."""
    key = _groq_key()
    if not key:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=key)
        tr = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=("mic.wav", wav_bytes, "audio/wav"),
        )
        text = (getattr(tr, "text", "") or "").strip()
        return text or None
    except Exception:
        return None


def transcribe_google(wav_bytes: bytes, samplerate: int = DEFAULT_SAMPLE_RATE) -> str | None:
    """Free fallback: Google Web Speech via SpeechRecognition (no pyaudio)."""
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        audio = sr.AudioData(wav_bytes, samplerate, DEFAULT_CHANNELS * 2)
        return r.recognize_google(audio)
    except Exception:
        return None


def transcribe(wav_bytes: bytes) -> tuple[str, str]:
    """Try Groq Whisper first, then Google. Returns (text, engine)."""
    if not wav_bytes:
        return ("", "none")
    text = transcribe_groq(wav_bytes)
    if text:
        return (text, "groq-whisper")
    text = transcribe_google(wav_bytes)
    if text:
        return (text, "google")
    return ("", "none")


def record_and_transcribe(seconds: int = 5, device: int | None = None) -> dict:
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
            text, engine = transcribe(wav)
            if not text:
                return {"success": False, "error": "Could not recognize speech. Please try again.", "text": "", "engine": engine}
            return {"success": True, "text": text, "engine": engine, "seconds": seconds}
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
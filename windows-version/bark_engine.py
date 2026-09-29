"""
J.E.N.N.Y - Bark neural voice engine (suno-ai/bark, fully on-device).

Bark is a transformer-based text-to-audio model that produces expressive,
emotive speech directly on top of torch. It is the highest-quality tier in
the assistant's voice ladder and it runs 100% locally once the model weights
have been downloaded once:

    engine ladder (best -> fallback)
        bark  ->  edge-tts  ->  Windows SAPI

Bark is intentionally NOT force-loaded on boot. Importing torch is heavy and
the first synthesis downloads ~1.2 GB of model weights from the HuggingFace
hub, so the engine activates lazily on the first utterance and only when the
user picks it from Settings (`voice_engine: bark`). Availability probes that
only import modules are always cheap and are what /api/voice-info exposes.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "speak_cache"

# Bark voice prompts that ship with the model. We pick one per persona so the
# assistant keeps its distinct identity no matter which engine renders it.
#   friday -> young female, playful and warm
#   jarvis -> calm male, executive and measured
#   ultron -> deeper male, harder and lower
MODE_SPEAKERS = {
    "friday": "v2/en_speaker_9",
    "jarvis": "v2/en_speaker_6",
    "ultron": "v2/en_speaker_8",
}
DEFAULT_SPEAKER = "v2/en_speaker_6"

# Sampling temperature for the text/audio towers. Lower = more stable, higher
# = more theatrical. Warm personalities get slightly higher temps.
MODE_TEMPERATURES = {
    "friday": (0.8, 0.8),
    "jarvis": (0.7, 0.7),
    "ultron": (0.6, 0.6),
}
DEFAULT_TEMPS = (0.7, 0.7)

# Bark's audio clips at roughly 13.5 seconds (~14k samples/second x 13.5s).
# Keep each synthesis chunk comfortably inside that window.
MAX_CHARS_PER_CHUNK = 200

_state_lock = threading.Lock()
_available: bool | None = None          # None = not probed yet
_available_reason: str = ""
_last_generate_error: str = ""
_generated_count = 0

_SENT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_CACHE_CLEAN = re.compile(r"[#*_`\[\]]")


def _settings() -> dict:
    try:
        return json.loads((DATA_DIR / "settings.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _cache_key(text: str, mode: str | None) -> Path:
    clean = _CACHE_CLEAN.sub("", text or "").strip().lower()
    h = hashlib.md5(f"{mode or 'default'}:bark:{clean}".encode()).hexdigest()
    return CACHE_DIR / f"{h}.wav"


def cached_wav(text: str, mode: str | None) -> Path | None:
    p = _cache_key(text, mode)
    return p if p.exists() else None


# ---------------------------------------------------------------------------
# Availability probe (module-only, never downloads weights)
# ---------------------------------------------------------------------------

def missing_dependencies() -> list[str]:
    """Return the list of installable deps bark needs but is missing."""
    missing = []
    try:
        import torch  # noqa: F401
    except Exception:
        missing.append("torch")
    try:
        import bark  # noqa: F401
    except Exception:
        missing.append("bark (pip install suno-bark)")
    return missing


def available() -> bool:
    """True when torch + bark are importable. Cheap; no model download here."""
    global _available, _available_reason
    with _state_lock:
        if _available is not None:
            return _available
        missing = missing_dependencies()
        if not missing:
            _available = True
            _available_reason = ""
        else:
            _available = False
            _available_reason = "missing: " + ", ".join(missing)
        return _available


def availability_reason() -> str:
    if _available is None:
        available()
    return _available_reason


def installed_hint() -> str:
    """Human-readable command for installing the engine on a capable machine."""
    return (
        "pip install torch --index-url https://download.pytorch.org/whl/cpu "
        "&& pip install suno-bark"
    )


# ---------------------------------------------------------------------------
# Speakers + temps
# ---------------------------------------------------------------------------

def speaker_for(mode: str | None) -> str:
    return MODE_SPEAKERS.get(mode or "", DEFAULT_SPEAKER)


def temps_for(mode: str | None) -> tuple[float, float]:
    return MODE_TEMPERATURES.get(mode or "", DEFAULT_TEMPS)


# ---------------------------------------------------------------------------
# Sentence chunking (bark audio-window safe)
# ---------------------------------------------------------------------------

def split_chunks(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    """Split text into bark-safe synthesis chunks (< ~13.5s of audio each)."""
    if not text or not text.strip():
        return []
    parts = []
    for chunk in _SENT_RE.split(text.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        while len(chunk) > max_chars:
            cut = chunk.rfind(" ", 0, max_chars)
            if cut < 60:
                cut = max_chars
            parts.append(chunk[:cut].strip())
            chunk = chunk[cut:].strip()
        if chunk:
            parts.append(chunk)
    return parts


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def _render(text: str, speaker: str, text_temp: float, waveform_temp: float):
    """Low-level bark call -> numpy float32 audio. Lazy-loads the model.

    Raises the underlying exception if the model can't be loaded/downloaded so
    callers can report it honestly instead of pretending to speak.
    """
    global _generated_count
    import numpy as np
    from bark import generate_audio

    history_prompt = speaker
    audio = generate_audio(
        text,
        history_prompt=history_prompt,
        text_temp=text_temp,
        waveform_temp=waveform_temp,
        silent=True,
        progress=False,
    )
    with _state_lock:
        _generated_count += 1
    return np.asarray(audio, dtype=np.float32)


def _save_wav(audio, path: Path) -> bool:
    """Write float32 samples to a 16-bit PCM WAV (no torchaudio required)."""
    import numpy as np

    try:
        from bark.api import SAMPLE_RATE
    except Exception:
        SAMPLE_RATE = 22050
    x = np.clip(np.asarray(audio, dtype=np.float64), -1.0, 1.0)
    pcm = (x * 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    import wave

    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(SAMPLE_RATE))
        w.writeframes(pcm.tobytes())
    return path.exists() and path.stat().st_size > 0


def synthesize_wav(text: str, out_wav: str | Path, mode: str | None = None,
                   text_temp: float | None = None,
                   waveform_temp: float | None = None) -> bool:
    """Synthesize text to a WAV through bark; returns True on success.

    Long text is chunked and stitched with a short silence gap so a full reply
    still fits inside bark's audio window. The caller decides when to cache.
    """
    global _last_generate_error
    try:
        speaker = speaker_for(mode)
        tt, wt = temps_for(mode)
        if text_temp is not None:
            tt = text_temp
        if waveform_temp is not None:
            wt = waveform_temp
        chunks = split_chunks(text)
        if not chunks:
            return False
        parts = []
        for i, c in enumerate(chunks):
            part = _render(c, speaker, tt, wt)
            if part is None or len(part) == 0:
                continue
            parts.append(part)
            if i < len(chunks) - 1:
                _glue_silence(parts)
        if not parts:
            return False
        audio = _join(parts)
        return _save_wav(audio, Path(out_wav))
    except Exception as e:
        with _state_lock:
            _last_generate_error = f"{type(e).__name__}: {e}"
        return False


def _glue_silence(parts: list) -> None:
    """Append ~200ms of silence between bark chunks (smoother joins)."""
    import numpy as np

    try:
        from bark.api import SAMPLE_RATE
    except Exception:
        SAMPLE_RATE = 22050
    gap = int(SAMPLE_RATE * 0.2)
    parts.append(np.zeros(gap, dtype=np.float32))


def _join(parts) -> "np.ndarray":
    import numpy as np

    if len(parts) == 1:
        return np.asarray(parts[0], dtype=np.float32)
    return np.concatenate(parts).astype(np.float32)


def last_generate_error() -> str:
    with _state_lock:
        return _last_generate_error


def generated_count() -> int:
    with _state_lock:
        return _generated_count


# ---------------------------------------------------------------------------
# Status surface (for /api/voice-info and settings UI)
# ---------------------------------------------------------------------------

def status() -> dict:
    """Summarize the engine state honestly (never claims to be online while
    unavailable, never fabricates a downstream failure)."""
    ok = available()
    return {
        "engine": "bark",
        "available": ok,
        "reason": availability_reason() if not ok else "",
        "installed": not missing_dependencies(),
        "missing": missing_dependencies(),
        "speakers": dict(MODE_SPEAKERS),
        "temps": {k: {"text": v[0], "waveform": v[1]} for k, v in MODE_TEMPERATURES.items()},
        "generated": _generated_count,
        "last_error": last_generate_error() or None,
        "install_hint": installed_hint(),
        "enabled": str(_settings().get("voice_engine", "auto")).lower() == "bark",
    }
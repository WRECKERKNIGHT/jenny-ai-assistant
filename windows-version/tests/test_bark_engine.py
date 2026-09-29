"""Offline unit tests for the Bark voice engine and the TTS engine ladder.

These run WITHOUT torch/bark installed (the environment this suite lives in).
Expected behaviour when deps are missing:
  - bark_engine.available() is False with a truthful reason
  - synthesize_wav() returns False and records the real error
  - the tts_engine ladder falls back to edge-tts / SAPI and reports what it
    actually used (never a fabricated "bark")

Run:  python -m unittest discover -s tests -v
"""
import sys
import io
import unittest
from pathlib import Path
from unittest import mock

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bark_engine
import tts_engine


class BarkEngineTests(unittest.TestCase):
    def test_availability_is_boolean_and_reported(self):
        ok = bark_engine.available()
        self.assertIsInstance(ok, bool)
        self.assertEqual(ok, not bark_engine.missing_dependencies())
        if not ok:
            self.assertIn("missing", bark_engine.availability_reason())

    def test_speaker_and_temperature_mapping(self):
        self.assertEqual(bark_engine.speaker_for("jarvis"), "v2/en_speaker_6")
        self.assertEqual(bark_engine.speaker_for("friday"), "v2/en_speaker_9")
        self.assertEqual(bark_engine.speaker_for("ultron"), "v2/en_speaker_8")
        self.assertEqual(bark_engine.speaker_for(None), bark_engine.DEFAULT_SPEAKER)
        self.assertEqual(bark_engine.temps_for("friday"), (0.8, 0.8))

    def test_chunking_stays_inside_bark_audio_window(self):
        long = "First sentence. " * 30 + "End."
        chunks = bark_engine.split_chunks(long)
        self.assertTrue(chunks)
        self.assertTrue(all(len(c) <= bark_engine.MAX_CHARS_PER_CHUNK for c in chunks))
        self.assertEqual(" ".join(chunks).replace(" ", ""),
                         long.replace(" ", "").rstrip(".") + ".")

    def test_empty_input_returns_no_chunks(self):
        self.assertEqual(bark_engine.split_chunks(""), [])
        self.assertEqual(bark_engine.split_chunks("   \n "), [])

    def test_cache_key_is_deterministic_and_mode_scoped(self):
        a = bark_engine._cache_key("Hello Sir.", "jarvis")
        b = bark_engine._cache_key("Hello Sir.", "jarvis")
        c = bark_engine._cache_key("Hello Sir.", "friday")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(a.suffix, ".wav")

    def test_synthesis_offline_fails_honestly(self):
        out = str(bark_engine.CACHE_DIR.parent.parent / "nope_bark_test.wav")
        ok = bark_engine.synthesize_wav("hello", out, "jarvis")
        self.assertFalse(ok)
        self.assertTrue(bark_engine.last_generate_error())

    def test_status_surface_never_lies_online(self):
        st = bark_engine.status()
        self.assertEqual(st["engine"], "bark")
        self.assertEqual(st["available"], bark_engine.available())
        self.assertIn("install_hint", st)
        self.assertIsInstance(st["speakers"], dict)


class TtsEngineLadderTests(unittest.TestCase):
    def test_auto_prefers_bark_then_edge_then_sapi(self):
        with mock.patch("tts_engine._engine_setting", return_value="auto"):
            self.assertIn(tts_engine._chosen_engine(), ("bark", "edge-tts", "sapi"))
            if not bark_engine.available():
                self.assertNotEqual(tts_engine._chosen_engine(), "bark")

    def test_pinned_bark_degrades_to_edge_or_sapi(self):
        with mock.patch("tts_engine._engine_setting", return_value="bark"):
            self.assertNotEqual(tts_engine._chosen_engine(), "bark")
            self.assertIn(tts_engine._chosen_engine(), ("edge-tts", "sapi"))

    def test_pinned_sapi_is_respected(self):
        with mock.patch("tts_engine._engine_setting", return_value="sapi"):
            self.assertEqual(tts_engine._chosen_engine(), "sapi")

    def test_voice_map_surfaces_bark_and_active_engine(self):
        vm = tts_engine.voice_map()
        self.assertIn("__engine_choice__", vm)
        self.assertIn("__bark__", vm)
        self.assertEqual(vm["__bark__"]["engine"], "bark")
        for m in ("friday", "jarvis", "ultron"):
            self.assertIn("engine", vm[m])


if __name__ == "__main__":
    unittest.main(verbosity=2)

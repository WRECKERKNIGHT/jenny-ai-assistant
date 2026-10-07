"""Offline unit tests for the vision computer-use agent.

They run WITHOUT the network and WITHOUT touching the machine: the model call,
the screenshot and the input injection are all patched. What is exercised here
is the part that must never be wrong -- the closed action vocabulary, the
coordinate clamping, the OS/shell fences, the kill switch and the audit log.

Run:  python -m pytest tests -q -s -p no:cacheprovider
  or: python -m unittest discover -s tests -v
"""
import sys
import io
import unittest
from pathlib import Path
from unittest import mock

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vision_agent as va


class ExtractJsonTests(unittest.TestCase):
    def test_plain_object(self):
        self.assertEqual(va._extract_json('{"action":"wait"}'), {"action": "wait"})

    def test_object_inside_prose_and_fence(self):
        raw = 'Sure! Here it is:\n```json\n{"action":"click","x":10,"y":20}\n```'
        self.assertEqual(va._extract_json(raw)["action"], "click")

    def test_braces_and_quotes_inside_strings(self):
        raw = '{"action":"type","text":"a {b} \\"c\\" d"} trailing'
        got = va._extract_json(raw)
        self.assertEqual(got["action"], "type")
        self.assertEqual(got["text"], 'a {b} "c" d')

    def test_no_object_is_none(self):
        self.assertIsNone(va._extract_json("I would click the start button."))
        self.assertIsNone(va._extract_json(""))
        self.assertIsNone(va._extract_json(None))

    def test_broken_json_is_none(self):
        self.assertIsNone(va._extract_json('{"action": "click", "x": '))
        self.assertIsNone(va._extract_json('{"unterminated": "string}'))


class ClampAndNumTests(unittest.TestCase):
    def test_clamp_rounds_and_bounds(self):
        self.assertEqual(va._clamp(5.6, 0, 100), 6)
        self.assertEqual(va._clamp(-5, 0, 100), 0)
        self.assertEqual(va._clamp(1000, 0, 100), 100)

    def test_num_tolerates_junk_and_booleans(self):
        self.assertEqual(va._num("42"), 42.0)
        self.assertEqual(va._num(None, 3), 3.0)
        self.assertEqual(va._num(True, 7), 7.0)   # bools are not numbers here
        self.assertEqual(va._num("abc", 1.5), 1.5)

    def test_norm_path_expands_user(self):
        self.assertTrue(va._norm_path("~/notes.txt").lower().endswith("notes.txt"))
        self.assertEqual(va._norm_path(None), str(Path(str("")).expanduser()))


class ProtectedPathTests(unittest.TestCase):
    def test_windows_tree_is_protected(self):
        for p in (r"c:\windows\system32\cmd.exe", "C:/Windows/notepad.exe",
                  r"d:\program files\app\run.exe", r"c:\bootmgr"):
            self.assertTrue(va._protected(p), p)

    def test_normal_paths_are_allowed(self):
        for p in (r"c:\Users\me\Documents\todo.txt",
                  r"C:\Users\me\Downloads\file.pdf", r"d:\code\app.py"):
            self.assertFalse(va._protected(p), p)


class NormaliseTests(unittest.TestCase):
    W, H, SCALE = 1366, 768, 2.0

    def norm(self, action):
        return va._normalise(action, self.W, self.H, self.SCALE)

    def test_not_a_dict(self):
        ok, why = self.norm('"click"')
        self.assertFalse(ok)
        self.assertIn("JSON object", why)

    def test_unknown_action_is_refused(self):
        ok, why = self.norm({"action": "format_disk", "drive": "c"})
        self.assertFalse(ok)
        self.assertIn("unknown action", why)

    def test_click_coords_are_clamped_and_descaled(self):
        ok, out = self.norm({"action": "click", "x": 5000, "y": -20})
        self.assertTrue(ok)
        self.assertEqual(out["img"], (self.W - 1, 0))     # clamped in image space
        self.assertEqual(out["xy"][1], 0)                 # and on the screen
        self.assertTrue(0 <= out["xy"][0] <= self.W - 1)
        ok, out = self.norm({"action": "click", "x": 100, "y": 200})
        self.assertEqual(out["img"], (100, 200))
        self.assertEqual(out["xy"], (50, 100))            # image px / scale

    def test_click_without_coords_is_refused(self):
        ok, why = self.norm({"action": "click"})
        self.assertFalse(ok)
        self.assertIn("x and y", why)

    def test_drag_needs_all_four_points(self):
        ok, why = self.norm({"action": "drag", "x1": 1, "y1": 1, "x2": 2})
        self.assertFalse(ok)
        ok, out = self.norm({"action": "drag", "x1": 1, "y1": 1, "x2": 5, "y2": 5})
        self.assertTrue(ok)
        self.assertEqual(sorted(out), ["action", "xy1", "xy2"])

    def test_scroll_defaults_when_model_omits_point(self):
        ok, out = self.norm({"action": "scroll", "amount": -300})
        self.assertTrue(ok)
        self.assertEqual(out["amount"], -300)
        self.assertEqual(len(out["xy"]), 2)

    def test_scroll_zero_or_huge_is_fixed(self):
        self.assertFalse(self.norm({"action": "scroll", "amount": 0})[0])
        ok, out = self.norm({"action": "scroll", "amount": 10 ** 9})
        self.assertTrue(ok)
        self.assertEqual(out["amount"], 5000)

    def test_type_is_empty_refused_and_capped(self):
        self.assertFalse(self.norm({"action": "type", "text": "   "})[0])
        ok, out = self.norm({"action": "type", "text": "x" * 9000})
        self.assertTrue(ok)
        self.assertEqual(len(out["text"]), 4000)

    def test_hotkey_and_press(self):
        self.assertFalse(self.norm({"action": "hotkey", "keys": []})[0])
        ok, out = self.norm({"action": "hotkey", "keys": ["CTRL", " T "]})
        self.assertTrue(ok)
        self.assertEqual(out["keys"], ["ctrl", "t"])
        self.assertFalse(self.norm({"action": "press", "key": ""})[0])
        self.assertTrue(self.norm({"action": "press", "key": "ENTER"})[0])

    def test_click_text_is_required(self):
        self.assertFalse(self.norm({"action": "click_text", "text": " "})[0])
        ok, out = self.norm({"action": "click_text", "text": "Save"})
        self.assertTrue(ok)
        self.assertEqual(out["text"], "Save")

    def test_file_actions_refuse_protected_paths(self):
        for name in ("file_read", "file_list", "file_write"):
            action = {"action": name, "path": r"c:\windows\system32"}
            if name == "file_write":
                action["text"] = "x"
            ok, why = self.norm(action)
            self.assertFalse(ok, name)
            self.assertIn("protected", why)

    def test_file_write_needs_text(self):
        ok, why = self.norm({"action": "file_write", "path": r"c:\Users\me\a.txt"})
        self.assertFalse(ok)
        self.assertIn("text", why)

    def test_shell_fences_block_destructive_commands(self):
        for cmd in ("format c: /y", "diskpart", "rm -rf /", "reg delete HKLM\\x",
                    "bcdedit /set", "shutdown /s", "Remove-Item -Recurse C:\\x",
                    "del /s /q c:\\", ":(){ :|:& };:", "mkfs.ext4 /dev/sda"):
            ok, why = self.norm({"action": "shell", "command": cmd})
            self.assertFalse(ok, cmd)
            self.assertIn("blocked", why)

    def test_shell_allows_a_normal_command(self):
        ok, out = self.norm({"action": "shell", "command": "dir C:\\Users"})
        self.assertTrue(ok)
        self.assertEqual(out["command"], "dir C:\\Users")

    def test_shell_length_limit(self):
        self.assertFalse(self.norm({"action": "shell", "command": "x" * 501})[0])

    def test_wait_is_capped(self):
        ok, out = self.norm({"action": "wait", "seconds": 999})
        self.assertTrue(ok)
        self.assertEqual(out["seconds"], 30.0)

    def test_terminal_actions_carry_their_payload(self):
        ok, out = self.norm({"action": "done", "summary": "folder opened"})
        self.assertTrue(ok)
        self.assertEqual(out["summary"], "folder opened")
        ok, out = self.norm({"action": "fail", "reason": "no Save button"})
        self.assertTrue(ok)
        self.assertEqual(out["reason"], "no Save button")


class RunOnceTests(unittest.TestCase):
    """One see -> think -> act cycle with capture/decide/exec mocked out."""

    CAPTURE = {"jpeg": b"", "w": 1366, "h": 768, "scale": 1.0}

    def setUp(self):
        va.reset()
        # reset() arms the agent; the run log belongs to the previous run and
        # is only cleared by _loop, so the tests clear it the same way.
        va._set(log=[], counts={"ok": 0, "failed": 0})

    def tearDown(self):
        va.reset()

    def run_step(self, decide_returns, exec_returns=None):
        with mock.patch.object(va, "_capture", return_value=self.CAPTURE), \
             mock.patch.object(va, "_decide", side_effect=decide_returns) as dec, \
             mock.patch.object(va, "_exec", return_value=exec_returns or {"ok": True, "note": "clicked"}) as ex:
            result = va.run_once("open notepad", 1, 5)
        return result, dec, ex

    def test_valid_action_is_executed_and_logged(self):
        result, dec, ex = self.run_step(['{"action":"click","x":10,"y":20}'])
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "click")
        ex.assert_called_once()
        st = va.status()
        self.assertEqual(st["counts"]["ok"], 1)
        self.assertEqual(st["counts"]["failed"], 0)
        self.assertEqual(len(st["log"]), 1)
        self.assertEqual(st["log"][0]["action"], "click")

    def test_prose_reply_retries_once_then_fails_loudly(self):
        result, dec, ex = self.run_step(["I think I would click here",
                                         "and again I will not give JSON"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["action"], "invalid")
        self.assertEqual(dec.call_count, 2)      # the corrective retry happened
        ex.assert_not_called()                  # nothing ran on a bad reply
        self.assertEqual(va.status()["counts"]["failed"], 1)

    def test_unknown_action_from_model_never_reaches_exec(self):
        result, _, ex = self.run_step(['{"action":"delete_registry_key"}'])
        self.assertFalse(result["ok"])
        self.assertIn("unknown action", result["note"])
        ex.assert_not_called()

    def test_failed_action_is_counted_as_failed(self):
        result, _, _ = self.run_step(['{"action":"click","x":1,"y":1}'],
                                     exec_returns={"ok": False, "note": "nothing there"})
        self.assertFalse(result["ok"])
        st = va.status()
        self.assertEqual(st["counts"]["failed"], 1)
        self.assertEqual(st["log"][0]["ok"], False)

    def test_stop_flag_aborts_before_acting(self):
        va._stop.set()
        with mock.patch.object(va, "_capture", return_value=self.CAPTURE), \
             mock.patch.object(va, "_decide") as dec, \
             mock.patch.object(va, "_exec") as ex:
            with self.assertRaises(va.Stopped):
                va.run_once("x", 1, 5)
        ex.assert_not_called()
        dec.assert_not_called()
        va._stop.clear()


class LifecycleTests(unittest.TestCase):
    def tearDown(self):
        va.reset()

    def test_idle_status_shape(self):
        st = va.status()
        self.assertEqual(st["status"], "idle")
        self.assertFalse(st["active"])
        self.assertFalse(st["killed"])
        self.assertEqual(st["steps"], {"done": 0, "of": st["max_steps"]})
        self.assertIn("has_pyautogui", st)

    def test_empty_goal_is_refused_without_side_effects(self):
        r = va.start("   ")
        self.assertFalse(r["ok"])
        self.assertIn("goal", r["error"].lower())
        self.assertEqual(va.status()["status"], "idle")

    def test_kill_halts_and_start_refuses_until_reset(self):
        r = va.kill("test")
        self.assertTrue(r["ok"])
        st = va.status()
        self.assertEqual(st["status"], "killed")
        self.assertTrue(st["killed"])
        self.assertEqual(st["kill_reason"], "test")

        with mock.patch.object(va, "HAS_PYAUTOGUI", True), \
             mock.patch.object(va, "_groq_key", return_value="gsk_test"):
            r = va.start("open notepad")
        self.assertFalse(r["ok"])
        self.assertIn("kill switch", r["error"].lower())

        va.reset()
        st = va.status()
        self.assertFalse(st["killed"])
        self.assertEqual(st["status"], "idle")
        self.assertEqual(st["kill_reason"], "")

    def test_stop_while_idle_reports_honestly(self):
        r = va.stop("panel")
        self.assertTrue(r["ok"])
        self.assertFalse(r["was_running"])
        self.assertEqual(va.status()["status"], "stopped")

    def test_status_is_a_snapshot_not_live_state(self):
        st1 = va.status()
        st1["log"].append({"n": 999})
        st2 = va.status()
        self.assertEqual(st2["log"], [])


class AvailableTests(unittest.TestCase):
    def test_available_reports_real_capability(self):
        with mock.patch.object(va, "_working_model", return_value="qwen/qwen3.8-27b"):
            info = va.available()
        self.assertIsInstance(info["ok"], bool)
        self.assertEqual(info["ok"], bool(info["has_pyautogui"] and info["has_key"]))
        self.assertEqual(info["model"], "qwen/qwen3.8-27b")
        self.assertEqual(info["kill_hotkey"], "ctrl+alt+x")
        self.assertEqual(info["actions"], sorted(va._ACTIONS))

    def test_action_vocabulary_is_closed(self):
        expected = {"move", "click", "double_click", "right_click", "drag", "scroll",
                    "type", "hotkey", "press", "click_text", "file_read", "file_list",
                    "file_write", "shell", "wait", "done", "fail"}
        self.assertEqual(va._ACTIONS, expected)


if __name__ == "__main__":
    unittest.main()

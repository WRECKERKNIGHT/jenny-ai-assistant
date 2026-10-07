"""
JENNY Vision Agent — a computer-use loop that actually looks at the screen.

Why this exists: everything else in JENNY is a *named* action ("open chrome",
"set volume 50"), so it only works for windows JENNY was programmed with, and
multi-step commands are just that sentence split on "then". This closes the
gap: screenshot the real desktop -> ask a multimodal model what to do next ->
execute exactly one action -> look again -> repeat until the goal is met or the
kill switch lands.

Design rules (all of them are deliberate):
  - One action per step, never a batch. Re-reading the screen after every
    action means a wrong click shows up on the next step instead of cascading.
  - The kill switch is checked before *every* action, not once per step, so
    stop lands within one action even mid-plan.
  - The action vocabulary is a closed set. The model cannot invent an action,
    so it cannot reach a destructive path it was not handed.
  - File and shell access are audited and fenced: the OS itself (C:\\Windows,
    Program Files, boot config) is off limits, everything else is allowed
    because "do anything anywhere" is the actual request.
  - Every action -- success or failure -- goes to the safety audit log.
  - Nothing claims success it did not observe.

Kill switch, in order of how fast you can reach it:
  Ctrl+Alt+X (global hotkey)  >  POST /api/agent/kill  >  the panel STOP button
  >  voice "stop agent"  >  throwing the mouse into the top-left corner
  (pyautogui FAILSAFE).
"""

import base64
import difflib
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True      # mouse to the top-left corner aborts anything
    pyautogui.PAUSE = 0.04
    HAS_PYAUTOGUI = True
except Exception:                  # headless / no display: agent must still load
    pyautogui = None
    HAS_PYAUTOGUI = False

try:
    import safety
except Exception:                  # safety is an audit trail, never a blocker
    safety = None

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_MAX_STEPS = 20
STEP_PACING = 0.25                 # breathing room so the screen settles
MAX_LOG = 200
FRAME_MAX_SIDE = 1280              # keep the image cheap in tokens

# The key this account can actually use for *images* was probed live; every
# other candidate on the free tier returned model_not_found. Listed anyway so
# a future model swap is one line, and the probe below keeps us honest.
VISION_MODELS = [
    "qwen/qwen3.8-27b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "mistralai/mistral-small-3.2-24b-instruct",
]
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Closed action set. Anything not in here is rejected before it can execute.
_ACTIONS = {
    "move", "click", "double_click", "right_click", "drag", "scroll",
    "type", "hotkey", "press", "click_text",
    "file_read", "file_list", "file_write", "shell",
    "wait", "done", "fail",
}

# The OS itself is not a legitimate target for an unattended agent.
_PROTECTED = ("c:\\windows", "c:/windows", "program files", "bootmgr")
_SHELL_BLOCK = (
    "format ", "diskpart", "rm -rf", "reg delete", "bcdedit", "shutdown",
    "Remove-Item -Recurse".lower(), "del /s /q", ":(){", "mkfs",
)

_LOCK = threading.Lock()
_stop = threading.Event()   # one run at a time
_kill = threading.Event()   # global kill switch, survives the run
_state = {
    "status": "idle",       # idle | running | done | stopped | killed | error
    "goal": "",
    "step": 0,
    "max_steps": DEFAULT_MAX_STEPS,
    "log": [],
    "started_at": "",
    "ended_at": "",
    "last_error": "",
    "kill_reason": "",
    "model": "",
    "hotkey": "",
    "frame_ts": "",
    "counts": {"ok": 0, "failed": 0},
}
_frame = {"jpeg": None}
_model_cache = {"id": None, "ts": 0.0}
_hotkey_started = False


class Stopped(Exception):
    """Raised inside the loop when stop/kill/FAILSAFE fires."""


# ---------------------------------------------------------------- key / model

def _groq_key():
    """BOM-tolerant key read. data/keys.json has been both an object and an
    array on this machine, so walk whatever shape we find."""
    for env in ("GROK_API_KEY", "GROQ_API_KEY", "GROQ_KEY"):
        v = os.environ.get(env)
        if v:
            return v.strip()
    path = DATA_DIR / "keys.json"
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8-sig")
        found = []

        def walk(o):
            if isinstance(o, str) and o.startswith("gsk_"):
                found.append(o)
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(json.loads(raw))
        return found[0] if found else None
    except Exception:
        return None


def _working_model(force=False):
    """First vision-capable model the key accepts. Probed, never assumed."""
    now = time.time()
    if _model_cache["id"] and not force and (now - _model_cache["ts"]) < 3600:
        return _model_cache["id"]
    key = _groq_key()
    if not key:
        return None
    # Groq rejects images under 32px per side, so the probe needs a real
    # (tiny) image rather than a 1x1 stub.
    try:
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (32, 32), (8, 10, 20)).save(buf, "PNG")
        tiny = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None
    for model in VISION_MODELS:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "ok"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + tiny}},
            ]}],
            "max_tokens": 2,
        }).encode("utf-8")
        req = urllib.request.Request(GROQ_URL, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            "User-Agent": _UA,
        })
        try:
            urllib.request.urlopen(req, timeout=30).read()
            _model_cache.update({"id": model, "ts": now})
            return model
        except urllib.error.HTTPError as e:
            # 404 = no such model for this key; anything else is a real problem
            # but still means "not this one".
            try:
                e.read()
            except Exception:
                pass
            continue
        except Exception:
            break
    return None


# ------------------------------------------------------------------- capture

def _capture():
    """One JPEG of the real screen plus the scale factor between what the model
    sees and the real display (we downsize oversized screens for tokens)."""
    from PIL import ImageGrab
    shot = ImageGrab.grab()
    w, h = shot.size
    scale = 1.0
    if max(w, h) > FRAME_MAX_SIDE:
        scale = FRAME_MAX_SIDE / float(max(w, h))
        shot = shot.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    buf = io.BytesIO()
    shot.save(buf, "JPEG", quality=58)
    jpeg = buf.getvalue()
    _frame["jpeg"] = jpeg
    with _LOCK:
        _state["frame_ts"] = datetime.now().strftime("%H:%M:%S")
    sent_w = int(round(w * scale))
    sent_h = int(round(h * scale))
    return {"b64": base64.b64encode(jpeg).decode(), "w": w, "h": h,
            "sent_w": sent_w, "sent_h": sent_h, "scale": scale}


def frame():
    """JPEG of the last thing the agent saw. Before the first step there is
    nothing cached, so take one capture rather than hand the panel an empty
    body it would render as a broken image."""
    if not _frame.get("jpeg"):
        try:
            _capture()
        except Exception:
            return b""
    return _frame.get("jpeg") or b""


# -------------------------------------------------------------------- decide

def _system_prompt(goal, step, max_steps, w, h):
    return (
        "You are JENNY's hands on a Windows PC. You see a screenshot of the "
        "real desktop as it is right now.\n"
        f"GOAL: {goal}\n"
        f"Step {step} of {max_steps}. Image is {w}x{h} pixels; coordinates you "
        "give are in that image and are mapped to the real display.\n\n"
        "Reply with EXACTLY ONE JSON object and nothing else. No prose, no "
        "markdown fences, no comments.\n\n"
        "ACTIONS\n"
        '  {"action":"move","x":0,"y":0}\n'
        '  {"action":"click","x":0,"y":0}\n'
        '  {"action":"double_click","x":0,"y":0}\n'
        '  {"action":"right_click","x":0,"y":0}\n'
        '  {"action":"drag","x1":0,"y1":0,"x2":0,"y2":0}\n'
        '  {"action":"scroll","amount":-600,"x":0,"y":0}\n'
        '  {"action":"type","text":"hello"}\n'
        '  {"action":"hotkey","keys":["ctrl","s"]}\n'
        '  {"action":"press","key":"enter"}\n'
        '  {"action":"click_text","text":"Save"}   OCR the screen, click that word\n'
        '  {"action":"file_read","path":"C:\\\\Users\\\\x\\\\a.txt"}\n'
        '  {"action":"file_list","path":"C:\\\\Users\\\\x\\\\Downloads"}\n'
        '  {"action":"file_write","path":"C:\\\\...","text":"...","append":false}\n'
        '  {"action":"shell","command":"dir"}\n'
        '  {"action":"wait","seconds":1}\n'
        '  {"action":"done","summary":"what achieved"}   goal reached\n'
        '  {"action":"fail","reason":"why it is impossible"}\n\n'
        "RULES\n"
        "- Look at the screenshot before acting. Prefer clicking a label you "
        "can actually see over typing blind coordinates.\n"
        "- One action per reply. You will be shown the result and a fresh "
        "screenshot after it runs.\n"
        "- Repeating the same failed action is useless: change approach or "
        "call fail.\n"
        "- Never touch the OS itself (C:\\Windows, Program Files, boot "
        "config, registry deletes, disk format) unless the GOAL explicitly "
        "demands it.\n"
        "- When the goal is verifiably achieved, call done."
    )


def _history_text(limit=10):
    entries = (_state["log"] or [])[-limit:]
    lines = []
    for e in entries:
        mark = "ok" if e.get("ok") else "FAILED"
        lines.append(f'step {e.get("n")}: {e.get("action")} -> {mark} '
                     f'{(e.get("note") or "")[:160]}')
    return "\n".join(lines) if lines else "(no steps yet)"


def _decide(goal, step, max_steps, capture, retry_note=""):
    model = _working_model()
    if not model:
        raise RuntimeError("no vision model available on this key")
    with _LOCK:
        _state["model"] = model
    prompt = _system_prompt(goal, step, max_steps, capture["sent_w"], capture["sent_h"])
    prompt += "\n\nWHAT ALREADY HAPPENED\n" + _history_text()
    if retry_note:
        prompt += "\n\nYOUR LAST REPLY WAS INVALID: " + retry_note + \
                  "\nReply with one JSON object only."
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": [
                {"type": "text", "text": "Screen attached. What is the next single action?"},
                {"type": "image_url", "image_url": {
                    "url": "data:image/jpeg;base64," + capture["b64"]}},
            ]},
        ],
        "max_tokens": 400,
        "temperature": 0.1,
    }).encode("utf-8")
    last = None
    for attempt in range(2):
        req = urllib.request.Request(GROQ_URL, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + _groq_key(),
            "User-Agent": _UA,
        })
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=90).read())
            return (r.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf8", "ignore")[:200]
            except Exception:
                pass
            last = f"HTTP {e.code}: {body}"
            if e.code in (400, 404) and "model" in body.lower():
                _model_cache.update({"id": None, "ts": 0.0})   # pick another
                if _working_model(force=True):
                    continue
            if e.code in (429, 500, 502, 503):
                time.sleep(1.0 + attempt)
                continue
            break
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(1.0 + attempt)
    raise RuntimeError(f"vision call failed ({last})")


def _extract_json(text):
    """Pull the first balanced JSON object out of a model reply, tolerating
    code fences and stray prose around it."""
    if not text:
        return None
    t = re.sub(r"```(?:json)?", "", text)
    start = t.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except Exception:
                    return None
    return None


def _num(v, default=0):
    try:
        if isinstance(v, bool):
            return int(default)
        return float(v)
    except Exception:
        return float(default)


def _clamp(v, lo, hi):
    return int(max(lo, min(hi, round(v))))


def _norm_path(p):
    try:
        return str(Path(str(p or "")).expanduser())
    except Exception:
        return str(p or "")


def _protected(path):
    low = str(path).lower().replace("/", "\\")
    return any(tok in low for tok in _PROTECTED)


def _normalise(action, w, h, scale):
    """Validate + clamp one model action against the closed vocabulary.
    Returns (ok, normalised_or_reason)."""
    if not isinstance(action, dict):
        return False, "reply was not a JSON object"
    name = str(action.get("action", "")).strip().lower()
    if name not in _ACTIONS:
        return False, f"unknown action '{name[:40]}'"

    def to_screen(x, y):
        # model coords are image pixels; scale back to the real display
        return (_clamp(_num(x), 0, max(0, w - 1)),
                _clamp(_num(y), 0, max(0, h - 1))), \
               (_clamp(_num(x) / (scale or 1.0), 0, max(0, w - 1)),
                _clamp(_num(y) / (scale or 1.0), 0, max(0, h - 1)))

    if name in ("move", "click", "double_click", "right_click"):
        img_pt, scr_pt = to_screen(action.get("x"), action.get("y"))
        if action.get("x") is None or action.get("y") is None:
            return False, f"{name} needs x and y"
        return True, {"action": name, "img": img_pt, "xy": scr_pt}
    if name == "drag":
        for k in ("x1", "y1", "x2", "y2"):
            if action.get(k) is None:
                return False, "drag needs x1, y1, x2, y2"
        _, a = to_screen(action.get("x1"), action.get("y1"))
        _, b = to_screen(action.get("x2"), action.get("y2"))
        return True, {"action": name, "xy1": a, "xy2": b}
    if name == "scroll":
        amt = _clamp(_num(action.get("amount"), 0), -5000, 5000)
        if not amt:
            return False, "scroll amount was 0"
        sx = 10 if action.get("x") is None else action.get("x")
        sy = 10 if action.get("y") is None else action.get("y")
        _, pt = to_screen(sx, sy)
        return True, {"action": name, "amount": amt, "xy": pt}
    if name == "type":
        text = str(action.get("text", ""))
        if not text.strip():
            return False, "type needs text"
        return True, {"action": name, "text": text[:4000]}
    if name == "hotkey":
        keys = action.get("keys")
        if not isinstance(keys, list) or not keys:
            return False, "hotkey needs a non-empty keys array"
        clean = [str(k).strip().lower() for k in keys[:4] if str(k).strip()]
        if not clean:
            return False, "hotkey keys were empty"
        return True, {"action": name, "keys": clean}
    if name == "press":
        key = str(action.get("key", "")).strip().lower()
        if not key:
            return False, "press needs a key"
        return True, {"action": name, "key": key[:24]}
    if name == "click_text":
        q = str(action.get("text", "")).strip()
        if not q:
            return False, "click_text needs text"
        return True, {"action": name, "text": q[:120]}
    if name in ("file_read", "file_list"):
        p = _norm_path(action.get("path"))
        if not p:
            return False, f"{name} needs a path"
        if _protected(p):
            return False, f"{name}: {p} is a protected OS path"
        return True, {"action": name, "path": p}
    if name == "file_write":
        p = _norm_path(action.get("path"))
        text = str(action.get("text", ""))
        if not p:
            return False, "file_write needs a path"
        if _protected(p):
            return False, f"file_write: {p} is a protected OS path"
        if not text:
            return False, "file_write needs text"
        return True, {"action": name, "path": p, "text": text[:200000],
                      "append": bool(action.get("append"))}
    if name == "shell":
        cmd = str(action.get("command", "")).strip()
        if not cmd:
            return False, "shell needs a command"
        if len(cmd) > 500:
            return False, "shell command too long"
        low = cmd.lower()
        for bad in _SHELL_BLOCK:
            if bad in low:
                return False, f"blocked by the OS guard: matches '{bad.strip()}'"
        return True, {"action": name, "command": cmd}
    if name == "wait":
        secs = min(30.0, max(0.0, _num(action.get("seconds"), 1)))
        return True, {"action": name, "seconds": secs}
    if name in ("done", "fail"):
        key = "summary" if name == "done" else "reason"
        return True, {"action": name, key: str(action.get(key, ""))[:400]}
    return False, f"unhandled action '{name}'"


# --------------------------------------------------------------------- act

def _type_text(text):
    """pyautogui.typewrite only speaks ASCII; non-ASCII goes through the
    clipboard so a Hindi or emoji payload still lands."""
    if HAS_PYAUTOGUI and text.isascii():
        pyautogui.typewrite(text, interval=0.012)
        return {"ok": True, "note": f"typed {len(text)} chars"}
    try:
        import pc_actions
        r = pc_actions.clipboard_write(text)
        if not r.get("ok"):
            return {"ok": False, "note": str(r.get("text") or r.get("error") or "clipboard failed")}
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.12)
        return {"ok": True, "note": f"pasted {len(text)} chars via clipboard"}
    except Exception as e:
        return {"ok": False, "note": f"type failed: {e}"}


def _ocr_hit(text):
    """Find a word on screen with the local OCR and click its middle.
    Costs ~5s (PowerShell round trip), so it is only used when the model
    explicitly asks for text it cannot locate by eye."""
    try:
        import ocr
        jpeg = _frame.get("jpeg")
        if not jpeg:
            return {"ok": False, "note": "no frame to OCR"}
        tmp = DATA_DIR / "_agent_ocr.jpg"
        tmp.write_bytes(jpeg)
        r = ocr.ocr_image(str(tmp))
        if not r.get("ok"):
            return {"ok": False, "note": f"ocr failed: {r.get('error')}"}
        words = []
        for line in r.get("lines") or []:
            for wd in line.get("words") or []:
                words.append(wd)
        if not words:
            return {"ok": False, "note": "ocr saw no text"}
        target = text.lower()
        best, score = None, 0.0
        for wd in words:
            w = str(wd.get("text", ""))
            s = difflib.SequenceMatcher(None, w.lower(), target).ratio()
            if w.lower() == target:
                s = 1.0
            if s > score:
                best, score = wd, s
        if not best or score < 0.62:
            return {"ok": False, "note": f"'{text}' not on screen (best {score:.2f})"}
        # OCR ran on the saved frame; if the frame was downscaled the pixel
        # space matches what the model saw, so scale back like other coords.
        cap = _last_capture or {}
        scale = cap.get("scale", 1.0) or 1.0
        cx = int((best.get("x", 0) + best.get("width", 0) / 2) / scale)
        cy = int((best.get("y", 0) + best.get("height", 0) / 2) / scale)
        if HAS_PYAUTOGUI:
            pyautogui.click(cx, cy)
        return {"ok": True, "note": f"clicked '{best.get('text')}' at ({cx},{cy})", "xy": (cx, cy)}
    except Exception as e:
        return {"ok": False, "note": f"click_text failed: {e}"}


def _exec(a):
    """Run one normalised action. Never raises: a failed action is data, not a
    crash, and the loop decides what to do with it."""
    name = a["action"]
    try:
        if name == "done" or name == "fail":
            return {"ok": True, "note": a.get("summary") or a.get("reason") or name,
                    "terminal": name}
        if name == "wait":
            time.sleep(a["seconds"])
            return {"ok": True, "note": f"waited {a['seconds']}s"}
        if not HAS_PYAUTOGUI:
            return {"ok": False, "note": "pyautogui unavailable on this machine"}
        if name in ("move", "click", "double_click", "right_click"):
            x, y = a["xy"]
            if name == "move":
                pyautogui.moveTo(x, y, duration=0.08)
            elif name == "click":
                pyautogui.click(x, y)
            elif name == "double_click":
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.rightClick(x, y)
            return {"ok": True, "note": f"{name} ({x},{y})"}
        if name == "drag":
            x1, y1 = a["xy1"]
            x2, y2 = a["xy2"]
            pyautogui.moveTo(x1, y1, duration=0.06)
            pyautogui.dragTo(x2, y2, duration=0.22, button="left")
            return {"ok": True, "note": f"drag ({x1},{y1})->({x2},{y2})"}
        if name == "scroll":
            x, y = a["xy"]
            pyautogui.scroll(a["amount"], x=x, y=y)
            return {"ok": True, "note": f"scroll {a['amount']} at ({x},{y})"}
        if name == "type":
            return _type_text(a["text"])
        if name == "hotkey":
            pyautogui.hotkey(*a["keys"])
            return {"ok": True, "note": "+".join(a["keys"])}
        if name == "press":
            pyautogui.press(a["key"])
            return {"ok": True, "note": f"press {a['key']}"}
        if name == "click_text":
            return _ocr_hit(a["text"])
        if name == "file_read":
            p = Path(a["path"])
            if not p.exists():
                return {"ok": False, "note": f"no such file: {p}"}
            if p.is_dir():
                return {"ok": False, "note": f"{p} is a folder, use file_list"}
            data = p.read_bytes()[:200000]
            text = data.decode("utf-8", "replace")
            return {"ok": True, "note": text[:3000], "content": text}
        if name == "file_list":
            p = Path(a["path"])
            if not p.is_dir():
                return {"ok": False, "note": f"not a folder: {p}"}
            rows = []
            for i, child in enumerate(sorted(p.iterdir(), key=lambda c: c.is_file())):
                if i >= 200:
                    rows.append("... (truncated at 200)")
                    break
                kind = "dir " if child.is_dir() else "file"
                size = "" if child.is_dir() else f" {child.stat().st_size // 1024}KB"
                rows.append(f"{kind} {child.name}{size}")
            listing = "\n".join(rows) or "(empty)"
            return {"ok": True, "note": listing[:3000], "content": listing}
        if name == "file_write":
            p = Path(a["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            if a.get("append"):
                with p.open("a", encoding="utf-8") as fh:
                    fh.write(a["text"])
            else:
                p.write_text(a["text"], encoding="utf-8")
            _audit("file_write", f"{p} ({'append' if a.get('append') else 'overwrite'}, "
                                 f"{len(a['text'])} chars)")
            return {"ok": True, "note": f"wrote {len(a['text'])} chars to {p}"}
        if name == "shell":
            import subprocess
            proc = subprocess.run(a["command"], shell=True, capture_output=True,
                                  timeout=45, text=True, errors="replace")
            out = (proc.stdout or "") + (proc.stderr or "")
            _audit("shell", a["command"], ok=proc.returncode == 0)
            return {"ok": proc.returncode == 0,
                    "note": out[:3000] or f"exit {proc.returncode}",
                    "content": out}
        return {"ok": False, "note": f"unhandled action {name}"}
    except pyautogui.FailSafeException:
        raise
    except Exception as e:
        return {"ok": False, "note": f"{type(e).__name__}: {e}"[:400]}


def _audit(kind, detail, ok=True, error=None):
    if safety is None:
        return
    try:
        safety.record(f"agent.{kind}", str(detail)[:500], ok=ok,
                      undoable=False, error=(str(error)[:200] if error else None))
    except Exception:
        pass


_last_capture = None


def _check():
    if _kill.is_set():
        raise Stopped("killed")
    if _stop.is_set():
        raise Stopped("stopped")


# ---------------------------------------------------------------- the loop

def _log(entry):
    with _LOCK:
        _state["log"].append(entry)
        if len(_state["log"]) > MAX_LOG:
            del _state["log"][:len(_state["log"]) - MAX_LOG]
        if entry.get("ok"):
            _state["counts"]["ok"] += 1
        else:
            _state["counts"]["failed"] += 1


def _set(**kw):
    with _LOCK:
        _state.update(kw)


def run_once(goal, step, max_steps, capture=None):
    """One see -> think -> act cycle. Also the unit tests' entry point: they
    patch _capture/_decide/_exec instead of touching the machine."""
    global _last_capture
    _check()
    cap = capture or _capture()
    _last_capture = cap
    raw = _decide(goal, step, max_steps, cap)
    parsed = _extract_json(raw)
    if parsed is None:
        # One corrective retry: models drift into prose under long prompts and
        # a whole step wasted on "here is what I would do" helps nobody.
        raw2 = _decide(goal, step, max_steps, cap,
                       retry_note="your reply had no JSON object in it")
        parsed = _extract_json(raw2)
        if parsed is None:
            _log({"n": step, "action": "invalid", "args": {}, "ok": False,
                  "note": "model returned no JSON", "t": _stamp()})
            return {"ok": False, "action": "invalid", "note": "model returned no JSON"}
    ok, out = _normalise(parsed, cap["w"], cap["h"], cap["scale"])
    if not ok:
        _log({"n": step, "action": str(parsed.get("action", "?")), "args": {},
              "ok": False, "note": out, "t": _stamp()})
        return {"ok": False, "action": str(parsed.get("action", "?"))[:40], "note": out}
    _check()   # stop lands here if you hit it while the model was thinking
    result = _exec(out)
    entry = {"n": step, "action": out["action"],
             "args": {k: v for k, v in out.items() if k != "action" and k != "text"},
             "ok": bool(result.get("ok")), "note": (result.get("note") or "")[:600],
             "t": _stamp()}
    if out["action"] in ("type", "shell", "file_write"):
        entry["args"]["preview"] = (out.get("text") or out.get("command") or out.get("path") or "")[:120]
    _log(entry)
    _audit(out["action"], entry["note"], ok=entry["ok"],
           error=(None if entry["ok"] else entry["note"]))
    return {"ok": bool(result.get("ok")), "action": out["action"],
            "note": entry["note"], "terminal": result.get("terminal"),
            "content": result.get("content", ""), "raw": out}


def _stamp():
    return datetime.now().strftime("%H:%M:%S")


def _loop(goal, max_steps):
    _set(status="running", goal=goal, step=0, max_steps=max_steps,
         started_at=_stamp(), ended_at="", last_error="", kill_reason="",
         log=[], counts={"ok": 0, "failed": 0})
    _stop.clear()
    repeats = {}
    final = "stopped"
    try:
        for n in range(1, max_steps + 1):
            _check()
            _set(step=n)
            r = run_once(goal, n, max_steps)
            action = r.get("action") or ""
            note = r.get("note") or ""
            # Stuck detection: three identical failures means the model is
            # looping on one idea, and looking again will not save it.
            if not r.get("ok"):
                repeats[action] = repeats.get(action, 0) + 1
                if repeats[action] >= 3:
                    _log({"n": n, "action": "stuck", "args": {}, "ok": False,
                          "note": f"'{action}' failed 3 times — aborting rather "
                                  f"than repeating it forever", "t": _stamp()})
                    final = "error"
                    _set(last_error=f"stuck on {action}")
                    break
            else:
                repeats.pop(action, None)
            if r.get("terminal") == "done":
                final = "done"
                _set(last_error="")
                break
            if r.get("terminal") == "fail":
                final = "error"
                _set(last_error=note or "agent reported the goal impossible")
                break
            time.sleep(STEP_PACING)
        else:
            final = "error"
            _set(last_error=f"reached the {max_steps}-step budget without finishing")
    except Stopped as e:
        final = "killed" if str(e) == "killed" else "stopped"
        if final == "killed":
            _set(kill_reason=_state.get("kill_reason") or "kill switch")
    except pyautogui.FailSafeException:
        # Mouse in the top-left corner: the operator is telling us to stop.
        _kill.set()
        _set(kill_reason="FAILSAFE (cursor in the corner)")
        final = "killed"
        _log({"n": _state["step"], "action": "failsafe", "args": {}, "ok": False,
              "note": "pyautogui FAILSAFE tripped — cursor hit the corner",
              "t": _stamp()})
    except Exception as e:
        final = "error"
        _set(last_error=f"{type(e).__name__}: {e}"[:300])
    finally:
        _set(status=final, ended_at=_stamp())


# ------------------------------------------------- start / stop / kill / state

def start(goal, max_steps=None):
    goal = str(goal or "").strip()
    if not goal:
        return {"ok": False, "success": False, "error": "Give the agent a goal."}
    if not HAS_PYAUTOGUI:
        return {"ok": False, "success": False,
                "error": "pyautogui is not installed, so there is nothing to drive the PC with."}
    if not _groq_key():
        return {"ok": False, "success": False, "error": "No Groq key — the agent cannot see."}
    if _kill.is_set():
        return {"ok": False, "success": False,
                "error": "Kill switch is engaged. Reset it before starting again."}
    with _LOCK:
        if _state["status"] == "running":
            return {"ok": False, "success": False,
                    "error": f"Already running (step {_state['step']}: {_state['goal'][:60]}). Stop it first."}
    try:
        steps = int(max_steps or DEFAULT_MAX_STEPS)
    except Exception:
        steps = DEFAULT_MAX_STEPS
    steps = max(1, min(60, steps))
    _stop.clear()
    _ensure_hotkey()
    threading.Thread(target=_loop, args=(goal, steps), daemon=True,
                     name="jenny-vision-agent").start()
    time.sleep(0.15)
    return {"ok": True, "success": True, "status": "running", "goal": goal,
            "max_steps": steps, "message": f"Agent started: {goal}"}


def stop(reason="user"):
    _stop.set()
    was_running = _state.get("status") == "running"
    # When it was running the loop owns the final status and will write it;
    # overwriting here would erase a "done"/"error" outcome on a late STOP press.
    if not was_running and _state.get("status") in ("idle", "stopped"):
        _set(status="stopped", ended_at=_stamp())
    return {"ok": True, "success": True, "was_running": was_running,
            "message": f"Agent stopped ({reason})."}


def kill(reason="user"):
    """Global kill switch: stops this run *and* refuses new ones until reset."""
    _kill.set()
    _stop.set()
    _set(kill_reason=str(reason), status="killed", ended_at=_stamp())
    _audit("kill", f"kill switch engaged: {reason}")
    return {"ok": True, "success": True, "message": "KILL SWITCH ENGAGED — agent halted."}


def reset():
    """Disarm the kill switch and clear the stop flag."""
    _kill.clear()
    _stop.clear()
    _set(kill_reason="", status="idle", last_error="", step=0, goal="")
    return {"ok": True, "success": True, "message": "Kill switch cleared. Agent armed."}


def status():
    with _LOCK:
        snap = {k: (dict(v) if isinstance(v, dict) else
                    list(v) if isinstance(v, list) else v)
                for k, v in _state.items()}
    snap["active"] = snap.get("status") == "running"
    snap["killed"] = _kill.is_set()
    snap["stopping"] = _stop.is_set() and snap["active"]
    snap["has_pyautogui"] = HAS_PYAUTOGUI
    snap["has_key"] = bool(_groq_key())
    snap["log"] = (snap.get("log") or [])[-60:]
    snap["steps"] = {"done": snap.get("step", 0), "of": snap.get("max_steps", 0)}
    return snap


def available():
    return {
        "ok": HAS_PYAUTOGUI and bool(_groq_key()),
        "has_pyautogui": HAS_PYAUTOGUI,
        "has_key": bool(_groq_key()),
        "model": _model_cache.get("id") or _working_model(),
        "actions": sorted(_ACTIONS),
        "kill_hotkey": "ctrl+alt+x",
        "frame": _state.get("frame_ts") or "",
    }


# ------------------------------------------------------------- kill hotkey

def _ensure_hotkey():
    """Ctrl+Alt+X kills the agent from anywhere, even mid-thought.
    Registered once in a daemon thread with the Win32 message loop; a failure
    is reported through status() instead of raising into the caller."""
    global _hotkey_started
    if _hotkey_started:
        return
    _hotkey_started = True

    def _worker():
        try:
            import ctypes
            from ctypes import wintypes
            MOD, VK_X, WM_HOTKEY = 0x0003, 0x58, 0x0312
            if not ctypes.windll.user32.RegisterHotKey(None, 1, MOD, VK_X):
                _set(hotkey="unavailable (already taken by another app)")
                return
            _set(hotkey="ctrl+alt+x")
            msg = wintypes.MSG()
            while not _kill.is_set():
                r = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if r <= 0:
                    break
                if msg.message == WM_HOTKEY:
                    kill("ctrl+alt+x hotkey")
                    break
            ctypes.windll.user32.UnregisterHotKey(None, 1)
        except Exception as e:
            _set(hotkey=f"failed: {e}")

    threading.Thread(target=_worker, daemon=True, name="jenny-agent-killkey").start()

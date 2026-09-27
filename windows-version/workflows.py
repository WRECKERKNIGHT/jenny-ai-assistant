"""Scheduled and event-triggered automations.

Three trigger kinds, all evaluated by `tick()` which the server calls on a
timer:

  time      "every 5 minutes", "daily at 09:00"
  file      "when a .pdf appears in Downloads"
  idle      "if nothing has happened for 10 minutes"

Actions are dispatched through a whitelist of module:function targets rather
than an arbitrary shell string, because a voice-created automation that can
run any command is a remote-code-execution hole. `run_shell` exists but is
marked `needs_approval` in safety.py, so it queues for a human instead of
executing on a voice command alone.

Every run is written to safety history, including failures.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "jenny"
STORE = DATA_DIR / "workflows.json"
STATE = DATA_DIR / "workflow_state.json"

# module:function targets a workflow may call, mapped to allowed arg names
ALLOWED = {
    "tasks:add_task", "tasks:list_tasks", "tasks:reminder_digest", "tasks:export_ics",
    "tasks:stats", "tasks:complete_task", "tasks:delete_task",
    "file_intel:find_duplicates", "file_intel:inventory", "file_intel:old_files",
    "file_intel:find_empty_files", "file_intel:similar_names",
    "pdf_tools:info", "pdf_tools:search", "pdf_tools:extract_text",
    "datascience:data_quality", "datascience:describe", "datascience:missing_values",
    "web_apis:weather", "web_apis:air_quality", "web_apis:translate",
    "research_api:search_papers", "research_api:openalex_author",
    "pc_actions:system_diagnostics", "pc_actions:large_files", "pc_actions:file_search",
    "pc_actions:recent_files", "pc_actions:startup_apps",
}


def _err(msg, **extra):
    return {"ok": False, "error": msg, **extra}


def _read(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig") or "null") or default
    except Exception:
        return default


def _write(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        raise OSError(f"Couldn't write {path.name}: {e}")


# -------------------------------------------------------- trigger parsing

def parse_trigger(spec):
    """Turn a human trigger phrase into a machine trigger dict.

    Matching is done on a lowercased copy, but the folder is lifted out of the
    ORIGINAL string: lowercasing a Windows path turns `C:\\Users\\harsh\\Downloads`
    into `c:\\users\\harsh\\downloads`, which does not exist.
    """
    original = re.sub(r"\s+", " ", str(spec or "").strip())
    low = original.lower()
    if not low:
        return None, "Give me a trigger, like 'every 10 minutes' or 'when a pdf lands in Downloads'."
    m = re.search(r"\bevery\s+(\d+)\s*(minute|min|hour|hr|day)s?\b", low)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        mins = n * {"minute": 1, "min": 1, "hour": 60, "hr": 60, "day": 1440}[unit]
        if mins < 1:
            return None, "Interval must be at least a minute."
        return {"type": "time", "every_minutes": mins}, None
    m = re.search(r"\b(?:daily|every day)\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", low)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2) or 0)
        ap = m.group(3)
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        if not (0 <= h <= 23 and 0 <= mi <= 59):
            return None, f"'{spec}' isn't a valid time of day."
        return {"type": "time", "daily_at": f"{h:02d}:{mi:02d}"}, None

    def _folder_from(orig, low_match_end):
        """Take the tail of the ORIGINAL string so path case survives."""
        return orig[low_match_end:].strip().strip("'\"")

    m = re.search(r"\b(?:when|if|whenever)\s+(?:a|an|any|some)?\s*(?:new\s+)?(\S+)\s+"
                  r"(?:files?\s+)?(?:is\s+|are\s+)?"
                  r"(?:added|created|appears?|lands?|dropped|shows?\s+up)\s*"
                  r"(?:in|to|into|under|inside)\s+", low)
    if m:
        # The token between the article and the verb is the extension, but
        # people write it every way: ".pdf", "pdf", "*.png", "PDF file".
        # Grab the single token then normalise, rather than trusting a pattern
        # that silently produced things like ".a .pdf file".
        ext = m.group(1).strip(".,:;!?\"'()").lower()
        if ext in ("file", "files", "doc", "document", "documents", "one", "it"):
            ext = ""
        if ext in ("*", "*.*", "anything", "any"):
            ext = "*"
        elif ext and not ext.startswith(".") and not ext.startswith("*"):
            ext = "." + ext
        folder = _folder_from(original, m.end())
        if len(folder) < 2:
            return None, "Tell me which folder to watch, e.g. 'when a pdf lands in Downloads'."
        # Already normalised above; an omitted extension means "any file".
        if not ext:
            ext = "*"
        return {"type": "file", "ext": ext.lower(), "folder": folder}, None
    m = re.search(r"\bwhen\s+(.+?)\s+(?:is\s+)?(?:added|created|appears?|lands?|dropped)\s*"
                  r"(?:in|to|into)\s+", low)
    if m:
        folder = _folder_from(original, m.end())
        return {"type": "file", "ext": "." + m.group(1).lstrip(".").lower(), "folder": folder}, None
    m = re.search(r"\bafter\s+(\d+)\s*(minute|min|hour|hr)s?\s+(?:of\s+)?(?:in)?activity\b", low)
    if m and ("idle" in low or "nothing" in low):
        n = int(m.group(1))
        return {"type": "idle", "idle_minutes": n * (60 if m.group(2) in ("hour", "hr") else 1)}, None
    if "idle" in low or "nothing" in low:
        return {"type": "idle", "idle_minutes": 10}, None
    return None, f"I don't understand the trigger '{spec}'. Try 'every 10 minutes', " \
                 f"'daily at 9am', or 'when a pdf lands in Downloads'."


def parse_action(spec, params=None):
    """Actions are whitelisted module:function names or an explicit shell run."""
    raw = str(spec or "").strip()
    if not raw:
        return None, "Give me an action."
    if raw.lower().startswith("run_shell:") or raw.lower() == "run_shell":
        return {"type": "shell", "command": str((params or {}).get("command", "")).strip()}, \
               (None if str((params or {}).get("command", "")).strip() else "run_shell needs a command.")
    key = raw.replace(" ", "")
    if key not in ALLOWED:
        close = [a for a in sorted(ALLOWED) if raw.split(":")[0].lower() in a.lower()][:6]
        return None, (f"'{raw}' isn't an action I can run. Allowed: "
                      + ", ".join(sorted(ALLOWED)[:8]) + " ..."
                      + (f" Closest: {', '.join(close)}" if close else ""))
    mod, fn = key.split(":", 1)
    return {"type": "call", "module": mod, "function": fn}, None


# ----------------------------------------------------------------- CRUD

def create(name, trigger, action, params=None, enabled=True, requires_approval=None):
    trig, terr = parse_trigger(trigger)
    if not trig:
        return _err(terr)
    act, aerr = parse_action(action, params)
    if not act:
        return _err(aerr)
    if trig["type"] == "file":
        folder = Path(trig["folder"]).expanduser()
        if not folder.is_dir():
            if len(trig["folder"]) < 2:
                return _err(f"'{trig['folder']}' doesn't look like a folder path.")
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return _err(f"Couldn't use '{trig['folder']}' as a watch folder: {e}")
        trig["folder"] = str(folder)
    data = _read(STORE, {"workflows": []})
    if not isinstance(data.get("workflows"), list):
        data["workflows"] = []
    wf = {"id": f"w{len(data['workflows']) + 1}{int(time.time()) % 10000}",
          "name": str(name or "automation")[:80], "trigger": trig,
          "action": act, "params": params or {},
          "enabled": bool(enabled), "created": datetime.now().isoformat(timespec="seconds"),
          "run_count": 0, "last_run": None, "last_result": None,
          "requires_approval": bool(requires_approval) if requires_approval is not None
          else act["type"] == "shell"}
    data["workflows"].append(wf)
    try:
        _write(STORE, data)
    except Exception as e:
        return _err(str(e))
    _seed_file_baseline(wf)
    import safety
    safety.record("workflow_create", f"{wf['name']} ({_describe(wf)})", ok=True)
    return {"ok": True, "workflow": wf, "text": f"Automation '{wf['name']}' created: {_describe(wf)}."}


def _describe(wf):
    t = wf["trigger"]
    if t["type"] == "time":
        return (f"daily at {t['daily_at']}" if "daily_at" in t
                else f"every {t['every_minutes']} min")
    if t["type"] == "file":
        what = "any file" if t["ext"] == "*" else f"a {t['ext']} file"
        return f"when {what} appears in {Path(t['folder']).name}"
    if t["type"] == "idle":
        return f"after {t['idle_minutes']} min of inactivity"
    return "?"


def _ext_matches(name, ext):
    """Does a filename match the trigger's extension?

    Accepts "*" (anything), ".pdf" and glob forms like "*.png", because
    parse_trigger preserves whichever form the user typed.
    """
    e = str(ext or "*").lower()
    if e in ("*", "*.*"):
        return True
    if e.startswith("*"):
        return name.lower().endswith(e[1:])
    return Path(name).suffix.lower() == e


def _seed_file_baseline(wf):
    """Record what's already there so only NEW files fire the trigger."""
    if wf["trigger"]["type"] != "file":
        return
    folder = Path(wf["trigger"]["folder"])
    ext = wf["trigger"]["ext"]
    seen = {}
    try:
        for p in folder.iterdir():
            if p.is_file() and _ext_matches(p.name, ext):
                seen[p.name] = p.stat().st_mtime
    except Exception:
        pass
    st = _read(STATE, {})
    st.setdefault(wf["id"], {})["seen"] = seen
    # Must be written, not just set: without this the baseline is thrown away
    # and the first tick fires on every file that was already in the folder.
    _write(STATE, st)


def list_workflows(enabled_only=False):
    data = _read(STORE, {"workflows": []})
    wfs = data.get("workflows", []) if isinstance(data.get("workflows"), list) else []
    if enabled_only:
        wfs = [w for w in wfs if w.get("enabled")]
    if not wfs:
        return {"ok": True, "count": 0, "workflows": [],
                "text": "No automations set up yet."}
    return {"ok": True, "count": len(wfs), "workflows": wfs,
            "text": "; ".join(f"{w['id']}: {w['name']} ({_describe(w)})"
                              + ("" if w.get("enabled") else " [paused]") for w in wfs[:10])}


def get_workflow(wf_id):
    data = _read(STORE, {"workflows": []})
    wfs = data.get("workflows", []) if isinstance(data.get("workflows"), list) else []
    for w in wfs:
        if w["id"] == str(wf_id).strip():
            return w
    return None


def set_enabled(wf_id, enabled):
    data = _read(STORE, {"workflows": []})
    wfs = data.get("workflows", []) if isinstance(data.get("workflows"), list) else []
    for w in wfs:
        if w["id"] == str(wf_id).strip():
            w["enabled"] = bool(enabled)
            try:
                _write(STORE, data)
            except Exception as e:
                return _err(str(e))
            return {"ok": True, "workflow": w,
                    "text": f"'{w['name']}' {'resumed' if enabled else 'paused'}."}
    return _err(f"No automation with id '{wf_id}'.")


def delete_workflow(wf_id):
    data = _read(STORE, {"workflows": []})
    wfs = data.get("workflows", []) if isinstance(data.get("workflows"), list) else []
    kept = [w for w in wfs if w["id"] != str(wf_id).strip()]
    if len(kept) == len(wfs):
        return _err(f"No automation with id '{wf_id}'.")
    name = next(w["name"] for w in wfs if w["id"] == str(wf_id).strip())
    data["workflows"] = kept
    try:
        _write(STORE, data)
    except Exception as e:
        return _err(str(e))
    import safety
    safety.record("workflow_delete", name, ok=True)
    return {"ok": True, "text": f"Deleted automation '{name}'."}


# ------------------------------------------------------------- execution

def _dispatch(wf):
    import safety
    act = wf["action"]
    params = wf.get("params") or {}
    if act["type"] == "shell":
        if safety.needs_approval("run_script"):
            return safety.request_approval(
                "run_script", f"automation '{wf['name']}' wants to run: {act['command'][:120]}",
                impact="arbitrary command", requester=f"workflow:{wf['id']}")
        return _run_shell(act["command"], timeout=120)
    key = f"{act['module']}:{act['function']}"
    if key not in ALLOWED:
        return _err(f"'{key}' is no longer an allowed action.")
    try:
        mod = importlib.import_module(act["module"])
        fn = getattr(mod, act["function"], None)
        if fn is None:
            return _err(f"{key} doesn't exist.")
    except Exception as e:
        return _err(f"Couldn't load {key}: {type(e).__name__}: {e}")
    kwargs = {k: v for k, v in params.items() if k in ("text", "query", "limit", "path",
                                                       "column", "location", "which", "base",
                                                       "pattern", "include_done")}
    if wf["trigger"]["type"] == "file":
        kwargs.setdefault("path", str(Path(wf["trigger"]["folder"]) / ""))
    if wf["trigger"]["type"] == "file" and not kwargs.get("path"):
        newest = _newest_file(wf)
        if newest:
            kwargs["path"] = newest
    try:
        out = fn(**kwargs)
    except TypeError as e:
        return _err(f"{key} rejected those parameters: {e}")
    except Exception as e:
        return _err(f"{key} raised {type(e).__name__}: {e}")
    if isinstance(out, dict) and out.get("ok") is False:
        return out
    return {"ok": True, "action": key, "output": out,
            "text": (out.get("text", f"{key} ran") if isinstance(out, dict) else str(out)[:200])}


def _newest_file(wf):
    folder = Path(wf["trigger"]["folder"])
    ext = wf["trigger"]["ext"]
    try:
        cands = [p for p in folder.iterdir()
                 if p.is_file() and _ext_matches(p.name, ext)]
        return str(max(cands, key=lambda p: p.stat().st_mtime)) if cands else None
    except Exception:
        return None


def _run_shell(command, timeout=120):
    import safety
    if not safety.needs_approval("run_script"):
        pass
    try:
        cp = subprocess.run(command, shell=True, capture_output=True, text=True,
                            timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return _err(f"Command timed out after {timeout}s.")
    except Exception as e:
        return _err(f"Command failed: {type(e).__name__}: {e}")
    safety.record("workflow_shell", command[:200], ok=cp.returncode == 0)
    if cp.returncode != 0:
        return _err(f"Command exited {cp.returncode}: {(cp.stderr or cp.stdout or '')[:200]}")
    return {"ok": True, "stdout": (cp.stdout or "")[:2000], "text": (cp.stdout or "").strip()[:200] or "Command ran."}


def run_now(wf_id):
    wf = get_workflow(wf_id)
    if not wf:
        return _err(f"No automation with id '{wf_id}'.")
    if wf.get("requires_approval") and wf["action"]["type"] == "shell":
        import safety
        return safety.request_approval("run_script",
                                       f"{wf['name']}: {wf['action']['command'][:120]}",
                                       requester=f"workflow:{wf['id']}")
    return _execute(wf, "manual")


def _execute(wf, reason):
    import safety
    res = _dispatch(wf)
    ok = res.get("ok") is True
    data = _read(STORE, {"workflows": []})
    wfs = data.get("workflows", []) if isinstance(data.get("workflows"), list) else []
    for w in wfs:
        if w["id"] == wf["id"]:
            w["run_count"] = int(w.get("run_count", 0)) + 1
            w["last_run"] = datetime.now().isoformat(timespec="seconds")
            w["last_reason"] = reason
            w["last_result"] = "ok" if ok else str(res.get("error", "failed"))[:200]
            break
    try:
        _write(STORE, data)
    except Exception:
        pass
    safety.record("workflow_run", f"{wf['name']} ({reason})", ok=ok,
                  error=res.get("error") if not ok else None)
    out = dict(res)
    out["workflow"] = wf["name"]
    out["trigger_reason"] = reason
    return out


def tick(activity=None):
    """Evaluate every enabled automation. Call this on a timer."""
    data = _read(STORE, {"workflows": []})
    wfs = data.get("workflows", []) if isinstance(data.get("workflows"), list) else []
    st = _read(STATE, {})
    now = datetime.now()
    fired, notes = [], []
    last_activity = st.get("_last_activity")
    try:
        last_activity = float(last_activity)
    except Exception:
        last_activity = time.time() - 9999
    for wf in wfs:
        if not wf.get("enabled"):
            continue
        t = wf["trigger"]
        if t["type"] == "time":
            key = f"next_{wf['id']}"
            nxt = st.get(key)
            if "every_minutes" in t:
                due = (float(nxt) if nxt else time.time() - t["every_minutes"] + 1) <= time.time()
            else:
                hh, mm = t["daily_at"].split(":")
                slot = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
                if not nxt:
                    # first evaluation: if today's slot already went by, wait for
                    # tomorrow instead of firing a whole day early
                    st[key] = (slot if now < slot else slot + timedelta(days=1)).isoformat()
                    continue
                # due means "the stored fire time has arrived", not "today's slot
                # differs" -- otherwise a deferred slot fires on the next tick
                try:
                    due = now >= datetime.fromisoformat(nxt)
                except ValueError:
                    due = False
            if not due:
                continue
            if "every_minutes" in t:
                st[key] = time.time() + t["every_minutes"]
            else:
                st[key] = (slot + timedelta(days=1)).isoformat()
            r = _execute(wf, "scheduled")
            fired.append({"id": wf["id"], "name": wf["name"], "ok": r.get("ok") is True,
                          "text": r.get("text") or r.get("error")})
        elif t["type"] == "file":
            folder = Path(t["folder"])
            if not folder.is_dir():
                continue
            ext = t["ext"]
            cur = {}
            try:
                for p in folder.iterdir():
                    if p.is_file() and _ext_matches(p.name, ext):
                        cur[p.name] = p.stat().st_mtime
            except Exception:
                continue
            seen = st.setdefault(wf["id"], {}).get("seen") or {}
            new = {k: v for k, v in cur.items() if k not in seen}
            if not new:
                st.setdefault(wf["id"], {})["seen"] = cur
                continue
            st.setdefault(wf["id"], {})["seen"] = cur
            newest = max(new, key=lambda k: new[k])
            wf_run = dict(wf)
            wf_run["params"] = {**(wf.get("params") or {}), "path": str(folder / newest)}
            r = _execute(wf_run, f"new file {newest}")
            fired.append({"id": wf["id"], "name": wf["name"], "ok": r.get("ok") is True,
                          "text": f"{newest}: " + str(r.get("text") or r.get("error"))[:160]})
        elif t["type"] == "idle":
            idle_for = (time.time() - last_activity) / 60.0
            key = f"idle_{wf['id']}"
            if idle_for >= t["idle_minutes"] and st.get(key) != now.strftime("%Y-%m-%d"):
                st[key] = now.strftime("%Y-%m-%d")
                r = _execute(wf, f"idle {idle_for:.0f}m")
                fired.append({"id": wf["id"], "name": wf["name"], "ok": r.get("ok") is True,
                              "text": r.get("text") or r.get("error")})
    st["_last_activity"] = time.time() if activity else last_activity
    try:
        _write(STATE, st)
    except Exception:
        pass
    return {"ok": True, "checked": len(wfs), "fired": fired, "count": len(fired),
            "text": (f"{len(fired)} automation(s) ran: " + "; ".join(f["name"] for f in fired)
                     if fired else f"Checked {len(wfs)} automation(s), none due.")}


def note_activity():
    try:
        st = _read(STATE, {})
        st["_last_activity"] = time.time()
        _write(STATE, st)
    except Exception:
        pass


def available() -> dict:
    data = _read(STORE, {"workflows": []})
    wfs = data.get("workflows", []) if isinstance(data.get("workflows"), list) else []
    return {"store": str(STORE), "workflows": len(wfs),
            "triggers": ["time (interval or daily at HH:MM)", "file (new file in folder)", "idle"],
            "allowed_actions": len(ALLOWED),
            "shell_requires_approval": True,
            "detail": f"{len(wfs)} automation(s) configured. "
                      f"{len(ALLOWED)} whitelisted actions; shell commands need your approval."}

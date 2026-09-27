"""Tasks, reminders and deadlines with real ICS calendar export.

Deliberately does not pretend to talk to Outlook/Google Calendar: those need
OAuth that isn't configured. Instead the store is local JSON and the export is
a genuine RFC 5545 .ics file, which Windows, Outlook, Google Calendar and
Apple Calendar can all open. That makes "add to my calendar" real instead of
a no-op.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "jenny"
STORE = DATA_DIR / "tasks.json"
PRIORITIES = {"low": 3, "medium": 2, "high": 1, "urgent": 0}
WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
            "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


class StoreError(Exception):
    pass


def _err(msg, **extra):
    return {"ok": False, "error": msg, **extra}


def _load():
    if not STORE.exists():
        return {"tasks": []}
    try:
        # utf-8-sig: this project's key file was written with a BOM, and the
        # same trap applies to any file PowerShell has touched.
        raw = json.loads(STORE.read_text(encoding="utf-8-sig") or "{}")
    except Exception as e:
        raise StoreError(f"{STORE.name} is corrupt ({e}); move it aside to start fresh.")
    if isinstance(raw, list):
        raw = {"tasks": raw}
    raw.setdefault("tasks", [])
    return raw


def _save(data):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, STORE)  # atomic: never leaves a half-written store
    except Exception as e:
        raise StoreError(f"Couldn't write {STORE.name}: {e}")


# --------------------------------------------------------- due-date parsing

def parse_when(text, now=None):
    """Parse a human due date. Returns (iso_date, remaining_text) or (None, text)."""
    now = now or datetime.now()
    t = str(text or "").strip()
    if not t:
        return None, ""
    low = t.lower()
    pats = [
        (r"\btoday\b", now.date(), 0), (r"\btomorrow\b", now.date() + timedelta(days=1), 0),
        (r"\byesterday\b", now.date() - timedelta(days=1), 0),
        (r"\bday after tomorrow\b", now.date() + timedelta(days=2), 0),
    ]
    for pat, d, _ in pats:
        m = re.search(pat, low)
        if m:
            return d.isoformat(), (t[:m.start()] + " " + t[m.end():]).strip(" ,")
    m = re.search(r"\bin (\d+)\s*(minute|min|hour|day|week)s?\b", low)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = {"minute": timedelta(minutes=n), "min": timedelta(minutes=n),
                 "hour": timedelta(hours=n), "day": timedelta(days=n),
                 "week": timedelta(weeks=n)}[unit]
        return (now + delta).date().isoformat(), (t[:m.start()] + " " + t[m.end():]).strip(" ,")
    m = re.search(r"\bnext (monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\b", low)
    if m:
        target = WEEKDAYS[m.group(1)]
        ahead = (target - now.weekday()) % 7 or 7
        return (now + timedelta(days=ahead)).date().isoformat(), \
               (t[:m.start()] + " " + t[m.end():]).strip(" ,")
    # bare weekday: "friday" means the coming Friday, today if today matches.
    # Checked after "next X" so "next friday" still means the one after.
    m = re.search(r"(?<!next )\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\b", low)
    if m:
        target = WEEKDAYS[m.group(1)]
        ahead = (target - now.weekday()) % 7
        return (now + timedelta(days=ahead)).date().isoformat(), \
               (t[:m.start()] + " " + t[m.end():]).strip(" ,")
    m = re.search(r"\b(?:on|by|due)?\s*(\d{4}-\d{2}-\d{2})\b", t)
    if m:
        try:
            return date.fromisoformat(m.group(1)).isoformat(), \
                   (t[:m.start()] + " " + t[m.end():]).strip(" ,")
        except ValueError:
            return None, t
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        yr = m.group(3)
        y = now.year
        if yr:
            y = int(yr) + (2000 if len(yr) == 2 else 0)
        try:
            cand = date(y, mo, d)
            if not yr and cand < now.date():
                cand = date(y + 1, mo, d)
            return cand.isoformat(), (t[:m.start()] + " " + t[m.end():]).strip(" ,")
        except ValueError:
            return None, t
    return None, t


def parse_title(text, now=None):
    """Split 'call mum tomorrow high priority' into title, due date and priority."""
    due, rest = parse_when(text, now)
    title, prio = rest, "medium"
    m = re.search(r"\b(urgent|high|medium|low)\s+priority\b", rest, re.I)
    if m:
        prio = m.group(1).lower()
        rest = (rest[:m.start()] + " " + rest[m.end():]).strip(" ,")
    else:
        m = re.search(r"\bpriority\s+(urgent|high|medium|low)\b", rest, re.I)
        if m:
            prio = m.group(1).lower()
            rest = (rest[:m.start()] + " " + rest[m.end():]).strip(" ,")
    return re.sub(r"\s+", " ", rest).strip(" ,.") or "Untitled task", due, prio


# ------------------------------------------------------------------ CRUD

def add_task(text, due=None, priority=None, notes=None, tags=None, remind_days_before=None):
    raw = str(text or "").strip()
    if not raw:
        return _err("Give the task a name.")
    try:
        data = _load()
    except StoreError as e:
        return _err(str(e))
    # parse_title strips BOTH the due date and any "high priority"-style wording.
    # Using parse_when alone left "high priority" sitting in the title and the
    # priority at its default, so the two entry points disagreed.
    if priority is None:
        title, auto_due, prio = parse_title(raw)
    else:
        prio = str(priority).lower()
        # parse_when returns (due_date, remaining_text) -- in that order
        auto_due, title = parse_when(raw)
        title = re.sub(r"\s+", " ", title).strip(" ,.") or raw
    if prio not in PRIORITIES:
        return _err(f"Priority must be one of {', '.join(PRIORITIES)}.")
    final_due = due or auto_due
    if final_due:
        try:
            date.fromisoformat(str(final_due)[:10])
        except ValueError:
            return _err(f"'{final_due}' isn't a date I understand. Use YYYY-MM-DD or say 'tomorrow'.")
    task = {
        "id": uuid.uuid4().hex[:8],
        "title": title[:200],
        "due": str(final_due)[:10] if final_due else None,
        "priority": prio,
        "notes": (notes or "")[:2000] or None,
        "tags": [str(x).lower()[:24] for x in (tags or [])][:10] or [],
        "remind_days_before": remind_days_before,
        "done": False,
        "created": datetime.now().isoformat(timespec="seconds"),
        "completed": None,
    }
    data["tasks"].append(task)
    try:
        _save(data)
    except StoreError as e:
        return _err(str(e))
    when = f", due {task['due']}" if task["due"] else ""
    return {"ok": True, "task": task, "auto_parsed_due": auto_due,
            "text": f"Added '{task['title']}' ({prio}{when})."}


def list_tasks(which="all", tag=None, limit=100):
    try:
        data = _load()
    except StoreError as e:
        return _err(str(e))
    today = date.today()
    tasks = data["tasks"]
    if tag:
        tasks = [t for t in tasks if str(tag).lower() in t.get("tags", [])]
    if which == "pending":
        tasks = [t for t in tasks if not t["done"]]
    elif which == "done":
        tasks = [t for t in tasks if t["done"]]
    elif which == "overdue":
        tasks = [t for t in tasks if not t["done"] and t.get("due") and t["due"] < today.isoformat()]
    elif which == "today":
        tasks = [t for t in tasks if not t["done"] and t.get("due") == today.isoformat()]
    elif which == "week":
        end = (today + timedelta(days=7)).isoformat()
        tasks = [t for t in tasks if not t["done"] and t.get("due") and today.isoformat() <= t["due"] <= end]
    tasks.sort(key=lambda t: (t["done"], t.get("due") or "9999", PRIORITIES[t["priority"]]))
    return {"ok": True, "filter": which, "count": len(tasks[:int(limit)]),
            "total_matching": len(tasks), "tasks": tasks[:int(limit)],
            "text": _summarise(tasks[:int(limit)], which)}


def _summarise(tasks, which):
    if not tasks:
        return {"overdue": f"Nothing {which}." if which != "all" else "No tasks yet."}[which] \
            if which in ("overdue",) else f"No tasks matching '{which}'."
    parts = []
    for t in tasks[:8]:
        mark = "x" if t["done"] else " "
        due = f" [due {t['due']}]" if t.get("due") else ""
        parts.append(f"{mark} {t['title']}{due}")
    more = f" (+{len(tasks) - 8} more)" if len(tasks) > 8 else ""
    return "; ".join(parts) + more


def complete_task(task_id):
    try:
        data = _load()
    except StoreError as e:
        return _err(str(e))
    tid = str(task_id).strip().lower()
    matches = [t for t in data["tasks"] if t["id"] == tid or tid in t["title"].lower()]
    if not matches:
        return _err(f"No task matching '{task_id}'. Use list to see ids.")
    if len(matches) > 1:
        return _err(f"'{task_id}' matches {len(matches)} tasks: "
                    + "; ".join(f"{t['id']}={t['title'][:30]}" for t in matches[:5]))
    t = matches[0]
    t["done"] = True
    t["completed"] = datetime.now().isoformat(timespec="seconds")
    try:
        _save(data)
    except StoreError as e:
        return _err(str(e))
    return {"ok": True, "task": t, "text": f"Done: {t['title']}"}


def uncomplete_task(task_id):
    try:
        data = _load()
    except StoreError as e:
        return _err(str(e))
    matches = [t for t in data["tasks"] if t["id"] == str(task_id).strip().lower()
               or str(task_id).lower() in t["title"].lower()]
    if not matches:
        return _err(f"No task matching '{task_id}'.")
    t = matches[0]
    t["done"], t["completed"] = False, None
    try:
        _save(data)
    except StoreError as e:
        return _err(str(e))
    return {"ok": True, "task": t, "text": f"Reopened: {t['title']}"}


def delete_task(task_id):
    try:
        data = _load()
    except StoreError as e:
        return _err(str(e))
    tid = str(task_id).strip().lower()
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"]
                     if not (t["id"] == tid or (tid in t["title"].lower() and len(tid) > 2))]
    removed = before - len(data["tasks"])
    if not removed:
        return _err(f"No task matching '{task_id}'.")
    try:
        _save(data)
    except StoreError as e:
        return _err(str(e))
    return {"ok": True, "removed": removed, "text": f"Deleted {removed} task(s)."}


def update_task(task_id, **fields):
    try:
        data = _load()
    except StoreError as e:
        return _err(str(e))
    matches = [t for t in data["tasks"] if t["id"] == str(task_id).strip().lower()
               or str(task_id).lower() in t["title"].lower()]
    if not matches:
        return _err(f"No task matching '{task_id}'.")
    t = matches[0]
    changed = []
    for k in ("title", "notes", "due", "priority"):
        if k in fields and fields[k] is not None:
            v = fields[k]
            if k == "priority" and str(v).lower() not in PRIORITIES:
                return _err(f"Priority must be one of {', '.join(PRIORITIES)}.")
            t[k] = v
            changed.append(k)
    if "tags" in fields and fields["tags"]:
        t["tags"] = [str(x).lower()[:24] for x in fields["tags"]][:10]
        changed.append("tags")
    try:
        _save(data)
    except StoreError as e:
        return _err(str(e))
    return {"ok": True, "task": t, "changed": changed,
            "text": f"Updated {', '.join(changed) or 'nothing'}: {t['title']}"}


def overdue():
    return list_tasks("overdue")


def due_within(days=7):
    return list_tasks("week" if int(days) <= 7 else "all")


def reminder_digest(days=3):
    """What needs attention soon -- the thing a reminder should actually say."""
    try:
        data = _load()
    except StoreError as e:
        return _err(str(e))
    today = date.today()
    horizon = (today + timedelta(days=int(days))).isoformat()
    due_soon = [t for t in data["tasks"] if not t["done"] and t.get("due")
                and today.isoformat() <= t["due"] <= horizon]
    late = [t for t in data["tasks"] if not t["done"] and t.get("due") and t["due"] < today.isoformat()]
    due_soon.sort(key=lambda t: (t["due"], PRIORITIES[t["priority"]]))
    if not due_soon and not late:
        pending = [t for t in data["tasks"] if not t["done"]]
        if not pending:
            return {"ok": True, "count": 0, "overdue": 0, "due_soon": [],
                    "text": "Nothing pending. Inbox clear."}
        return {"ok": True, "count": len(pending), "overdue": 0, "due_soon": [],
                "text": f"Nothing due in the next {days} day(s), but {len(pending)} task(s) "
                        f"are open with no date."}
    bits = []
    if late:
        bits.append(f"{len(late)} overdue (oldest: {late[0]['title'][:40]}, due {late[0]['due']})")
    if due_soon:
        bits.append(f"{len(due_soon)} due within {days} day(s), next: "
                    f"{due_soon[0]['title'][:40]} on {due_soon[0]['due']}")
    return {"ok": True, "count": len(due_soon) + len(late), "overdue": len(late),
            "due_soon": due_soon[:10], "text": "; ".join(bits)}


def stats():
    try:
        data = _load()
    except StoreError as e:
        return _err(str(e))
    tasks = data["tasks"]
    done = [t for t in tasks if t["done"]]
    open_ = [t for t in tasks if not t["done"]]
    today = date.today()
    by_prio = {p: sum(1 for t in open_ if t["priority"] == p) for p in PRIORITIES}
    completed_times = [datetime.fromisoformat(t["completed"]) for t in done if t.get("completed")]
    rate = ""
    if len(completed_times) >= 2:
        span = (max(completed_times) - min(completed_times)).total_seconds() / 86400
        rate = f", about {len(completed_times) / max(1.0, span):.1f}/day over that window"
    return {"ok": True, "total": len(tasks), "open": len(open_), "done": len(done),
            "overdue": sum(1 for t in open_ if t.get("due") and t["due"] < today.isoformat()),
            "by_priority": by_prio, "completion_rate": round(100.0 * len(done) / len(tasks), 1) if tasks else 0.0,
            "text": f"{len(open_)} open, {len(done)} done"
                    + (f", {sum(1 for t in open_ if t.get('due') and t['due'] < today.isoformat())} overdue" if True else "")
                    + f", {round(100.0 * len(done) / len(tasks), 1) if tasks else 0}% complete" + rate}


# ------------------------------------------------------------------- ICS

def _ics_escape(s):
    return (str(s or "").replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def export_ics(out_path=None, include_done=False):
    """Write a real RFC 5545 calendar file the OS can open."""
    try:
        data = _load()
    except StoreError as e:
        return _err(str(e))
    tasks = [t for t in data["tasks"] if t.get("due") and (include_done or not t["done"])]
    if not tasks:
        return _err("No dated tasks to export yet.")
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//JENNY//Task Export//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for t in tasks:
        d = t["due"].replace("-", "")
        nxt = (date.fromisoformat(t["due"]) + timedelta(days=1)).strftime("%Y%m%d")
        lines += ["BEGIN:VEVENT", f"UID:{t['id']}@jenny.local",
                  f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{d}", f"DTEND;VALUE=DATE:{nxt}",
                  f"SUMMARY:{_ics_escape(t['title'])}",
                  f"DESCRIPTION:{_ics_escape((t.get('notes') or '') + ' [priority: ' + t['priority'] + ']')}",
                  "STATUS:CONFIRMED" if not t["done"] else "STATUS:CANCELLED"]
        if t["priority"] != "medium":
            lines.append(f"X-MICROSOFT-CDO-PRIORITY:{PRIORITIES[t['priority']]}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    body = "\r\n".join(lines) + "\r\n"
    out = Path(str(out_path)).expanduser() if out_path else DATA_DIR / "jenny-tasks.ics"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8", newline="")
    except Exception as e:
        return _err(f"Couldn't write {out.name}: {e}")
    return {"ok": True, "events": len(tasks), "path": str(out),
            "text": f"Wrote {len(tasks)} event(s) to {out} -- open it to add them to your calendar."}


def available() -> dict:
    return {"store": str(STORE), "calendar": "RFC 5545 .ics export (no OAuth needed)",
            "detail": "Tasks, due dates, priorities, tags and calendar export are available locally."}

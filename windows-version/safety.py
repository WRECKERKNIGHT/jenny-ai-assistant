"""Action history, undo and approval gates.

Exists because the audit found JENNY reporting success for things that never
happened. Two mechanisms close that hole:

  history   every mutating action is logged with a before/after snapshot
  approvals risky actions queue up and refuse to run until a human confirms

Undo is real only for operations whose inverse is known (move, rename,
delete-to-trash-by-copy). Anything else is logged but reported as not
undoable rather than quietly pretending.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "jenny"
HISTORY = DATA_DIR / "action_history.json"
APPROVALS = DATA_DIR / "approvals.json"
TRASH = DATA_DIR / "undo_trash"
MAX_HISTORY = 500
NEEDS_APPROVAL = {"delete", "delete_file", "delete_folder", "format_disk", "registry_write",
                  "run_script", "send_email", "install", "shutdown", "mass_rename",
                  "mass_delete", "system_config"}


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


def _stamp():
    return datetime.now().strftime("%H:%M:%S")


# ---------------------------------------------------------------- history

def record(kind, detail=None, ok=True, undoable=False, snapshot=None, error=None):
    """Log one action. `ok=False` is recorded too -- failures matter for trust."""
    try:
        entries = _read(HISTORY, [])
        if not isinstance(entries, list):
            entries = []
    except Exception:
        entries = []
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "time": _stamp(),
        "kind": str(kind)[:80],
        "detail": str(detail)[:500] if detail is not None else None,
        "ok": bool(ok),
        "undoable": bool(undoable),
        "error": str(error)[:300] if error else None,
    }
    if snapshot:
        entry["snapshot"] = snapshot
    entries.append(entry)
    entries = entries[-MAX_HISTORY:]
    try:
        _write(HISTORY, entries)
    except Exception:
        pass
    return {**entry, "text": f"{_stamp()} {'ok' if ok else 'FAILED'}: {entry['kind']}"
                             + (f" - {entry['detail']}" if entry.get("detail") else "")}


def history(limit=25, kind=None, only_failures=False):
    try:
        entries = _read(HISTORY, [])
    except Exception as e:
        return _err(str(e))
    if not isinstance(entries, list):
        return _err("The action history file is malformed.")
    if kind:
        entries = [e for e in entries if kind.lower() in str(e.get("kind", "")).lower()]
    if only_failures:
        entries = [e for e in entries if not e.get("ok")]
    recent = list(reversed(entries))[:int(limit)]
    total = len(entries)
    failed = sum(1 for e in entries if not e.get("ok"))
    if not recent:
        return {"ok": True, "count": 0, "total": 0,
                "text": "No actions recorded yet."}
    lines = []
    for e in recent[:8]:
        mark = "!" if not e.get("ok") else "+"
        lines.append(f"{e['time']} {mark} {e.get('kind')}"
                     + (f": {str(e.get('detail'))[:50]}" if e.get("detail") else "")
                     + (f" FAILED: {e.get('error')}" if e.get("error") else ""))
    return {"ok": True, "count": len(recent), "total": total, "failed": failed,
            "entries": recent, "text": "; ".join(lines)}


def stats():
    entries = _read(HISTORY, [])
    if not isinstance(entries, list):
        entries = []
    by_kind = {}
    for e in entries:
        k = str(e.get("kind", "?"))[:40]
        d = by_kind.setdefault(k, {"total": 0, "failed": 0})
        d["total"] += 1
        if not e.get("ok"):
            d["failed"] += 1
    failed = sum(1 for e in entries if not e.get("ok"))
    return {"ok": True, "total": len(entries), "failed": failed,
            "success_rate": round(100.0 * (len(entries) - failed) / len(entries), 1) if entries else None,
            "by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1]["total"])[:20]),
            "text": f"{len(entries)} action(s) logged, {failed} failed."
                    + (f" {100.0 * (len(entries) - failed) / len(entries):.1f}% succeeded." if entries else "")}


def clear_history():
    try:
        _write(HISTORY, [])
        return {"ok": True, "text": "Action history cleared."}
    except Exception as e:
        return _err(str(e))


# ------------------------------------------------------------------- undo

def record_move(src, dst):
    """Log a move/rename so it can be walked back."""
    return record("move", f"{src} -> {dst}", ok=True, undoable=True,
                  snapshot={"from": str(src), "to": str(dst)})


def record_delete(path):
    """Copy a file into undo-trash first, so delete can be reversed."""
    p = Path(str(path)).expanduser()
    if not p.exists():
        return _err(f"{p} doesn't exist, so there's nothing to undo.")
    try:
        TRASH.mkdir(parents=True, exist_ok=True)
        dest = TRASH / f"{time.time_ns()}_{p.name}"
        if p.is_dir():
            shutil.copytree(p, dest)
        else:
            shutil.copy2(p, dest)
        size = (sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
                if p.is_dir() else p.stat().st_size)
    except Exception as e:
        return _err(f"Couldn't snapshot {p.name} for undo: {e}")
    record("delete", f"{p} (snapshot kept)", ok=True, undoable=True,
           snapshot={"path": str(p), "trash": str(dest), "is_dir": p.is_dir()})
    return {"ok": True, "snapshot": str(dest),
            "text": f"{p.name} snapshotted to undo trash; delete it and I can put it back."}


def undo_last():
    """Reverse the most recent undoable action that hasn't been reversed yet.

    Each entry is marked `undone` once reversed. Without that, the same entry
    is found again on the next call and 'undo' can only ever reverse the very
    last action -- repeated undos would never walk further back.
    """
    entries = _read(HISTORY, [])
    if not isinstance(entries, list):
        return _err("The action history file is malformed.")
    for e in reversed(entries):
        if not e.get("undoable") or not e.get("snapshot") or e.get("undone"):
            continue
        snap, kind = e["snapshot"], e.get("kind")
        try:
            if kind == "move":
                src, dst = Path(snap["from"]), Path(snap["to"])
                if not dst.exists():
                    return _err(f"Can't undo the move: {dst} is no longer there.")
                if src.exists():
                    return _err(f"Can't undo the move: {src} already exists, so I won't overwrite it.")
                src.parent.mkdir(parents=True, exist_ok=True)
                dst.rename(src)
                _mark_undone(e)
                record("undo", f"moved back {dst} -> {src}", ok=True)
                return {"ok": True, "undone": f"move {dst} -> {src}",
                        "text": f"Undid the move: {dst.name} is back at {src}"}
            if kind == "delete":
                trash = Path(snap["trash"])
                target = Path(snap["path"])
                if not trash.exists():
                    return _err(f"Can't undo: the saved copy at {trash} is gone.")
                if target.exists():
                    return _err(f"Can't undo: {target} already exists again.")
                if snap.get("is_dir"):
                    shutil.copytree(trash, target)
                else:
                    shutil.copy2(trash, target)
                _mark_undone(e)
                record("undo", f"restored {target}", ok=True)
                return {"ok": True, "undone": f"restore {target}", "text": f"Restored {target}"}
        except Exception as ex:
            record("undo", f"failed on {kind}", ok=False, error=str(ex))
            return _err(f"Undo failed: {type(ex).__name__}: {ex}")
        return _err(f"A '{kind}' entry is marked undoable but has no handler.")
    pending = sum(1 for e in entries if e.get("undoable") and not e.get("undone"))
    if not pending:
        return _err("There's nothing left to undo.")
    return _err("No undoable action could be reversed safely.")


def _mark_undone(entry):
    """Persist `undone` on the matching history entry by timestamp+kind."""
    try:
        entries = _read(HISTORY, [])
        if not isinstance(entries, list):
            return
        for other in entries:
            if other.get("ts") == entry.get("ts") and other.get("kind") == entry.get("kind") \
                    and other.get("snapshot") == entry.get("snapshot"):
                other["undone"] = datetime.now().isoformat(timespec="seconds")
                break
        _write(HISTORY, entries)
    except Exception:
        pass


# --------------------------------------------------------------- approvals

def needs_approval(kind):
    k = str(kind or "").lower()
    base = k.split(".")[-1]
    return base in NEEDS_APPROVAL or k in NEEDS_APPROVAL


def request_approval(kind, detail, impact="", requester="voice"):
    """Queue a risky action instead of running it."""
    try:
        pend = _read(APPROVALS, [])
        if not isinstance(pend, list):
            pend = []
    except Exception:
        pend = []
    for p in pend:
        if p["kind"] == str(kind) and p.get("detail") == str(detail):
            return {"ok": True, "status": "already_pending", "approval": p,
                    "text": f"That one's already waiting for you to confirm (id {p['id']})."}
    entry = {"id": f"a{len(pend) + 1}{int(time.time()) % 1000}",
             "kind": str(kind)[:80], "detail": str(detail)[:500],
             "impact": str(impact)[:300], "requester": str(requester)[:40],
             "requested": datetime.now().isoformat(timespec="seconds"),
             "status": "pending"}
    pend.append(entry)
    try:
        _write(APPROVALS, pend)
    except Exception as e:
        return _err(str(e))
    record("approval_requested", f"{kind}: {detail}", ok=True)
    return {"ok": True, "status": "pending", "approval": entry, "action_executed": False,
            "text": f"Held back '{detail}' -- it needs your OK first (id {entry['id']}). "
                    f"Say 'approve {entry['id']}' to let it through."}


def list_approvals(status="pending"):
    try:
        pend = _read(APPROVALS, [])
        if not isinstance(pend, list):
            pend = []
    except Exception:
        pend = []
    out = [p for p in pend if p.get("status") == status]
    if not out:
        return {"ok": True, "count": 0, "approvals": [],
                "text": f"Nothing {status}."}
    return {"ok": True, "count": len(out), "approvals": out,
            "text": "; ".join(f"{p['id']}: {p['detail']}" for p in out[:8])}


def resolve_approval(approval_id, decision, reason=""):
    """Approve or reject. Returns the queued action for the caller to run."""
    try:
        pend = _read(APPROVALS, [])
        if not isinstance(pend, list):
            pend = []
    except Exception:
        pend = []
    aid = str(approval_id).strip().lower()
    matches = [p for p in pend if p["id"].lower() == aid and p.get("status") == "pending"]
    if not matches:
        loose = [p for p in pend if p["id"].lower() == aid]
        if loose:
            return _err(f"Approval {aid} was already {loose[0].get('status')}.")
        return _err(f"No pending approval with id '{aid}'.")
    d = str(decision).lower()
    if d not in ("approve", "reject", "yes", "no"):
        return _err("Say 'approve' or 'reject'.")
    p = matches[0]
    p["status"] = "approved" if d in ("approve", "yes") else "rejected"
    p["resolved"] = datetime.now().isoformat(timespec="seconds")
    p["reason"] = str(reason)[:200]
    try:
        _write(APPROVALS, pend)
    except Exception as e:
        return _err(str(e))
    record("approval_" + p["status"], f"{p['kind']}: {p['detail']}", ok=True)
    if p["status"] == "approved":
        return {"ok": True, "status": "approved", "approval": p,
                "should_execute": True, "action_kind": p["kind"], "action_detail": p["detail"],
                "text": f"Approved {p['id']}: {p['detail']}. Go ahead."}
    return {"ok": True, "status": "rejected", "approval": p, "should_execute": False,
            "text": f"Rejected {p['id']}: {p['detail']} will not run."}


def clear_resolved():
    try:
        pend = _read(APPROVALS, [])
        if not isinstance(pend, list):
            pend = []
        kept = [p for p in pend if p.get("status") == "pending"]
        _write(APPROVALS, kept)
        return {"ok": True, "removed": len(pend) - len(kept), "text": f"Cleared {len(pend) - len(kept)} resolved approval(s)."}
    except Exception as e:
        return _err(str(e))


def available() -> dict:
    return {"history": str(HISTORY), "approvals": str(APPROVALS), "undo_trash": str(TRASH),
            "gated_actions": sorted(NEEDS_APPROVAL),
            "detail": "Action history, real undo for moves/deletes, and approval gates are active."}

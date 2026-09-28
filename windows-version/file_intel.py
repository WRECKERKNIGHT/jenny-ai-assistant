"""File intelligence: duplicates, batch rename, metadata, classification.

Everything here runs locally and reports what it actually found. Batch
operations are two-phase by design -- `rename_plan` only proposes, and
`rename_apply` needs an explicit confirm token -- so a voice command can
never silently rename 400 files.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

CATEGORY_EXT = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff", ".svg", ".ico"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"},
    "audio": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".opus"},
    "document": {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".tex", ".epub", ".ppt", ".pptx", ".xls", ".xlsx", ".csv"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst"},
    "code": {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".ps1", ".html", ".css", ".json", ".xml", ".yml", ".yaml", ".sql"},
    "data": {".db", ".sqlite", ".sqlite3", ".parquet", ".h5", ".npz", ".npy"},
    "executable": {".exe", ".msi", ".bat", ".cmd", ".com", ".dll", ".appx"},
}
DEFAULT_ROOTS = ["Desktop", "Documents", "Downloads"]
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "AppData", "$RECYCLE.BIN",
             "System Volume Information", ".cache", "site-packages"}
MAX_FILES = 60000


def _err(msg, **extra):
    return {"ok": False, "error": msg, **extra}


def roots(base=None):
    home = Path(str(base)).expanduser() if base else Path.home()
    out = []
    for name in DEFAULT_ROOTS:
        d = home / name
        if d.is_dir():
            out.append(d)
    return out


def _walk(base_dirs, max_depth=4, exts=None, min_mb=0.0):
    found = []
    for base in base_dirs:
        base = Path(base)
        if not base.is_dir():
            continue
        base_depth = len(base.parts)
        for dirpath, dirnames, filenames in os.walk(base):
            depth = len(Path(dirpath).parts) - base_depth
            if depth >= max_depth:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                if fn.startswith("~$"):
                    continue
                p = Path(dirpath) / fn
                if exts and p.suffix.lower() not in exts:
                    continue
                try:
                    st = p.stat()
                except Exception:
                    continue
                if st.st_size < min_mb * 1048576:
                    continue
                found.append({"path": p, "name": fn, "ext": p.suffix.lower(),
                              "bytes": st.st_size, "mtime": st.st_mtime})
                if len(found) >= MAX_FILES:
                    return found
    return found


def classify_file(path):
    p = Path(str(path)).expanduser()
    if not p.exists():
        return _err(f"No such file: {p}")
    cat = "other"
    for name, exts in CATEGORY_EXT.items():
        if p.suffix.lower() in exts:
            cat = name
            break
    st = p.stat()
    return {"ok": True, "path": str(p), "name": p.name, "category": cat,
            "ext": p.suffix.lower() or "(none)",
            "size_mb": round(st.st_size / 1048576, 3),
            "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "text": f"{p.name} is a {cat} file, {round(st.st_size / 1048576, 2)} MB, "
                    f"modified {datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d')}."}


def inventory(base=None, max_depth=4):
    dirs = [Path(str(base)).expanduser()] if base else roots()
    if not dirs:
        return _err("No Desktop, Documents or Downloads folder was found to scan.")
    files = _walk(dirs, max_depth=max_depth)
    by_cat = defaultdict(lambda: {"count": 0, "bytes": 0})
    by_ext = defaultdict(lambda: {"count": 0, "bytes": 0})
    for f in files:
        cat = "other"
        for name, exts in CATEGORY_EXT.items():
            if f["ext"] in exts:
                cat = name
                break
        by_cat[cat]["count"] += 1
        by_cat[cat]["bytes"] += f["bytes"]
        by_ext[f["ext"] or "(none)"]["count"] += 1
        by_ext[f["ext"] or "(none)"]["bytes"] += f["bytes"]
    total = sum(f["bytes"] for f in files)
    return {"ok": True, "scanned": [str(d) for d in dirs], "file_count": len(files),
            "total_gb": round(total / 1073741824, 2),
            "by_category": {k: {"count": v["count"], "mb": round(v["bytes"] / 1048576, 1)}
                            for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]["bytes"])},
            "top_extensions": {k: v["count"] for k, v in
                               sorted(by_ext.items(), key=lambda kv: -kv[1]["count"])[:15]},
            "text": f"{len(files)} file(s), {round(total / 1073741824, 2)} GB across "
                    f"{len(dirs)} folder(s). Biggest type: "
                    f"{max(by_cat.items(), key=lambda kv: kv[1]['bytes'])[0] if by_cat else 'none'}."}


def find_duplicates(base=None, min_kb=1, max_depth=4, hash_full=False):
    """Size-first, then content-hash. Only files matching on BOTH are reported."""
    dirs = [Path(str(base)).expanduser()] if base else roots()
    if not dirs:
        return _err("No folders were found to scan.")
    files = _walk(dirs, max_depth=max_depth, min_mb=min_kb / 1024)
    if not files:
        return {"ok": True, "group_count": 0, "wasted_mb": 0, "groups": [],
                "text": f"No files at or above {min_kb} KB in the scanned folders."}
    by_size = defaultdict(list)
    for f in files:
        by_size[f["bytes"]].append(f)
    candidates = [g for g in by_size.values() if len(g) > 1]
    if not candidates:
        return {"ok": True, "group_count": 0, "wasted_mb": 0, "groups": [],
                "text": f"No duplicate sizes found across {len(files)} file(s)."}
    groups, wasted, unreadable = [], 0, []
    for same in candidates:
        by_hash = defaultdict(list)
        for f in same:
            try:
                if hash_full:
                    digest = hashlib.sha256(f["path"].read_bytes()).hexdigest()
                else:
                    h = hashlib.sha256()
                    with f["path"].open("rb") as fh:
                        h.update(fh.read(65536))
                    h.update(str(f["bytes"]).encode())
                    digest = h.hexdigest()
                by_hash[digest].append(f)
            except Exception as e:
                unreadable.append({"path": str(f["path"]), "error": f"{type(e).__name__}: {e}"})
        for digest, group in by_hash.items():
            if len(group) < 2:
                continue
            reclaim = group[0]["bytes"] * (len(group) - 1)
            wasted += reclaim
            groups.append({
                "hash": digest[:16], "bytes_each": group[0]["bytes"],
                "mb_each": round(group[0]["bytes"] / 1048576, 2),
                "count": len(group), "reclaimable_mb": round(reclaim / 1048576, 2),
                "name": group[0]["name"],
                "paths": [str(g["path"]) for g in group[:10]],
            })
    groups.sort(key=lambda g: -g["reclaimable_mb"])
    if not groups and unreadable:
        return _err(f"Could not hash {len(unreadable)} file(s), so duplicate detection failed: "
                    f"{unreadable[0]['error']}")
    return {"ok": True, "scanned_files": len(files), "group_count": len(groups),
            "wasted_mb": round(wasted / 1048576, 2),
            "duplicate_files": sum(g["count"] - 1 for g in groups),
            "unreadable": unreadable[:10],
            "groups": groups[:40],
            "text": f"Found {len(groups)} duplicate group(s) totalling {round(wasted / 1048576, 1)} MB "
                    f"reclaimable, across {sum(g['count'] - 1 for g in groups)} redundant file(s). "
                    f"Largest: '{groups[0]['name']}' x{groups[0]['count']}" if groups else "No duplicates."}


def _sanitize(pattern, original, counter):
    stem = Path(original).stem
    ext = Path(original).suffix
    date = datetime.now().strftime("%Y-%m-%d")
    out = (pattern.replace("{name}", stem).replace("{stem}", stem)
           .replace("{ext}", ext).replace("{n}", str(counter).zfill(3))
           .replace("{date}", date).replace("{ext_nodot}", ext.lstrip(".")))
    out = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", out).strip(" .")
    return out[:180] or (stem + ext)


def rename_plan(folder, pattern, exts=None, recursive=False, start=1):
    if not pattern or "{" not in pattern:
        return _err("Give a pattern with a placeholder, e.g. 'report_{n}{ext}' or '{date}_{name}{ext}'.")
    d = Path(str(folder)).expanduser()
    if not d.is_dir():
        return _err(f"{d} is not a folder.")
    files = _walk([d], max_depth=99 if recursive else 1,
                  exts={e.lower() if e.startswith(".") else "." + e.lower() for e in exts} if exts else None)
    files.sort(key=lambda f: str(f["path"]).lower())
    plan, counter, taken = [], start, {p.name.lower() for p in d.iterdir()} if d.is_dir() else set()
    for f in files:
        new = _sanitize(pattern, f["name"], counter)
        if new.lower() == f["name"].lower():
            continue
        if new.lower() in taken:
            continue
        taken.add(new.lower())
        plan.append({"from": str(f["path"]), "to": str(d / new), "from_name": f["name"], "to_name": new})
        counter += 1
    if not plan:
        return {"ok": True, "folder": str(d), "planned": 0, "plan": [],
                "text": "Nothing would change with that pattern."}
    return {"ok": True, "folder": str(d), "planned": len(plan), "plan": plan[:200],
            "confirmation_required": True,
            "text": f"Would rename {len(plan)} file(s) in {d.name} using '{pattern}'. "
                    f"Confirm to apply; nothing has changed yet."}


def rename_apply(plan_items, overwrite=False, approval_id=None):
    """Apply a rename plan, but only after an approval record for the same
    plan has been granted. Without an approval_id this queues the plan (and
    does nothing to disk). With one, the approval must be approved, must not
    have been consumed already, and its payload must still match the plan."""
    if not plan_items:
        return _err("No rename plan was supplied.")
    import safety
    if not approval_id:
        first = plan_items[0]
        req = safety.request_approval(
            "file_intel.rename_apply",
            detail=f"Rename {len(plan_items)} file(s), e.g. {first.get('from_name') or first.get('from')} -> {first.get('to_name') or first.get('to')}",
            impact=f"{len(plan_items)} file renames; no reverse stored.",
            payload=list(plan_items))
        aid = (req.get("approval") or {}).get("id")
        return {"ok": True, "status": "pending", "action_executed": False,
                "approval_id": aid,
                "text": f"Held the rename of {len(plan_items)} file(s): nothing changed on disk. "
                        f"Approve it, then call rename_apply again with approval_id={aid}."}
    got = safety.get_approval(approval_id)
    if not got.get("ok"):
        return _err(got.get("error") or "Approval not found.")
    a = got["approval"]
    if a.get("status") != "approved":
        return _err(f"Approval {approval_id} is {a.get('status')}; it isn't approved yet.")
    if a.get("executed"):
        return _err(f"Approval {approval_id} was already used once. Generate a fresh rename_plan and approve that.")
    payload = a.get("payload")
    if payload is not None and payload != list(plan_items):
        return _err("The plan changed since it was approved. Run rename_plan again and re-approve the new plan.")
    done, failed = [], []
    for item in plan_items:
        src = Path(str(item.get("from")))
        dst = Path(str(item.get("to")))
        try:
            if not src.exists():
                failed.append({"from": str(src), "error": "source no longer exists"})
                continue
            if dst.exists() and not overwrite:
                failed.append({"from": str(src), "error": f"{dst.name} already exists"})
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            done.append({"from": str(src), "to": str(dst)})
        except Exception as e:
            failed.append({"from": str(src), "error": f"{type(e).__name__}: {e}"})
    safety.mark_executed(approval_id)
    return {"ok": bool(done) or not failed, "renamed": len(done), "failed": failed[:20],
            "detail": done[:200], "dry_run": False,
            "text": f"Renamed {len(done)} file(s)" + (f", {len(failed)} failed." if failed else ".")}


def find_empty_files(base=None, max_depth=4):
    dirs = [Path(str(base)).expanduser()] if base else roots()
    files = _walk(dirs, max_depth=max_depth)
    empty = [str(f["path"]) for f in files if f["bytes"] == 0]
    return {"ok": True, "count": len(empty), "files": empty[:60],
            "text": f"{len(empty)} zero-byte file(s) found."}


def old_files(base=None, days=365, max_depth=4):
    cutoff = time.time() - days * 86400
    dirs = [Path(str(base)).expanduser()] if base else roots()
    files = [f for f in _walk(dirs, max_depth=max_depth) if f["mtime"] < cutoff]
    files.sort(key=lambda f: f["mtime"])
    return {"ok": True, "older_than_days": days, "count": len(files),
            "total_mb": round(sum(f["bytes"] for f in files) / 1048576, 1),
            "oldest": [{"path": str(f["path"]),
                        "modified": datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d"),
                        "mb": round(f["bytes"] / 1048576, 2)} for f in files[:25]],
            "text": f"{len(files)} file(s) untouched for {days}+ days "
                    f"({round(sum(f['bytes'] for f in files) / 1048576, 1)} MB total)."}


def metadata(path):
    p = Path(str(path)).expanduser()
    if not p.exists() or not p.is_file():
        return _err(f"No such file: {p}")
    st = p.stat()
    info = {"ok": True, "path": str(p), "name": p.name, "size_mb": round(st.st_size / 1048576, 3),
            "created": datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M"),
            "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "accessed": datetime.fromtimestamp(st.st_atime).strftime("%Y-%m-%d %H:%M"),
            "read_only": not os.access(p, os.W_OK)}
    if p.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            info["pdf_pages"] = len(PdfReader(str(p)).pages)
        except Exception:
            pass
    if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"):
        try:
            from PIL import Image
            with Image.open(p) as im:
                info["image_size"] = f"{im.width}x{im.height}"
                info["image_mode"] = str(im.mode)
        except Exception:
            pass
    if p.suffix.lower() in (".docx", ".xlsx", ".pptx"):
        info["office_type"] = "OOXML (zip container)"
    info["text"] = f"{p.name}: {info['size_mb']} MB, modified {info['modified']}."
    return info


def similar_names(folder, limit=30):
    d = Path(str(folder)).expanduser()
    if not d.is_dir():
        return _err(f"{d} is not a folder.")
    groups = defaultdict(list)
    for p in d.iterdir():
        if p.is_file():
            key = re.sub(r"[\s_\-()\[\]]+", "", p.stem).lower()
            key = re.sub(r"\d+", "#", key)
            if key:
                groups[key].append(p.name)
    out = [{"pattern": k, "count": len(v), "names": v[:8]}
           for k, v in groups.items() if len(v) > 1]
    out.sort(key=lambda g: -g["count"])
    return {"ok": True, "folder": str(d), "groups": out[:limit],
            "text": f"{len(out)} near-duplicate name group(s) in {d.name}."}

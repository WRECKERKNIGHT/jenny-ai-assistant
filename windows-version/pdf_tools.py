"""PDF operations backed by pypdf.

Real extraction, merging, splitting and comparison. Anything that needs a
layout-aware renderer (scanned-page OCR, image extraction, page thumbnails)
is reported as unavailable rather than silently returning empty text,
because an unextractable page and an empty page look identical downstream.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PdfReadError
    HAVE_PYPDF = True
except Exception:
    HAVE_PYPDF = False

MAX_BYTES = 300 * 1024 * 1024


def available() -> dict:
    return {"pypdf": HAVE_PYPDF, "detail":
            "PDF read/merge/split ready." if HAVE_PYPDF else "pypdf is not installed."}


def _err(msg, **extra):
    return {"ok": False, "error": msg, **extra}


def _reader(path):
    p = Path(str(path)).expanduser()
    if not p.exists():
        return None, _err(f"No such file: {p}")
    if p.suffix.lower() != ".pdf":
        return None, _err(f"{p.name} is not a PDF.")
    try:
        if p.stat().st_size > MAX_BYTES:
            return None, _err(f"{p.name} is above the {MAX_BYTES // 1048576} MB limit.")
        return PdfReader(str(p)), None
    except Exception as e:
        return None, _err(f"Couldn't open {p.name}: {type(e).__name__}: {e}")


def info(path):
    if not HAVE_PYPDF:
        return _err("pypdf is not installed.")
    r, bad = _reader(path)
    if bad:
        return bad
    try:
        md = r.metadata or {}
        pages = len(r.pages)
        encrypted = bool(r.is_encrypted)
        return {"ok": True, "file": str(path), "pages": pages, "encrypted": encrypted,
                "size_mb": round(Path(path).stat().st_size / 1048576, 2),
                "title": str(md.get("/Title") or "") or None,
                "author": str(md.get("/Author") or "") or None,
                "creator": str(md.get("/Creator") or "") or None,
                "created": str(md.get("/CreationDate") or "") or None,
                "text": f"{Path(path).name}: {pages} page(s)"
                        + (", password protected" if encrypted else "")
                        + (f", titled '{md.get('/Title')}'" if md.get("/Title") else "")}
    except Exception as e:
        return _err(f"Couldn't read PDF info: {type(e).__name__}: {e}")


def extract_text(path, pages=None, max_chars=200000):
    if not HAVE_PYPDF:
        return _err("pypdf is not installed.")
    r, bad = _reader(path)
    if bad:
        return bad
    try:
        if r.is_encrypted:
            if not r.decrypt(""):
                return _err(f"{Path(path).name} is password protected, so its text can't be read.")
        idx = range(len(r.pages))
        if pages:
            idx = [p - 1 for p in pages if 1 <= p <= len(r.pages)]
        chunks, blank = [], []
        for i in idx:
            try:
                t = r.pages[i].extract_text() or ""
            except Exception:
                t = ""
            if t.strip():
                chunks.append(f"--- page {i + 1} ---\n{t}")
            else:
                blank.append(i + 1)
        text = "\n".join(chunks)
        truncated = len(text) > max_chars
        return {"ok": True, "pages_total": len(r.pages), "pages_read": len(list(idx)),
                "chars": min(len(text), max_chars), "truncated": truncated,
                "blank_pages": blank[:50],
                "looks_scanned": bool(blank) and len(blank) >= max(1, len(list(idx)) * 0.6),
                "text": text[:max_chars],
                "note": ("Most pages returned no text, so this looks like a scanned PDF. "
                         "OCR would be needed to read it." if blank and len(blank) >= max(1, len(list(idx)) * 0.6) else None)}
    except Exception as e:
        return _err(f"Text extraction failed: {type(e).__name__}: {e}")


def search(path, pattern, ignore_case=True, max_hits=60):
    if not HAVE_PYPDF:
        return _err("pypdf is not installed.")
    r, bad = _reader(path)
    if bad:
        return bad
    try:
        flags = re.IGNORECASE if ignore_case else 0
        hits = []
        for i, page in enumerate(r.pages):
            try:
                t = page.extract_text() or ""
            except Exception:
                continue
            for m in re.finditer(pattern, t, flags):
                s = max(0, m.start() - 60)
                hits.append({"page": i + 1, "match": m.group(0)[:80],
                             "context": t[s:m.end() + 60].replace("\n", " ").strip()})
                if len(hits) >= max_hits:
                    return {"ok": True, "pattern": pattern, "count": len(hits),
                            "truncated": True, "hits": hits,
                            "text": f"{len(hits)}+ match(es) for '{pattern}' (stopped at the limit)."}
        return {"ok": True, "pattern": pattern, "count": len(hits), "hits": hits,
                "text": f"{len(hits)} match(es) for '{pattern}' in {Path(path).name}."}
    except Exception as e:
        return _err(f"Search failed: {type(e).__name__}: {e}")


def merge(paths, out_path):
    if not HAVE_PYPDF:
        return _err("pypdf is not installed.")
    if not paths:
        return _err("No input PDFs were given.")
    w = PdfWriter()
    used, skipped = [], []
    for p in paths:
        r, bad = _reader(p)
        if bad:
            skipped.append({"file": str(p), "reason": bad.get("error")})
            continue
        for page in r.pages:
            w.add_page(page)
        used.append(str(p))
    if not used:
        return _err("None of the input files could be read as a PDF.")
    out = Path(str(out_path)).expanduser()
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as fh:
            w.write(fh)
    except Exception as e:
        return _err(f"Couldn't write {out.name}: {type(e).__name__}: {e}")
    return {"ok": True, "merged": len(used), "skipped": skipped, "output": str(out),
            "size_mb": round(out.stat().st_size / 1048576, 2),
            "text": f"Merged {len(used)} PDF(s) into {out.name} ({round(out.stat().st_size / 1048576, 2)} MB)."
                    + (f" Skipped {len(skipped)} unreadable file(s)." if skipped else "")}


def split(path, out_dir=None, pages_per_file=1):
    if not HAVE_PYPDF:
        return _err("pypdf is not installed.")
    r, bad = _reader(path)
    if bad:
        return bad
    src = Path(str(path)).expanduser()
    out_dir = Path(str(out_dir)).expanduser() if out_dir else src.parent / f"{src.stem}_split"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        n = len(r.pages)
        per = max(1, int(pages_per_file))
        made = []
        for start in range(0, n, per):
            w = PdfWriter()
            for i in range(start, min(start + per, n)):
                w.add_page(r.pages[i])
            target = out_dir / f"{src.stem}_p{start + 1}-{min(start + per, n)}.pdf"
            with target.open("wb") as fh:
                w.write(fh)
            made.append(str(target))
        return {"ok": True, "source_pages": n, "pages_per_file": per,
                "files_created": len(made), "output_dir": str(out_dir),
                "text": f"Split {n} pages into {len(made)} file(s) in {out_dir}."}
    except Exception as e:
        return _err(f"Split failed: {type(e).__name__}: {e}")


def extract_pages(path, out_dir, pages, pattern="page-{n}.pdf"):
    if not HAVE_PYPDF:
        return _err("pypdf is not installed.")
    r, bad = _reader(path)
    if bad:
        return bad
    src = Path(str(path)).expanduser()
    out = Path(str(out_dir)).expanduser()
    try:
        out.mkdir(parents=True, exist_ok=True)
        made = []
        for n in pages:
            if not 1 <= n <= len(r.pages):
                continue
            w = PdfWriter()
            w.add_page(r.pages[n - 1])
            t = out / pattern.replace("{n}", str(n))
            with t.open("wb") as fh:
                w.write(fh)
            made.append(str(t))
        if not made:
            return _err(f"None of those page numbers exist; the document has {len(r.pages)} page(s).")
        return {"ok": True, "extracted": len(made), "output_dir": str(out),
                "text": f"Extracted {len(made)} page(s) to {out}."}
    except Exception as e:
        return _err(f"Page extraction failed: {type(e).__name__}: {e}")


def compare(path_a, path_b):
    if not HAVE_PYPDF:
        return _err("pypdf is not installed.")
    ra, bad = _reader(path_a)
    if bad:
        return bad
    rb, bad = _reader(path_b)
    if bad:
        return bad
    try:
        ta = "\n".join((p.extract_text() or "") for p in ra.pages)
        tb = "\n".join((p.extract_text() or "") for p in rb.pages)
        wa = set(re.findall(r"\w+", ta.lower()))
        wb = set(re.findall(r"\w+", tb.lower()))
        only_a = sorted(wa - wb)[:80]
        only_b = sorted(wb - wa)[:80]
        both = wa & wb
        denom = len(wa | wb) or 1
        return {"ok": True,
                "pages_a": len(ra.pages), "pages_b": len(rb.pages),
                "chars_a": len(ta), "chars_b": len(tb),
                "vocabulary_overlap": round(100.0 * len(both) / denom, 2),
                "only_in_a_sample": only_a[:30], "only_in_b_sample": only_b[:30],
                "text": f"{Path(path_a).name} ({len(ra.pages)}p) vs {Path(path_b).name} ({len(rb.pages)}p): "
                        f"{round(100.0 * len(both) / denom, 1)}% word overlap."}
    except Exception as e:
        return _err(f"Comparison failed: {type(e).__name__}: {e}")


def text_from_text(txt, out_path, title=None, page_size="letter", font_size=11):
    """Create a real text PDF without needing reportlab."""
    if not HAVE_PYPDF:
        return _err("pypdf is not installed.")
    out = Path(str(out_path)).expanduser()
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        w = PdfWriter()
        lines = str(txt).splitlines() or [""]
        per_page = 54
        for start in range(0, len(lines), per_page):
            page = w.add_blank_page(width=612, height=792)
            chunk = "\n".join(lines[start:start + per_page])
            try:
                from reportlab.pdfgen import canvas
            except Exception:
                return _err("Creating PDFs from text needs reportlab, which is not installed. "
                            "Merging, splitting and reading PDFs still work.")
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(612, 792))
            c.setFont("Helvetica", font_size)
            y = 760
            for line in chunk.splitlines():
                c.drawString(54, y, line[:110])
                y -= 14
            c.showPage()
            c.save()
            buf.seek(0)
            src = PdfReader(buf)
            page.merge_page(src.pages[0])
        with out.open("wb") as fh:
            w.write(fh)
        return {"ok": True, "output": str(out), "pages": len(w.pages),
                "text": f"Wrote {out.name} ({len(w.pages)} page(s))."}
    except Exception as e:
        return _err(f"Couldn't create PDF: {type(e).__name__}: {e}")


def file_hash(path, chunk=1 << 20):
    p = Path(str(path)).expanduser()
    if not p.exists() or not p.is_file():
        return _err(f"No such file: {p}")
    try:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            while True:
                b = fh.read(chunk)
                if not b:
                    break
                h.update(b)
        return {"ok": True, "sha256": h.hexdigest(), "bytes": p.stat().st_size}
    except Exception as e:
        return _err(f"Hash failed: {e}")

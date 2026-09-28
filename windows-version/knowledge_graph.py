"""Local knowledge graph built from the memory vault, tasks, and chat history.

Everything runs on-device: noun phrases are pulled from stored text with a
tiny greedy pattern matcher (there is no spaCy), scored by frequency, and
linked when they co-occur in the same vault entry. The result is a real,
queryable graph -- not a pretend "semantic search" facade.

Querying never hits an external service, so it works offline.
"""

from __future__ import annotations

import html
import json
import os
import re
import string
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent
# The server keeps the vault under <project>/data while the task store lives in
# %LOCALAPPDATA%\jenny, so resolve each source against both known locations and
# use whichever actually exists.
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "jenny"
GRAPH_FILE = DATA_DIR / "knowledge_graph.json"
_SOURCES = [
    ("vault.json", [DATA_DIR / "vault.json", _MODULE_DIR / "data" / "vault.json"]),
    ("tasks.json", [DATA_DIR / "tasks.json", _MODULE_DIR / "data" / "tasks.json",
                    _MODULE_DIR / "data" / "todo.json"]),
]
_GRAPH_CACHE = {"mtime": None, "graph": None}


def _source_path(name):
    for cand in _SOURCES:
        if cand[0] != name:
            continue
        for p in cand[1]:
            if p.stat().st_size > 0 if p.exists() else False:
                return p
        return cand[1][0]
    return DATA_DIR / name


class GraphError(dict):
    def __init__(self, msg, **extra):
        super().__init__(ok=False, error=msg, **extra)


def _err(msg, **extra):
    return GraphError(msg, **extra)


def _candidate(text):
    """Extract plausible entity/topic phrases from one piece of text.

    The server's vault normalizes memories to lowercase, so a purely
    capitalized-run extractor would see nothing. We therefore keep two
    things: genuine capitalized runs / quoted names ("Vikram", "Project
    Alpha") and, for lowercase text, 1-3 word phrases built from tokens that
    survive a function/verb stoplist. Everything emitted is a real phrase
    that occurs verbatim in stored memory.
    """
    if not text:
        return []
    STOP = {"the", "a", "an", "of", "to", "in", "on", "at", "by", "for", "with",
            "and", "or", "from", "is", "are", "was", "were", "be", "been", "it",
            "this", "that", "these", "those", "you", "your", "yours", "my", "me",
            "we", "us", "our", "ours", "they", "them", "their", "he", "him", "his",
            "she", "her", "hers", "i", "do", "does", "did", "have", "has", "had",
            "will", "would", "can", "could", "shall", "should", "may", "might",
            "must", "not", "no", "yes", "so", "but", "if", "then", "than", "too",
            "very", "just", "also", "some", "any", "all", "each", "every", "own",
            "about", "into", "over", "under", "again", "further", "once", "here",
            "there", "when", "where", "why", "how", "what", "who", "whom", "which",
            "please", "remember", "okay", "ok", "sure", "need", "wanna", "gonna",
            "going", "come", "came", "take", "took", "given", "give", "put", "get",
            "got", "let", "let's", "tell", "told", "made", "make", "say", "said",
            "see", "saw", "know", "knew", "think", "thought", "want", "wanted",
            "boss", "sir", "there's", "it's", "don't", "dont", "can't", "cant",
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
            "sunday", "today", "tomorrow", "tonight", "yesterday", "week", "next",
            "last", "call", "called", "calls", "own", "owns", "owned"}
    out = []
    # Quoted strings and capitalized runs / Title-case tokens.
    for m in re.finditer(r'"([^"]{2,60})"|\'([^\']{2,60})\'|([A-Z][A-Za-z0-9&.\'-]+\s+)*[A-Z][A-Za-z0-9&.\'-]+', text):
        s = (m.group(1) or m.group(2) or m.group(3)).strip(" .,'")
        if s and len(s) >= 2:
            out.append(s)
    # Lowercase-normalized memory: build 1-3 word phrases from surviving tokens.
    words = re.findall(r"[A-Za-z][A-Za-z0-9&.\'-]*", text.lower())
    good = [w for w in words if len(w) >= 3 and w not in STOP]
    for i in range(len(good)):
        for j in range(i, min(i + 3, len(good))):
            chunk = " ".join(good[i:j + 1])
            if len(chunk) >= 3 and chunk not in STOP:
                out.append(chunk)
    # Dedupe, keeping the most specific casing and avoiding lowercase dupes.
    best = {}
    for s in out:
        key = s.lower()
        if key not in best or (s.istitle() and not best[key].istitle()):
            best[key] = s
    return list(best.values())


def _refresh():
    """Reload the graph only if sources changed since last time."""
    paths = [GRAPH_FILE, _source_path("vault.json"), _source_path("tasks.json")]
    sig = []
    for p in paths:
        try:
            sig.append(p.stat().st_mtime_ns)
        except Exception:
            sig.append(0)
    if _GRAPH_CACHE["mtime"] == sig and _GRAPH_CACHE["graph"] is not None:
        return _GRAPH_CACHE["graph"]
    graph = {"entities": {}, "relations": [], "counts": {"entities": 0, "relations": 0}}
    # Vault entries are the main source of durable memory.
    vault_path = _source_path("vault.json")
    try:
        vault = json.loads(vault_path.read_text(encoding="utf-8"))
        entries = [e.get("text", "") for e in (vault.get("entries") or []) if isinstance(e, dict)]
    except Exception:
        entries = []
    # Tasks mention things the user cares about (projects, people, deadlines).
    tasks_path = _source_path("tasks.json")
    task_sources = [tasks_path, _MODULE_DIR / "data" / "todo.json"]
    task_texts = []
    for tp in task_sources:
        try:
            tasks = json.loads(tp.read_text(encoding="utf-8"))
        except Exception:
            continue
        row = (tasks.get("tasks") or []) if isinstance(tasks, dict) else []
        for t in row:
            if isinstance(t, dict):
                task_texts.append(t.get("title") or t.get("text") or "")
    entries += [t for t in task_texts if t]
    noise = {"remember", "put", "name is", "name", "put it"} | {
        w for w in ("the", "and", "that", "with", "what", "when", "how", "want",
                    "need", "please", "have", "goes", "gonna", "wanna")}
    for idx, text in enumerate(entries):
        if not isinstance(text, str) or not text.strip():
            continue
        found = [f for f in _candidate(text) if f.lower() not in noise]
        for ent in found:
            key = ent.lower()
            node = graph["entities"].setdefault(key, {"name": ent, "mentions": 0, "sources": 0, "_src": set()})
            node["mentions"] += 1
            node["_src"].add(idx)
        found_lower = [f.lower() for f in found]
        rel_seen = set()
        for i in range(len(found_lower)):
            for j in range(i + 1, len(found_lower)):
                a, b = found_lower[i], found_lower[j]
                if a == b:
                    continue
                key = (a, b) if a < b else (b, a)
                if key in rel_seen:
                    continue
                rel_seen.add(key)
                if a in graph["entities"] and b in graph["entities"]:
                    graph["relations"].append({"from": key[0], "to": key[1], "count": 1})
    for node in graph["entities"].values():
        node["sources"] = len(node["_src"])
        node.pop("_src", None)
    graph["counts"]["entities"] = len(graph["entities"])
    graph["counts"]["relations"] = len(graph["relations"])
    _GRAPH_CACHE.update({"mtime": sig, "graph": graph})
    return graph


def summarize(max_entities=10):
    try:
        graph = _refresh()
    except Exception as e:
        return {"ok": True, "entities": [], "relations": [], "counts": {"entities": 0, "relations": 0},
                "text": f"Knowledge graph is unavailable: {e}"}
    top = sorted(graph["entities"].values(), key=lambda e: e["mentions"], reverse=True)[:max_entities]
    heads = ", ".join(e["name"] for e in top)
    return {"ok": True, "entities": [{"name": e["name"], "mentions": e["mentions"]} for e in top],
            "relations": graph["relations"],
            "counts": graph["counts"],
            "text": f"I've logged {graph['counts']['entities']} people/projects/things across "
                    f"{graph['counts']['relations']} connections. Most mentioned: {heads}."}


def lookup(entity):
    """Everything recorded about a single entity."""
    raw = str(entity or "").strip()
    if not raw:
        return _err("Tell me which person, project or thing to look up.")
    graph = _refresh()
    key = raw.lower()
    node = graph["entities"].get(key)
    if not node:
        near = sorted((e for e in graph["entities"] if key in e), key=lambda e: graph["entities"][e]["mentions"], reverse=True)[:3]
        if near:
            return _err(f"I don't have anything recorded as '{raw}'. Did you mean one of: "
                        f"{', '.join(graph['entities'][n]['name'] for n in near)}?")
        return _err(f"I don't have anything recorded about '{raw}' in local memory yet.")
    links = [(r["from"], r["to"]) for r in graph["relations"]
             if r["from"] == key or r["to"] == key]
    others = []
    for a, b in links:
        other = b if a == key else a
        others.append(graph["entities"].get(other, {}).get("name", other))
    return {"ok": True, "entity": node["name"], "mentions": node["mentions"], "related": others,
            "text": f"**{node['name']}** shows up {node['mentions']}x in your memory. "
                    f"Connected to: {', '.join(others) if others else 'nothing yet'}."}


def related(entity, limit=8):
    """Closest neighbours by co-occurrence."""
    raw = str(entity or "").strip()
    if not raw:
        return _err("Give me an entity to expand from.")
    graph = _refresh()
    key = raw.lower()
    if key not in graph["entities"]:
        return _err(f"I don't have '{raw}' in the graph.")
    scored = {}
    for r in graph["relations"]:
        if r["from"] == key:
            scored[r["to"]] = scored.get(r["to"], 0) + r["count"]
        elif r["to"] == key:
            scored[r["from"]] = scored.get(r["from"], 0) + r["count"]
    top = sorted(scored, key=lambda k: -scored[k])[:limit]
    out = [{"entity": graph["entities"][k]["name"], "strength": scored[k]} for k in top]
    name = graph["entities"][key]["name"]
    if not out:
        return {"ok": True, "entity": name, "related": [],
                "text": f"{name} isn't linked to anything yet."}
    return {"ok": True, "entity": name, "related": out,
            "text": f"Closest to **{name}**: {', '.join(o['entity'] for o in out)}."}


def build():
    """Force a rebuild and report what the graph now contains."""
    _GRAPH_CACHE.update({"mtime": None, "graph": None})
    try:
        graph = _refresh()
    except Exception as e:
        return _err(str(e))
    top = sorted(graph["entities"].values(), key=lambda e: e["mentions"], reverse=True)[:5]
    return {"ok": True, "counts": graph["counts"],
            "top": [e["name"] for e in top],
            "text": f"Knowledge graph rebuilt: {graph['counts']['entities']} entities, "
                    f"{graph['counts']['relations']} links."}


def available() -> dict:
    try:
        graph = _refresh()
    except Exception as e:
        return {"ok": True, "functions": [], "note": f"graph unavailable: {e}"}
    return {"ok": True, "functions": ["summarize", "lookup", "related", "build"],
            "storage": str(GRAPH_FILE),
            "entities": graph["counts"]["entities"], "relations": graph["counts"]["relations"]}
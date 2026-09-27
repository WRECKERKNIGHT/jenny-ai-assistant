"""Bridge to the locally installed Hermes Agent (Nous Research, MIT).

This module deliberately exposes only Hermes subsystems that work within the
limits of the free Groq key already configured for JENNY. Every function here
returns real observed output or an honest error -- nothing is simulated.

Why there is no agent/chat function
-----------------------------------
Measured on this machine against the free Groq key: Groq rejects any request
larger than ~28,500 bytes (~7.9k tokens) with HTTP 413 "Request too large ...
on tokens per minute". All 11 models on the account were probed; none accept a
larger prompt. Hermes's own fixed system prompt is 27.3 KB *before* any tool
schemas are added, and its full CLI payload measures 84.5 KB (27.3 KB prompt +
57.2 KB of tool schemas across 19 tools). Since 27.3 KB alone nearly exhausts the
28.5 KB budget, no toolset trimming can make the agent loop fit. Lifting this
needs a provider with a higher per-request budget (or a local model), not a
config change.

What does work, and is exposed here:
  * the installed skills library (73 skills)
  * the built-in memory store (MEMORY.md / USER.md)
  * the Slack app manifest generator
  * memory-provider status, including Honcho
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

HERMES_HOME = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "hermes"
HERMES_BIN = HERMES_HOME / "hermes-agent" / "bin" / "hermes.exe"
HERMES_ROOT = HERMES_HOME / "hermes-agent"
MEMORY_DIR = HERMES_HOME / "memories"
SOUL_FILE = HERMES_HOME / "SOUL.md"

#: Largest request the configured free Groq key will accept, in bytes.
GROQ_REQUEST_BYTE_CAP = 28_500
#: Hermes's fixed CLI system prompt, measured via `hermes prompt-size`.
HERMES_SYSTEM_PROMPT_BYTES = 27_312
#: Hermes's full CLI payload (system prompt + tool schemas), also measured.
HERMES_FULL_PAYLOAD_BYTES = 84_498

_CLI_TIMEOUT = 45


def _run(args, timeout: int = _CLI_TIMEOUT) -> dict:
    """Run a hermes subcommand and report exactly what happened."""
    if not HERMES_BIN.exists():
        return {"ok": False, "rc": None, "stdout": "", "stderr": "",
                "error": f"Hermes isn't installed at {HERMES_BIN}"}
    try:
        proc = subprocess.run(
            [str(HERMES_BIN), *args],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": None, "stdout": "", "stderr": "",
                "error": f"'hermes {' '.join(args)}' timed out after {timeout}s"}
    except Exception as exc:
        return {"ok": False, "rc": None, "stdout": "", "stderr": "",
                "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": proc.returncode == 0, "rc": proc.returncode,
            "stdout": proc.stdout or "", "stderr": proc.stderr or "", "error": ""}


def installed() -> bool:
    return HERMES_BIN.exists()


def version() -> str:
    res = _run(["--version"])
    if not res["ok"]:
        return ""
    match = re.search(r"Hermes Agent v([^\s(]+)", res["stdout"])
    return match.group(1) if match else ""


def _config_value(key: str) -> str:
    res = _run(["config", "get", key])
    return res["stdout"].strip() if res["ok"] else ""


def prompt_budget() -> dict:
    """The measured reason the Hermes agent loop cannot run on this key."""
    return {
        "agent_loop_available": False,
        "reason": (
            f"Groq on this free key rejects requests over ~{GROQ_REQUEST_BYTE_CAP:,} bytes "
            f"(~7.9k tokens) with HTTP 413. Hermes's fixed system prompt alone is "
            f"{HERMES_SYSTEM_PROMPT_BYTES:,} bytes, and its full payload is "
            f"{HERMES_FULL_PAYLOAD_BYTES:,} bytes, so the loop cannot fit."
        ),
        "groq_request_byte_cap": GROQ_REQUEST_BYTE_CAP,
        "hermes_system_prompt_bytes": HERMES_SYSTEM_PROMPT_BYTES,
        "hermes_full_payload_bytes": HERMES_FULL_PAYLOAD_BYTES,
        "fix_requires": "a provider with a higher per-request budget, or a local model (e.g. Ollama)",
        "subsystems_available": ["skills", "memory", "slack_manifest", "memory_provider_status"],
    }


def status() -> dict:
    ver = version()
    mem = memory_provider_status()
    return {
        "ok": installed(),
        "version": ver,
        "install_dir": str(HERMES_ROOT),
        "provider": _config_value("model.provider"),
        "base_url": _config_value("model.base_url"),
        "model": _config_value("model.default"),
        "api_key_configured": bool(_config_value("model.api_key")),
        "skills_count": len(skills()),
        "memory_provider": mem.get("provider", "unknown"),
        "honcho_installed": mem.get("honcho_installed", False),
        "slack_manifest_available": slack_manifest().get("ok", False),
        "prompt_budget": prompt_budget(),
    }


def skills(enabled_only: bool = False) -> list:
    """Parse `hermes skills list`. The CLI only renders a table, so read it."""
    args = ["skills", "list"]
    if enabled_only:
        args.append("--enabled-only")
    res = _run(args)
    if not res["ok"]:
        return []
    rows = []
    for line in res["stdout"].splitlines():
        if "│" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("│").split("│")]
        if len(cells) < 5:
            continue
        name, category, source, trust, state = cells[:5]
        if not name or set(name) <= set("-─ "):
            continue
        if name.lower() == "name":
            continue
        rows.append({"name": name, "category": category, "source": source,
                     "trust": trust, "status": state})
    return rows


def memory_provider_status() -> dict:
    """Report the active external memory provider (Honcho, mem0, ...)."""
    res = _run(["memory", "status"])
    text = res["stdout"] or res["stderr"]
    provider = ""
    match = re.search(r"Provider:\s*(.+)", text)
    if match:
        provider = match.group(1).strip()
    plugins = re.findall(r"•\s*([a-z0-9]+)", text)
    label = provider or "none (built-in only)"
    label = re.sub(r"[^\x20-\x7e]", "-", label).strip()
    return {
        "ok": res["ok"],
        "provider": provider or "none (built-in only)",
        "plugins_installed": plugins,
        "honcho_installed": "honcho" in plugins,
        "raw": text.strip(),
        "error": res["error"],
    }


def _memory_path(kind: str) -> Path:
    return MEMORY_DIR / ("MEMORY.md" if kind == "memory" else "USER.md")


def memory_read() -> dict:
    out = {}
    for kind in ("memory", "user"):
        path = _memory_path(kind)
        try:
            out[kind] = path.read_text(encoding="utf-8") if path.exists() else ""
        except Exception as exc:
            out[kind] = ""
            out.setdefault("errors", []).append(f"{kind}: {exc}")
        out[f"{kind}_path"] = str(path)
    return out


def memory_append(text: str, kind: str = "memory") -> dict:
    """Append to Hermes's built-in memory store (no model call involved)."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "Nothing to remember - the text was empty."}
    path = _memory_path(kind)
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        stamp = ""
        block = f"\n- {text}\n"
        path.write_text(existing.rstrip("\n") + "\n" + block, encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": f"Couldn't write {path.name}: {exc}"}
    return {"ok": True, "path": str(path), "appended": text,
            "bytes": path.stat().st_size}


def slack_manifest() -> dict:
    """The Slack app manifest with every Hermes gateway command registered."""
    res = _run(["slack", "manifest"], timeout=_CLI_TIMEOUT)
    if not res["ok"]:
        return {"ok": False, "error": res["error"] or res["stderr"].strip()[:400]}
    try:
        return {"ok": True, "manifest": json.loads(res["stdout"])}
    except Exception as exc:
        return {"ok": False, "error": f"Couldn't parse manifest as JSON: {exc}",
                "raw": res["stdout"][:800]}

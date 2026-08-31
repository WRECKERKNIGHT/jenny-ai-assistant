"""
Agency OS client — lets Jarvis (and ULTROM) query and control the
lead-generation agency automation system running at localhost:3200.

Agency OS is a Next.js app with a SQLite back-end exposing:
  GET  /api/state                 -> full dashboard snapshot
  POST /api/pipeline              -> launch a new lead mission
  POST /api/outreach              -> approve / reject / edit / send outreach
  POST /api/response              -> ingest an inbound reply

All calls are resilient: if the agency server is down the helpers return
None / offline flags so the assistant degrades gracefully.
"""
import os
import time
import json
import urllib.request
import urllib.error

AGENCY_BASE = os.environ.get("AGENCY_OS_URL", "http://localhost:3200").rstrip("/")
AGENCY_TIMEOUT = 6
_state_cache = {"t": 0, "data": None}


def _get(path, timeout=AGENCY_TIMEOUT):
    try:
        req = urllib.request.Request(f"{AGENCY_BASE}{path}", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _post(path, payload, timeout=AGENCY_TIMEOUT):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{AGENCY_BASE}{path}", data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def agency_online():
    """True if the Agency OS server is reachable."""
    return _get("/api/state") is not None


def agency_state(cached=2):
    """Return the Agency OS dashboard snapshot, or None if offline.
    `cached` controls how many seconds a snapshot may be reused."""
    now = time.time()
    if _state_cache["data"] is not None and (now - _state_cache["t"]) < cached:
        return _state_cache["data"]
    data = _get("/api/state")
    if data is not None:
        _state_cache["t"] = now
        _state_cache["data"] = data
    return data


def agency_launch_mission(city, category="School", limit=10):
    """Launch a new lead-finder mission. Returns result dict or None."""
    return _post("/api/pipeline", {"city": city, "category": category, "limit": limit})


def agency_outreach_action(item_id, action, body=None, subject=None):
    """Approve / reject / edit / send an outreach item."""
    payload = {"id": item_id, "action": action}
    if body is not None:
        payload["body"] = body
    if subject is not None:
        payload["subject"] = subject
    return _post("/api/outreach", payload)


def summarize_state(state):
    """Turn a raw Agency OS snapshot into a compact, human-readable briefing."""
    if not state:
        return None
    stats = state.get("stats") or {}
    missions = state.get("missions") or []
    institutions = state.get("institutions") or []
    outreach = state.get("outreach") or []
    runs = state.get("agentRuns") or []
    by_stage = stats.get("byStage") or {}

    active_missions = sum(1 for m in missions if (m.get("status") or "").lower() == "running")
    error_agents = [r.get("agent_id") for r in runs if (r.get("status") or "").lower() == "error"]

    return {
        "agents_online": stats.get("agentsOnline", 0),
        "agents_working": stats.get("agentsWorking", 0),
        "agents_error": stats.get("agentsError", 0),
        "total_leads": stats.get("totalLeads", 0),
        "leads_today": stats.get("leadsToday", 0),
        "interested": stats.get("interested", 0),
        "curious": stats.get("curious", 0),
        "not_interested": stats.get("notInterested", 0),
        "meetings": stats.get("meetings", 0),
        "replies": stats.get("replies", 0),
        "pending_approval": stats.get("pendingApproval", 0),
        "sent_outreach": stats.get("sentOutreach", 0),
        "missions_running": active_missions,
        "institution_count": len(institutions),
        "outreach_pending": len([o for o in outreach if (o.get("status") or "") == "pending_approval"]),
        "by_stage": by_stage,
        "error_agents": error_agents,
    }

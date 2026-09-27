"""
Spotify Web API - real queue, real library, real play-by-name.

The desktop-client path in app_integrations can only press media keys, so it
genuinely cannot answer "what is next in the queue". This module talks to
Spotify's Web API instead, which is the only way to see the queue, your saved
playlists and your saved tracks.

Auth is the standard Authorization Code flow with a loopback redirect, so the
browser opens on 127.0.0.1:3005 and the code comes straight back to us. Tokens
are refreshed automatically with the refresh token and stored in the
git-ignored data/keys.json - never in the repo.

Scope note, and it matters: /me/player/queue, /me/player/play and library reads
require Spotify PREMIUM. On a free account Spotify answers 403 and this module
says so plainly instead of inventing an answer. connected_state() reports the
real product tier so callers can be honest before they try.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
KEYS_FILE = DATA_DIR / "keys.json"

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"

SCOPES = (
    "user-read-private user-read-email "
    "user-library-read user-library-modify "
    "playlist-read-private playlist-read-collaborative playlist-modify-private "
    "user-read-playback-state user-modify-playback-state user-read-currently-playing"
)

# Loopback redirect registered in the Spotify dashboard. Must match exactly.
REDIRECT_URI = "http://127.0.0.1:3005/api/spotify/callback"

# All API reads are short. 8s is well inside Spotify's own guidance and keeps a
# dead network from stalling the chat reply.
TIMEOUT = 8

_lock = threading.Lock()
_state = "idle"  # idle | waiting | ok | error
_state_detail = ""


# ---------------------------------------------------------------- key storage
def _load_keys() -> dict:
    """Read the shared key store.

    Two quirks in the existing data/keys.json are handled deliberately:
      * it is a LIST of one object ([{"grok_api_key": ...}]), not a bare object
      * it is written with a UTF-8 BOM, so it needs utf-8-sig to parse at all

    _save_keys writes back the same shape it found, so adding a Spotify key
    can never silently drop the user's Groq key.
    """
    try:
        raw = json.loads(KEYS_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                return dict(item)
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _save_keys(keys: dict) -> None:
    KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    as_list = isinstance(_load_raw(), list)
    payload = [keys] if as_list else keys
    tmp = KEYS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(KEYS_FILE)


def _load_raw():
    """The parsed file exactly as stored, without shape coercion."""
    try:
        return json.loads(KEYS_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _config() -> tuple[str, str]:
    k = _load_keys()
    return str(k.get("spotify_client_id", "") or ""), str(k.get("spotify_client_secret", "") or "")


def _tokens() -> dict:
    k = _load_keys()
    return {
        "access": k.get("spotify_access_token", "") or "",
        "refresh": k.get("spotify_refresh_token", "") or "",
        "expires": float(k.get("spotify_token_expires", 0) or 0),
    }


def _store_tokens(access: str, refresh: str, expires_in: int) -> None:
    keys = _load_keys()
    keys["spotify_access_token"] = access
    if refresh:
        keys["spotify_refresh_token"] = refresh
    keys["spotify_token_expires"] = time.time() + max(60, int(expires_in or 3600)) - 60
    _save_keys(keys)


# ------------------------------------------------------------------- plumbing
def _post_form(url: str, fields: dict) -> dict:
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "JENNY-Assistant",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _refresh_access_token() -> str:
    """Swap the refresh token for a fresh access token. Returns "" on failure."""
    cid, secret = _config()
    tok = _tokens()
    if not (cid and secret and tok["refresh"]):
        return ""
    try:
        d = _post_form(TOKEN_URL, {
            "grant_type": "refresh_token",
            "refresh_token": tok["refresh"],
            "client_id": cid,
            "client_secret": secret,
        })
    except Exception:
        return ""
    access = str(d.get("access_token", "") or "")
    if not access:
        return ""
    _store_tokens(access, str(d.get("refresh_token", "") or ""), int(d.get("expires_in", 3600)))
    return access


def _access_token() -> str:
    tok = _tokens()
    if not tok["access"] and not tok["refresh"]:
        return ""
    if tok["access"] and tok["expires"] > time.time():
        return tok["access"]
    return _refresh_access_token()


def _api(method: str, path: str, params: dict | None = None, body: dict | None = None):
    """Call a Web API endpoint. Returns (status, parsed_json_or_text)."""
    token = _access_token()
    if not token:
        return 401, {"error": "not_connected"}
    url = API + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    for attempt in (0, 1):
        req = urllib.request.Request(url, data=data, headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "JENNY-Assistant",
        }, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read().decode("utf-8")
                try:
                    return r.status, json.loads(raw)
                except Exception:
                    return r.status, {"raw": raw}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {"error": {"status": e.code, "message": raw[:200]}}
            # 401 once means the token died early; refresh and retry exactly once.
            if e.code == 401 and attempt == 0:
                if _refresh_access_token():
                    continue
            return e.code, parsed
        except Exception as e:
            return 0, {"error": "network", "message": str(e)[:160]}


# --------------------------------------------------------------- public state
def configured() -> bool:
    cid, secret = _config()
    return bool(cid and secret)


def connected() -> bool:
    return bool(_tokens()["access"] or _tokens()["refresh"])


def auth_url() -> str:
    cid, _ = _config()
    if not cid:
        return ""
    q = {
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": "jenny",
        "show_dialog": "true",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(q)


def wait_state() -> tuple[str, str]:
    return _state, _state_detail


def mark_waiting(detail: str = "Waiting for Spotify approval in the browser...") -> None:
    global _state, _state_detail
    _state, _state_detail = "waiting", detail


def exchange_code(code: str) -> tuple[bool, str]:
    global _state, _state_detail
    with _lock:
        cid, secret = _config()
        if not (cid and secret):
            _state, _state_detail = "error", "Client ID/secret not saved yet."
            return False, _state_detail
        try:
            d = _post_form(TOKEN_URL, {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": cid,
                "client_secret": secret,
            })
        except urllib.error.HTTPError as e:
            _state, _state_detail = "error", f"Spotify rejected the code (HTTP {e.code})."
            return False, _state_detail
        except Exception as e:
            _state, _state_detail = "error", f"Could not reach Spotify: {e}"
            return False, _state_detail
        access = str(d.get("access_token", "") or "")
        if not access:
            _state, _state_detail = "error", "Spotify returned no access token."
            return False, _state_detail
        _store_tokens(access, str(d.get("refresh_token", "") or ""), int(d.get("expires_in", 3600)))
        _state, _state_detail = "ok", "Connected."
        return True, "Connected to Spotify."


def disconnect() -> tuple[bool, str]:
    keys = _load_keys()
    for k in ("spotify_access_token", "spotify_refresh_token", "spotify_token_expires"):
        keys.pop(k, None)
    _save_keys(keys)
    return True, "Spotify disconnected."


def account() -> dict:
    st, d = _api("GET", "/me")
    if st != 200:
        return {"ok": False, "status": st, "detail": _explain(st, d)}
    return {
        "ok": True,
        "display_name": d.get("display_name") or d.get("id") or "",
        "product": (d.get("product") or "unknown"),  # premium | free
        "premium": (d.get("product") == "premium"),
    }


def _explain(st: int, d) -> str:
    """Turn a Spotify status code into an honest, actionable sentence."""
    if st == 0:
        return "Couldn't reach Spotify (offline?)."
    if st == 401:
        try:
            if (d or {}).get("error") == "not_connected":
                return "Spotify isn't connected yet - use the Connect Spotify button first."
        except Exception:
            pass
        return "Spotify session expired - reconnect."
    if st == 403:
        msg = ""
        try:
            msg = d["error"]["message"]
        except Exception:
            pass
        if "premium" in msg.lower() or "restricted" in msg.lower():
            return ("This needs Spotify Premium - a free account can't read the "
                    "queue, library or control playback.")
        return f"Spotify refused that ({msg or 'forbidden'})."
    if st == 404:
        return "Nothing found on Spotify."
    if st == 429:
        return "Spotify rate limit - try again in a moment."
    return f"Spotify returned HTTP {st}."


# ------------------------------------------------------------------- features
def _track_line(t: dict) -> str:
    name = t.get("name") or "?"
    artists = ", ".join(a.get("name", "") for a in (t.get("artists") or []) if a.get("name"))
    return f"{name} - {artists}" if artists else name


def now_playing() -> dict:
    st, d = _api("GET", "/me/player/currently-playing")
    if st == 204 or (st == 200 and not d):
        return {"ok": False, "playing": False, "detail": "Spotify is connected but nothing is playing."}
    if st != 200:
        return {"ok": False, "detail": _explain(st, d)}
    item = d.get("item") or {}
    if item.get("type") != "track":
        return {"ok": False, "playing": False,
                "detail": f"Playing {item.get('type', 'something')} - not a track."}
    return {
        "ok": True, "playing": True, "title": item.get("name") or "",
        "artist": ", ".join(a.get("name", "") for a in (item.get("artists") or [])),
        "album": (item.get("album") or {}).get("name", ""),
        "device": (d.get("device") or {}).get("name", ""),
        "source": "web-api",
    }


def queue() -> dict:
    """The real 'what is next' answer. Premium only."""
    st, d = _api("GET", "/me/player/queue")
    if st != 200:
        return {"ok": False, "detail": _explain(st, d)}
    items = d.get("queue") or []
    return {
        "ok": True,
        "currently_playing": _track_line(d.get("currently_playing") or {}),
        "next": [_track_line(t) for t in items[:10]],
        "total": len(items),
        "source": "web-api",
    }


def search_and_play(query: str) -> tuple[bool, str]:
    """Play the best match for a song, album, artist or playlist by name.

    This replaces the pyautogui search-box guess, which typed into Spotify's UI
    and pressed enter twice - it regularly played the wrong track.
    """
    if not connected():
        return False, "Spotify isn't connected yet. Open the Spotify connect panel first."
    st, d = _api("GET", "/search", {
        "q": query, "type": "track,album,artist,playlist", "limit": 1,
    })
    if st != 200:
        return False, _explain(st, d)
    blocks = d.get("tracks", {}).get("items") or []
    if blocks:
        t = blocks[0]
        st2, d2 = _api("PUT", "/me/player/play", body={"uris": [t.get("uri")]})
        if st2 not in (200, 204):
            return False, _explain(st2, d2)
        return True, f"Playing {t.get('name')} by " + ", ".join(
            a.get("name", "") for a in (t.get("artists") or []))
    for kind in ("albums", "artists", "playlists"):
        items = (d.get(kind, {}) or {}).get("items") or []
        if items:
            it = items[0]
            st2, d2 = _api("PUT", "/me/player/play", body={"context_uri": it.get("uri")})
            if st2 not in (200, 204):
                return False, _explain(st2, d2)
            return True, f"Playing {kind[:-1]} {it.get('name')}"
    return False, f"Nothing on Spotify matched '{query}'."


def playlists(limit: int = 25) -> dict:
    st, d = _api("GET", "/me/playlists", {"limit": max(1, min(50, int(limit or 25)))})
    if st != 200:
        return {"ok": False, "detail": _explain(st, d)}
    return {
        "ok": True,
        "playlists": [{"name": p.get("name"), "tracks": (p.get("tracks") or {}).get("total", 0),
                       "uri": p.get("uri", "")}
                      for p in (d.get("items") or [])],
        "total": (d.get("total") or 0),
    }


def play_playlist_by_name(name: str) -> tuple[bool, str]:
    """Play a saved playlist by its exact name (or the closest match)."""
    st, d = playlists(50)
    if not d.get("ok"):
        return False, d.get("detail", "Could not read your playlists.")
    want = name.strip().lower()
    exact = [p for p in d["playlists"] if (p.get("name") or "").strip().lower() == want and p.get("uri")]
    loose = [p for p in d["playlists"] if want and want in (p.get("name") or "").lower() and p.get("uri")]
    hit = (exact or loose or [None])[0]
    if not hit:
        return False, f"No playlist called '{name}' in your library."
    st2, d2 = _api("PUT", "/me/player/play", body={"context_uri": hit["uri"]})
    if st2 not in (200, 204):
        return False, _explain(st2, d2)
    return True, f"Playing your playlist '{hit['name']}'."

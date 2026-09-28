"""Weather, geocoding and translation against free APIs that need no key.

All three were probed from this machine before being wired in:

  Open-Meteo   200, no key, no credit card
  Nominatim    200, no key, but requires a real User-Agent and rate limits
  MyMemory     200, no key, ~5000 chars/day anonymous

Nominatim's usage policy caps requests at 1 per second, so geocoding is
throttled in-process rather than hammering OpenStreetMap.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "jenny-assistant/1.0 (local desktop assistant; contact: local user)"
NOMINATIM_UA = "jenny-assistant/1.0"
TIMEOUT = 20
WMO = {
    0: ("Clear sky", "clear"), 1: ("Mainly clear", "clear"), 2: ("Partly cloudy", "cloud"),
    3: ("Overcast", "cloud"), 45: ("Fog", "fog"), 48: ("Rime fog", "fog"),
    51: ("Light drizzle", "rain"), 53: ("Drizzle", "rain"), 55: ("Heavy drizzle", "rain"),
    61: ("Light rain", "rain"), 63: ("Rain", "rain"), 65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"), 67: ("Heavy freezing rain", "rain"),
    71: ("Light snow", "snow"), 73: ("Snow", "snow"), 75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"), 80: ("Light showers", "rain"), 81: ("Showers", "rain"),
    82: ("Violent showers", "rain"), 85: ("Snow showers", "snow"), 86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorm", "storm"), 96: ("Thunderstorm with hail", "storm"),
    99: ("Thunderstorm with heavy hail", "storm"),
}
_GEOCODE_LOCK = threading.Lock()
_LAST_GEOCODE = [0.0]


class ApiError(dict):
    def __init__(self, msg, **extra):
        super().__init__(ok=False, error=msg, **extra)


def _err(msg, **extra):
    return ApiError(msg, **extra)


def _get(url, ua=UA, accept="application/json", timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _err("rate limited - too many requests, wait a moment")
        return _err(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        return _err(f"Network problem: {e.reason}")
    except Exception as e:
        return _err(f"{type(e).__name__}: {e}")


def _get_json(url, ua=UA):
    raw = _get(url, ua)
    if isinstance(raw, ApiError):
        return raw
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except Exception as e:
        return _err(f"Bad JSON: {e}")


# ------------------------------------------------------------- geocoding

def geocode(query, limit=1, country=None):
    """Turn a place name into coordinates using OpenStreetMap Nominatim."""
    q = str(query or "").strip()
    if not q:
        return _err("Give me a place to look up.")
    with _GEOCODE_LOCK:
        wait = 1.05 - (time.time() - _LAST_GEOCODE[0])
        if wait > 0:
            time.sleep(wait)
        try:
            params = {"q": q, "format": "jsonv2", "limit": str(int(limit))}
            if country:
                params["countrycodes"] = str(country).lower()
            data = _get_json("https://nominatim.openstreetmap.org/search?"
                             + urllib.parse.urlencode(params), ua=NOMINATIM_UA)
        finally:
            _LAST_GEOCODE[0] = time.time()
    if isinstance(data, ApiError):
        return data
    if not isinstance(data, list):
        return _err("Geocoder returned an unexpected payload.")
    if not data:
        return _err(f"I couldn't find anywhere called '{q}'.")
    out = [{"name": d.get("display_name", "")[:200],
            "lat": float(d["lat"]), "lon": float(d["lon"]),
            "type": d.get("type"), "category": d.get("class"),
            "country": (d.get("address") or {}).get("country")}
           for d in data]
    t = out[0]
    return {"ok": True, "query": q, "count": len(out), "places": out,
            "lat": t["lat"], "lon": t["lon"],
            "text": f"{t['name'][:90]} ({t['lat']:.3f}, {t['lon']:.3f})"}


def reverse_geocode(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except Exception:
        return _err("Give numeric latitude and longitude.")
    with _GEOCODE_LOCK:
        wait = 1.05 - (time.time() - _LAST_GEOCODE[0])
        if wait > 0:
            time.sleep(wait)
        try:
            data = _get_json("https://nominatim.openstreetmap.org/reverse?"
                             + urllib.parse.urlencode({"lat": lat, "lon": lon, "format": "jsonv2"}),
                             ua=NOMINATIM_UA)
        finally:
            _LAST_GEOCODE[0] = time.time()
    if isinstance(data, ApiError):
        return data
    if not isinstance(data, dict) or "error" in data:
        return _err("No place found at those coordinates.")
    return {"ok": True, "name": (data.get("display_name") or "")[:200],
            "lat": lat, "lon": lon,
            "text": f"{lat:.3f}, {lon:.3f} is {(data.get('display_name') or '')[:90]}"}


# ------------------------------------------------------- places & routes

# Overpass (OpenStreetMap) and OSRM's public demo server are both keyless, so
# "nearby" and "route" are real answers here rather than "needs a maps key".
_PLACE_KINDS = {
    "food": '["amenity"="restaurant"]["amenity"="cafe"]["amenity"="fast_food"]',
    "cafe": '["amenity"="cafe"]',
    "restaurant": '["amenity"="restaurant"]',
    "shop": '["shop"]',
    "pharmacy": '["amenity"="pharmacy"]',
    "hospital": '["amenity"="hospital"]["amenity"="clinic"]',
    "fuel": '["amenity"="fuel"]',
    "bank": '["amenity"="bank"]',
    "atm": '["amenity"="atm"]',
    "supermarket": '["shop"="supermarket"]["shop"="convenience"]',
    "park": '["leisure"="park"]["leisure"="garden"]',
    "school": '["amenity"="school"]["amenity"="university"]',
    "gym": '["leisure"="fitness_centre"]',
    "hotel": '["tourism"="hotel"]["tourism"="hostel"]',
    "police": '["amenity"="police"]',
    "library": '["amenity"="library"]',
}
_OSRM = "https://router.project-osrm.org/route/v1/driving"
# The main Overpass box times out (504) often enough to need mirrors; each is
# the same API on different hardware.
_OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
# Overpass rate-limits aggressively; space out queries so a burst of
# "what's near me" requests doesn't 504 every mirror at once.
_OVERPASS_LOCK = threading.Lock()
_LAST_OVERPASS = [0.0]
_OVERPASS_MIN_GAP = 2.0


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def _coerce_point(lat, lon, location):
    """Accept raw coordinates or a place name and always return a point."""
    if lat is None or lon is None:
        if not location:
            return None, _err("Give a location name, or latitude and longitude.")
        g = geocode(location)
        if isinstance(g, ApiError):
            return None, g
        # geocode() returns its hits under "places", with lat/lon hoisted to
        # the top level for the first hit.
        hits = g.get("places") or []
        if not hits:
            return None, _err(f"Couldn't find '{location}'.")
        first = hits[0]
        return (float(first.get("lat", g.get("lat"))),
                float(first.get("lon", g.get("lon")))), None
    try:
        lat, lon = float(lat), float(lon)
    except Exception:
        return None, _err("Give numeric latitude and longitude.")
    return (lat, lon), None


def _overpass_query(q, attempts=2):
    """Ask Overpass for q, rotating mirrors and backing off between rounds.

    The free instances rate-limit hard (429/504) under any burst, so a single
    pass frequently fails. Returns (raw_bytes, error_string); exactly one of
    the two is None. Errors from every mirror are collected so a failure
    report says what actually happened instead of blaming the last box.
    """
    last_round = []
    for round_no in range(max(1, int(attempts))):
        if round_no:
            time.sleep(_OVERPASS_MIN_GAP * (round_no + 2))
        misses = []
        for base in _OVERPASS_MIRRORS:
            host = base.split("//")[1].split("/")[0]
            with _OVERPASS_LOCK:
                wait = _OVERPASS_MIN_GAP - (time.time() - _LAST_OVERPASS[0])
                if wait > 0:
                    time.sleep(wait)
                _LAST_OVERPASS[0] = time.time()
            try:
                got = _get(base + "?" + urllib.parse.urlencode({"data": q}),
                           ua=UA, accept="application/json", timeout=60)
            except Exception as e:
                misses.append(f"{host}: {type(e).__name__} {e}")
                continue
            # _get never raises -- it hands back an ApiError dict. Anything that
            # isn't a parseable payload with elements means "this mirror is
            # busy", so try the next one rather than reporting a 504.
            if isinstance(got, ApiError):
                misses.append(f"{host}: {got.get('error')}")
                continue
            try:
                if not (json.loads(got) or {}).get("elements"):
                    misses.append(f"{host}: timed out, no elements")
                    continue
            except Exception as e:
                misses.append(f"{host}: unreadable response ({e})")
                continue
            return got, None
        last_round = misses
    return None, "; ".join(last_round)


def nearby_places(kind="food", location=None, lat=None, lon=None, radius_m=1500, limit=10):
    """Real nearby-POI lookup from OpenStreetMap's Overpass API. No key."""
    if not isinstance(radius_m, (int, float)) or radius_m <= 0 or radius_m > 50000:
        return _err("radius_m must be between 1 and 50000.")
    limit = max(1, min(int(limit or 10), 50))
    sel = _PLACE_KINDS.get(str(kind).lower())
    if sel is None:
        return _err(f"Unknown kind '{kind}'. Try: {', '.join(sorted(_PLACE_KINDS))}.")
    pt, err = _coerce_point(lat, lon, location)
    if err is not None:
        return err
    lat, lon = pt
    q = (f"[out:json][timeout:25];(node{sel}(around:{int(radius_m)},{lat:.5f},{lon:.5f}););"
         f"out center {limit};")
    raw, why = _overpass_query(q)
    if raw is None:
        return _err("Nearby lookup failed on every Overpass mirror -- "
                    f"{why}. Overpass's free servers are rate-limited right now; "
                    "wait a minute and ask again.")
    try:
        nodes = (json.loads(raw) or {}).get("elements") or []
    except Exception as e:
        return _err(f"Overpass sent back something unreadable: {e}")
    out = []
    for el in nodes:
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("brand") or tags.get("operator")
        if not name:
            continue
        c = el.get("center") or el
        elat, elon = c.get("lat"), c.get("lon")
        if elat is None or elon is None:
            continue
        out.append({"name": name[:90],
                    "lat": float(elat), "lon": float(elon),
                    "distance_m": round(_haversine_m(lat, lon, float(elat), float(elon))),
                    "kind": tags.get("amenity") or tags.get("shop") or tags.get("leisure")
                            or tags.get("tourism") or kind})
    out.sort(key=lambda r: r["distance_m"])
    if not out:
        return {"ok": True, "kind": kind, "location": location or f"{lat:.3f},{lon:.3f}",
                "results": [],
                "text": f"No {kind} within {int(radius_m)}m of {location or f'{lat:.3f},{lon:.3f}'}."}
    heads = ", ".join(f"{r['name']} ({r['distance_m']}m)" for r in out[:3])
    return {"ok": True, "kind": kind, "location": location or f"{lat:.3f},{lon:.3f}",
            "count": len(out), "results": out,
            "text": f"{len(out)} {kind} near {location or f'{lat:.3f},{lon:.3f}'}: {heads}."}


def route(destination=None, origin=None, lat=None, lon=None,
          dest_lat=None, dest_lon=None, mode="driving", units="auto"):
    """Turn-by-turn-free route summary, distance and ETA from OSRM. No key."""
    if mode not in ("driving", "walking", "cycling"):
        return _err("mode must be driving, walking or cycling.")
    a, err = _coerce_point(lat, lon, origin)
    if err is not None:
        return err
    b, err = _coerce_point(dest_lat, dest_lon, destination)
    if err is not None:
        return err
    (alat, alon), (blat, blon) = a, b
    profile = {"driving": "driving", "walking": "foot", "cycling": "bike"}[mode]
    url = (f"https://router.project-osrm.org/route/v1/{profile}/"
           f"{alon:.6f},{alat:.6f};{blon:.6f},{blat:.6f}"
           f"?overview=false&steps=true&alternatives=false")
    try:
        raw = _get(url, ua=UA, accept="application/json")
    except Exception as e:
        return _err(f"Routing failed: {type(e).__name__}: {e}")
    if isinstance(raw, ApiError):
        return raw
    try:
        r = (json.loads(raw) or {}).get("routes") or []
    except Exception as e:
        return _err(f"Router sent back something unreadable: {e}")
    if not r:
        return _err("No route found between those points (are they on drivable roads?).")
    legs = r[0].get("legs") or [{}]
    dist_m = float(r[0].get("distance") or 0.0)
    dur_s = float(r[0].get("duration") or 0.0)
    steps = legs[0].get("steps") or []
    road = ""
    for s in steps:
        nm = s.get("name")
        if nm:
            road = nm[:60]
            break
    if units not in ("auto", "km", "mi"):
        return _err("units must be auto, km or mi.")
    if units == "auto":
        use_mi = dist_m < 1609.0
    else:
        use_mi = units == "mi"
    if use_mi:
        dist_s = f"{dist_m / 1609.34:.1f} mi"
    else:
        dist_s = f"{dist_m / 1000.0:.1f} km"
    mins = int(round(dur_s / 60.0))
    if mins < 60:
        eta = f"{mins} min"
    else:
        eta = f"{mins // 60}h {mins % 60:02d}m"
    where = f"{origin or f'{alat:.3f},{alon:.3f}'} to {destination or f'{blat:.3f},{blon:.3f}'}"
    return {"ok": True, "from": [alat, alon], "to": [blat, blon],
            "distance_m": round(dist_m), "duration_s": int(dur_s),
            "distance": dist_s, "duration": eta, "mode": mode,
            "road": road, "steps": len(steps),
            "text": f"{where}: {dist_s} by {mode}, about {eta}."}


# --------------------------------------------------------------- weather

def weather(location=None, lat=None, lon=None, forecast_days=3):
    """Current conditions plus a short daily forecast. No API key required."""
    place = None
    if location and (lat is None or lon is None):
        g = geocode(location)
        if not g.get("ok"):
            return g
        lat, lon, place = g["lat"], g["lon"], g["places"][0]["name"]
    if lat is None or lon is None:
        return _err("Give a location name, or latitude and longitude.")
    try:
        lat, lon = float(lat), float(lon)
    except Exception:
        return _err("Latitude and longitude must be numbers.")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return _err(f"({lat}, {lon}) isn't a real coordinate.")
    days = max(1, min(int(forecast_days), 16))
    url = ("https://api.open-meteo.com/v1/forecast?"
           + urllib.parse.urlencode({
               "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
               "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                          "precipitation,weather_code,wind_speed_10m,is_day",
               "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                        "precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
               "timezone": "auto", "forecast_days": str(days)}))
    data = _get_json(url)
    if isinstance(data, ApiError):
        return data
    cur = data.get("current") or {}
    code = cur.get("weather_code")
    desc, kind = WMO.get(code, (f"Code {code}", "unknown"))
    daily = data.get("daily") or {}
    out_days = []
    for i, d in enumerate((daily.get("time") or [])[:days]):
        dcode = (daily.get("weather_code") or [None] * days)[i]
        out_days.append({
            "date": d,
            "high": (daily.get("temperature_2m_max") or [None] * days)[i],
            "low": (daily.get("temperature_2m_min") or [None] * days)[i],
            "rain_mm": (daily.get("precipitation_sum") or [None] * days)[i],
            "rain_chance": (daily.get("precipitation_probability_max") or [None] * days)[i],
            "wind": (daily.get("wind_speed_10m_max") or [None] * days)[i],
            "desc": WMO.get(dcode, ("", ""))[0],
        })
    where = place or f"{lat:.3f}, {lon:.3f}"
    rain = any((d.get("rain_chance") or 0) >= 50 for d in out_days)
    return {"ok": True, "location": where, "lat": lat, "lon": lon,
            "current": {"temp_c": cur.get("temperature_2m"), "feels_c": cur.get("apparent_temperature"),
                        "humidity": cur.get("relative_humidity_2m"),
                        "precip_mm": cur.get("precipitation"),
                        "wind_kmh": cur.get("wind_speed_10m"),
                        "desc": desc, "kind": kind,
                        "is_day": bool(cur.get("is_day", 1))},
            "forecast": out_days,
            "will_rain": rain,
            "units": "celsius, km/h, mm",
            "text": f"{where}: {desc.lower()}, {cur.get('temperature_2m')}C "
                    f"(feels {cur.get('apparent_temperature')}C), "
                    f"{cur.get('relative_humidity_2m')}% humidity, "
                    f"wind {cur.get('wind_speed_10m')} km/h."
                    + (f" Rain likely in the next {days} day(s)." if rain else "")}


def air_quality(location=None, lat=None, lon=None):
    """Open-Meteo's air-quality endpoint, also keyless."""
    if location and (lat is None or lon is None):
        g = geocode(location)
        if not g.get("ok"):
            return g
        lat, lon, place = g["lat"], g["lon"], g["places"][0]["name"]
    else:
        place = f"{lat}, {lon}"
    try:
        url = ("https://air-quality-api.open-meteo.com/v1/air-quality?"
               + urllib.parse.urlencode({"latitude": f"{float(lat):.4f}",
                                          "longitude": f"{float(lon):.4f}",
                                          "current": "pm2_5,pm10,european_aqi,us_aqi"}))
    except Exception:
        return _err("Give a location or numeric coordinates.")
    data = _get_json(url)
    if isinstance(data, ApiError):
        return data
    cur = data.get("current") or {}
    aqi = cur.get("european_aqi")
    band = ("Good" if aqi is not None and aqi <= 20 else
            "Fair" if aqi is not None and aqi <= 40 else
            "Moderate" if aqi is not None and aqi <= 60 else
            "Poor" if aqi is not None and aqi <= 80 else
            "Very poor" if aqi is not None and aqi <= 100 else "Extremely poor")
    return {"ok": True, "location": place, "aqi": aqi, "us_aqi": cur.get("us_aqi"),
            "pm2_5": cur.get("pm2_5"), "pm10": cur.get("pm10"), "band": band,
            "text": f"Air quality in {place}: {band} (AQI {aqi}, PM2.5 {cur.get('pm2_5')} ug/m3)."}


# ----------------------------------------------------------- translation

_LANGS = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de", "italian": "it",
    "portuguese": "pt", "dutch": "nl", "russian": "ru", "japanese": "ja", "korean": "ko",
    "chinese": "zh-CN", "arabic": "ar", "hindi": "hi", "turkish": "tr", "polish": "pl",
    "swedish": "sv", "bengali": "bn", "tamil": "ta", "urdu": "ur", "vietnamese": "vi",
    "thai": "th", "greek": "el", "hebrew": "he", "czech": "cs", "romanian": "ro",
    "hungarian": "hu", "ukrainian": "uk", "indonesian": "id", "persian": "fa",
}


def detect_language(text):
    """Cheap script/keyword detection. Not a substitute for a real model."""
    t = str(text or "")
    if not t.strip():
        return _err("Give me some text to identify.")
    counts = {
        "en": len(re.findall(r"\b(the|and|is|of|to|and|you|that|it)\b", t.lower())),
        "es": len(re.findall(r"\b(el|la|de|que|y|en|los|las|por)\b", t.lower())),
        "fr": len(re.findall(r"\b(le|la|les|des|est|et|que|pour|dans)\b", t.lower())),
        "de": len(re.findall(r"\b(der|die|das|und|ist|nicht|mit|ich)\b", t.lower())),
        "pt": len(re.findall(r"\b(o|a|de|que|não|para|com|uma)\b", t.lower())),
        "it": len(re.findall(r"\b(il|la|di|che|non|per|con|una)\b", t.lower())),
    }
    script = {"ru": len(re.findall(r"[\u0400-\u04FF]", t)),
              "el": len(re.findall(r"[\u0370-\u03FF]", t)),
              "ar": len(re.findall(r"[\u0600-\u06FF]", t)),
              "he": len(re.findall(r"[\u0590-\u05FF]", t)),
              "ja": len(re.findall(r"[\u3040-\u30FF]", t)),
              "ko": len(re.findall(r"[\uAC00-\uD7AF]", t)),
              "zh-CN": len(re.findall(r"[\u4E00-\u9FFF]", t))}
    for k, v in script.items():
        if v:
            return {"ok": True, "lang": k, "lang_name": k, "confidence": "high (script)",
                    "text": f"That looks like {k}."}
    best = max(counts.items(), key=lambda kv: kv[1])
    if best[1] == 0:
        return {"ok": True, "lang": "unknown", "lang_name": "unknown", "confidence": "low",
                "text": "I couldn't identify that language from the words alone."}
    return {"ok": True, "lang": best[0], "lang_name": best[0], "confidence": "low (keywords only)",
            "text": f"It looks like {best[0]}, but that's a rough guess."}


def translate(text, target_lang, source_lang=None, email=None):
    """Translate via MyMemory. No key, ~5000 chars/day anonymously."""
    t = str(text or "").strip()
    if not t:
        return _err("Give me something to translate.")
    tgt = _LANGS.get(str(target_lang).lower().strip(), str(target_lang).strip()[:5])
    src = _LANGS.get(str(source_lang).lower().strip(), None) if source_lang else "autodetect"
    if len(t) > 4800:
        return _err(f"That's {len(t)} characters; the free anonymous limit is 5000 per day. "
                    f"Send a shorter chunk.")
    pair = f"{src}|{tgt}"
    params = {"q": t[:4800], "langpair": pair}
    # MyMemory rejects an invalid `de` address outright, so only send one that
    # looks like a real address. Omitting it works fine for anonymous quota.
    if email and re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", str(email), re.I):
        params["de"] = str(email)
    url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    if isinstance(data, ApiError):
        return data
    if int(data.get("responseStatus", 200)) != 200:
        return _err(f"Translation rejected: {data.get('responseDetails')}")
    if data.get("quotaFinished"):
        return _err("The free daily translation quota is used up. It resets within 24 hours.")
    resp = (data.get("responseData") or {})
    out = resp.get("translatedText") or ""
    if not out or not out.strip():
        return _err("The translation service returned nothing.")
    if out.strip().lower() == t.strip().lower() and (src == "autodetect" or src == tgt):
        return _err("The service couldn't identify the source language, so it returned the "
                    "text unchanged. Try naming the source language.")
    return {"ok": True, "source": src, "target": tgt, "translation": out,
            "match_quality": resp.get("match"), "chars": len(t),
            "text": out[:400]}


def supported_languages():
    return {"ok": True, "count": len(_LANGS), "languages": _LANGS,
            "text": f"{len(_LANGS)} language codes available."}


def available() -> dict:
    return {"needs_key": False,
            "services": {
                "weather": "Open-Meteo (live)",
                "air_quality": "Open-Meteo air quality (live)",
                "geocoding": "OpenStreetMap Nominatim (live, 1 req/sec)",
                "translation": "MyMemory (live, ~5000 chars/day anonymous)",
            },
            "detail": "Weather, air quality, place lookup and translation are live with no API key."}

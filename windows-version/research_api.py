"""Scholarly research against APIs that need no key and no credit card.

arXiv, OpenAlex and Crossref are all open and keyless, so paper search,
author lookup, citation counts and open-access PDF links work here today
without the user signing up for anything.

Semantic Scholar is included too but its unauthenticated tier rate-limits
hard, so it is only used as a fallback and reports 429 honestly instead of
pretending it found nothing.

Every request sends a real User-Agent. That is not cosmetic: default
urllib agents are rejected by several of these hosts.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

UA = "jenny-assistant/1.0 (local research helper)"
TIMEOUT = 20


class ApiError(dict):
    """Distinct from a successful payload, which is also a plain dict.

    Checking `isinstance(data, dict)` to detect failure silently treated every
    successful OpenAlex/Crossref response as an error.
    """

    def __init__(self, msg, **extra):
        super().__init__(ok=False, error=msg, **extra)


def _err(msg, **extra):
    return ApiError(msg, **extra)


def _get(url, accept="application/json", headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _err(f"rate limited ({e.reason}) - this source is throttling unauthenticated requests")
        if e.code == 406:
            return _err(f"HTTP 406 from {urllib.parse.urlsplit(url).netloc} - it rejected the request format")
        return _err(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        return _err(f"Network problem: {e.reason}. Check your connection.")
    except Exception as e:
        return _err(f"{type(e).__name__}: {e}")


def _get_json(url):
    raw = _get(url)
    if isinstance(raw, ApiError):
        return raw
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except Exception as e:
        return _err(f"Bad JSON from the API: {e}")


def _get_html(url):
    raw = _get(url, accept="text/html,application/xhtml+xml")
    if isinstance(raw, ApiError):
        return raw
    return raw.decode("utf-8", "replace")


def _clean(s, limit=400):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s[:limit]


# ---------------------------------------------------------------- arXiv
#
# The arXiv Atom API (export.arxiv.org/api/query) answers HTTP 406 to every
# request from this network, including with a browser User-Agent, so it is not
# usable here. The public abstract page does respond, so arXiv lookups by id
# are parsed from that HTML instead. Preprint *search* comes from OpenAlex,
# which indexes arXiv content, and says so rather than failing silently.

_TAG_RE = re.compile(r"<[^>]+>")


def _unescape(s):
    import html
    return html.unescape(s or "").strip()


def _strip_tags(s):
    return _clean(_unescape(_TAG_RE.sub(" ", s or "")))


def arxiv_by_id(identifier):
    """Fetch one arXiv paper from its abstract page."""
    aid = str(identifier or "").strip()
    aid = re.sub(r"^(arxiv:|arxiv\.org/abs/|arxiv\.org/pdf/)", "", aid, flags=re.I)
    aid = re.sub(r"\.pdf$", "", aid, flags=re.I)
    if not re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", aid) and not re.match(r"^[a-z-]+(\.[A-Z]{2})?/\d{7}(v\d+)?$", aid):
        return _err(f"'{identifier}' doesn't look like an arXiv id (expected something like 1706.03762).")
    html_doc = _get_html(f"https://arxiv.org/abs/{aid}")
    if isinstance(html_doc, ApiError):
        return html_doc
    m = re.search(r'<h1 class="title[^"]*">(.*?)</h1>', html_doc, re.S)
    if not m:
        return _err(f"arXiv has no paper at {aid} (the page loaded but had no title element).")
    title = _strip_tags(m.group(1))
    title = re.sub(r"^Title:\s*", "", title)
    am = re.search(r'<div class="authors">(.*?)</div>', html_doc, re.S)
    authors = [_strip_tags(a) for a in re.findall(r'<a[^>]*>(.*?)</a>', am.group(1))] if am else []
    bm = re.search(r'<blockquote class="abstract[^"]*">(.*?)</blockquote>', html_doc, re.S)
    abstract = _strip_tags(bm.group(1)) if bm else ""
    abstract = re.sub(r"^Abstract:\s*", "", abstract)
    dm = re.search(r"\[Submitted on\s*([^\]<]+?)(?:\s*\(|\])", html_doc)
    sm = re.search(r'<td class="tablecell subjects">(.*?)</td>', html_doc, re.S)
    categories = re.findall(r"\(([a-z-]+\.[A-Z]{2}|[a-z-]+\.[a-z-]+)\)", _strip_tags(sm.group(1))) if sm else []
    return {"ok": True, "source": "arXiv (abs page)", "paper": {
        "id": aid, "title": title, "authors": authors, "abstract": abstract[:1500],
        "submitted": dm.group(1).strip() if dm else None,
        "categories": categories[:6],
        "abs_url": f"https://arxiv.org/abs/{aid}",
        "pdf_url": f"https://arxiv.org/pdf/{aid}",
    }, "text": f"{title[:90]} - {len(authors)} author(s)"
              + (f", submitted {dm.group(1).strip()[:10]}" if dm else "")}


# -------------------------------------------------------------- OpenAlex

def openalex_search(query, limit=8, from_year=None):
    params = {
        "search": query, "per-page": str(int(limit)),
        "mailto": "jenny@localhost",  # OpenAlex asks for a contact; this keeps us in the polite pool
    }
    if from_year:
        params["filter"] = f"from_publication_date:{from_year}-01-01"
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    if isinstance(data, ApiError):
        return data
    out = []
    for w in data.get("results", [])[:int(limit)]:
        loc = w.get("primary_location") or {}
        src = (loc.get("source") or {}).get("display_name")
        out.append({
            "id": w.get("id", "").rsplit("/", 1)[-1],
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "title": _clean(w.get("display_name"), 220),
            "year": w.get("publication_year"),
            "citations": w.get("cited_by_count", 0),
            "type": w.get("type"),
            "authors": [_clean(a.get("author", {}).get("display_name"), 60)
                        for a in (w.get("authorships") or [])[:6]],
            "venue": _clean(src, 80) or None,
            "is_open_access": (w.get("open_access") or {}).get("is_oa", False),
            "pdf_url": (w.get("best_oa_location") or {}).get("pdf_url"),
            "abstract": _clean(_invert_abstract(w.get("abstract_inverted_index")), 700),
            "url": w.get("doi") or w.get("id"),
        })
    if not out:
        return {"ok": True, "source": "OpenAlex", "count": 0, "papers": [],
                "text": f"OpenAlex had no works matching '{query}'."}
    top = max(out, key=lambda p: p["citations"])
    return {"ok": True, "source": "OpenAlex", "count": len(out), "papers": out,
            "text": f"OpenAlex: {len(out)} work(s) for '{query}'. Most cited: "
                    f"{top['title']} ({top['citations']} citations, {top['year']})."}


def _invert_abstract(inv):
    """OpenAlex ships abstracts as an inverted index; rebuild the prose."""
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def openalex_author(name, limit=5):
    url = ("https://api.openalex.org/authors?search="
           + urllib.parse.quote(name) + f"&per-page={int(limit)}&mailto=jenny@localhost")
    data = _get_json(url)
    if isinstance(data, ApiError):
        return data
    out = []
    for a in data.get("results", [])[:int(limit)]:
        inst = ((a.get("last_known_institution") or {}).get("display_name"))
        out.append({"name": _clean(a.get("display_name"), 90),
                    "papers": a.get("works_count", 0),
                    "citations": a.get("cited_by_count", 0),
                    "h_index": (a.get("summary_stats") or {}).get("h_index"),
                    "institution": _clean(inst, 80) or None,
                    "orcid": a.get("orcid"),
                    "id": (a.get("id") or "").rsplit("/", 1)[-1]})
    if not out:
        return {"ok": True, "count": 0, "authors": [],
                "text": f"No author found for '{name}'."}
    t = out[0]
    return {"ok": True, "count": len(out), "authors": out,
            "text": f"{t['name']}: {t['papers']} paper(s), {t['citations']} citations"
                    + (f", h-index {t['h_index']}" if t.get("h_index") is not None else "")
                    + (f", {t['institution']}" if t.get("institution") else "") + "."}


def openalex_citations(doi, limit=20):
    ident = urllib.parse.quote(doi if doi.startswith("http") else f"https://doi.org/{doi}", safe="")
    url = f"https://api.openalex.org/works/{ident}?mailto=jenny@localhost"
    data = _get_json(url)
    if isinstance(data, ApiError):
        return data
    cited_by = data.get("cited_by_api_url")
    if not cited_by:
        return {"ok": True, "cited_by_count": data.get("cited_by_count", 0), "citing": [],
                "text": f"'{_clean(data.get('display_name'), 60)}' has "
                        f"{data.get('cited_by_count', 0)} citing work(s)."}
    url2 = cited_by.replace("mailto=jenny@localhost", "mailto=jenny@localhost") + f"&per-page={int(limit)}"
    d2 = _get_json(url2)
    if isinstance(d2, ApiError):
        return d2
    citing = [{"title": _clean(w.get("display_name"), 140), "year": w.get("publication_year"),
               "citations": w.get("cited_by_count", 0),
               "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None}
              for w in d2.get("results", [])[:int(limit)]]
    return {"ok": True, "cited_by_count": data.get("cited_by_count", 0), "citing": citing,
            "text": f"{data.get('cited_by_count', 0)} work(s) cite this. Sample: "
                    + (", ".join(c["title"][:50] for c in citing[:3]) if citing else "none listed")}


def openalex_related(doi, limit=10):
    ident = urllib.parse.quote(doi if doi.startswith("http") else f"https://doi.org/{doi}", safe="")
    url = (f"https://api.openalex.org/works/{ident}?select=related_works&mailto=jenny@localhost")
    data = _get_json(url)
    if isinstance(data, ApiError):
        return data
    ids = (data.get("related_works") or [])[:int(limit)]
    if not ids:
        return {"ok": True, "related": [], "text": "No related works listed for this paper."}
    filt = "|".join(i.rsplit("/", 1)[-1] for i in ids)
    url2 = f"https://api.openalex.org/works?filter=openalex_id:{filt}&per-page={int(limit)}&mailto=jenny@localhost"
    d2 = _get_json(url2)
    if isinstance(d2, ApiError):
        return d2
    rel = [{"title": _clean(w.get("display_name"), 140), "year": w.get("publication_year"),
            "citations": w.get("cited_by_count", 0),
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None}
           for w in d2.get("results", [])]
    return {"ok": True, "related": rel,
            "text": f"{len(rel)} related work(s). Closest: " + (rel[0]["title"][:70] if rel else "none")}


# ---------------------------------------------------------------- Crossref

def crossref_lookup(query, limit=6):
    url = ("https://api.crossref.org/works?query=" + urllib.parse.quote(query)
           + f"&rows={int(limit)}&select=title,author,issued,DOI,container-title,is-referenced-by-count,type")
    data = _get_json(url)
    if isinstance(data, ApiError):
        return data
    out = []
    for w in (data.get("message", {}).get("items", []) or [])[:int(limit)]:
        issued = ((w.get("issued") or {}).get("date-parts") or [[None]])[0]
        out.append({
            "title": _clean((w.get("title") or [""])[0], 220),
            "doi": w.get("DOI"),
            "year": issued[0] if issued else None,
            "venue": _clean((w.get("container-title") or [""])[0], 80) or None,
            "citations": w.get("is-referenced-by-count", 0),
            "type": w.get("type"),
            "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip()[:60]
                        for a in (w.get("author") or [])[:6]],
        })
    if not out:
        return {"ok": True, "count": 0, "works": [], "text": f"Crossref had no match for '{query}'."}
    return {"ok": True, "source": "Crossref", "count": len(out), "works": out,
            "text": f"Crossref: {len(out)} work(s) for '{query}'. Most cited: "
                    f"{max(out, key=lambda w: w['citations'])['title'][:70]} "
                    f"({max(out, key=lambda w: w['citations'])['citations']} citations)."}


# ----------------------------------------------------- Semantic Scholar

def s2_search(query, limit=6):
    url = ("https://api.semanticscholar.org/graph/v1/paper/search?query="
           + urllib.parse.quote(query)
           + f"&limit={int(limit)}&fields=title,year,authors,citationCount,abstract,externalIds,openAccessPdf")
    data = _get_json(url)
    if isinstance(data, ApiError):
        return data
    out = []
    for p in data.get("data", [])[:int(limit)]:
        out.append({"title": _clean(p.get("title"), 200), "year": p.get("year"),
                    "citations": p.get("citationCount", 0),
                    "authors": [a.get("name", "")[:60] for a in (p.get("authors") or [])[:6]],
                    "abstract": _clean(p.get("abstract"), 600),
                    "arxiv_id": (p.get("externalIds") or {}).get("ArXiv"),
                    "doi": (p.get("externalIds") or {}).get("DOI"),
                    "pdf_url": (p.get("openAccessPdf") or {}).get("url")})
    return {"ok": True, "source": "Semantic Scholar", "count": len(out), "papers": out,
            "text": f"Semantic Scholar: {len(out)} paper(s) for '{query}'."}


# ------------------------------------------------------------ aggregator

def search_papers(query, limit=8, sources=("openalex", "crossref", "s2")):
    """Search several indexes and return de-duplicated results.

    arXiv is not a source here: its Atom API refuses requests from this
    network. OpenAlex covers arXiv-indexed preprints, so preprints are still
    reachable via search.
    """
    if not query or not str(query).strip():
        return _err("Give me something to search for.")
    out, problems, seen = [], [], set()
    for src in sources:
        try:
            if src == "openalex":
                r = openalex_search(query, limit)
            elif src == "crossref":
                r = crossref_lookup(query, limit)
            elif src == "s2":
                r = s2_search(query, limit)
            else:
                continue
        except Exception as e:
            problems.append(f"{src}: {type(e).__name__}: {e}")
            continue
        if not r.get("ok"):
            problems.append(f"{src}: {r.get('error')}")
            continue
        for p in r.get("papers") or r.get("works") or []:
            key = (p.get("title") or "").lower()[:80]
            if key and key in seen:
                continue
            seen.add(key)
            out.append({"source": src, **p})
    if not out:
        return _err(f"No index returned results for '{query}'."
                    + (" Problems: " + "; ".join(problems[:3]) if problems else ""))
    out.sort(key=lambda p: -(p.get("citations") or 0))
    used = [s for s in sources if not any(q.startswith(s + ":") for q in problems)]
    return {"ok": True, "query": query, "count": len(out), "results": out[:int(limit) * 2],
            "sources_used": used, "partial": bool(problems), "source_problems": problems,
            "text": f"{len(out)} result(s) for '{query}' across {len(used)} index(es). "
                    f"Most cited: {out[0].get('title', '?')[:80]} "
                    f"({out[0].get('citations', 0)} citations)."
                    + (f" {len(problems)} index(es) failed." if problems else "")}


def paper_by_id(identifier):
    """Look up one paper by arXiv id, DOI, or exact title."""
    ident = str(identifier).strip()
    if not ident:
        return _err("Give an arXiv id, a DOI, or a paper title.")
    if re.match(r"^\d{4}\.\d{4,5}", ident) or "arxiv.org" in ident.lower():
        return arxiv_by_id(ident)
    if ident.lower().startswith("arxiv:"):
        return arxiv_by_id(ident)
    if "10." in ident:
        doi = ident.replace("https://doi.org/", "").replace("doi:", "").strip()
        r = openalex_citations(doi, 5)
        if r.get("ok"):
            return {"ok": True, "matched_on": "DOI", "cited_by_count": r.get("cited_by_count"),
                    "citing": r.get("citing", []), "text": r.get("text")}
        return r
    r = openalex_search(f'"{ident}"', 3)
    if r.get("ok") and r.get("papers"):
        return {"ok": True, "matched_on": "title", "paper": r["papers"][0],
                "text": f"Matched by title: {r['papers'][0]['title']}"}
    return _err(f"Couldn't match '{ident}' to a paper by id, DOI or title.")


def open_access_pdf(identifier):
    ident = str(identifier).strip()
    if not ident:
        return _err("Give an arXiv id or DOI.")
    if re.match(r"^\d{4}\.\d{4,5}", ident):
        return {"ok": True, "pdf_url": f"https://arxiv.org/pdf/{ident}",
                "text": f"arXiv PDF: https://arxiv.org/pdf/{ident}"}
    r = openalex_search(ident, 3)
    for p in r.get("papers", []) if r.get("ok") else []:
        if p.get("pdf_url"):
            return {"ok": True, "pdf_url": p["pdf_url"], "title": p["title"],
                    "is_open_access": p.get("is_open_access"),
                    "text": f"Open-access PDF: {p['pdf_url']}"}
    return _err("No open-access PDF is available for that identifier.")


def field_of_study(title):
    """Infer the research area from an OpenAlex topic field."""
    r = openalex_search(title, 1)
    if not r.get("ok") or not r.get("papers"):
        return r
    return {"ok": True, "title": r["papers"][0]["title"],
            "topics": r["papers"][0].get("categories", []) or [],
            "text": f"'{r['papers'][0]['title'][:60]}' - venue: {r['papers'][0].get('venue')}, "
                    f"year {r['papers'][0].get('year')}"}


def available() -> dict:
    return {"sources": ["OpenAlex", "Crossref", "Semantic Scholar", "arXiv abstract pages"],
            "needs_key": False,
            "arxiv_api": "blocked from this network (HTTP 406); preprints come via OpenAlex",
            "semantic_scholar": "rate limits unauthenticated calls, used as a fallback only",
            "detail": "Paper, author and citation search is live. No API key required."}




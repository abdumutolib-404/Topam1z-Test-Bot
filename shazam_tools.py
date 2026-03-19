import asyncio
import logging
import os
import sys
import types
import urllib.parse

# Python 3.13 removed audioop from stdlib. pydub imports it at module level,
# and shazamio imports pydub. We don't actually USE pydub's audio processing
# (recognition uses raw bytes directly), so a blank stub module is enough.
if sys.version_info >= (3, 13) and "audioop" not in sys.modules:
    sys.modules["audioop"] = types.ModuleType("audioop")

import aiohttp
import yt_dlp
from shazamio import Shazam as ShazamIO

from config import SHAZAM_KEY, COOKIES
from shared import _executor
from utils import yt_url

log = logging.getLogger("bot.shazam")

def _parse_shazam(raw: dict) -> dict | None:
    track = raw.get("track") or {}
    if not track: return None
    sections = track.get("sections") or []
    meta     = next((s for s in sections if s.get("type") == "SONG"), {})
    mdata    = meta.get("metadata") or []
    album    = next((m["text"] for m in mdata if "album"    in (m.get("title","")).lower()), None)
    released = next((m["text"] for m in mdata if "released" in (m.get("title","")).lower()), None)
    sp = None
    for opt in ((track.get("hub") or {}).get("options") or []):
        for action in (opt.get("actions") or []):
            if "spotify" in (action.get("uri") or ""):
                sp = action["uri"]; break
    title  = track.get("title")
    artist = track.get("subtitle")
    return {"title":title,"artist":artist,"album":album,"released":released,
            "spotify_url":sp,"youtube_url":yt_url(title,artist)}

async def _shazamio_recognize(path: str) -> dict | None:
    try:
        with open(path,"rb") as f: data = f.read()
        raw = await ShazamIO().recognize(data)
        if not raw or not isinstance(raw, dict): return None
        return _parse_shazam(raw)
    except Exception as e:
        log.warning(f"ShazamIO recognize: {e}")
    return None

def _ytdlp_search(query: str, limit: int = 10) -> list:
    """Search YouTube Music via yt-dlp. Reliable, no API key, no rate limits."""
    opts = {
        "quiet": True, "no_warnings": True, "noprogress": True,
        "extract_flat": True, "skip_download": True,
        "default_search": f"ytsearch{limit}",
    }
    if COOKIES and os.path.exists(COOKIES):
        opts["cookiefile"] = COOKIES
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(f"ytsearch{limit}:{query}", download=False)
        entries = info.get("entries") or []
        results = []
        for e in entries[:limit]:
            if not e: continue
            title    = e.get("title") or ""
            uploader = e.get("uploader") or e.get("channel") or ""
            dur_s    = e.get("duration") or 0
            url      = e.get("url") or e.get("webpage_url") or ""
            if not title or not url: continue
            dur_str = f"{int(dur_s)//60}:{int(dur_s)%60:02d}" if dur_s else "?"
            results.append({
                "title":       title,
                "artist":      uploader,
                "duration":    dur_str,
                "youtube_url": url,
                "spotify_url": None,
                "album": None, "released": None,
            })
        return results
    except Exception as e:
        log.warning(f"yt-dlp search: {e}")
        return []

async def _shazamio_search(query: str, limit: int = 10) -> list:
    """Search via yt-dlp YouTube Music (primary) with ShazamIO as fallback."""
    # Primary: yt-dlp — always reliable
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(_executor, _ytdlp_search, query, limit)
    if results:
        return results
    # Fallback: try ShazamIO recognize with different approach
    try:
        raw = await ShazamIO().search_track(query=query, limit=limit)
        if not raw or not isinstance(raw, dict): return []
        hits = []
        for key in ("tracks", "hits", "results"):
            val = raw.get(key)
            if isinstance(val, dict): hits = val.get("hits") or []; break
            if isinstance(val, list): hits = val; break
        for item in hits[:limit]:
            if not isinstance(item, dict): continue
            track  = item.get("track") or item
            title  = track.get("title") or track.get("name") if isinstance(track, dict) else None
            artist = track.get("subtitle") or track.get("artist") if isinstance(track, dict) else None
            if title:
                results.append({
                    "title": str(title), "artist": str(artist or "Unknown"),
                    "duration": "?", "youtube_url": yt_url(title, artist),
                    "spotify_url": None, "album": None, "released": None,
                })
    except Exception as e:
        log.debug(f"ShazamIO search fallback: {e}")
    return results

async def _rapidapi_recognize(path: str) -> dict | None:
    if not SHAZAM_KEY: return None
    try:
        import base64
        with open(path,"rb") as f: b64 = base64.b64encode(f.read()).decode()
        hdrs = {"content-type":"text/plain",
                "X-RapidAPI-Key":SHAZAM_KEY,"X-RapidAPI-Host":"shazam.p.rapidapi.com"}
        async with aiohttp.ClientSession() as s:
            async with s.post("https://shazam.p.rapidapi.com/songs/v2/detect",
                              data=b64, headers=hdrs,
                              timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status != 200: return None
                d = await r.json(content_type=None)
        if not d or not isinstance(d, dict): return None
        t = d.get("track") or {}
        if t and t.get("title"):
            return {"title":t.get("title"),"artist":t.get("subtitle"),
                    "album":None,"released":None,"spotify_url":None,
                    "youtube_url":yt_url(t.get("title"),t.get("subtitle"))}
    except Exception as e:
        log.warning(f"RapidAPI recognize: {e}")
    return None

async def _rapidapi_search(query: str, limit: int = 5) -> list:
    if not SHAZAM_KEY: return []
    try:
        hdrs = {"X-RapidAPI-Key":SHAZAM_KEY,"X-RapidAPI-Host":"shazam.p.rapidapi.com"}
        async with aiohttp.ClientSession() as s:
            async with s.get("https://shazam.p.rapidapi.com/search",
                             params={"term":query,"locale":"en-US","limit":str(limit)},
                             headers=hdrs, allow_redirects=True,
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status not in (200, 201):
                    log.warning(f"RapidAPI search HTTP {r.status}")
                    return []
                d = await r.json(content_type=None)
        if not d or not isinstance(d, dict):
            return []
        hits = (d.get("tracks") or {}).get("hits") or []
        results = []
        for item in hits[:limit]:
            if not isinstance(item, dict): continue
            t = item.get("track") or {}
            title  = t.get("title") or t.get("heading", {}).get("title") if isinstance(t, dict) else None
            artist = t.get("subtitle") or t.get("heading", {}).get("subtitle") if isinstance(t, dict) else None
            if title:
                results.append({
                    "title": title, "artist": artist or "Unknown",
                    "album": None, "released": None, "spotify_url": None,
                    "youtube_url": yt_url(title, artist),
                })
        return results
    except Exception as e:
        log.warning(f"RapidAPI search: {e}")
    return []

async def recognize(path: str)      -> dict | None:
    return await _shazamio_recognize(path) or await _rapidapi_recognize(path)
async def search_song(query: str, limit: int = 10) -> list:
    r = await _shazamio_search(query, limit)
    if not r: r = await _rapidapi_search(query, limit)
    return r

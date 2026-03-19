import re
import os
import time
import uuid
import urllib.parse
from telegram.constants import ParseMode

HTML = ParseMode.HTML

def h(text) -> str:
    return str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# ── Platform detection ────────────────────────────────────────────────────
def is_ig(url: str) -> bool:
    return bool(re.search(r"instagram\.com/(p|reel|tv|stories)/", url, re.I))

def is_yt(url: str) -> bool:
    return bool(re.search(r"(youtube\.com/(watch|shorts)|youtu\.be/)", url, re.I))

def is_tiktok(url: str) -> bool:
    return bool(re.search(r"tiktok\.com/", url, re.I))

def is_twitter(url: str) -> bool:
    return bool(re.search(r"(twitter\.com|x\.com)/\w+/status/", url, re.I))

def is_facebook(url: str) -> bool:
    return bool(re.search(r"facebook\.com/(watch|reel|videos|share/r)/", url, re.I))

def is_pinterest(url: str) -> bool:
    return bool(re.search(r"pinterest\.(com|co\.[a-z]+)/pin/", url, re.I))

def detect_platform(url: str) -> tuple[str, str]:
    """Returns (platform_name, emoji)."""
    if is_ig(url):       return "Instagram",  "📸"
    if is_yt(url):       return "YouTube",    "▶️"
    if is_tiktok(url):   return "TikTok",     "🎵"
    if is_twitter(url):  return "Twitter/X",  "🐦"
    if is_facebook(url): return "Facebook",   "📘"
    if is_pinterest(url):return "Pinterest",  "📌"
    return "Unknown",    "🔗"

def is_supported_url(url: str) -> bool:
    name, _ = detect_platform(url)
    return name != "Unknown"

def is_url(text: str) -> bool:
    return bool(re.match(r"https?://\S+", text.strip()))

def fmt_dur(s) -> str:
    if not s: return "?"
    s = int(s); hh, r = divmod(s, 3600); mm, ss = divmod(r, 60)
    return f"{hh}h {mm:02d}m {ss:02d}s" if hh else f"{mm}m {ss:02d}s"

def fmt_sz(b) -> str:
    b = int(b or 0)
    for u in ("B","KB","MB","GB"):
        if b < 1024: return f"{b:.1f} {u}"
        b //= 1024
    return f"{b:.1f} TB"

def fmt_views(v) -> str:
    if not v: return "N/A"
    v = int(v)
    if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if v >= 1_000:     return f"{v/1_000:.1f}K"
    return str(v)

def yt_url(title, artist=None) -> str | None:
    if not title: return None
    q = f"{artist or ''} {title}".strip()
    return "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q)

def clean(*paths):
    """Safely remove temporary files. Only removes files in TMPDIR to prevent path traversal."""
    from config import TMPDIR
    tmpdir_abs = os.path.abspath(TMPDIR)
    for p in paths:
        if not p:
            continue
        try:
            # SECURITY: Prevent path traversal - only delete files in TMPDIR
            p_abs = os.path.abspath(p)
            if not p_abs.startswith(tmpdir_abs):
                continue
            if os.path.exists(p_abs) and os.path.isfile(p_abs):
                os.remove(p_abs)
        except (OSError, ValueError):
            pass

_rate:        dict[int, float] = {}
def rate_check(uid: int, RATE_SEC: int = 5) -> float | None:
    if RATE_SEC <= 0: return None
    now  = time.time()
    wait = RATE_SEC - (now - _rate.get(uid, 0))
    if wait > 0: return round(wait, 1)
    _rate[uid] = now
    return None

_SAFE_EXTS = {".mp3",".m4a",".ogg",".mp4",".webm",".mov",".mkv",".avi"}

def tg_ext(obj) -> str:
    """SEC-8: only return whitelisted extensions to prevent path issues."""
    from telegram import Voice
    if isinstance(obj, Voice): return ".ogg"
    path = getattr(obj, "file_path", "") or ""
    if "." in path:
        ext = "." + path.rsplit(".",1)[-1].lower()
        if ext in _SAFE_EXTS: return ext
    return {
        "audio/mpeg":".mp3","audio/mp4":".m4a","audio/ogg":".ogg",
        "audio/opus":".ogg","video/mp4":".mp4","video/webm":".webm",
        "video/quicktime":".mov","video/x-matroska":".mkv",
    }.get(getattr(obj,"mime_type","") or "", ".mp4")

def parse_time(s: str) -> int | None:
    """Parse '1:23' or '83' or '1:23:45' → seconds. Return None if invalid."""
    s = s.strip()
    try:
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 2:   return int(parts[0])*60 + int(parts[1])
            if len(parts) == 3:   return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        return int(s)
    except Exception:
        return None

_CB: dict[str, str] = {}
_CBP = "~"

def cb_put(value: str) -> str:
    if len(value.encode()) <= 55:
        return f"{_CBP}{value}"
    key = uuid.uuid4().hex[:8]
    _CB[key] = value
  
    if len(_CB) > 1000:
        oldest = list(_CB.keys())[:len(_CB)-1000]
        for k in oldest: _CB.pop(k, None)
    return key

def cb_get(token: str) -> str | None:
    if token.startswith(_CBP): return token[len(_CBP):]
    return _CB.get(token)

async def sedit(msg, text: str, **kw):
    try:    await msg.edit_text(text, parse_mode=HTML, **kw)
    except Exception as e: pass

async def sdel(msg):
    try:    await msg.delete()
    except Exception as e: pass



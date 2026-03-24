import os
import uuid
import urllib.parse
import yt_dlp
from config import TMPDIR, COOKIES, COOKIES_YT, COOKIES_IG

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

def _clean_url(url: str) -> str:
    """Strip only tracking parameters that are known to cause issues."""
    try:
        p = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(p.query, keep_blank_values=True)
        # We no longer aggressively strip params like 'igsh' or 'si' as modern platforms 
        # often use them for routing, which broke downloads previously.
        _STRIP = {"utm_source", "utm_medium", "utm_campaign", "fbclid", "ref", "referer"}
        qs_clean = {k: v for k, v in qs.items() if k not in _STRIP}
        clean_query = urllib.parse.urlencode(qs_clean, doseq=True)
        return urllib.parse.urlunparse(p._replace(query=clean_query))
    except Exception:
        return url

def _ydl_opts(out: str, extra: dict = None) -> dict:
    """Base yt-dlp options — no client restrictions, cookies-first approach."""
    o = {
        "outtmpl": out,
        "quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
        "socket_timeout": 60,
        "retries": 5,
        "fragment_retries": 5,
        "http_headers": {
            "User-Agent": _UA,
            "Accept-Language": "en-US,en;q=0.9",
        },
        # Skip format availability pre-check — attempt download regardless
        "check_formats": False,
        "extractor_retries": 3,
    }
    if extra:
        o.update(extra)
    return o

def _cookie_for_url(url: str) -> str:
    """Pick the best cookie file for a URL, if available."""
    if ("youtube" in url or "youtu.be" in url) and COOKIES_YT and os.path.exists(COOKIES_YT):
        return COOKIES_YT
    if "instagram" in url and COOKIES_IG and os.path.exists(COOKIES_IG):
        return COOKIES_IG
    return COOKIES

def _dl_info(url: str) -> dict:
    url = _clean_url(url)
    _ck = _cookie_for_url(url)
    opts = {
        "quiet": True, "no_warnings": True, "noprogress": True,
        "noplaylist": True, "socket_timeout": 20,
    }
    if _ck and os.path.exists(_ck):
        opts["cookiefile"] = _ck
    with yt_dlp.YoutubeDL(opts) as y:
        return y.extract_info(url, download=False)

def _find_file(uid: str) -> str | None:
    for f in sorted(os.listdir(TMPDIR)):
        if f.startswith(uid):
            p = os.path.join(TMPDIR, f)
            if os.path.getsize(p) > 0: return p
    return None

def _dl_video(url: str, quality: int) -> tuple[str, dict]:
    """Download video natively targeting the requested resolution to fix format bugs."""
    url = _clean_url(url)
    uid = uuid.uuid4().hex
    got = {"path": None}
    
    def hook(d):
        if d["status"] == "finished":
            got["path"] = d.get("filename")

    _cookie = _cookie_for_url(url)
    
    # Use yt-dlp's native format_sort to reliably pick the best stream up to 'quality'.
    # This replaces the error-prone manual parsing of info['formats'] and avoids double API requests.
    _extra = {
        "format": "bestvideo+bestaudio/best",
        "format_sort": [f"res:{quality}", "ext:mp4:m4a", "vcodec:h264"],
        "merge_output_format": "mp4",
        "progress_hooks": [hook],
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
    }
    
    if _cookie and os.path.exists(_cookie):
        _extra["cookiefile"] = _cookie
        
    opts = _ydl_opts(os.path.join(TMPDIR, f"{uid}.%(ext)s"), _extra)
    
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
        
    path = got["path"]
    if path and os.path.exists(path): 
        return path, info
        
    # Absolute fallback if hook missed the final merged file
    found = _find_file(uid)
    if found: 
        return found, info
        
    raise FileNotFoundError("Video file missing after download.")

def _dl_audio(url: str) -> tuple[str, dict]:
    url = _clean_url(url)
    uid = uuid.uuid4().hex
    got = {"path": None}

    def hook(d):
        if d["status"] == "finished":
            got["path"] = d.get("filename")

    _cookie = _cookie_for_url(url)
    
    # Target pure audio extraction
    _extra = {
        "format": "bestaudio/best",
        "progress_hooks": [hook],
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3", 
            "preferredquality": "192"
        }],
    }
    
    if _cookie and os.path.exists(_cookie):
        _extra["cookiefile"] = _cookie
        
    opts = _ydl_opts(os.path.join(TMPDIR, f"{uid}.%(ext)s"), _extra)
    
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
        
    path = got["path"]
    if path and os.path.exists(path):
        return path, info
        
    # Check if a .mp3 was natively created by the postprocessor
    mp3 = os.path.join(TMPDIR, f"{uid}.mp3")
    if os.path.exists(mp3): 
        return mp3, info
        
    found = _find_file(uid)
    if found: 
        return found, info
        
    raise FileNotFoundError("Audio file missing after download.")

def _dl_sample(url: str) -> str:
    uid = uuid.uuid4().hex
    url = _clean_url(url)
    _cookie = _cookie_for_url(url)
    
    def attempt(start: int, end: int) -> str | None:
        pfx = f"smp_{uid}_{start}"
        opts = _ydl_opts(os.path.join(TMPDIR, f"{pfx}.%(ext)s"), {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128"
            }],
        })
        if _cookie and os.path.exists(_cookie):
            opts["cookiefile"] = _cookie
            
        try:
            opts["download_ranges"] = yt_dlp.utils.download_range_func([], [[start, end]])
            opts["force_keyframes_at_cuts"] = False
        except AttributeError: 
            pass
            
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                y.extract_info(url, download=True)
        except Exception: 
            return None
            
        mp3 = os.path.join(TMPDIR, f"{pfx}.mp3")
        if os.path.exists(mp3) and os.path.getsize(mp3) > 1024: 
            return mp3
            
        for f in os.listdir(TMPDIR):
            if f.startswith(pfx):
                p = os.path.join(TMPDIR, f)
                if os.path.getsize(p) > 1024: 
                    return p
        return None
        
    result = attempt(30, 45) or attempt(0, 30)
    if result: 
        return result
        
    raise RuntimeError("Could not download audio sample.")

def _dl_profile(username: str, count: int) -> list[str]:
    """Download latest N posts from an Instagram profile."""
    username = username.lstrip("@")
    uid = uuid.uuid4().hex
    opts = _ydl_opts(os.path.join(TMPDIR, f"{uid}_%(autonumber)s.%(ext)s"), {
        "playlistend": count,
        "noplaylist": False,
        "merge_output_format": "mp4",
        "format": "bestvideo+bestaudio/best",
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
    })
    
    url = f"https://www.instagram.com/{username}/"
    if COOKIES_IG and os.path.exists(COOKIES_IG):
        opts["cookiefile"] = COOKIES_IG
        
    with yt_dlp.YoutubeDL(opts) as y:
        y.extract_info(url, download=True)
        
    files = []
    for f in sorted(os.listdir(TMPDIR)):
        if f.startswith(uid):
            p = os.path.join(TMPDIR, f)
            if os.path.getsize(p) > 0: 
                files.append(p)
                
    return files[:count]

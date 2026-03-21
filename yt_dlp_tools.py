import os
import re
import uuid
import urllib.parse
import yt_dlp
from config import TMPDIR, COOKIES

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

def _clean_url(url: str) -> str:
    """Strip tracking/session parameters that confuse yt-dlp extractors.

    Instagram:  ?igsh=... ?img_index=...  → stripped (cause "No video formats found")
    YouTube:    ?si=...                   → stripped (tracking only)
    TikTok:     ?_r=... ?checksum=...    → stripped
    Keep:       YouTube ?v=, ?list= etc  → kept (functional params)
    """
    try:
        p = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(p.query, keep_blank_values=True)
        # Params to always strip (tracking/session — never needed by extractor)
        _STRIP = {"igsh", "img_index", "si", "_r", "checksum",
                  "utm_source", "utm_medium", "utm_campaign",
                  "fbclid", "ref", "referer"}
        qs_clean = {k: v for k, v in qs.items() if k not in _STRIP}
        clean_query = urllib.parse.urlencode(qs_clean, doseq=True)
        return urllib.parse.urlunparse(p._replace(query=clean_query))
    except Exception:
        return url  # if anything fails, use original

def _ydl_opts(out: str, extra: dict = None) -> dict:
    """Base yt-dlp options.

    YouTube bot bypass strategy (2026):
    - ios client is the most reliable on server/datacenter IPs
    - Does NOT require cookies for most videos
    - web_creator as secondary, mweb as tertiary
    - Cookies passed when available for age-restricted content
    """
    o = {
        "outtmpl": out,
        "quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
        "socket_timeout": 60,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "http_headers": {
            "User-Agent": _UA,
            "Accept-Language": "en-US,en;q=0.9",
        },
        "extractor_args": {
            "youtube": {
                # ios is the most reliable client on server IPs in 2026
                # It uses a different API endpoint that doesn't flag datacenter IPs
                "player_client": ["ios", "web_creator", "mweb"],
                "skip": ["translated_subs"],
            },
        },
    }
    if COOKIES and os.path.exists(COOKIES):
        o["cookiefile"] = COOKIES
    if extra:
        o.update(extra)
    return o

def _dl_info(url: str) -> dict:
    url  = _clean_url(url)
    opts = {
        "quiet": True, "no_warnings": True, "noprogress": True,
        "noplaylist": True, "socket_timeout": 20,
    }
    if COOKIES and os.path.exists(COOKIES):
        opts["cookiefile"] = COOKIES
    with yt_dlp.YoutubeDL(opts) as y:
        return y.extract_info(url, download=False)

def _find_file(uid: str) -> str | None:
    for f in sorted(os.listdir(TMPDIR)):
        if f.startswith(uid):
            p = os.path.join(TMPDIR, f)
            if os.path.getsize(p) > 0: return p
    return None

def _dl_video(url: str, quality: int) -> tuple[str, dict]:
    """Download video at requested quality with aggressive fallback chain.

    Format priority (yt-dlp picks first one that works):
    1. Split streams: best video ≤ quality + best audio  (highest quality)
    2. Split streams: any video ≤ quality + best audio
    3. Single combined stream ≤ quality
    4. Single combined stream any quality (ignores height, just get something)
    5. Absolute fallback: whatever yt-dlp thinks is best

    This handles: age-restricted, members-only, shorts, TikTok, IG, etc.
    """
    url = _clean_url(url)
    uid = uuid.uuid4().hex
    got = {"path": None}
    def hook(d):
        if d["status"] == "finished": got["path"] = d["filename"]

    # No format filtering — server IPs get restricted streams;
    # let yt-dlp pick the best available format automatically.
    # Quality param is used as a hint via --format-sort only.
    fmt = "best"
    opts = _ydl_opts(os.path.join(TMPDIR, f"{uid}.%(ext)s"), {
        "format": fmt,
        "format_sort": [f"res:{quality}", "ext:mp4:m4a", "codec:h264:aac"],
        "merge_output_format": "mp4",
        "progress_hooks": [hook],
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
    })
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
    path = got["path"]
    if path and os.path.exists(path): return path, info
    found = _find_file(uid)
    if found: return found, info
    raise FileNotFoundError("Video file missing after download.")

def _dl_audio(url: str) -> tuple[str, dict]:
    url  = _clean_url(url)
    uid  = uuid.uuid4().hex
    # Broad fallback chain: try every common audio format before giving up
    fmt = (
        "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio[ext=opus]/"
        "bestaudio[ext=mp3]/bestaudio/best[ext=mp4]/best"
    )
    opts = _ydl_opts(os.path.join(TMPDIR, f"{uid}.%(ext)s"), {
        "format": fmt,
        "postprocessors": [{"key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3", "preferredquality": "192"}],
    })
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
    mp3 = os.path.join(TMPDIR, f"{uid}.mp3")
    if os.path.exists(mp3): return mp3, info
    found = _find_file(uid)
    if found: return found, info
    raise FileNotFoundError("Audio file missing after download.")

def _dl_sample(url: str) -> str:
    uid = uuid.uuid4().hex
    def attempt(start: int, end: int) -> str | None:
        pfx  = f"smp_{uid}_{start}"
        opts = _ydl_opts(os.path.join(TMPDIR, f"{pfx}.%(ext)s"), {
            "format": "bestaudio/best",
            "postprocessors": [{"key":"FFmpegExtractAudio",
                                "preferredcodec":"mp3","preferredquality":"128"}],
        })
        try:
            opts["download_ranges"] = yt_dlp.utils.download_range_func([],[[start,end]])
            opts["force_keyframes_at_cuts"] = False
        except AttributeError: pass
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                y.extract_info(url, download=True)
        except Exception: return None
        mp3 = os.path.join(TMPDIR, f"{pfx}.mp3")
        if os.path.exists(mp3) and os.path.getsize(mp3) > 1024: return mp3
        for f in os.listdir(TMPDIR):
            if f.startswith(pfx):
                p = os.path.join(TMPDIR, f)
                if os.path.getsize(p) > 1024: return p
        return None
    url    = _clean_url(url)
    result = attempt(30, 45) or attempt(0, 30)
    if result: return result
    raise RuntimeError("Could not download audio sample.")

def _dl_profile(username: str, count: int) -> list[str]:
    """Download latest N posts from an Instagram profile."""
    username = username.lstrip("@")
    uid  = uuid.uuid4().hex
    opts = _ydl_opts(os.path.join(TMPDIR, f"{uid}_%(autonumber)s.%(ext)s"), {
        "playlistend": count,
        "noplaylist":  False,
        "merge_output_format": "mp4",
        "format": "bestvideo+bestaudio/best",
        "postprocessors": [{"key":"FFmpegVideoConvertor","preferedformat":"mp4"}],
    })
    url = f"https://www.instagram.com/{username}/"
    with yt_dlp.YoutubeDL(opts) as y:
        y.extract_info(url, download=True)
    files = []
    for f in sorted(os.listdir(TMPDIR)):
        if f.startswith(uid):
            p = os.path.join(TMPDIR, f)
            if os.path.getsize(p) > 0: files.append(p)
    return files[:count]

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

def _find_file(uid: str) -> str | None:
    """Find downloaded file by UID prefix - improved version."""
    candidates = []
    for f in os.listdir(TMPDIR):
        if f.startswith(uid):
            p = os.path.join(TMPDIR, f)
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                candidates.append((p, os.path.getsize(p)))
    
    # Return largest file if multiple found (merged file is usually larger)
    if candidates:
        return max(candidates, key=lambda x: x[1])[0]
    return None

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

def _dl_video(url: str, quality: int) -> tuple[str, dict]:
    """Download video with robust path detection and proper format selection."""
    url = _clean_url(url)
    uid = uuid.uuid4().hex
    output_template = os.path.join(TMPDIR, f"{uid}.%(ext)s")
    
    _cookie = _cookie_for_url(url)
    
    # Build format string based on quality - simpler and more reliable
    if quality >= 2160:
        format_str = "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"
    elif quality >= 1440:
        format_str = "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best"
    elif quality >= 1080:
        format_str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
    elif quality >= 720:
        format_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    elif quality >= 480:
        format_str = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
    else:
        format_str = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
    
    _extra = {
        "format": format_str,
        "merge_output_format": "mp4",
    }
    
    if _cookie and os.path.exists(_cookie):
        _extra["cookiefile"] = _cookie
        
    opts = _ydl_opts(output_template, _extra)
    
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
    
    # Multiple fallback strategies for finding the downloaded file
    # 1. Check for .mp4 file with our UID
    mp4_path = os.path.join(TMPDIR, f"{uid}.mp4")
    if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
        return mp4_path, info
    
    # 2. Check for any file starting with our UID
    found = _find_file(uid)
    if found:
        return found, info
    
    # 3. Check info dict for filepath
    if info and info.get("requested_downloads"):
        for dl in info["requested_downloads"]:
            fp = dl.get("filepath")
            if fp and os.path.exists(fp) and os.path.getsize(fp) > 0:
                return fp, info
    
    # 4. Last resort: look for newest file in TMPDIR
    files = [(os.path.join(TMPDIR, f), os.path.getmtime(os.path.join(TMPDIR, f))) 
             for f in os.listdir(TMPDIR) 
             if f.endswith(('.mp4', '.webm', '.mkv')) and os.path.getsize(os.path.join(TMPDIR, f)) > 1024]
    if files:
        newest = max(files, key=lambda x: x[1])[0]
        return newest, info
        
    raise FileNotFoundError("Video file missing after download.")

def _dl_audio(url: str) -> tuple[str, dict]:
    """Download audio with robust path detection."""
    url = _clean_url(url)
    uid = uuid.uuid4().hex
    output_template = os.path.join(TMPDIR, f"{uid}.%(ext)s")

    _cookie = _cookie_for_url(url)
    
    _extra = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3", 
            "preferredquality": "192"
        }],
    }
    
    if _cookie and os.path.exists(_cookie):
        _extra["cookiefile"] = _cookie
        
    opts = _ydl_opts(output_template, _extra)
    
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
    
    # Multiple fallback strategies
    # 1. Check for .mp3 with exact UID
    mp3_path = os.path.join(TMPDIR, f"{uid}.mp3")
    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
        return mp3_path, info
    
    # 2. Check for any file starting with UID
    found = _find_file(uid)
    if found:
        return found, info
    
    # 3. Check info dict
    if info and info.get("requested_downloads"):
        for dl in info["requested_downloads"]:
            fp = dl.get("filepath")
            if fp and os.path.exists(fp) and os.path.getsize(fp) > 0:
                return fp, info
    
    # 4. Look for newest .mp3 in TMPDIR
    files = [(os.path.join(TMPDIR, f), os.path.getmtime(os.path.join(TMPDIR, f))) 
             for f in os.listdir(TMPDIR) 
             if f.endswith('.mp3') and os.path.getsize(os.path.join(TMPDIR, f)) > 1024]
    if files:
        newest = max(files, key=lambda x: x[1])[0]
        return newest, info
        
    raise FileNotFoundError("Audio file missing after download.")

def _dl_sample(url: str) -> str:
    """Download 15-second audio sample with multiple fallback attempts."""
    uid = uuid.uuid4().hex
    url = _clean_url(url)
    _cookie = _cookie_for_url(url)
    
    def attempt(start: int, end: int) -> str | None:
        """Try to download a specific time range."""
        pfx = f"smp_{uid}_{start}"
        output_template = os.path.join(TMPDIR, f"{pfx}.%(ext)s")
        
        opts = _ydl_opts(output_template, {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128"
            }],
        })
        
        if _cookie and os.path.exists(_cookie):
            opts["cookiefile"] = _cookie
        
        # Try to use download_ranges if available (newer yt-dlp versions)
        try:
            opts["download_ranges"] = yt_dlp.utils.download_range_func([], [[start, end]])
            opts["force_keyframes_at_cuts"] = False
        except (AttributeError, Exception):
            # Older yt-dlp or not supported - just download full and trim later
            pass
            
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                y.extract_info(url, download=True)
        except Exception:
            return None
        
        # Check for downloaded file
        mp3 = os.path.join(TMPDIR, f"{pfx}.mp3")
        if os.path.exists(mp3) and os.path.getsize(mp3) > 1024:
            return mp3
            
        # Check for any file with this prefix
        for f in os.listdir(TMPDIR):
            if f.startswith(pfx):
                p = os.path.join(TMPDIR, f)
                if os.path.getsize(p) > 1024:
                    return p
        return None
    
    # Try multiple time ranges - increase chances of success
    for start, end in [(30, 45), (0, 15), (60, 75), (15, 30)]:
        result = attempt(start, end)
        if result:
            return result
    
    # If ranges don't work, download full audio and extract sample with ffmpeg
    try:
        full_audio, _ = _dl_audio(url)
        if full_audio and os.path.exists(full_audio):
            # Use ffmpeg to extract 15 seconds from middle
            import subprocess
            sample_path = os.path.join(TMPDIR, f"sample_{uid}.mp3")
            subprocess.run([
                "ffmpeg", "-y", "-i", full_audio,
                "-ss", "30", "-t", "15",
                "-c", "copy", sample_path
            ], capture_output=True, timeout=30)
            
            if os.path.exists(sample_path) and os.path.getsize(sample_path) > 1024:
                # Clean up full audio
                try:
                    os.remove(full_audio)
                except:
                    pass
                return sample_path
    except Exception:
        pass
        
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

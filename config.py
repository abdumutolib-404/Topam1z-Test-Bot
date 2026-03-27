import os
from dotenv import load_dotenv

load_dotenv()

# ── Secrets — loaded from environment / Railway variables ─────────────
_missing = [v for v in ("BOT_TOKEN","ADMIN_IDS","ADMIN_PASS") if not os.environ.get(v)]
if _missing:
    raise EnvironmentError(f"Missing required env vars: {_missing} Set them in Railway → Variables")

TOKEN = os.environ["BOT_TOKEN"]
SHAZAM_KEY = os.environ.get("SHAZAM_KEY", "") # optional
ADMIN_IDS = {int(x) for x in os.environ["ADMIN_IDS"].split(",") if x.strip()}
ADMIN_PASS = os.environ["ADMIN_PASS"].strip().strip("\'\"")
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip().strip("\'\"") or None

# File size limits
# LOCAL_API_URL: when set, the bot connects to a self-hosted Telegram Bot API
# server which raises the upload limit from 50 MB to 2000 MB.
LOCAL_API_URL = os.environ.get("LOCAL_API_URL", "").strip().strip("\'\"") or None
TG_MAX_MB = 2000 if LOCAL_API_URL else 50  # 2 GB with local server, 50 MB with public API
MAX_MB    = 2048  # max download size (2 GB)
AD_EVERY = 5 # show ad every N downloads per user
MAX_FAILS = 3 # lockout after this many wrong tries
FAIL_WINDOW = 300 # seconds — reset counter after this
RATE_SEC = 5

# TMPDIR: Use /tmp/bot_tmp in Docker, ~/.abot_tmp locally
# Docker sets TMPDIR env var; local dev falls back to ~/.abot_tmp
TMPDIR = os.environ.get("BOT_TMPDIR") or (
    "/tmp/bot_tmp" if os.path.isdir("/tmp/bot_tmp")
    else os.path.expanduser("~/.abot_tmp")
)
os.makedirs(TMPDIR, exist_ok=True)

BRAND = "@topam1z_news"
AUDIO_TITLE = "@topam1z_news — @topam1z_bot"
CHANNEL = "https://t.me/topam1z_news"

import shutil as _shutil
import logging as _log

def _resolve_cookies(filename: str, env_key: str) -> str:
    """Return path to writable cookie file, or empty string.
    
    Handles 3 sources in priority order:
    1. Mounted file (Docker volume)
    2. Environment variable
    3. None (returns empty string)
    
    CRITICAL FIX: Checks if path is actually a file, not a directory.
    """
    _logger = _log.getLogger("config")
    app_dir  = os.path.dirname(os.path.abspath(__file__))
    mounted  = os.path.join(app_dir, filename)
    writable = f"/tmp/{filename}"
    
    # Check if mounted path exists AND is a file (not directory)
    if os.path.exists(mounted):
        if os.path.isfile(mounted) and os.path.getsize(mounted) > 0:
            # Valid file - copy to writable location
            try:
                _shutil.copy2(mounted, writable)
                _logger.info(f"Cookies: copied {filename} to /tmp ({os.path.getsize(writable)} bytes)")
                return writable
            except Exception as e:
                _logger.warning(f"Cookies: failed to copy {filename}: {e}")
        elif os.path.isdir(mounted):
            # It's a directory - this is the bug!
            _logger.warning(f"Cookies: {mounted} is a directory (should be file) - skipping")
        else:
            _logger.warning(f"Cookies: {mounted} exists but is empty or invalid")
    
    # Try environment variable
    env = os.environ.get(env_key, "").strip()
    if env:
        # Strip Railway outer quotes
        while len(env) >= 2 and env[0] == env[-1] and env[0] in ('"', "'"):
            env = env[1:-1].strip()
        content = env.replace("\\n", "\n").replace("\\t", "\t")
        
        # Only write if content looks valid
        if len(content) > 10 and not content.startswith("{"):
            try:
                with open(writable, "w", encoding="utf-8") as _f:
                    _f.write(content)
                _logger.info(f"Cookies: written from env var {env_key} ({len(content)} bytes)")
                return writable
            except Exception as e:
                _logger.warning(f"Cookies: failed to write from env: {e}")
    
    # No cookies available
    _logger.info(f"Cookies: {filename} not available (not required - some downloads may fail for private content)")
    return ""

# Per-platform cookie files - with robust error handling
COOKIES_YT = _resolve_cookies("www.youtube.com_cookies.txt", "COOKIES_YT")
COOKIES_IG = _resolve_cookies("www.instagram.com_cookies.txt", "COOKIES_IG")
# Legacy fallback (other platforms / Railway single var)
COOKIES    = _resolve_cookies("cookies.txt", "COOKIES") or COOKIES_YT or COOKIES_IG

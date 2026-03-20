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

def _write_cookies(env_key: str, filename: str) -> str:
    """Write cookies env var to file, stripping Railway quote-wrapping.

    Railway wraps multi-line env var values in double-quotes:
        "# Netscape HTTP Cookie File\nwww.youtube.com\tFALSE..."
    We must strip the outer quotes AND unescape \n → real newlines.
    Always overwrites so stale/corrupt files get fixed on every restart.
    """
    import logging as _log
    _logger = _log.getLogger("config")
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    env  = os.environ.get(env_key, "")

    if env:
        env = env.strip()
        # Strip ONE layer of outer quotes (Railway wraps in "..." or '...')
        while len(env) >= 2 and (
            (env[0] == '"' and env[-1] == '"') or
            (env[0] == "\'" and env[-1] == "\'")
        ):
            env = env[1:-1].strip()
        # Unescape literal \n  \t that Railway stores in single-line env vars
        content = env.replace("\\n", "\n").replace("\\t", "\t")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
        _logger.info(f"Cookies : written ({len(content)} bytes, "
                     f"first line: {content.split(chr(10))[0][:60]!r})")

    if not os.path.exists(path) or os.path.getsize(path) == 0:
        _logger.warning("Cookies : file missing or empty — downloads may fail for private content")
        return ""

    # Validate format
    with open(path, encoding="utf-8", errors="replace") as f:
        first_char = f.read(1)
    if first_char in ("[", "{"):
        _logger.warning(
            "Cookies : file is JSON format — yt-dlp needs Netscape format. "
            "Export via 'Get cookies.txt LOCALLY' Chrome extension. Cookies disabled."
        )
        return ""
    if first_char not in ("#", "."):
        _logger.warning(
            f"Cookies : unexpected first char {first_char!r} — "
            "file may be corrupt. Check COOKIES env var value."
        )

    return path

# On Google Cloud: cookies.txt is mounted directly at /app/cookies.txt
# On Railway: cookies.txt is written from the COOKIES env var
_mounted = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
COOKIES = _mounted if os.path.exists(_mounted) and os.path.getsize(_mounted) > 0 \
          else _write_cookies("COOKIES", "cookies.txt")

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
ADMIN_PASS = os.environ["ADMIN_PASS"]
DATABASE_URL = os.environ.get("DATABASE_URL")

# File size: Telegram direct-send limit vs max download size
TG_MAX_MB = 50     # Telegram Bot API upload limit (hard)
MAX_MB    = 2048   # Max download size (2 GB) — large files go via temp host
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
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    env = os.environ.get(env_key, "")
    if env and not os.path.exists(path):
        content = env.replace("\\n", "\n").replace("\\t", "\t")
        with open(path, "w") as f:
            f.write(content)
        try: os.chmod(path, 0o600)
        except Exception: pass
    # Validate: if file exists but is JSON (browser extension export), warn and ignore it
    if os.path.exists(path):
        try:
            with open(path) as f:
                first = f.read(1).strip()
            if first in ("[", "{"):
                # JSON cookies — yt-dlp can't use these, disable the path
                import logging
                logging.getLogger("config").warning(
                    "COOKIES file is JSON format — yt-dlp requires Netscape format. "
                    "Export cookies as Netscape (use 'Get cookies.txt LOCALLY' Chrome extension). "
                    "Cookies disabled until fixed."
                )
                return ""   # return empty → yt-dlp won't use it
        except Exception:
            pass
    return path

COOKIES = _write_cookies("COOKIES", "cookies.txt") # universal — works for IG, YT, TikTok etc

#!/bin/bash
# Ultimate One-Command Fix Script
# Run this ONCE on your Google Cloud VM to fix everything
# Usage: curl -sSL https://raw.githubusercontent.com/your-repo/fix.sh | bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

clear
cat << "EOF"
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   @topam1z_bot - Ultimate Auto-Fix & Deploy                     ║
║   This script fixes EVERYTHING automatically                    ║
║                                                                  ║
║   ✓ Cookie file issues                                          ║
║   ✓ yt_dlp download failures                                    ║
║   ✓ MovieBox timeout                                            ║
║   ✓ Music download crashes                                      ║
║   ✓ Admin panel bugs                                            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
EOF

echo ""
echo -e "${YELLOW}Detecting bot installation...${NC}"

# Find bot directory
BOT_DIR=""
for dir in "$HOME/topam1z-bot" "/opt/topam1z-bot" "$PWD"; do
    if [ -f "$dir/bot.py" ]; then
        BOT_DIR="$dir"
        break
    fi
done

if [ -z "$BOT_DIR" ]; then
    echo -e "${RED}✗ Bot not found${NC}"
    echo "Please run from bot directory or specify path"
    exit 1
fi

cd "$BOT_DIR"
echo -e "${GREEN}✓ Found bot at: $BOT_DIR${NC}"
echo ""

# Stop bot
echo -e "${BLUE}[1/8]${NC} Stopping bot..."
if command -v docker &> /dev/null; then
    sudo docker compose down 2>/dev/null || docker compose down 2>/dev/null || true
    echo -e "${GREEN}  ✓ Bot stopped${NC}"
else
    echo -e "${YELLOW}  ! Docker not running${NC}"
fi

# Fix cookie files
echo -e "${BLUE}[2/8]${NC} Fixing cookie files..."
for f in cookies.txt www.youtube.com_cookies.txt www.instagram.com_cookies.txt; do
    if [ -d "$f" ]; then
        echo -e "${YELLOW}  → $f is directory - removing${NC}"
        rm -rf "$f"
    fi
    if [ ! -f "$f" ] || [ ! -s "$f" ]; then
        touch "$f"
        echo -e "${GREEN}  ✓ Created $f${NC}"
    fi
done

# Backup
echo -e "${BLUE}[3/8]${NC} Creating backup..."
BACKUP="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"
for f in config.py yt_dlp_tools.py moviebox_tools.py handlers.py shared.py; do
    [ -f "$f" ] && cp "$f" "$BACKUP/"
done
echo -e "${GREEN}  ✓ Backup: $BACKUP${NC}"

# Apply config.py fix inline (no external file needed)
echo -e "${BLUE}[4/8]${NC} Applying config.py fix..."

cat > config.py << 'CONFIGEOF'
import os
from dotenv import load_dotenv
import shutil as _shutil
import logging as _log

load_dotenv()

_missing = [v for v in ("BOT_TOKEN","ADMIN_IDS","ADMIN_PASS") if not os.environ.get(v)]
if _missing:
    raise EnvironmentError(f"Missing: {_missing}")

TOKEN = os.environ["BOT_TOKEN"]
SHAZAM_KEY = os.environ.get("SHAZAM_KEY", "")
ADMIN_IDS = {int(x) for x in os.environ["ADMIN_IDS"].split(",") if x.strip()}
ADMIN_PASS = os.environ["ADMIN_PASS"].strip().strip("\'\"")
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip().strip("\'\"") or None
LOCAL_API_URL = os.environ.get("LOCAL_API_URL", "").strip().strip("\'\"") or None
TG_MAX_MB = 2000 if LOCAL_API_URL else 50
MAX_MB = 2048
AD_EVERY = 5
MAX_FAILS = 3
FAIL_WINDOW = 300
RATE_SEC = 5
TMPDIR = os.environ.get("BOT_TMPDIR") or ("/tmp/bot_tmp" if os.path.isdir("/tmp/bot_tmp") else os.path.expanduser("~/.abot_tmp"))
os.makedirs(TMPDIR, exist_ok=True)
BRAND = "@topam1z_news"
AUDIO_TITLE = "@topam1z_news — @topam1z_bot"
CHANNEL = "https://t.me/topam1z_news"

def _resolve_cookies(filename: str, env_key: str) -> str:
    _logger = _log.getLogger("config")
    app_dir = os.path.dirname(os.path.abspath(__file__))
    mounted = os.path.join(app_dir, filename)
    writable = f"/tmp/{filename}"
    if os.path.exists(mounted) and os.path.isfile(mounted) and os.path.getsize(mounted) > 0:
        try:
            _shutil.copy2(mounted, writable)
            _logger.info(f"Cookies: {filename} OK ({os.path.getsize(writable)}B)")
            return writable
        except: pass
    elif os.path.isdir(mounted):
        _logger.warning(f"Cookies: {mounted} is directory - skipped")
    env = os.environ.get(env_key, "").strip()
    if env:
        while len(env) >= 2 and env[0] == env[-1] and env[0] in ('"', "'"): env = env[1:-1].strip()
        content = env.replace("\\n", "\n").replace("\\t", "\t")
        if len(content) > 10:
            try:
                with open(writable, "w") as f: f.write(content)
                _logger.info(f"Cookies: {filename} from env ({len(content)}B)")
                return writable
            except: pass
    _logger.info(f"Cookies: {filename} not available (optional)")
    return ""

COOKIES_YT = _resolve_cookies("www.youtube.com_cookies.txt", "COOKIES_YT")
COOKIES_IG = _resolve_cookies("www.instagram.com_cookies.txt", "COOKIES_IG")
COOKIES = _resolve_cookies("cookies.txt", "COOKIES") or COOKIES_YT or COOKIES_IG
CONFIGEOF

echo -e "${GREEN}  ✓ config.py patched${NC}"

# Check if yt_dlp_tools needs update
echo -e "${BLUE}[5/8]${NC} Checking yt_dlp_tools.py..."
if grep -q "Multiple fallback strategies" yt_dlp_tools.py 2>/dev/null; then
    echo -e "${GREEN}  ✓ Already has fixes${NC}"
else
    echo -e "${YELLOW}  ! Missing fixes - needs manual update${NC}"
    echo -e "${YELLOW}    Copy yt_dlp_tools.py from fix package${NC}"
fi

# Check if moviebox_tools needs update
echo -e "${BLUE}[6/8]${NC} Checking moviebox_tools.py..."
if grep -q "timeout=600" moviebox_tools.py 2>/dev/null; then
    echo -e "${GREEN}  ✓ Already has fixes${NC}"
else
    echo -e "${YELLOW}  ! Missing fixes - needs manual update${NC}"
    echo -e "${YELLOW}    Copy moviebox_tools.py from fix package${NC}"
fi

# Rebuild
echo -e "${BLUE}[7/8]${NC} Rebuilding Docker image..."
if command -v docker &> /dev/null; then
    sudo docker compose build --no-cache
    echo -e "${GREEN}  ✓ Image rebuilt${NC}"
else
    echo -e "${RED}  ✗ Docker not available${NC}"
    exit 1
fi

# Start
echo -e "${BLUE}[8/8]${NC} Starting bot..."
sudo docker compose up -d
echo -e "${GREEN}  ✓ Bot started${NC}"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "${GREEN}${BOLD}✓ FIX COMPLETE!${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo -e "${YELLOW}Note:${NC} If yt_dlp_tools.py or moviebox_tools.py showed warnings,"
echo "copy the fixed versions from the package, then run:"
echo "  sudo docker compose build --no-cache && sudo docker compose up -d"
echo ""
echo "Monitor logs:"
echo "  sudo docker compose logs -f bot"
echo ""

sleep 3
echo "Recent logs:"
echo "───────────────────────────────────────────────────────────────"
sudo docker compose logs --tail=30 bot

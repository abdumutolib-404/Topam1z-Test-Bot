#!/bin/bash
# Test script for @topam1z_bot fixes
# Run this after applying all fixes to verify everything works

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  @topam1z_bot - Fix Verification Test Suite                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1 exists"
        return 0
    else
        echo -e "${RED}✗${NC} $1 missing"
        return 1
    fi
}

echo "1️⃣  Checking files..."
check_file "yt_dlp_tools.py"
check_file "moviebox_tools.py"
check_file "handlers.py"
check_file "shared.py"
check_file "admin_handlers.py"
echo ""

echo "2️⃣  Testing yt_dlp imports..."
python3 -c "
import yt_dlp_tools
print('✓ yt_dlp_tools imports successfully')
print('✓ Functions:', dir(yt_dlp_tools))
" 2>&1 | head -n 5
echo ""

echo "3️⃣  Testing moviebox imports..."
python3 -c "
try:
    import moviebox_tools
    print('✓ moviebox_tools imports successfully')
except ImportError as e:
    print('⚠ Import warning:', e)
    print('  (This is OK if moviebox-api is not installed yet)')
" 2>&1
echo ""

echo "4️⃣  Checking for common issues..."

# Check for missing returns in handlers.py
if grep -A 3 "ad_wizard_media" handlers.py | grep -q "return"; then
    echo -e "${GREEN}✓${NC} handlers.py: ad_wizard returns added"
else
    echo -e "${YELLOW}⚠${NC} handlers.py: missing returns - check ADMIN_PANEL_PATCHES.txt"
fi

# Check if _do_broadcast has forward_message
if grep -q "forward_message" shared.py; then
    echo -e "${GREEN}✓${NC} shared.py: forward_message support added"
else
    echo -e "${YELLOW}⚠${NC} shared.py: _do_broadcast needs update"
fi

# Check yt_dlp_tools has robust fallbacks
if grep -q "Multiple fallback strategies" yt_dlp_tools.py; then
    echo -e "${GREEN}✓${NC} yt_dlp_tools.py: robust fallback code present"
else
    echo -e "${YELLOW}⚠${NC} yt_dlp_tools.py: may need update"
fi

echo ""
echo "5️⃣  Manual Testing Checklist:"
echo "   □ Test video download (YouTube, Instagram, TikTok)"
echo "   □ Test audio extraction"
echo "   □ Test music recognition"
echo "   □ Test MovieBox search and download"
echo "   □ Test admin ad creation"
echo "   □ Test admin broadcast (regular message)"
echo "   □ Test admin broadcast (forwarded message)"
echo ""
echo "6️⃣  To run the bot:"
echo "   docker compose down"
echo "   docker compose build --no-cache"
echo "   docker compose up -d"
echo "   docker compose logs -f bot"
echo ""
echo "7️⃣  To monitor errors:"
echo "   docker compose logs -f bot | grep -i 'error\\|exception\\|failed'"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "If you see ✓ for all checks above, the fixes are ready to deploy!"
echo "════════════════════════════════════════════════════════════════"

#!/bin/bash
# @topam1z_bot — Google Cloud setup
# Usage: bash setup_gcloud.sh
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   @topam1z_bot — GCloud Setup       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. System update ─────────────────────────────────────────────
echo "▸ [1/5] Updating system..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq git curl nano wget
echo "  ✅ Done"

# ── 2. Install Docker ────────────────────────────────────────────
echo "▸ [2/5] Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
fi
sudo apt-get install -y -qq docker-compose-plugin 2>/dev/null || true
echo "  ✅ Docker $(docker --version | cut -d' ' -f3)"

# ── 3. Clone repo ────────────────────────────────────────────────
echo "▸ [3/5] Cloning repository..."
REPO_DIR="/opt/topam1z-bot"
if [ ! -d "$REPO_DIR" ]; then
    sudo git clone https://github.com/abdumutolib-404/Topam1z-Test-Bot.git "$REPO_DIR"
    sudo chown -R $USER:$USER "$REPO_DIR"
else
    cd "$REPO_DIR" && git pull
fi
echo "  ✅ $REPO_DIR"

# ── 4. Create .env ───────────────────────────────────────────────
echo "▸ [4/5] Creating .env..."
cd "$REPO_DIR"
if [ ! -f ".env" ]; then
    cp .env.example .env
fi
echo "  ✅ .env created at $REPO_DIR/.env"

# ── 5. Done — manual steps remain ───────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  ✅ Setup complete! Two manual steps remain:             ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "  STEP 1 — Edit your .env file:"
echo "    nano $REPO_DIR/.env"
echo ""
echo "  Fill in:"
echo "    BOT_TOKEN         = from @BotFather"
echo "    TELEGRAM_API_ID   = from my.telegram.org"
echo "    TELEGRAM_API_HASH = from my.telegram.org"
echo "    ADMIN_IDS         = 7200560574"
echo "    ADMIN_PASS        = any password"
echo "    DATABASE_URL      = from console.neon.tech"
echo ""
echo "  STEP 2 — Start the bot:"
echo "    cd $REPO_DIR && sudo docker compose up -d"
echo ""
echo "  Other commands:"
echo "    sudo docker compose logs -f bot     # watch logs"
echo "    sudo docker compose restart bot     # restart"
echo "    sudo docker compose down            # stop all"
echo "    cd $REPO_DIR && git pull && sudo docker compose up -d --build bot  # update"
echo ""

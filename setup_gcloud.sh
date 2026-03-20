#!/bin/bash
# ════════════════════════════════════════════════════════════════════════
#  @topam1z_bot — Google Cloud VM one-shot setup script
#  Run this ONCE on a fresh Google Cloud VM (Ubuntu 22.04 or 24.04)
#
#  Usage:
#    chmod +x setup_gcloud.sh
#    ./setup_gcloud.sh
# ════════════════════════════════════════════════════════════════════════

set -e
echo "════════════════════════════════════════"
echo " @topam1z_bot — Google Cloud Setup"
echo "════════════════════════════════════════"

# ── 1. System update ──────────────────────────────────────────────────
echo "[1/6] Updating system..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# ── 2. Install Docker ─────────────────────────────────────────────────
echo "[2/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    echo "✅ Docker installed"
else
    echo "✅ Docker already installed"
fi

# ── 3. Install Docker Compose ─────────────────────────────────────────
echo "[3/6] Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    sudo apt-get install -y -qq docker-compose-plugin
    echo "✅ Docker Compose installed"
else
    echo "✅ Docker Compose already installed"
fi

# ── 4. Clone repo ─────────────────────────────────────────────────────
echo "[4/6] Cloning bot repository..."
if [ ! -d "/opt/topam1z-bot" ]; then
    sudo git clone https://github.com/abdumutolib-404/Topam1z-Test-Bot.git /opt/topam1z-bot
    sudo chown -R $USER:$USER /opt/topam1z-bot
    echo "✅ Repo cloned to /opt/topam1z-bot"
else
    echo "✅ Repo already exists, pulling latest..."
    cd /opt/topam1z-bot && git pull
fi

# ── 5. Setup environment ──────────────────────────────────────────────
echo "[5/6] Setting up environment..."
cd /opt/topam1z-bot
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "══════════════════════════════════════════════════════"
    echo "  IMPORTANT: Edit .env with your actual values!"
    echo "  Run: nano /opt/topam1z-bot/.env"
    echo ""
    echo "  Required values to fill in:"
    echo "    BOT_TOKEN         — from @BotFather"
    echo "    TELEGRAM_API_ID   — from my.telegram.org"
    echo "    TELEGRAM_API_HASH — from my.telegram.org"
    echo "    ADMIN_IDS         — your Telegram user ID"
    echo "    ADMIN_PASS        — choose any password"
    echo "    DB_PASSWORD       — choose any strong password"
    echo "══════════════════════════════════════════════════════"
    echo ""
    read -p "Press ENTER after editing .env to continue..." _
fi

# ── 6. Build and start ────────────────────────────────────────────────
echo "[6/6] Building and starting services..."
docker compose build --no-cache
docker compose up -d

echo ""
echo "════════════════════════════════════════"
echo "✅ Bot is running!"
echo ""
echo "Commands:"
echo "  View logs:    docker compose logs -f bot"
echo "  Stop bot:     docker compose down"
echo "  Restart bot:  docker compose restart bot"
echo "  Update bot:   git pull && docker compose build bot && docker compose up -d bot"
echo "════════════════════════════════════════"

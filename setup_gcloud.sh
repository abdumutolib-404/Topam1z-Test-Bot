#!/bin/bash
# ════════════════════════════════════════════════════════════════════════
#  @topam1z_bot — Google Cloud VM setup
#  Stack: Telegram Local API + Bot + Neon (external DB)
#  Run once on a fresh Ubuntu 22.04/24.04 VM
# ════════════════════════════════════════════════════════════════════════
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   @topam1z_bot — GCloud Setup       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. System update ──────────────────────────────────────────────────
echo "▸ [1/5] Updating system..."
sudo apt-get update -qq && sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq git curl nano

# ── 2. Install Docker ─────────────────────────────────────────────────
echo "▸ [2/5] Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    echo "  ✅ Docker installed — NOTE: log out and back in if docker commands fail"
else
    echo "  ✅ Docker already installed"
fi

# Ensure compose plugin is available
if ! docker compose version &>/dev/null; then
    sudo apt-get install -y -qq docker-compose-plugin
fi
echo "  ✅ Docker Compose ready"

# ── 3. Clone / update repo ────────────────────────────────────────────
echo "▸ [3/5] Setting up repository..."
REPO_DIR="/opt/topam1z-bot"
if [ ! -d "$REPO_DIR" ]; then
    sudo git clone https://github.com/abdumutolib-404/Topam1z-Test-Bot.git "$REPO_DIR"
    sudo chown -R $USER:$USER "$REPO_DIR"
    echo "  ✅ Cloned to $REPO_DIR"
else
    cd "$REPO_DIR" && git pull
    echo "  ✅ Repo updated"
fi

# ── 4. Configure environment ──────────────────────────────────────────
echo "▸ [4/5] Configuring environment..."
cd "$REPO_DIR"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  Fill in these values in the editor that will open: │"
    echo "  │                                                      │"
    echo "  │  BOT_TOKEN         from @BotFather                  │"
    echo "  │  TELEGRAM_API_ID   from my.telegram.org             │"
    echo "  │  TELEGRAM_API_HASH from my.telegram.org             │"
    echo "  │  ADMIN_IDS         your Telegram user ID            │"
    echo "  │  ADMIN_PASS        any password you choose          │"
    echo "  │  DATABASE_URL      from console.neon.tech           │"
    echo "  └─────────────────────────────────────────────────────┘"
    echo ""
    read -p "  Press ENTER to open the editor..." _
    nano .env
fi

# ── 5. Build and start ────────────────────────────────────────────────
echo "▸ [5/5] Building and starting..."
# Apply group change without logout
newgrp docker << 'DOCKERCMD'
cd /opt/topam1z-bot
docker compose pull tg-api
docker compose build bot
docker compose up -d
DOCKERCMD

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  ✅ Bot is live!                     ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  Watch logs:   docker compose -f /opt/topam1z-bot/docker-compose.yml logs -f bot"
echo "  Stop:         docker compose -f /opt/topam1z-bot/docker-compose.yml down"
echo "  Update:       cd /opt/topam1z-bot && git pull && docker compose up -d --build bot"
echo ""

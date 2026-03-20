#!/bin/bash
# @topam1z_bot — Google Cloud VM full setup from scratch
# Run: bash setup_gcloud.sh
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   @topam1z_bot — Full Setup         ║"
echo "╚══════════════════════════════════════╝"

# ── 1. System packages ───────────────────────────────────────────────
echo "[1/4] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq git curl nano wget docker.io docker-compose-v2
sudo systemctl enable docker --now
sudo usermod -aG docker $USER
echo "  ✅ Done"

# ── 2. Clone repo ────────────────────────────────────────────────────
echo "[2/4] Cloning repository..."
REPO="https://github.com/abdumutolib-404/Topam1z-Test-Bot.git"
DIR="/opt/topam1z-bot"
sudo rm -rf "$DIR"
sudo git clone "$REPO" "$DIR"
sudo chown -R $USER:$USER "$DIR"
echo "  ✅ Cloned to $DIR"

# ── 3. Create empty secrets ──────────────────────────────────────────
echo "[3/4] Creating secret files..."
touch "$DIR/cookies.txt"
cp "$DIR/.env.example" "$DIR/.env"
echo "  ✅ Done"

# ── 4. Instructions ──────────────────────────────────────────────────
echo ""
echo "[4/4] Manual steps — run these next:"
echo ""
echo "  ┌── STEP A: fill in your .env ──────────────────────────────────┐"
echo "  │  nano $DIR/.env                                               │"
echo "  └───────────────────────────────────────────────────────────────┘"
echo ""
echo "  ┌── STEP B: paste your cookies ─────────────────────────────────┐"
echo "  │  nano $DIR/cookies.txt                                        │"
echo "  └───────────────────────────────────────────────────────────────┘"
echo ""
echo "  ┌── STEP C: start the bot ──────────────────────────────────────┐"
echo "  │  cd $DIR && sudo docker compose up -d --build                 │"
echo "  └───────────────────────────────────────────────────────────────┘"
echo ""
echo "  ┌── STEP D: watch logs ─────────────────────────────────────────┐"
echo "  │  sudo docker compose -f $DIR/docker-compose.yml logs -f      │"
echo "  └───────────────────────────────────────────────────────────────┘"
echo ""

#!/bin/bash
# @topam1z_bot — Google Cloud VM setup
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         @topam1z_bot — Setup         ║"
echo "╚══════════════════════════════════════╝"

# ── Clone repo ───────────────────────────────────────────────────────
echo "[1/2] Cloning repository..."
DIR="/opt/topam1z-bot"
sudo git clone https://github.com/abdumutolib-404/Topam1z-Test-Bot.git "$DIR"
sudo chown -R $USER:$USER "$DIR"
touch "$DIR/cookies.txt"
cp "$DIR/.env.example" "$DIR/.env"
echo "  ✅ Cloned to $DIR"

# ── Instructions ─────────────────────────────────────────────────────
echo ""
echo "[2/2] Now run these 3 commands:"
echo ""
echo "  nano $DIR/.env        ← fill in your values"
echo "  nano $DIR/cookies.txt ← paste your cookies"
echo "  cd $DIR && sudo docker compose up -d --build"
echo ""

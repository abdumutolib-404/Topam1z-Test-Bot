# 🚀 Google Cloud - Quick Fix & Deploy (Copy & Paste)

**Just run these commands on your Google Cloud VM. That's it.**

---

## Step 1: Connect to Your VM

```bash
# SSH into your Google Cloud VM
gcloud compute ssh your-vm-name --zone=your-zone
```

---

## Step 2: Navigate to Bot Directory

```bash
cd ~/topam1z-bot
# Or if installed in /opt:
# cd /opt/topam1z-bot
```

---

## Step 3: Fix Cookie Files (Critical - Run This First!)

```bash
# Stop the bot
sudo docker compose down

# Fix the cookie directory bug
sudo rm -rf cookies.txt www.youtube.com_cookies.txt www.instagram.com_cookies.txt
touch cookies.txt
touch www.youtube.com_cookies.txt  
touch www.instagram.com_cookies.txt

echo "✓ Cookie files fixed"
```

---

## Step 4: Download Fixed Files

```bash
# Download the fix package
wget https://your-server.com/bot-fixes.tar.gz
tar -xzf bot-fixes.tar.gz

# OR manually upload these files via SCP:
# scp config.py user@vm-ip:~/topam1z-bot/
# scp yt_dlp_tools.py user@vm-ip:~/topam1z-bot/
# scp moviebox_tools.py user@vm-ip:~/topam1z-bot/
```

**Manual Upload Alternative (if wget doesn't work):**

On your local machine:
```bash
# Upload fixed files to your VM
gcloud compute scp config.py your-vm:~/topam1z-bot/
gcloud compute scp yt_dlp_tools.py your-vm:~/topam1z-bot/
gcloud compute scp moviebox_tools.py your-vm:~/topam1z-bot/
```

---

## Step 5: Rebuild & Deploy

```bash
cd ~/topam1z-bot

# Rebuild with new code
sudo docker compose build --no-cache

# Start the bot
sudo docker compose up -d

# Check if it's running
sudo docker compose ps
```

---

## Step 6: Verify It Works

```bash
# Watch logs (Ctrl+C to exit)
sudo docker compose logs -f bot

# Should see:
# ✓ "Bot is live!"
# ✓ No "IsADirectoryError"
# ✓ No crashes
```

**Expected output:**
```
bot-1 | ╔══════════════════════════════════════════╗
bot-1 | ║   ASSISTANT BOT  ·  @topam1z_news        ║
bot-1 | ╚══════════════════════════════════════════╝
bot-1 | Cookies: cookies.txt loaded (1234 bytes)
bot-1 | DB     : ✓  asyncpg pool ready
bot-1 | 🤖 Bot is live!
```

---

## Emergency: If Still Crashing

```bash
# Stop everything
sudo docker compose down

# Nuclear option - complete cleanup
sudo docker system prune -af
sudo docker volume prune -f

# Verify cookie files are FILES not directories
ls -la *.txt
# Should show: -rw-r--r-- (file) NOT drwxr-xr-x (directory)

# If any show 'd' at start, remove them:
rm -rf cookies.txt
touch cookies.txt

# Rebuild from scratch
sudo docker compose build --no-cache --pull
sudo docker compose up -d
```

---

## Check Status Anytime

```bash
# Is it running?
sudo docker compose ps

# Recent logs
sudo docker compose logs --tail=50 bot

# Live logs
sudo docker compose logs -f bot

# Restart
sudo docker compose restart bot

# Stop
sudo docker compose down
```

---

## Common Issues

### Issue: "IsADirectoryError: cookies.txt"
**Fix:**
```bash
cd ~/topam1z-bot
sudo docker compose down
rm -rf cookies.txt www.youtube.com_cookies.txt www.instagram.com_cookies.txt
touch cookies.txt www.youtube.com_cookies.txt www.instagram.com_cookies.txt
sudo docker compose up -d
```

### Issue: "Video file missing after download"
**Fix:** Replace yt_dlp_tools.py with the fixed version from package

### Issue: "Music download crashes"
**Fix:** Apply handlers.py patches from MUSIC_DOWNLOAD_FIX.txt

### Issue: Bot keeps restarting
**Check:**
```bash
# See why it crashed
sudo docker compose logs bot | tail -100

# Check environment variables
sudo docker compose config | grep BOT_TOKEN
```

---

## Auto-Update Script (Optional)

Save this as `update_bot.sh`:

```bash
#!/bin/bash
cd ~/topam1z-bot
sudo docker compose down
git pull
sudo docker compose build --no-cache
sudo docker compose up -d
sudo docker compose logs -f bot
```

Then run:
```bash
chmod +x update_bot.sh
./update_bot.sh
```

---

## Monitoring

```bash
# CPU/Memory usage
docker stats

# Disk space
df -h

# Bot container details
sudo docker inspect topam1z-bot-bot-1
```

---

## That's It!

Your bot should now be running on Google Cloud without crashes.

**Test it:**
- Send the bot a YouTube link
- Try music search
- Test admin features

**Questions?** Check logs first:
```bash
sudo docker compose logs --tail=100 bot
```

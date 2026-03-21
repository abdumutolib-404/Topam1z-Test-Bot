# ════════════════════════════════════════════════════════════════════════
#  @topam1z_bot  —  Dockerfile
#  Local usage:
#    docker build -t topam1z-bot .
#    docker run --env-file .env topam1z-bot
# ════════════════════════════════════════════════════════════════════════

FROM python:3.12-slim

# ── Environment ───────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BOT_TMPDIR=/tmp/bot_tmp

# ── System packages ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ─────────────────────────────────────────────────────────
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app /tmp/bot_tmp && \
    chown -R botuser:botuser /app /tmp/bot_tmp

WORKDIR /app

# ── Python dependencies (cached layer) ───────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
# Install core packages first with pinned versions (avoids resolver depth issue)
RUN pip install --no-cache-dir \
    "python-telegram-bot[job-queue]==22.7" \
    "aiohttp==3.11.18" \
    "asyncpg==0.30.0" \
    "shazamio==0.8.1" \
    "python-dotenv==1.0.1" \
    "httpx==0.27.2" \
    "beautifulsoup4==4.12.3"
# Install moviebox dependencies explicitly to avoid resolver loop
# Install moviebox-api deps first to avoid resolver loop,
# then install moviebox-api latest (0.3.5 lacks quality= support)
RUN pip install --no-cache-dir \
    "throttlebuster>=0.1.11" \
    "pydantic>=2.9.2" \
    "rich" \
    "click" \
    "httpx>=0.27.0" \
    "bs4" && \
    pip install --no-cache-dir --no-deps moviebox-api
# Always upgrade yt-dlp to latest
RUN pip install --no-cache-dir --upgrade yt-dlp

# ── Application source ────────────────────────────────────────────────────
# Copy only the Python source files — NOT .env, cookies.txt, .idea/
COPY --chown=botuser:botuser *.py ./

# ── Switch to non-root ────────────────────────────────────────────────────
USER botuser

# ── Healthcheck ───────────────────────────────────────────────────────────
# Bot is not a web server — check that Python + key packages are importable
HEALTHCHECK --interval=60s --timeout=15s --start-period=60s --retries=3 \
    CMD python -c "import asyncpg, telegram, yt_dlp, aiohttp; print('ok')" || exit 1

# ── Run ───────────────────────────────────────────────────────────────────
CMD ["python", "-u", "bot.py"]

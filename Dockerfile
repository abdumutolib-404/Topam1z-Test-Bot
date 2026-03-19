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
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp

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

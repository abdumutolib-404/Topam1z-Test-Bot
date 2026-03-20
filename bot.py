#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════╗
║   ASSISTANT BOT  —  @topam1z_news       ║
║   python3 bot.py                             ║
╚══════════════════════════════════════════════╝
"""
import logging
import os
import shutil
import sys
import time

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChosenInlineResultHandler,
    CommandHandler,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

from inline_handlers import on_inline_query, on_chosen_inline
from admin_handlers import (
    admin_panel,
    cmd_broadcast,
    cmd_logout,
    cmd_stats_admin,
    on_admin_callback,
)
from config import (
    TOKEN, BRAND, TMPDIR, LOCAL_API_URL,
    SHAZAM_KEY, COOKIES, ADMIN_IDS,
)
from database import db_create_pool, db_init
from handlers import (
    on_animation_file,
    on_audio_file,
    on_callback,
    on_error,
    on_message,
    on_photo_file,
    on_start,
    on_video_file,
)

# ══════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════
os.makedirs(TMPDIR, exist_ok=True)
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(TMPDIR, "bot.log"), encoding="utf-8"),
    ],
)
for _noisy in ("httpx", "telegram", "urllib3", "apscheduler"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
log = logging.getLogger("bot")


def _update_ytdlp():
    """Run yt-dlp upgrade in a background thread so startup is instant."""
    import threading
    def _run():
        try:
            import importlib, subprocess
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "--upgrade", "yt-dlp"],
                capture_output=True, text=True, timeout=120,
            )
            if "Successfully installed" in r.stdout:
                log.info("yt-dlp : ✓  updated to latest")
                import yt_dlp
                importlib.reload(yt_dlp)
            else:
                log.info("yt-dlp : ✓  already latest")
        except Exception as e:
            log.warning(f"yt-dlp auto-update: {e}")
    threading.Thread(target=_run, daemon=True).start()


async def _job_expire_ads(ctx) -> None:
    """Deactivate ads whose scheduled end time has passed."""
    from database import db_expire_ads
    await db_expire_ads()

async def _job_purge_logs(ctx) -> None:
    """Delete logs/errors/security older than 7 days. Never touches users."""
    from database import db_purge_old_logs
    await db_purge_old_logs()

def main():
    if not shutil.which("ffmpeg"):
        sys.exit("❌  ffmpeg not found.\n    sudo apt install -y ffmpeg")
    if not shutil.which("ffprobe"):
        sys.exit("❌  ffprobe not found — install ffmpeg package.")
    try:
        for f in os.listdir(TMPDIR):
            p = os.path.join(TMPDIR, f)
            if f != "bot.log" and os.path.isfile(p):
                if time.time() - os.path.getmtime(p) > 3600:
                    os.remove(p)
    except Exception:
        pass

    _update_ytdlp()
    log.info("╔══════════════════════════════════════════╗")
    log.info(f"║   ASSISTANT BOT  ·  {BRAND}    ║")
    log.info("╚══════════════════════════════════════════╝")
    log.info(f"ShazamIO : ✓  free (primary)")
    log.info(f"RapidAPI : {'✓  backup' if SHAZAM_KEY else '✗  no key'}")
    log.info(f"ffmpeg   : ✓  {shutil.which('ffmpeg')}")
    log.info(
        f"Cookies  : {'✓  loaded' if os.path.exists(COOKIES) else '✗  not found (set COOKIES env var)'}"
    )
    log.info(f"Admins   : {ADMIN_IDS}")
    log.info("")

    # ── database init happens inside the bot's OWN event loop ────
    async def _post_init(application):
        await db_create_pool()
        await db_init()
        # Schedule hourly maintenance jobs
        jq = application.job_queue
        jq.run_repeating(_job_expire_ads,   interval=3600,  first=60)
        jq.run_repeating(_job_purge_logs,   interval=86400, first=300)  # daily

    # ── Cleanup on shutdown ────
    async def _post_shutdown(application):
        """Clean up resources on bot shutdown."""
        log.info("Bot shutting down, cleaning up resources...")
        # Close database pool
        from database import _pool
        if _pool:
            await _pool.close()
            log.info("Database pool closed")
        # Clean up temp files
        try:
            for f in os.listdir(TMPDIR):
                p = os.path.join(TMPDIR, f)
                if f != "bot.log" and os.path.isfile(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        except Exception:
            pass
        log.info("Cleanup complete")

    _builder = (
        Application.builder()
        .token(TOKEN)
        .concurrent_updates(True)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
    )
    if LOCAL_API_URL:
        # Self-hosted Telegram Bot API — 2 GB file limit, direct delivery
        _builder = _builder.base_url(f"{LOCAL_API_URL}/bot")
        _builder = _builder.base_file_url(f"{LOCAL_API_URL}/file/bot")
        log.info(f"API      : ✓  local server ({LOCAL_API_URL})")
    else:
        log.info("API      : ✓  api.telegram.org (50 MB limit)")
    app = _builder.build()
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("admin", admin_panel))
    # app.add_handler(CommandHandler("broadcast",      cmd_broadcast))
    app.add_handler(CommandHandler("logout", cmd_logout))
    app.add_handler(CommandHandler("exit", cmd_logout))
    app.add_handler(CommandHandler("stats", cmd_stats_admin))
    app.add_handler(CallbackQueryHandler(on_admin_callback, pattern=r"^adp\|"))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo_file))
    app.add_handler(MessageHandler(filters.ANIMATION, on_animation_file))
    app.add_handler(MessageHandler(filters.VIDEO, on_video_file))
    app.add_handler(
        MessageHandler(
            filters.Document.VIDEO
            | filters.Document.MimeType("video/mp4")
            | filters.Document.MimeType("video/quicktime")
            | filters.Document.MimeType("video/x-matroska")
            | filters.Document.MimeType("video/webm")
            | filters.Document.MimeType("video/avi"),
            on_video_file,
        )
    )
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, on_audio_file))
    # ── Inline mode ───────────────────────────────────────────────
    app.add_handler(InlineQueryHandler(on_inline_query))
    app.add_handler(ChosenInlineResultHandler(on_chosen_inline))
    app.add_error_handler(on_error)

    # Small delay so any previous Railway instance fully stops polling
    # before this one starts — prevents Conflict errors on rollout.
    time.sleep(3)

    log.info("🤖 Bot is live!")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=0.5,
        timeout=30,
    )


if __name__ == "__main__":
    main()
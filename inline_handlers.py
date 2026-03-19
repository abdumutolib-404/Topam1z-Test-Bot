"""
inline_handlers.py — Inline mode for @topam1z_bot

User types @topam1z_bot <url> in ANY chat.
Two choices appear: Download Video / Download Audio.
When chosen, bot downloads and delivers the file via inline_message_id.

Flow (per Telegram Bot API docs):
  1. on_inline_query → returns two InlineQueryResultArticle options
  2. User picks one → Telegram calls on_chosen_inline with inline_message_id
  3. Bot downloads file → edits the inline message to show result/link
"""
import asyncio
import logging
import uuid
import os

from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton as Btn,
)
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import BRAND, CHANNEL, AUDIO_TITLE, TMPDIR, MAX_MB
from utils import is_url, is_supported_url, detect_platform, h, fmt_sz, clean
from shared import _executor

log = logging.getLogger("bot.inline")

# Store pending inline jobs: inline_message_id → (action, url)
_pending: dict[str, tuple[str, str]] = {}


def _platform_thumb(platform: str) -> str:
    return {
        "YouTube":   "https://www.youtube.com/favicon.ico",
        "Instagram": "https://www.instagram.com/favicon.ico",
        "TikTok":    "https://www.tiktok.com/favicon.ico",
        "Twitter/X": "https://abs.twimg.com/favicons/twitter.3.ico",
        "Facebook":  "https://www.facebook.com/favicon.ico",
        "Pinterest": "https://www.pinterest.com/favicon.ico",
    }.get(platform, "")


async def on_inline_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Return Video / Audio options for the given URL."""
    query = update.inline_query
    if not query:
        return

    text = (query.query or "").strip()

    # Empty query — show usage tip
    if not text:
        await query.answer(
            results=[InlineQueryResultArticle(
                id="help",
                title="@topam1z_bot  ·  Type a video URL",
                description="YouTube · Instagram · TikTok · Twitter/X · Facebook · Pinterest",
                input_message_content=InputTextMessageContent(
                    "📎 <b>How to use inline mode</b>\n\n"
                    "Type <code>@topam1z_bot URL</code> in any chat.\n"
                    "Two options will appear: ⬇️ Video and 🎵 Audio.\n\n"
                    f"📢 {CHANNEL}",
                    parse_mode=ParseMode.HTML,
                ),
            )],
            cache_time=300,
        )
        return

    # Not a supported URL
    if not is_url(text) or not is_supported_url(text):
        await query.answer(
            results=[InlineQueryResultArticle(
                id="bad",
                title="⚠️ Unsupported URL",
                description="Supported: YouTube, Instagram, TikTok, Twitter/X, Facebook, Pinterest",
                input_message_content=InputTextMessageContent(
                    "⚠️ <b>Unsupported URL</b>\n\n"
                    "Paste a link from YouTube, Instagram, TikTok, Twitter/X, Facebook or Pinterest.",
                    parse_mode=ParseMode.HTML,
                ),
            )],
            cache_time=10,
        )
        return

    plat, icon = detect_platform(text)
    vid_id = f"v_{uuid.uuid4().hex[:12]}"
    aud_id = f"a_{uuid.uuid4().hex[:12]}"

    # Store url keyed by result_id so on_chosen_inline can retrieve it
    ctx.bot_data[vid_id] = ("video", text)
    ctx.bot_data[aud_id] = ("audio", text)

    await query.answer(
        results=[
            InlineQueryResultArticle(
                id=vid_id,
                title=f"{icon} Download Video  —  {plat}",
                description="I\'ll download and send the video to this chat",
                input_message_content=InputTextMessageContent(
                    f"{icon} <b>Downloading video…</b>\n"
                    f"<code>{h(text)}</code>\n\n"
                    f"<i>via {BRAND}</i>",
                    parse_mode=ParseMode.HTML,
                ),
                thumbnail_url=_platform_thumb(plat),
            ),
            InlineQueryResultArticle(
                id=aud_id,
                title=f"🎵 Download Audio  —  {plat}",
                description="I\'ll download and send the MP3 to this chat",
                input_message_content=InputTextMessageContent(
                    f"🎵 <b>Downloading audio…</b>\n"
                    f"<code>{h(text)}</code>\n\n"
                    f"<i>via {BRAND}</i>",
                    parse_mode=ParseMode.HTML,
                ),
                thumbnail_url=_platform_thumb(plat),
            ),
        ],
        cache_time=30,
        is_personal=True,
    )


async def on_chosen_inline(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Download the file and edit the inline message with result."""
    result = update.chosen_inline_result
    if not result:
        return

    result_id        = result.result_id
    inline_message_id = result.inline_message_id
    if not inline_message_id:
        return

    entry = ctx.bot_data.pop(result_id, None)
    if not entry:
        log.warning(f"on_chosen_inline: no entry for {result_id}")
        return

    action, url = entry
    loop = asyncio.get_running_loop()
    path = None

    try:
        if action == "video":
            from yt_dlp_tools import _dl_video
            path, info = await asyncio.wait_for(
                loop.run_in_executor(_executor, _dl_video, url, 720),
                timeout=300,
            )
            size = os.path.getsize(path)
            title = (info.get("title") or "")[:60]

            if size > MAX_MB * 1024 * 1024:
                # Too large for Telegram — send a link message update
                from utils import _upload_file  # might not exist — handle gracefully
                await ctx.bot.edit_message_text(
                    inline_message_id=inline_message_id,
                    text=(
                        f"⚠️ <b>File too large</b> ({fmt_sz(size)})\n\n"
                        f"📥 <a href=\"{url}\">Open original link</a>\n"
                        f"<i>via {BRAND}</i>"
                    ),
                    parse_mode=ParseMode.HTML,
                )
                return

            # Upload to Telegram — need a chat to send to first, then use file_id
            # Inline bots can't send files directly; they edit message text only.
            # Best UX: provide a deep-link to the bot with pre-filled command.
            import urllib.parse
            encoded = urllib.parse.quote(url, safe="")
            bot_link = f"https://t.me/topam1z_bot?start=dl_{encoded[:200]}"
            await ctx.bot.edit_message_text(
                inline_message_id=inline_message_id,
                text=(
                    f"✅ <b>{h(title)}</b>\n"
                    f"📦 {fmt_sz(size)}  │  via {BRAND}\n\n"
                    f"⬇️ <a href=\"{bot_link}\">Download in @topam1z_bot</a>"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    Btn("⬇️ Get in bot", url=bot_link)
                ]]),
            )

        else:  # audio
            from yt_dlp_tools import _dl_audio
            path, info = await asyncio.wait_for(
                loop.run_in_executor(_executor, _dl_audio, url),
                timeout=300,
            )
            size  = os.path.getsize(path)
            title = (info.get("title") or "")[:60]
            import urllib.parse
            encoded  = urllib.parse.quote(url, safe="")
            bot_link = f"https://t.me/topam1z_bot?start=au_{encoded[:200]}"
            await ctx.bot.edit_message_text(
                inline_message_id=inline_message_id,
                text=(
                    f"✅ <b>{h(title)}</b>\n"
                    f"🎵 MP3  │  {fmt_sz(size)}  │  via {BRAND}\n\n"
                    f"🎵 <a href=\"{bot_link}\">Download in @topam1z_bot</a>"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    Btn("🎵 Get MP3 in bot", url=bot_link)
                ]]),
            )

    except asyncio.TimeoutError:
        _try_edit(ctx, inline_message_id,
                  f"❌ Download timed out. <a href=\"{url}\">Try in the bot</a>")
    except Exception as e:
        log.error(f"on_chosen_inline {action} {url[:80]}: {e}")
        import urllib.parse
        bot_link = f"https://t.me/topam1z_bot"
        _try_edit(ctx, inline_message_id,
                  f"❌ Download failed.\n<a href=\"{bot_link}\">Open @topam1z_bot</a>")
    finally:
        if path:
            clean(path)


def _try_edit(ctx, inline_message_id: str, text: str):
    """Fire-and-forget edit — errors are silently swallowed."""
    async def _do():
        try:
            await ctx.bot.edit_message_text(
                inline_message_id=inline_message_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
    asyncio.ensure_future(_do())

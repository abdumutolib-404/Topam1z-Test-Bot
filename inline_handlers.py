"""
inline_handlers.py — Inline mode for @topam1z_bot

Usage in any chat:
  @topam1z_bot https://youtu.be/xxx   → Download Video / Download Audio
  @topam1z_bot Avatar                 → MovieBox search results

When user picks an option, they get a deep link that opens the bot
and immediately triggers the download — zero extra steps.
"""
import asyncio
import logging
import uuid
import urllib.parse

from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton as Btn,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import BRAND, CHANNEL, TMPDIR
from utils import is_url, is_supported_url, detect_platform, h

log = logging.getLogger("bot.inline")

# Map result_id → (action, payload) for on_chosen_inline
# Cleared on retrieval (memory-safe)
_PENDING: dict[str, tuple[str, str]] = {}


def _make_deep_link(action: str, payload: str) -> str:
    """Create a t.me deep link that opens the bot and triggers action immediately.

    Actions:
      dl   = download video (payload = url)
      au   = download audio (payload = url)
      mv   = movie search   (payload = query)
    """
    # Encode payload safely for Telegram start parameter (max 64 chars after encoding)
    encoded = urllib.parse.quote(payload, safe="")[:60]
    return f"https://t.me/topam1z_bot?start={action}_{encoded}"


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
    query = update.inline_query
    if not query:
        return

    text = (query.query or "").strip()

    # ── Empty query — show usage ──────────────────────────────────────
    if not text:
        await query.answer(
            results=[InlineQueryResultArticle(
                id="help",
                title="@topam1z_bot  ·  Paste a link or movie name",
                description="YouTube · Instagram · TikTok · Twitter/X · MovieBox",
                input_message_content=InputTextMessageContent(
                    "📎 <b>How to use inline mode</b>\n\n"
                    "Type <code>@topam1z_bot</code> followed by:\n"
                    "• A video link (YouTube, Instagram, TikTok…)\n"
                    "• A movie or series name\n\n"
                    f"📢 {CHANNEL}",
                    parse_mode=ParseMode.HTML,
                ),
            )],
            cache_time=300,
        )
        return

    # ── Video URL ─────────────────────────────────────────────────────
    if is_url(text) and is_supported_url(text):
        plat, icon = detect_platform(text)
        vid_id = f"v_{uuid.uuid4().hex[:12]}"
        aud_id = f"a_{uuid.uuid4().hex[:12]}"

        # Store for on_chosen_inline
        ctx.bot_data[vid_id] = ("dl", text)
        ctx.bot_data[aud_id] = ("au", text)

        dl_link  = _make_deep_link("dl", text)
        au_link  = _make_deep_link("au", text)

        await query.answer(
            results=[
                InlineQueryResultArticle(
                    id=vid_id,
                    title=f"{icon} Download Video  ·  {plat}",
                    description="Tap → bot sends the video directly to this chat",
                    input_message_content=InputTextMessageContent(
                        f"{icon} <b>{h(plat)} video</b>\n"
                        f"<code>{h(text[:80])}</code>\n\n"
                        f"<i>via {BRAND}</i>",
                        parse_mode=ParseMode.HTML,
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        Btn("⬇️ Download Video", url=dl_link)
                    ]]),
                    thumbnail_url=_platform_thumb(plat),
                ),
                InlineQueryResultArticle(
                    id=aud_id,
                    title=f"🎵 Download Audio  ·  {plat}",
                    description="Tap → bot sends the MP3 to this chat",
                    input_message_content=InputTextMessageContent(
                        f"🎵 <b>{h(plat)} audio</b>\n"
                        f"<code>{h(text[:80])}</code>\n\n"
                        f"<i>via {BRAND}</i>",
                        parse_mode=ParseMode.HTML,
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        Btn("🎵 Download Audio", url=au_link)
                    ]]),
                    thumbnail_url=_platform_thumb(plat),
                ),
            ],
            cache_time=30,
            is_personal=True,
        )
        return

    # ── Movie/series search ───────────────────────────────────────────
    mv_id = f"m_{uuid.uuid4().hex[:12]}"
    ctx.bot_data[mv_id] = ("mv", text)
    mv_link = _make_deep_link("mv", text)

    await query.answer(
        results=[
            InlineQueryResultArticle(
                id=mv_id,
                title=f"🎬 Search MovieBox: {text[:40]}",
                description="Tap → opens bot with search results",
                input_message_content=InputTextMessageContent(
                    f"🎬 <b>MovieBox search:</b> {h(text[:60])}\n\n"
                    f"<i>via {BRAND}</i>",
                    parse_mode=ParseMode.HTML,
                ),
                reply_markup=InlineKeyboardMarkup([[
                    Btn("🎬 Open in bot", url=mv_link)
                ]]),
            ),
        ],
        cache_time=10,
        is_personal=True,
    )


async def on_chosen_inline(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Log chosen result — actual download happens when user taps deep link."""
    result = update.chosen_inline_result
    if not result:
        return
    log.info(f"Inline chosen: {result.result_id} query={result.query[:60]}")

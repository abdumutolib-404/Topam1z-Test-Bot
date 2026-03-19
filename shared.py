"""
shared.py — Functions used by BOTH handlers.py and admin_handlers.py.
Keeping them here breaks the circular import:
  admin_handlers.py  ←  handlers.py  (was circular)
  Both now import from shared.py instead.
"""
import asyncio
import logging
import time

from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as IKM
from telegram.ext import ContextTypes

import database as db
from config import (
    ADMIN_PASS, MAX_FAILS, FAIL_WINDOW, BRAND, CHANNEL,
)
from state import (
    _admin_auth, _fail_counts, _fail_times,
    is_admin, is_admin_authed,
    waiting_for, pending_op,
    GLOBAL_RATE_SEC, _global_rate,
    _global_sem, get_user_sem,
)
from utils import HTML, h, sedit, sdel
from translations import t

from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("bot.shared")

# Shared thread-pool executor — used by handlers and shazam_tools
_executor = ThreadPoolExecutor(max_workers=6)  # 4 downloads + 2 shazam

# ── Admin auth-prompt message references (so we can delete them) ──────────
_auth_prompt_msg: dict[int, object] = {}

# ── Seen-users cache — skips db_register for repeat visitors ──────────────
_seen_users:  set[int]          = set()
_ban_counter: dict[int, int]    = {}

# ── Per-user language cache (uid → lang code) ──────────────────────────────
_lang_cache:  dict[int, str]    = {}

async def get_lang(uid: int) -> str:
    """Return cached language, falling back to DB then default 'en'."""
    if uid in _lang_cache:
        return _lang_cache[uid]
    lang = await db.db_get_lang(uid)
    if lang is None:
        lang = "en"
    _lang_cache[uid] = lang
    return lang



async def guard(update: Update) -> bool:
    """Register user, check ban, apply global rate limit. Return False to abort."""
    user = update.effective_user
    if not user:
        return False
    # Only hit DB on first message per session — huge perf win
    if user.id not in _seen_users:
        await db.db_register(user.id, user.username or "", user.full_name or "")
        if await db.db_is_banned(user.id):
            lang   = await get_lang(user.id)
            reason = await db.db_get_ban_reason(user.id)
            text   = t(lang, "banned")
            if reason:
                text += f"\n\n📋 <b>Reason:</b> {reason}"
            await update.effective_message.reply_text(text, parse_mode="HTML")
            return False
        _seen_users.add(user.id)
    else:
        # Seen user: only check ban every 50th message (cheap counter per uid)
        # This avoids a DB read on every single message while still catching bans quickly
        _ban_counter[user.id] = _ban_counter.get(user.id, 0) + 1
        if _ban_counter[user.id] % 50 == 0:
            if await db.db_is_banned(user.id):
                lang   = await get_lang(user.id)
                reason = await db.db_get_ban_reason(user.id)
                text   = t(lang, "banned")
                if reason:
                    text += f"\n\n📋 <b>Reason:</b> {reason}"
                await update.effective_message.reply_text(text, parse_mode="HTML")
                return False
    if not is_admin(user.id):
        now  = time.time()
        last = _global_rate.get(user.id, 0)
        if now - last < GLOBAL_RATE_SEC:
            return False   # silently drop — too fast
        _global_rate[user.id] = now
    return True


async def require_auth(update: Update) -> bool:
    """
    Verify admin is authenticated.
    If not → send passcode prompt and return False.
    """
    uid = update.effective_user.id
    if not is_admin(uid):
        lang = await get_lang(uid)
        await update.effective_message.reply_text(t(lang, "admins_only"))
        return False
    if is_admin_authed(uid):
        return True
    lang = await get_lang(uid)
    waiting_for[uid] = "admin_pass"
    prompt = await update.effective_message.reply_text(
        t(lang, "admin_pass_prompt"),
        parse_mode=HTML,
        reply_markup=IKM([[Btn("❌ Cancel", callback_data="cancel")]]),
    )
    _auth_prompt_msg[uid] = prompt
    return False


# ═══════════════════════════════════════════════════════════════════════════
#  ACTION HELPERS  (run in a thread executor, then send result)
# ═══════════════════════════════════════════════════════════════════════════


async def _do_broadcast(ctx, msg, users: list, caption: str | None = None) -> None:
    """Send a message (text / photo / video / animation / audio) to every user."""
    status = await msg.reply_text(
        f"📣 Broadcasting to <b>{len(users)}</b> users…", parse_mode=HTML)
    ok = fail = 0
    for i, row in enumerate(users):
        target = row["uid"]
        try:
            if msg.video or (
                msg.document and (msg.document.mime_type or "").startswith("video")
            ):
                fid = msg.video.file_id if msg.video else msg.document.file_id
                await ctx.bot.send_video(target, fid, caption=caption, parse_mode=HTML)
            elif msg.photo:
                await ctx.bot.send_photo(
                    target, msg.photo[-1].file_id, caption=caption, parse_mode=HTML)
            elif msg.animation:
                await ctx.bot.send_animation(
                    target, msg.animation.file_id, caption=caption, parse_mode=HTML)
            elif msg.audio:
                await ctx.bot.send_audio(
                    target, msg.audio.file_id, caption=caption, parse_mode=HTML)
            else:
                if caption:
                    await ctx.bot.send_message(target, caption, parse_mode=HTML)
            ok += 1
        except Exception as be:
            fail += 1
            if "blocked" not in str(be).lower():
                log.debug(f"broadcast uid={target}: {be}")
        await asyncio.sleep(1.0 if (i > 0 and i % 25 == 0) else 0.04)
    await sedit(
        status,
        f"✅ <b>Broadcast done!</b>\n\n"
        f"✅ Delivered : <code>{ok}</code>\n"
        f"❌ Failed    : <code>{fail}</code>",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  GUARD / AUTH
# ═══════════════════════════════════════════════════════════════════════════

async def send_done(msg, lang: str = "en") -> None:
    """Send a 'Done! What's next?' reply with the main keyboard."""
    try:
        from keyboards import main_kb
        await msg.reply_text("✅ Done! What's next?", reply_markup=main_kb(lang))
    except Exception:
        pass


import contextlib as _contextlib

@_contextlib.asynccontextmanager
async def queue_task(uid: int, msg, lang: str = "en", busy_text: str = "⏳"):
    """Context manager that:
    1. Acquires per-user + global semaphores (queuing if needed)
    2. Sends a "working…" indicator while waiting
    3. Releases on exit

    Usage:
        async with queue_task(uid, msg, lang) as go:
            if go:
                # do heavy work

    If user already has 2 active tasks, shows queue position message.
    """
    user_sem   = get_user_sem(uid)
    wait_msg   = None

    # Check if user sem is already at capacity → show queue notice
    if user_sem._value == 0:
        try:
            wait_msg = await msg.reply_text(
                f"{busy_text} Your request is queued — I'll process it shortly…"
            )
        except Exception:
            pass

    try:
        async with user_sem:
            async with _global_sem:
                if wait_msg:
                    try:
                        await wait_msg.delete()
                    except Exception:
                        pass
                yield True
    except Exception:
        yield False
    finally:
        if wait_msg:
            try:
                await wait_msg.delete()
            except Exception:
                pass

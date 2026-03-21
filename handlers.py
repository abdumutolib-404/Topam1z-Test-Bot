"""
handlers.py — Main user-facing message and callback handlers.
"""
import asyncio
import aiohttp
import logging
import os
import time
import uuid

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as IKM, Update
from telegram.ext import ContextTypes

import database as db
from database import db_schedule_ad
from config import (
    ADMIN_PASS, AUDIO_TITLE, BRAND, CHANNEL,
    FAIL_WINDOW, MAX_FAILS, MAX_MB, RATE_SEC, TG_MAX_MB, TMPDIR,
)
from ffmpeg_tools import (
    ffmpeg_change_speed, ffmpeg_compress, ffmpeg_convert,
    ffmpeg_extract_audio, ffmpeg_media_info, ffmpeg_merge,
    ffmpeg_remove_audio, ffmpeg_reverse, ffmpeg_screenshot,
    ffmpeg_to_gif, ffmpeg_trim,
)
from keyboards import (
    action_kb, cancel_btn, change_lang_kb, compress_kb, convert_kb, file_kb,
    lang_kb, main_kb, menu_btn, music_src_kb, quality_kb, quality_kb_avail,
    result_kb, speed_kb, _movie_quality_direct_kb,
)
from translations import LANGS, t
from shazam_tools import recognize, search_song
from moviebox_tools import mb_search, mb_download
from state import (
    GLOBAL_RATE_SEC, _admin_auth, _fail_counts, _fail_times,
    _global_rate, is_admin, is_admin_authed, pending_op, stats, waiting_for,
    check_action_rate_limit,
)
from shared import (
    guard, require_auth, _auth_prompt_msg, _do_broadcast,
    _executor, send_done, get_lang,
    _seen_users, _ban_counter, _lang_cache,
    queue_task,
)
from state import get_user_sem
from utils import (
    HTML, cb_get, cb_put, clean, detect_platform, fmt_dur,
    fmt_sz, fmt_views, h, is_supported_url, is_url, parse_time,
    rate_check, sdel, sedit, tg_ext,
)
from yt_dlp_tools import (
    _dl_audio, _dl_info, _dl_sample, _dl_video,
)

log = logging.getLogger("bot.handlers")

# ── Per-user music search state (paginated) ──────────────────────────────
# MEMORY OPTIMIZATION: Limit cache sizes to prevent unbounded growth
_MAX_CACHE_SIZE = 1000
_music_results: dict[int, list] = {}
_music_page:    dict[int, int]  = {}
_PAGE_SIZE = 10

# MovieBox search state
_movie_results: dict[int, list] = {}
_movie_page:    dict[int, int]  = {}





# ═══════════════════════════════════════════════════════════════════════════
#  LOW-LEVEL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

async def _download_tg_file(ctx, file_id: str, ext: str = ".mp4") -> str:
    """Download a Telegram file to TMPDIR and return its local path."""
    tg_file = await ctx.bot.get_file(file_id)
    path    = os.path.join(TMPDIR, f"{uuid.uuid4().hex}{ext}")
    await tg_file.download_to_drive(path)
    return path


async def _upload_gofile(path: str) -> str | None:
    """Gofile.io — unlimited size, free, 10-day retention after last download.
    Step 1: get best server. Step 2: upload to that server.
    """
    try:
        async with aiohttp.ClientSession() as s:
            # Get the best available upload server
            async with s.get("https://api.gofile.io/servers",
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200: return None
                data = await r.json()
            servers = data.get("data", {}).get("servers", [])
            if not servers: return None
            server = servers[0]["name"]

            # Upload the file
            form = aiohttp.FormData()
            with open(path, "rb") as f:
                form.add_field("file", f,
                               filename=os.path.basename(path),
                               content_type="application/octet-stream")
            async with s.post(
                f"https://{server}.gofile.io/contents/uploadfile",
                data=form,
                timeout=aiohttp.ClientTimeout(total=1800)  # 30 min for huge files
            ) as r:
                if r.status != 200: return None
                resp = await r.json()
            if resp.get("status") == "ok":
                return resp["data"]["downloadPage"]
    except Exception as e:
        log.warning(f"gofile upload: {e}")
    return None


async def _upload_litterbox(path: str) -> str | None:
    """Litterbox (catbox.moe) — up to 1 GB, 72h retention, very fast."""
    size_mb = os.path.getsize(path) / 1024 / 1024
    if size_mb > 1000:  # 1 GB hard limit
        return None
    try:
        async with aiohttp.ClientSession() as s:
            form = aiohttp.FormData()
            form.add_field("reqtype", "fileupload")
            form.add_field("time", "72h")
            with open(path, "rb") as f:
                form.add_field("fileToUpload", f,
                               filename=os.path.basename(path),
                               content_type="application/octet-stream")
            async with s.post("https://litterbox.catbox.moe/resources/internals/api.php",
                              data=form,
                              timeout=aiohttp.ClientTimeout(total=600)) as r:
                if r.status == 200:
                    url = (await r.text()).strip()
                    if url.startswith("http"):
                        return url
    except Exception as e:
        log.warning(f"litterbox upload: {e}")
    return None


async def _upload_0x0(path: str) -> str | None:
    """0x0.st — up to 512 MB, 30-day retention."""
    size_mb = os.path.getsize(path) / 1024 / 1024
    if size_mb > 512:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            form = aiohttp.FormData()
            with open(path, "rb") as f:
                form.add_field("file", f,
                               filename=os.path.basename(path),
                               content_type="application/octet-stream")
            async with s.post("https://0x0.st", data=form,
                              timeout=aiohttp.ClientTimeout(total=600)) as r:
                if r.status == 200:
                    return (await r.text()).strip()
    except Exception as e:
        log.warning(f"0x0 upload: {e}")
    return None


async def _upload_file(path: str, status_msg=None) -> tuple[str | None, str]:
    """Upload to the first working host from a priority chain.

    Priority:
      1. Gofile.io   — unlimited size, 10-day retention
      2. Litterbox   — up to 1 GB,  72h retention
      3. 0x0.st      — up to 512 MB, 30-day retention

    Returns (url, host_name) — url is None only if all three fail.
    Updates status_msg text as it tries each host.
    """
    size_mb = os.path.getsize(path) / 1024 / 1024

    hosts = [
        ("Gofile",    _upload_gofile,    None),
        ("Litterbox", _upload_litterbox, 1000),
        ("0x0.st",    _upload_0x0,       512),
    ]

    for name, fn, limit_mb in hosts:
        if limit_mb and size_mb > limit_mb:
            log.debug(f"_upload_file: skipping {name} (file {size_mb:.0f}MB > {limit_mb}MB limit)")
            continue
        if status_msg:
            try:
                await sedit(status_msg,
                    f"⬆️ Uploading to <b>{name}</b>… ({fmt_sz(os.path.getsize(path))})",
                )
            except Exception:
                pass
        log.info(f"_upload_file: trying {name} ({size_mb:.1f} MB)")
        url = await fn(path)
        if url:
            log.info(f"_upload_file: ✓ {name} → {url}")
            return url, name

    log.error(f"_upload_file: all hosts failed for {os.path.basename(path)}")
    return None, "unknown"


async def _show_ad(ctx, uid: int, msg) -> None:
    """Show up to 3 random active ads based on user rank.
    Higher rank = longer interval between ads.
    """
    try:
        ads = await db.db_get_active_ads()  # already limited to 3, ORDER BY RANDOM()
        if not ads: return
        for ad in ads:
            cap = ad.get("caption") or ""
            mt  = ad.get("media_type", "text")
            kb  = None
            if ad.get("url") and ad.get("button_label"):
                kb = IKM([[Btn(str(ad["button_label"]), url=str(ad["url"]))]])
            try:
                if   mt == "photo"     and ad.get("file_id"):
                    await ctx.bot.send_photo(uid, ad["file_id"], caption=cap, reply_markup=kb, parse_mode=HTML)
                elif mt == "video"     and ad.get("file_id"):
                    await ctx.bot.send_video(uid, ad["file_id"], caption=cap, reply_markup=kb, parse_mode=HTML)
                elif mt == "animation" and ad.get("file_id"):
                    await ctx.bot.send_animation(uid, ad["file_id"], caption=cap, reply_markup=kb, parse_mode=HTML)
                elif cap:
                    await ctx.bot.send_message(uid, cap, reply_markup=kb, parse_mode=HTML)
                await db.db_imp_ad(ad["id"])
            except Exception:
                pass
            await asyncio.sleep(0.3)  # small gap between multiple ads
    except Exception as e:
        log.debug(f"_show_ad: {e}")


def _music_page_text(uid: int, page: int) -> str:
    results = _music_results.get(uid, [])
    total   = len(results)
    total_p = (total - 1) // _PAGE_SIZE + 1 if total else 1
    start   = page * _PAGE_SIZE
    end     = min(start + _PAGE_SIZE, total)

    lines = [
        f"🎵 <b>Music Results</b>",
        f"Page {page + 1} of {total_p}  ·  {total} found",
        "",
    ]
    for i in range(start, end):
        r      = results[i]
        title  = h(r.get("title",  "Unknown"))
        artist = h(r.get("artist", "Unknown"))
        dur    = r.get("duration", "")
        dur_s  = f"  <code>{dur}</code>" if dur and dur != "?" else ""
        lines.append(f"<b>{i + 1}.</b> {title}{dur_s}")
        lines.append(f"    👤 {artist}")
    lines.append("")
    lines.append("<i>Tap a number to download as MP3</i>")
    return "\n".join(lines)


def _music_page_kb(uid: int, page: int, total: int) -> IKM:
    """12 numbered download buttons (2 rows × 6) + nav row (◀️  ▶️) + cancel."""
    start = page * _PAGE_SIZE
    end   = min(start + _PAGE_SIZE, total)
    rows: list = []

    # Number buttons — 6 per row, max 2 rows (= 12 buttons)
    btns = [Btn(str(i + 1), callback_data=f"mdown|{i}") for i in range(start, end)]
    rows.append(btns[:6])
    if len(btns) > 6:
        rows.append(btns[6:12])

    # Navigation row — always at the bottom of number buttons
    nav: list = []
    if page > 0:
        nav.append(Btn("◀️  Prev", callback_data=f"mpage|{page - 1}"))
    if end < total:
        nav.append(Btn("Next  ▶️", callback_data=f"mpage|{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([Btn("✖️ Close", callback_data="cancel")])
    return IKM(rows)


def _movie_page_text(uid: int, page: int) -> str:
    results = _movie_results.get(uid, [])
    total   = len(results)
    total_p = (total - 1) // _PAGE_SIZE + 1 if total else 1
    start   = page * _PAGE_SIZE
    end     = min(start + _PAGE_SIZE, total)
    lines   = [
        "🎬 <b>MovieBox Results</b>",
        f"Page {page + 1} of {total_p}  ·  {total} found",
        "",
    ]
    for i in range(start, end):
        r     = results[i]
        title = h(r.get("title", "Unknown"))
        year  = r.get("year", "")
        mtype = "📺" if r.get("type", "movie") != "movie" else "🎬"
        rat   = r.get("rating", "")
        rat_s = f"  ⭐{rat}" if rat else ""
        lines.append(f"<b>{i + 1}.</b> {mtype} {title}")
        lines.append(f"    📅 {year}{rat_s}")
    lines.append("")
    lines.append("<i>Tap a number to choose quality and download</i>")
    return "\n".join(lines)


def _movie_page_kb(uid: int, page: int, total: int) -> IKM:
    start = page * _PAGE_SIZE
    end   = min(start + _PAGE_SIZE, total)
    rows: list = []
    btns = [Btn(str(i + 1), callback_data=f"mvpick|{i}") for i in range(start, end)]
    rows.append(btns[:6])
    if len(btns) > 6:
        rows.append(btns[6:12])
    nav: list = []
    if page > 0:
        nav.append(Btn("◀️  Prev", callback_data=f"mvpage|{page - 1}"))
    if end < total:
        nav.append(Btn("Next  ▶️", callback_data=f"mvpage|{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([Btn("✖️ Close", callback_data="cancel")])
    return IKM(rows)


def _movie_quality_kb(idx: int) -> IKM:
    return IKM([
        [Btn("📱 720p",  callback_data=f"mvdl|{idx}|720p"),
         Btn("🖥 1080p", callback_data=f"mvdl|{idx}|1080p")],
        [Btn("✨ Best",  callback_data=f"mvdl|{idx}|best")],
        [Btn("🔙 Back",  callback_data=f"mvback|{idx}")],
    ])



# ═══════════════════════════════════════════════════════════════════════════
#  BROADCAST (shared by handlers + admin_handlers)
# ═══════════════════════════════════════════════════════════════════════════





async def act_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                    url: str, quality: int) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    # Show queue position if user already has tasks running
    _usem = get_user_sem(uid)
    if _usem._value == 0:
        await msg.reply_text("⏳ Another download is in progress — your request is queued and will start automatically.")

    lang = await get_lang(uid)

    # RATE LIMITING: Check download rate limit
    allowed, wait_time = check_action_rate_limit(uid, "download")
    if not allowed:
        await msg.reply_text(
            f"⏳ Please wait <b>{wait_time}s</b> before the next download.\n"
            f"This keeps the bot fast for everyone.",
            parse_mode=HTML,
            reply_markup=main_kb(lang)
        )
        return

    wait = await msg.reply_text(f"⏳ Downloading video ({quality}p)…")
    path = None
    try:
        # Validate inputs
        if not url or not isinstance(url, str) or len(url) > 2000:
            raise ValueError("Invalid URL")
        if quality not in {360, 720, 1080, 2160}:
            raise ValueError(f"Invalid quality: {quality}")

        loop = asyncio.get_running_loop()
        path, info = await asyncio.wait_for(
            loop.run_in_executor(_executor, _dl_video, url, quality),
            timeout=300)

        # Verify file exists and has size
        if not path or not os.path.exists(path):
            raise FileNotFoundError("Downloaded file not found")

        size = os.path.getsize(path)
        if size == 0:
            raise ValueError("Downloaded file is empty")
        title   = (info.get("title") or "")[:100] or "Video"
        caption = f"🎬 <b>{h(title)}</b>\n📦 {fmt_sz(size)}\n\n📣 {BRAND}"
        await sdel(wait)
        if size > TG_MAX_MB * 1024 * 1024:
            # Above Telegram limit — use external host fallback
            upl_msg = await msg.reply_text(
                f"📦 <b>{fmt_sz(size)}</b> — preparing upload…", parse_mode=HTML)
            link, host = await _upload_file(path, upl_msg)
            clean(path); path = None
            if link:
                retention = {"Gofile": "10 days", "Litterbox": "72 hours", "0x0.st": "30 days"}.get(host, "limited time")
                await sedit(upl_msg,
                    f"{caption}\n\n"
                    f"⬇️ <a href=\"{link}\">Download link</a>\n"
                    f"<i>via {host}  ·  expires in {retention}</i>",
                    disable_web_page_preview=True)
            else:
                await sedit(upl_msg,
                    "❌ Upload failed. Try a lower quality.",
                    reply_markup=main_kb(lang))
        else:
            # Within limit — send directly through Telegram
            await msg.reply_video(
                path, caption=caption, parse_mode=HTML,
                reply_markup=menu_btn(), supports_streaming=True,
            )
            clean(path); path = None
        stats["videos"] += 1
        dl_count = await db.db_inc_downloads(uid)
        await db.db_track("videos")
        await db.db_log(uid, "video", url[:200])
        # Rank-based ad interval: Newcomer=every 5, Beginner=10, Regular=25…
        user_row   = await db.db_get_user(uid)
        total_acts = (
            (user_row["downloads"] if user_row else 0)
            + (user_row["edits"] if user_row else 0)
            + (user_row["recognitions"] if user_row else 0)
        )
        interval = db.rank_ad_interval(total_acts)
        if interval and dl_count % interval == 0:
            await _show_ad(ctx, uid, msg)
    except asyncio.TimeoutError:
        log.error(f"act_video uid={uid} url={url[:100]}: Timeout")
        await db.db_log_error(uid, "act_video", "Download timeout")
        await db.db_track("errors")
        await sedit(wait,
            f"❌ <b>Download timeout</b>\nThe video took too long to download. Try a different video.",
            reply_markup=main_kb(lang))
    except FileNotFoundError as e:
        log.error(f"act_video uid={uid} url={url[:100]}: {e}")
        await db.db_log_error(uid, "act_video", str(e))
        await db.db_track("errors")
        await sedit(wait,
            f"❌ <b>File not found</b>\nThe download completed but the file is missing.",
            reply_markup=main_kb(lang))
    except ValueError as e:
        log.error(f"act_video uid={uid} url={url[:100]}: {e}")
        await db.db_log_error(uid, "act_video", str(e))
        await db.db_track("errors")
        await sedit(wait,
            f"❌ <b>Invalid request</b>\n<code>{h(str(e))}</code>",
            reply_markup=main_kb(lang))
    except Exception as e:
        log.error(f"act_video uid={uid} url={url[:100]}: {e}", exc_info=True)
        await db.db_log_error(uid, "act_video", str(e))
        await db.db_track("errors")
        await sedit(wait,
            f"❌ <b>Download failed</b>\n<code>{h(str(e)[:300])}</code>",
            reply_markup=main_kb(lang))
    finally:
        clean(path)


async def act_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    # Show queue position if user already has tasks running
    _usem = get_user_sem(uid)
    if _usem._value == 0:
        await msg.reply_text("⏳ Another download is in progress — your request is queued and will start automatically.")

    lang = await get_lang(uid)

    # RATE LIMITING: Check download rate limit
    allowed, wait_time = check_action_rate_limit(uid, "download")
    if not allowed:
        await msg.reply_text(
            f"⏳ <b>Rate limit exceeded</b>\n"
            f"Please wait {wait_time} seconds before downloading again.",
            parse_mode=HTML,
            reply_markup=main_kb(lang)
        )
        return

    wait = await msg.reply_text("⏳ Downloading audio…")
    path = None
    try:
        # Validate input
        if not url or not isinstance(url, str) or len(url) > 2000:
            raise ValueError("Invalid URL")

        loop = asyncio.get_running_loop()
        path, info = await asyncio.wait_for(
            loop.run_in_executor(_executor, _dl_audio, url),
            timeout=300)

        # Verify file exists
        if not path or not os.path.exists(path):
            raise FileNotFoundError("Audio file not found after download")

        size  = os.path.getsize(path)
        if size == 0:
            raise ValueError("Downloaded audio file is empty")
        if size > MAX_MB * 1024 * 1024:
            clean(path); path = None
            await sedit(wait,
                f"⚠️ Audio file too large ({fmt_sz(size)}).",
                reply_markup=main_kb(lang))
            return

        dur    = info.get("duration")
        await sdel(wait)
        await msg.reply_audio(
            path,
            title=AUDIO_TITLE,
            performer=AUDIO_TITLE,
            duration=int(dur) if dur else None,
            caption=f"🎵 {AUDIO_TITLE}",
            reply_markup=menu_btn(),
        )
        stats["audios"] += 1
        dl_count = await db.db_inc_downloads(uid)
        await db.db_track("audios")
        await db.db_log(uid, "audio", url[:200])
        user_row   = await db.db_get_user(uid)
        total_acts = (
            (user_row["downloads"] if user_row else 0)
            + (user_row["edits"] if user_row else 0)
            + (user_row["recognitions"] if user_row else 0)
        )
        interval = db.rank_ad_interval(total_acts)
        if interval and dl_count % interval == 0:
            await _show_ad(ctx, uid, msg)
    except asyncio.TimeoutError:
        log.error(f"act_audio uid={uid} url={url[:100]}: Timeout")
        await db.db_log_error(uid, "act_audio", "Download timeout")
        await db.db_track("errors")
        await sedit(wait,
            "❌ <b>Download timeout</b>\nThe audio took too long to download.",
            reply_markup=main_kb(lang))
    except FileNotFoundError as e:
        log.error(f"act_audio uid={uid} url={url[:100]}: {e}")
        await db.db_log_error(uid, "act_audio", str(e))
        await db.db_track("errors")
        await sedit(wait,
            "❌ <b>File not found</b>\nThe download completed but the file is missing.",
            reply_markup=main_kb(lang))
    except ValueError as e:
        log.error(f"act_audio uid={uid} url={url[:100]}: {e}")
        await db.db_log_error(uid, "act_audio", str(e))
        await db.db_track("errors")
        await sedit(wait,
            f"❌ <b>Invalid request</b>\n<code>{h(str(e))}</code>",
            reply_markup=main_kb(lang))
    except Exception as e:
        log.error(f"act_audio uid={uid} url={url[:100]}: {e}", exc_info=True)
        await db.db_log_error(uid, "act_audio", str(e))
        await db.db_track("errors")
        await sedit(wait,
            f"❌ <b>Download failed</b>\n<code>{h(str(e)[:300])}</code>",
            reply_markup=main_kb(lang))
    finally:
        clean(path)


async def act_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text("ℹ️ Fetching info…")
    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(_executor, _dl_info, url)
        if not info:
            await sedit(wait, "❌ Could not fetch info.", reply_markup=main_kb())
            return
        plat, icon = detect_platform(url)
        title     = h((info.get("title")       or "N/A")[:120])
        uploader  = h((info.get("uploader")    or "N/A")[:80])
        desc      = h((info.get("description") or "")[:300])
        views     = fmt_views(info.get("view_count"))
        likes     = fmt_views(info.get("like_count"))
        dur       = fmt_dur(info.get("duration"))
        upload_dt = (info.get("upload_date") or "")
        lines = [
            f"{icon} <b>{title}</b>",
            f"👤 {uploader}",
            f"⏱ {dur}  │  👁 {views}  │  ❤️ {likes}",
        ]
        if upload_dt and len(upload_dt) == 8:
            lines.append(f"📅 {upload_dt[:4]}-{upload_dt[4:6]}-{upload_dt[6:]}")
        if desc:
            lines.append(f"\n📝 {desc}…" if len(desc) >= 300 else f"\n📝 {desc}")
        k = cb_put(url)
        await sedit(wait, "\n".join(lines), reply_markup=action_kb(k))
        await db.db_log(uid, "info", url[:200])
    except Exception as e:
        log.error(f"act_info uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Failed to fetch info</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())


async def act_music_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text("🎵 Downloading sample to identify…")
    sample = None
    try:
        loop   = asyncio.get_running_loop()
        sample = await loop.run_in_executor(_executor, _dl_sample, url)
        result = await recognize(sample)
        await sdel(wait)
        if result:
            await _send_music_result(msg, result)
        else:
            await msg.reply_text(
                "❓ Could not identify the song.  Try a different clip.",
                reply_markup=main_kb())
        stats["music"] += 1
        await db.db_track("music")
        await db.db_inc_recognitions(uid)
        await db.db_log(uid, "music_url", url[:200])
    except Exception as e:
        log.error(f"act_music_url uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Recognition failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(sample)


async def act_music_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                         file_id: str, tgf=None) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text("🎵 Identifying music…")
    path = None
    try:
        ext  = tg_ext(tgf) if tgf else ".mp3"
        path = await _download_tg_file(ctx, file_id, ext)
        result = await recognize(path)
        await sdel(wait)
        if result:
            await _send_music_result(msg, result)
        else:
            await msg.reply_text(
                "❓ Could not identify the song.",
                reply_markup=main_kb())
        stats["music"] += 1
        await db.db_track("music")
        await db.db_inc_recognitions(uid)
        await db.db_log(uid, "music_file", "")
    except Exception as e:
        log.error(f"act_music_file uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Recognition failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(path)


async def _send_music_result(msg, result: dict) -> None:
    title    = h(result.get("title",  "Unknown"))
    artist   = h(result.get("artist", "Unknown"))
    album    = h(result.get("album",  "") or "")
    released = result.get("released", "")
    lines = [
        "🎵 <b>Song identified!</b>\n",
        f"🎤 <b>{title}</b>",
        f"👤 {artist}",
    ]
    if album:    lines.append(f"💿 {album}")
    if released: lines.append(f"📅 {released}")
    await msg.reply_text(
        "\n".join(lines),
        parse_mode=HTML,
        reply_markup=result_kb(
            yt=result.get("youtube_url"),
            sp=result.get("spotify_url"),
        ),
    )


async def act_file_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                         file_id: str) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text("🎵 Extracting audio…")
    src = out = None
    try:
        src = await _download_tg_file(ctx, file_id, ".mp4")
        loop = asyncio.get_running_loop()
        out  = await loop.run_in_executor(_executor, ffmpeg_extract_audio, src)
        size = os.path.getsize(out)
        await sdel(wait)
        await msg.reply_audio(
            out,
            performer=AUDIO_TITLE,
            caption=f"🎵 {AUDIO_TITLE}",
            reply_markup=menu_btn(),
        )
        stats["audios"] += 1
        await db.db_track("audios")
        await db.db_log(uid, "file_audio", "")
    except Exception as e:
        log.error(f"act_file_audio uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Extraction failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(src, out)


async def act_trim(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                   file_id: str, start: int, end: int) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text(f"✂️ Trimming {start}s → {end}s…")
    src = out = None
    try:
        src  = await _download_tg_file(ctx, file_id, ".mp4")
        loop = asyncio.get_running_loop()
        out  = await loop.run_in_executor(_executor, ffmpeg_trim, src, start, end)
        size = os.path.getsize(out)
        await sdel(wait)
        await msg.reply_video(
            out, caption=f"✂️ <b>Trimmed</b>\n📦 {fmt_sz(size)}\n\n📣 {BRAND}",
            parse_mode=HTML, reply_markup=menu_btn(), supports_streaming=True,
        )
        await db.db_log(uid, "trim", f"{start}-{end}")
    except Exception as e:
        log.error(f"act_trim uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Trim failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(src, out)


async def act_compress(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                       file_id: str, height: int) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text(f"🗜️ Compressing to {height}p…")
    src = out = None
    try:
        src  = await _download_tg_file(ctx, file_id, ".mp4")
        loop = asyncio.get_running_loop()
        out  = await loop.run_in_executor(_executor, ffmpeg_compress, src, height)
        size = os.path.getsize(out)
        await sdel(wait)
        await msg.reply_video(
            out,
            caption=f"🗜️ <b>Compressed</b> to {height}p\n📦 {fmt_sz(size)}\n\n📣 {BRAND}",
            parse_mode=HTML, reply_markup=menu_btn(), supports_streaming=True,
        )
        await db.db_log(uid, "compress", str(height))
    except Exception as e:
        log.error(f"act_compress uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Compression failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(src, out)


async def act_screenshot(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                          file_id: str, ts: int) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text(f"📸 Taking screenshot at {ts}s…")
    src = out = None
    try:
        src  = await _download_tg_file(ctx, file_id, ".mp4")
        loop = asyncio.get_running_loop()
        out  = await loop.run_in_executor(_executor, ffmpeg_screenshot, src, ts)
        await sdel(wait)
        await msg.reply_photo(
            out,
            caption=f"📸 <b>Screenshot</b> at {ts}s\n\n📣 {BRAND}",
            parse_mode=HTML, reply_markup=menu_btn(),
        )
        stats["screenshots"] += 1
        await db.db_inc_edits(uid)
        await db.db_track("screenshots")
        await db.db_log(uid, "screenshot", str(ts))
    except Exception as e:
        log.error(f"act_screenshot uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Screenshot failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(src, out)


async def act_gif(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                  file_id: str, start: int, end: int) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    dur  = end - start
    wait = await msg.reply_text(f"🎞️ Creating GIF ({dur}s)…")
    src = out = None
    try:
        src  = await _download_tg_file(ctx, file_id, ".mp4")
        loop = asyncio.get_running_loop()
        out  = await loop.run_in_executor(_executor, ffmpeg_to_gif, src, start, dur)
        size = os.path.getsize(out)
        await sdel(wait)
        await msg.reply_animation(
            out,
            caption=f"🎞️ <b>GIF created</b>\n📦 {fmt_sz(size)}\n\n📣 {BRAND}",
            parse_mode=HTML, reply_markup=menu_btn(),
        )
        stats["gifs"] += 1
        await db.db_inc_edits(uid)
        await db.db_track("gifs")
        await db.db_log(uid, "gif", f"{start}-{end}")
    except Exception as e:
        log.error(f"act_gif uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>GIF failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(src, out)


async def act_convert(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                      file_id: str, fmt: str) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text(f"🔄 Converting to {fmt.upper()}…")
    src = out = None
    try:
        src  = await _download_tg_file(ctx, file_id, ".mp4")
        loop = asyncio.get_running_loop()
        out  = await loop.run_in_executor(_executor, ffmpeg_convert, src, fmt)
        size = os.path.getsize(out)
        await sdel(wait)
        await msg.reply_document(
            out,
            caption=f"🔄 <b>Converted</b> to {fmt.upper()}\n📦 {fmt_sz(size)}\n\n📣 {BRAND}",
            parse_mode=HTML, reply_markup=menu_btn(),
        )
        await db.db_log(uid, "convert", fmt)
    except Exception as e:
        log.error(f"act_convert uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Conversion failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(src, out)


async def act_remove_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                            file_id: str) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text("🔇 Removing audio…")
    src = out = None
    try:
        src  = await _download_tg_file(ctx, file_id, ".mp4")
        loop = asyncio.get_running_loop()
        out  = await loop.run_in_executor(_executor, ffmpeg_remove_audio, src)
        size = os.path.getsize(out)
        await sdel(wait)
        await msg.reply_video(
            out,
            caption=f"🔇 <b>Audio removed</b>\n📦 {fmt_sz(size)}\n\n📣 {BRAND}",
            parse_mode=HTML, reply_markup=menu_btn(), supports_streaming=True,
        )
        await db.db_log(uid, "remove_audio", "")
    except Exception as e:
        log.error(f"act_remove_audio uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(src, out)


async def act_speed(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                    file_id: str, speed: float) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text(f"⚡ Changing speed to {speed}x…")
    src = out = None
    try:
        src  = await _download_tg_file(ctx, file_id, ".mp4")
        loop = asyncio.get_running_loop()
        out  = await loop.run_in_executor(_executor, ffmpeg_change_speed, src, speed)
        size = os.path.getsize(out)
        await sdel(wait)
        await msg.reply_video(
            out,
            caption=f"⚡ <b>Speed changed</b> to {speed}x\n📦 {fmt_sz(size)}\n\n📣 {BRAND}",
            parse_mode=HTML, reply_markup=menu_btn(), supports_streaming=True,
        )
        await db.db_log(uid, "speed", str(speed))
    except Exception as e:
        log.error(f"act_speed uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(src, out)


async def act_reverse(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                      file_id: str) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text("🔁 Reversing video…")
    src = out = None
    try:
        src  = await _download_tg_file(ctx, file_id, ".mp4")
        loop = asyncio.get_running_loop()
        out  = await loop.run_in_executor(_executor, ffmpeg_reverse, src)
        size = os.path.getsize(out)
        await sdel(wait)
        await msg.reply_video(
            out,
            caption=f"🔁 <b>Reversed</b>\n📦 {fmt_sz(size)}\n\n📣 {BRAND}",
            parse_mode=HTML, reply_markup=menu_btn(), supports_streaming=True,
        )
        await db.db_log(uid, "reverse", "")
    except Exception as e:
        log.error(f"act_reverse uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(src, out)


async def act_media_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                          file_id: str) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text("📋 Analysing media…")
    path = None
    try:
        path = await _download_tg_file(ctx, file_id, ".mp4")
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(_executor, ffmpeg_media_info, path)
        size = os.path.getsize(path)
        codec    = info.get("codec_name",  "N/A")
        width    = info.get("width",        "?")
        height   = info.get("height",       "?")
        fps_raw  = info.get("r_frame_rate", "?")
        duration = info.get("duration",     "?")
        bitrate  = info.get("bit_rate",     "?")
        # parse fps fraction e.g. "30000/1001"
        fps_str = fps_raw
        if "/" in str(fps_raw):
            try:
                n, d = fps_raw.split("/")
                n_int, d_int = int(n), int(d)
                if d_int != 0:  # SAFETY: Prevent division by zero
                    fps_str = f"{n_int // d_int} fps"
                else:
                    fps_str = str(fps_raw)
            except (ValueError, ZeroDivisionError):
                fps_str = str(fps_raw)
        dur_str = fmt_dur(duration) if duration not in ("N/A", "?") else "?"
        lines = [
            "📋 <b>Media Info</b>\n",
            f"📐 Resolution : <code>{width}×{height}</code>",
            f"🎬 Codec      : <code>{h(codec)}</code>",
            f"🎞️ FPS        : <code>{fps_str}</code>",
            f"⏱ Duration   : <code>{dur_str}</code>",
            f"📡 Bitrate    : <code>{h(bitrate)}</code>",
            f"📦 File size  : <code>{fmt_sz(size)}</code>",
        ]
        await sedit(wait, "\n".join(lines), reply_markup=menu_btn())
        await db.db_log(uid, "media_info", "")
    except Exception as e:
        log.error(f"act_media_info uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(path)


async def act_merge(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                    video_id: str, audio_id: str) -> None:
    msg  = update.effective_message
    uid  = update.effective_user.id
    wait = await msg.reply_text("🔀 Merging audio + video…")
    vpath = apath = out = None
    try:
        vpath, apath = await asyncio.gather(
            _download_tg_file(ctx, video_id, ".mp4"),
            _download_tg_file(ctx, audio_id, ".mp3"),
        )
        loop = asyncio.get_running_loop()
        out  = await loop.run_in_executor(_executor, ffmpeg_merge, vpath, apath)
        size = os.path.getsize(out)
        await sdel(wait)
        await msg.reply_video(
            out,
            caption=f"🔀 <b>Merged</b>\n📦 {fmt_sz(size)}\n\n📣 {BRAND}",
            parse_mode=HTML, reply_markup=menu_btn(), supports_streaming=True,
        )
        await db.db_log(uid, "merge", "")
    except Exception as e:
        log.error(f"act_merge uid={uid}: {e}")
        await sedit(wait,
            f"❌ <b>Merge failed</b>\n<code>{h(str(e)[:200])}</code>",
            reply_markup=main_kb())
    finally:
        clean(vpath, apath, out)


async def act_my_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user's own profile card with stats and rank."""
    msg  = update.effective_message
    uid  = update.effective_user.id
    user = update.effective_user
    lang = await get_lang(uid)

    row = await db.db_get_user(uid)
    downloads    = row["downloads"]    if row else 0
    edits        = row["edits"]        if row else 0
    recognitions = row["recognitions"] if row else 0
    joined_at    = row["joined_at"]    if row else None
    total_actions = downloads + edits + recognitions

    if total_actions == 0:     rank, badge = "Newcomer",    "🌱"
    elif total_actions < 10:   rank, badge = "Beginner",    "⭐"
    elif total_actions < 50:   rank, badge = "Regular",     "🥈"
    elif total_actions < 200:  rank, badge = "Active",      "🥇"
    elif total_actions < 500:  rank, badge = "Power User",  "💎"
    else:                      rank, badge = "Legend",      "👑"

    try:
        joined_str = joined_at.strftime("%B %d, %Y") if joined_at else "N/A"
    except Exception:
        joined_str = str(joined_at)[:10] if joined_at else "N/A"

    name  = h(user.full_name or user.first_name or "")
    uname = f"@{user.username}" if user.username else "—"

    # Progress bar to next rank
    thresholds = [0, 10, 50, 200, 500, 2000]
    bar_line   = ""
    if total_actions < 2000:
        next_t = next(v for v in thresholds if v > total_actions)
        prev_t = max(v for v in thresholds if v <= total_actions)
        filled = int(10 * (total_actions - prev_t) / max(next_t - prev_t, 1))
        bar    = "█" * filled + "░" * (10 - filled)
        bar_line = f"\n▸ Progress: [{bar}] {total_actions}/{next_t}"

    text = (
        f"👤 <b>Your Profile</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏷️ <b>Name:</b> {name}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"📅 <b>Member since:</b> {joined_str}\n"
        f"🏆 <b>Rank:</b> {badge} {rank}"
        f"{bar_line}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Statistics</b>\n"
        f"📥 Downloads: <code>{downloads}</code>\n"
        f"✂️ Edits: <code>{edits}</code>\n"
        f"🎵 Recognitions: <code>{recognitions}</code>\n"
        f"⚡ Total actions: <code>{total_actions}</code>"
    )
    await msg.reply_text(text, parse_mode=HTML, reply_markup=main_kb(lang))




# ── Button dispatch table — computed ONCE at import ─────────────────────────
from translations import _T as _ALL_STRINGS  # noqa: E402
_BTN_MAP_DEF: dict[str, tuple] = {
    "btn_download":      ("download",      "prompt_download"),
    "btn_extract_audio": ("extract_audio", "prompt_extract_audio"),
    "btn_file_audio":    ("file_audio",    "prompt_file_audio"),
    "btn_profile":       ("_myprofile",    ""),
    "btn_batch":         ("batch_dl",      "prompt_batch"),
    "btn_trim":          ("trim",          "prompt_trim"),
    "btn_compress":      ("compress",      "prompt_compress"),
    "btn_screenshot":    ("screenshot",    "prompt_screenshot"),
    "btn_gif":           ("gif",           "prompt_gif"),
    "btn_convert":       ("convert",       "prompt_convert"),
    "btn_remove_audio":  ("remove_audio",  "prompt_remove_audio"),
    "btn_merge":         ("merge_video",   "prompt_merge_video"),
    "btn_media_info":    ("media_info",    "prompt_media_info"),
    "btn_speed":         ("speed",         "prompt_speed"),
    "btn_reverse":       ("reverse",       "prompt_reverse"),
    "btn_post_info":     ("post_info",     "prompt_post_info"),
    "btn_stats":         ("_stats",        ""),
    "btn_help":          ("_help",         ""),
    "btn_movie":         ("_movie_search", ""),
}
_FLAT: dict[str, tuple] = {}
for _bk, _bv in _BTN_MAP_DEF.items():
    for _lng in ("en", "ru", "uz"):
        _txt = _ALL_STRINGS.get(_bk, {}).get(_lng, "")
        if _txt:
            _FLAT[_txt] = _bv



async def _show_admin_panel_after_auth(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel after successful passcode — avoids circular import."""
    import database as _db
    from keyboards import admin_main_kb
    uid   = update.effective_user.id
    total = await _db.db_total_users()
    banned= await _db.db_total_banned()
    ads   = await _db.db_ad_stats()
    text  = (
        "🛡 <b>Admin Panel</b>\n\n"
        f"👥 Users     : <code>{total:,}</code>\n"
        f"🚫 Banned    : <code>{banned:,}</code>\n"
        f"📢 Active ads: <code>{ads['active_ads']}</code>\n"
        f"🎬 Videos    : <code>{stats['videos']}</code>\n"
        f"🎵 Audios    : <code>{stats['audios']}</code>\n"
        f"❌ Errors    : <code>{stats['errors']}</code>"
    )
    await update.effective_message.reply_text(text, parse_mode=HTML, reply_markup=admin_main_kb())


async def _periodic_cleanup(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Called every hour by job queue to prevent memory leaks."""
    _cleanup_caches()


async def on_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update): return
    user = update.effective_user
    uid  = user.id

    # Check if user has explicitly chosen a language before
    # get_lang uses cache — no extra DB hit if already seen
    stored = await db.db_get_lang(uid)   # None = never chosen, "en"/"ru"/"uz" = explicitly set
    lang_is_set = stored in ("en", "ru", "uz")
    if not lang_is_set or waiting_for.get(uid) == "choosing_lang":
        # Fresh user or returning without a lang — always show picker
        waiting_for[uid] = "choosing_lang"
        pick_text = "\n".join([
            t("en", "choose_lang"),
            t("ru", "choose_lang"),
            t("uz", "choose_lang"),
        ])
        await update.effective_message.reply_text(pick_text, reply_markup=lang_kb())
        return

    # ── Handle deep links from inline mode ────────────────────────
    args = ctx.args  # text after /start
    if args:
        param = args[0]  # e.g. "dl_https%3A%2F%2F..."
        import urllib.parse as _up
        if param.startswith("dl_") or param.startswith("au_"):
            action  = param[:2]   # "dl" or "au"
            payload = _up.unquote(param[3:]).strip()
            if payload and is_url(payload):
                await _send_welcome(update, uid, stored)
                if action == "dl":
                    await act_video(update, ctx, payload, 2160)
                else:
                    await act_audio(update, ctx, payload)
                return
        elif param.startswith("mv_"):
            query = _up.unquote(param[3:]).strip()
            if query:
                await _send_welcome(update, uid, stored)
                lang = await get_lang(uid)
                wait = await update.effective_message.reply_text(
                    t(lang, "movie_searching", query=h(query[:50])), parse_mode=HTML)
                from moviebox_tools import mb_search
                results = await mb_search(query, limit=20)
                if not results:
                    await sedit(wait,
                        t(lang, "movie_no_results", query=h(query[:50])),
                        reply_markup=main_kb(lang))
                else:
                    uid2 = update.effective_user.id
                    _movie_results[uid2] = results
                    _movie_page[uid2]    = 0
                    await sedit(wait,
                        _movie_page_text(uid2, 0),
                        reply_markup=_movie_page_kb(uid2, 0, len(results)))
                return

    await _send_welcome(update, uid, stored)
    await db.db_track("commands")


async def _send_welcome(update: Update, uid: int, lang: str) -> None:
    user = update.effective_user
    await update.effective_message.reply_text(
        t(lang, "welcome",
          name=h(user.first_name or "there"),
          brand=BRAND,
          channel=CHANNEL),
        parse_mode=HTML,
        disable_web_page_preview=True,
        reply_markup=main_kb(lang),
    )

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: C901
    if not await guard(update): return
    msg  = update.effective_message
    uid  = update.effective_user.id
    text = (msg.text or "").strip()
    pend = waiting_for.get(uid)

    # ── Admin password ────────────────────────────────────────────────────
    if pend == "admin_pass" and is_admin(uid):
        # delete the password message for security
        try:
            await msg.delete()
        except Exception:
            pass
        prompt = _auth_prompt_msg.pop(uid, None)
        if prompt:
            try: await prompt.delete()
            except Exception: pass

        now    = time.time()
        fails  = _fail_counts.get(uid, 0)
        f_time = _fail_times.get(uid, 0)

        # reset counter if window expired
        if now - f_time > FAIL_WINDOW:
            _fail_counts[uid] = 0
            fails = 0

        if fails >= MAX_FAILS:
            remaining = int(FAIL_WINDOW - (now - f_time))
            await msg.chat.send_message(
                f"🔒 Too many failed attempts.  Try again in {remaining}s.",
                reply_markup=main_kb())
            await db.db_security_log(uid, "lockout", f"fails={fails}")
            return

        if text == ADMIN_PASS:
            _admin_auth[uid]  = True
            _fail_counts[uid] = 0
            waiting_for.pop(uid, None)
            await msg.chat.send_message(
                "✅ <b>Authenticated!</b>  Welcome to the admin panel.",
                parse_mode=HTML, reply_markup=main_kb())
            await db.db_security_log(uid, "admin_login", "success")
            # Re-trigger admin panel
            # Re-open admin panel after successful auth
            await _show_admin_panel_after_auth(update, ctx)
        else:
            _fail_counts[uid] = fails + 1
            _fail_times.setdefault(uid, now)
            left = MAX_FAILS - _fail_counts[uid]
            await msg.chat.send_message(
                f"❌ Wrong passcode.  {left} attempt(s) left.",
                reply_markup=main_kb())
            await db.db_security_log(uid, "wrong_pass", f"attempt={fails+1}")
        return

    # ── Admin text broadcast ──────────────────────────────────────────────
    if pend == "admin_broadcast_text" and is_admin_authed(uid):
        waiting_for.pop(uid)
        users = await db.db_all_users()
        # build a plain-text broadcast
        ok = fail = 0
        status = await msg.reply_text(
            f"📣 Broadcasting to <b>{len(users)}</b> users…", parse_mode=HTML)
        for i, row in enumerate(users):
            try:
                await ctx.bot.send_message(row["uid"], text, parse_mode=HTML)
                ok += 1
            except Exception:
                fail += 1
            await asyncio.sleep(1.0 if (i > 0 and i % 25 == 0) else 0.04)
        await sedit(status,
            f"✅ <b>Broadcast done!</b>\n✅ {ok} delivered  │  ❌ {fail} failed")
        return

    # ── Admin user-management states ──────────────────────────────────────
    if pend == "admin_finduser" and is_admin_authed(uid):
        waiting_for.pop(uid)
        try:
            target = int(text.strip())
            user_r = await db.db_get_user(target)
            if not user_r:
                await msg.reply_text("❌ User not found.", reply_markup=main_kb())
                return
            u = dict(user_r)
            lines = [
                f"👤 <b>User #{u['uid']}</b>",
                f"Name     : {h(u.get('full_name',''))}",
                f"Username : @{h(u.get('username',''))}",
                f"Joined   : {str(u.get('joined_at',''))[:10]}",
                f"Downloads: {u.get('downloads',0)}",
                f"Banned   : {'Yes ⛔' if u.get('is_banned') else 'No ✅'}",
            ]
            if u.get("ban_reason"):
                lines.append(f"Reason   : {h(u['ban_reason'])}")
            await msg.reply_text("\n".join(lines), parse_mode=HTML,
                                 reply_markup=IKM([[
                                     Btn("🚫 Ban",   callback_data=f"adm_ban|{target}"),
                                     Btn("✅ Unban", callback_data=f"adm_unban|{target}"),
                                 ]]))
        except (ValueError, TypeError):
            await msg.reply_text("⚠️ Send a numeric user ID.", reply_markup=main_kb())
        return

    if pend == "admin_banuser" and is_admin_authed(uid):
        waiting_for.pop(uid)
        parts  = text.split(None, 1)
        reason = parts[1] if len(parts) > 1 else "Banned by admin"
        try:
            target = int(parts[0])
            await db.db_ban(target, reason)
            await db.db_log(uid, "ban", f"target={target} reason={reason}")
            await msg.reply_text(
                f"🚫 User <code>{target}</code> banned.\nReason: {h(reason)}",
                parse_mode=HTML, reply_markup=main_kb())
            try:
                await ctx.bot.send_message(target, "🚫 You have been banned from this bot.")
            except Exception:
                pass
        except (ValueError, IndexError):
            await msg.reply_text("⚠️ Format: <code>USER_ID [reason]</code>",
                                 parse_mode=HTML, reply_markup=main_kb())
        return

    if pend == "admin_unbanuser" and is_admin_authed(uid):
        waiting_for.pop(uid)
        try:
            target = int(text.strip())
            await db.db_unban(target)
            await db.db_log(uid, "unban", f"target={target}")
            await msg.reply_text(
                f"✅ User <code>{target}</code> unbanned.",
                parse_mode=HTML, reply_markup=main_kb())
            try:
                await ctx.bot.send_message(target, "✅ You have been unbanned!")
            except Exception:
                pass
        except ValueError:
            await msg.reply_text("⚠️ Send a numeric user ID.", reply_markup=main_kb())
        return

    # ── Ad wizard ─────────────────────────────────────────────────────────
    if pend == "ad_wizard_name" and is_admin_authed(uid):
        pending_op[uid] = {**pending_op.get(uid, {}), "name": text}
        waiting_for[uid] = "ad_wizard_media"
        await msg.reply_text(
            f"✅ Name: <b>{h(text)}</b>\n\nStep 2/4 — Send the ad media (photo/video/GIF)\nor type <code>text</code> for a text-only ad:",
            parse_mode=HTML, reply_markup=cancel_btn())
        return

    if pend == "ad_wizard_media" and is_admin_authed(uid):
        # text-only ad path
        if text.lower() == "text":
            pending_op[uid] = {**pending_op.get(uid, {}), "media_type": "text", "file_id": None}
            waiting_for[uid] = "ad_wizard_caption"
            await msg.reply_text(
                "✅ Text ad selected.\nStep 3/4 — Send the ad caption:",
                reply_markup=cancel_btn())
        else:
            await msg.reply_text(
                "📤 Please send the actual media file (photo/video/GIF).\n"
                "Or type <code>text</code> for a text-only ad.",
                parse_mode=HTML, reply_markup=cancel_btn())
        return

    if pend == "ad_wizard_caption" and is_admin_authed(uid):
        cap = None if text.lower() == "skip" else text
        pending_op[uid] = {**pending_op.get(uid, {}), "caption": cap}
        waiting_for[uid] = "ad_wizard_url"
        await msg.reply_text(
            "Step 4/4 — Send button URL (or <code>skip</code>):",
            parse_mode=HTML, reply_markup=cancel_btn())
        return

    if pend == "ad_wizard_url" and is_admin_authed(uid):
        url = None if text.lower() == "skip" else text
        pending_op[uid] = {**pending_op.get(uid, {}), "url": url}
        waiting_for[uid] = "ad_wizard_btn"
        await msg.reply_text(
            "Button label (or <code>skip</code>):",
            parse_mode=HTML, reply_markup=cancel_btn())
        return

    if pend == "ad_wizard_btn" and is_admin_authed(uid):
        btn_label = None if text.lower() == "skip" else text
        op = pending_op.pop(uid, {})
        waiting_for.pop(uid, None)
        ad_id = await db.db_add_admin_ad(
            name=op.get("name", "Ad"),
            media_type=op.get("media_type", "text"),
            caption=op.get("caption"),
            file_id=op.get("file_id"),
            url=op.get("url"),
            button_label=btn_label,
        )
        await db.db_log(uid, "create_ad", f"id={ad_id}")
        await msg.reply_text(
            f"✅ <b>Ad #{ad_id} created!</b>",
            parse_mode=HTML, reply_markup=main_kb())
        return

    if pend == "adp_send_ad_id" and is_admin_authed(uid):
        waiting_for.pop(uid)
        try:
            ad_id    = int(text.strip())
            ads_list = await db.db_list_ads()
            ad       = next((a for a in ads_list if a["id"] == ad_id), None)
            if not ad:
                await msg.reply_text("❌ Ad not found.", reply_markup=main_kb())
                return
            if not ad["active"]:
                await msg.reply_text(
                    f"⛔ Ad #{ad_id} is <b>paused</b>. Activate it first before sending.",
                    parse_mode=HTML, reply_markup=main_kb())
                return
            users = await db.db_all_users()
            ok = fail = 0
            cap = ad.get("caption") or ""
            mt  = ad.get("media_type", "text")
            kb  = None
            if ad.get("url") and ad.get("button_label"):
                kb = IKM([[Btn(str(ad["button_label"]), url=str(ad["url"]))]])
            status = await msg.reply_text(
                f"📢 Sending ad #{ad_id} to {len(users)} users…")
            for i, row in enumerate(users):
                try:
                    target = row["uid"]
                    if   mt == "photo"     and ad.get("file_id"):
                        await ctx.bot.send_photo(target, ad["file_id"], caption=cap, reply_markup=kb, parse_mode=HTML)
                    elif mt == "video"     and ad.get("file_id"):
                        await ctx.bot.send_video(target, ad["file_id"], caption=cap, reply_markup=kb, parse_mode=HTML)
                    elif mt == "animation" and ad.get("file_id"):
                        await ctx.bot.send_animation(target, ad["file_id"], caption=cap, reply_markup=kb, parse_mode=HTML)
                    elif cap:
                        await ctx.bot.send_message(target, cap, reply_markup=kb, parse_mode=HTML)
                    ok += 1
                    await db.db_imp_ad(ad_id)
                except Exception:
                    fail += 1
                await asyncio.sleep(1.0 if (i > 0 and i % 25 == 0) else 0.04)
            await sedit(status, f"✅ Ad sent!  ✅{ok}  ❌{fail}")
        except ValueError:
            await msg.reply_text("⚠️ Send a numeric ad ID.", reply_markup=main_kb())
        return

    if pend == "adp_edit_ad_field" and is_admin_authed(uid):
        waiting_for.pop(uid)
        op    = pending_op.pop(uid, {})
        ad_id = op.get("edit_ad_id")
        parts = text.split(None, 1)
        if len(parts) < 2 or not ad_id:
            await msg.reply_text("⚠️ Format: <code>field value</code>",
                                 parse_mode=HTML, reply_markup=main_kb())
            return
        field, value = parts[0].lower(), parts[1]
        kw: dict = {}
        if field == "name":         kw["name"]         = value
        elif field == "caption":    kw["caption"]      = value
        elif field == "url":        kw["url"]          = value
        elif field == "label":      kw["button_label"] = value
        else:
            await msg.reply_text(
                "⚠️ Valid fields: <code>name</code> <code>caption</code> "
                "<code>url</code> <code>label</code>",
                parse_mode=HTML, reply_markup=main_kb())
            return
        await db.db_update_ad(ad_id, **kw)
        await db.db_log(uid, "edit_ad", f"id={ad_id} {field}=…")
        await msg.reply_text(f"✅ Ad #{ad_id} updated.", reply_markup=main_kb())
        return

    # ── Music search states ───────────────────────────────────────────────
    if pend == "music_link":
        waiting_for.pop(uid)
        if is_url(text):
            await act_music_url(update, ctx, text)
        else:
            await msg.reply_text("⚠️ That doesn't look like a URL.", reply_markup=main_kb())
        return

    if pend == "music_text":
        waiting_for.pop(uid)
        wait = await msg.reply_text(f"🔍 Searching for <b>{h(text)}</b>…", parse_mode=HTML)
        try:
            results = await search_song(text, limit=20)
            if not results:
                await sedit(wait, "❓ No results found.", reply_markup=main_kb())
                return
            _music_results[uid] = results
            _music_page[uid]    = 0
            await sedit(wait,
                _music_page_text(uid, 0),
                reply_markup=_music_page_kb(uid, 0, len(results)))
            stats["music"] += 1
            await db.db_track("music")
            await db.db_inc_recognitions(uid)
            await db.db_log(uid, "music_search", text[:100])
        except Exception as e:
            log.error(f"music_text uid={uid}: {e}")
            await sedit(wait,
                f"❌ Search failed: <code>{h(str(e)[:200])}</code>",
                reply_markup=main_kb())
        return

    # ── Trim timestamp ────────────────────────────────────────────────────
    if pend == "trim_ts":
        op = pending_op.get(uid, {})
        fid = op.get("file_id")
        if not fid:
            waiting_for.pop(uid, None)
            await msg.reply_text("⚠️ Session expired. Send the video again.", reply_markup=main_kb())
            return
        # parse "0:30 - 1:45" or "30 105"
        import re as _re
        m = _re.split(r"[\s\-–—]+", text.strip())
        parts_t = [p for p in m if p]
        if len(parts_t) >= 2:
            s = parse_time(parts_t[0])
            e = parse_time(parts_t[-1])
        else:
            s = e = None
        if s is None or e is None or e <= s:
            await msg.reply_text(
                "⚠️ Invalid timestamps.  Use format:\n"
                "<code>0:30 - 1:45</code>  or  <code>30 105</code>",
                parse_mode=HTML, reply_markup=cancel_btn())
            return
        waiting_for.pop(uid)
        pending_op.pop(uid, None)
        await act_trim(update, ctx, fid, s, e)
        return

    # ── Screenshot timestamp ──────────────────────────────────────────────
    if pend == "ss_ts":
        op  = pending_op.get(uid, {})
        fid = op.get("file_id")
        if not fid:
            waiting_for.pop(uid, None)
            await msg.reply_text("⚠️ Session expired.", reply_markup=main_kb())
            return
        ts = parse_time(text)
        if ts is None:
            await msg.reply_text(
                "⚠️ Invalid timestamp.  Use: <code>1:23</code> or <code>83</code>",
                parse_mode=HTML, reply_markup=cancel_btn())
            return
        waiting_for.pop(uid)
        pending_op.pop(uid, None)
        await act_screenshot(update, ctx, fid, ts)
        return

    # ── GIF timestamps ────────────────────────────────────────────────────
    if pend == "gif_ts":
        op  = pending_op.get(uid, {})
        fid = op.get("file_id")
        if not fid:
            waiting_for.pop(uid, None)
            await msg.reply_text("⚠️ Session expired.", reply_markup=main_kb())
            return
        m = _re.split(r"[\s\-–—]+", text.strip())
        parts_g = [p for p in m if p]
        if len(parts_g) >= 2:
            s = parse_time(parts_g[0])
            e = parse_time(parts_g[-1])
        else:
            s = e = None
        if s is None or e is None or e <= s:
            await msg.reply_text(
                "⚠️ Invalid range.  Use: <code>0:10 - 0:20</code>",
                parse_mode=HTML, reply_markup=cancel_btn())
            return
        if e - s > 15:
            await msg.reply_text(
                "⚠️ Max GIF duration is 15 seconds.",
                reply_markup=cancel_btn())
            return
        waiting_for.pop(uid)
        pending_op.pop(uid, None)
        await act_gif(update, ctx, fid, s, e)
        return

    # ── Profile username ──────────────────────────────────────────────────
    if pend == "profile":
        # If user pressed a menu button instead of typing a username — cancel the state
        if text in _FLAT or text in {"🔍 Find Music","🔍 Найти музыку","🔍 Musiqa topish"}:
            waiting_for.pop(uid, None)
            # fall through to normal dispatch below
        else:
            waiting_for.pop(uid)
            username = text.lstrip("@").split("/")[-1].strip()
            if not username or len(username) > 100:
                lang = await get_lang(uid)
                await msg.reply_text(t(lang, "prompt_profile"), parse_mode=HTML, reply_markup=cancel_btn())
                waiting_for[uid] = "profile"  # keep waiting
                return
            await act_my_profile(update, ctx)
            return

    # ── Batch download ────────────────────────────────────────────────────
    if pend == "movie_search":
        waiting_for.pop(uid)
        lang = await get_lang(uid)
        # MovieAuto.run(title) searches AND downloads in one step.
        # Skip the paginated list — go straight to quality picker.
        title_clean = text.strip()
        await msg.reply_text(
            f"🎬 <b>{h(title_clean)}</b>\n\n"
            f"Choose quality to download:",
            parse_mode=HTML,
            reply_markup=_movie_quality_direct_kb(title_clean))
        return

    if pend == "batch_dl":
        waiting_for.pop(uid)
        urls = [line.strip() for line in text.splitlines() if is_url(line.strip())]
        if not urls:
            await msg.reply_text("⚠️ No valid URLs found.", reply_markup=main_kb())
            return
        # Cap at 10 URLs per batch to reduce load and abuse potential
        urls = urls[:10]
        status = await msg.reply_text(
            f"⬇️ Starting <b>{len(urls)}</b> download(s)…\n"
            "<i>Each will be sent as it finishes.</i>",
            parse_mode=HTML)
        ok = fail = 0
        for i, url in enumerate(urls):
            try:
                plat, _ = detect_platform(url)
                if plat == "Unknown":
                    fail += 1
                    continue
                await act_video(update, ctx, url, 720)
                ok += 1
                # Small pause between downloads to avoid overloading resources
                await asyncio.sleep(0.5)
            except Exception as e:
                fail += 1
                log.warning(f"batch_dl url={url}: {e}")
        await sedit(status,
            f"✅ Batch done — <b>{ok}</b> delivered, <b>{fail}</b> failed.",
            reply_markup=main_kb())
        return

    # ── Main-keyboard button dispatching — uses module-level _FLAT dict ────────
    if text in _FLAT:
        lang = await get_lang(uid)
        state, prompt_key = _FLAT[text]
        if state == "_myprofile":
            await act_my_profile(update, ctx)
            return
        if state == "_movie_search":
            lang = await get_lang(uid)
            await msg.reply_text(
                t(lang, "prompt_movie_search"),
                parse_mode=HTML, reply_markup=cancel_btn())
            waiting_for[uid] = "movie_search"
            return
        if state == "_stats":
            # inline stats handling
            if is_admin_authed(uid):
                d = await db.db_stats_overview()
                u = d.get("users", {})
                td = d.get("today", {})
                a = d.get("ads", {})
                lines_s = [
                    t(lang, "btn_stats") + "\n",
                    f"👥 {int(u.get('total',0)):,}  │  🚫 {int(u.get('banned',0)):,}  │  📅 +{int(u.get('today',0))}",
                    f"⬇️ {int(u.get('total_downloads',0)):,} total downloads",
                    "",
                    f"🎬 {td.get('videos',0)}  🎵 {td.get('audios',0)}  🎶 {td.get('music',0)}  ❌ {td.get('errors',0)}",
                    f"📢 Active ads: {a.get('active_ads',0)}",
                ]
                await msg.reply_text("\n".join(lines_s), parse_mode=HTML, reply_markup=main_kb(lang))
            else:
                # Non-admin: show full profile card (same as My Profile button)
                await act_my_profile(update, ctx)
            return
        if state == "_help":
            lang = await get_lang(uid)
            await msg.reply_text(
                t(lang, "help", brand=BRAND, channel=CHANNEL),
                parse_mode=HTML,
                disable_web_page_preview=True,
                reply_markup=main_kb(lang))
            return
        waiting_for[uid] = state
        await msg.reply_text(t(lang, prompt_key), parse_mode=HTML, reply_markup=cancel_btn())
        await db.db_track("commands")
        return

    # ── Language change button (matches any language's translation) ─────────
    lang_btns = {"🌐 Language", "🌐 Язык", "🌐 Til"}
    if text in lang_btns:
        lang = await get_lang(uid)
        await msg.reply_text(
            t(lang, "btn_language"),
            reply_markup=change_lang_kb(lang))
        return

    if text == "🔍 Find Music" or text == "🔍 Найти музыку" or text == "🔍 Musiqa topish":
        lang = await get_lang(uid)
        await msg.reply_text(
            t(lang, "prompt_music_how"),
            parse_mode=HTML, reply_markup=music_src_kb())
        return





    # ── URL auto-detection ────────────────────────────────────────────────
    if is_url(text):
        if not is_supported_url(text):
            await msg.reply_text(
                "⚠️ Platform not supported yet.\n"
                "Supported: YouTube, Instagram, TikTok, Twitter/X, Facebook, Pinterest",
                reply_markup=main_kb())
            return
        plat, icon = detect_platform(text)
        k = cb_put(text)
        # honour pending download/audio/info state
        if pend == "download":
            waiting_for.pop(uid, None)
        if pend == "extract_audio":
            waiting_for.pop(uid, None)
            await act_audio(update, ctx, text)
            return
        if pend == "post_info":
            waiting_for.pop(uid, None)
            await act_info(update, ctx, text)
            return
        if pend == "music_link":
            waiting_for.pop(uid, None)
            await act_music_url(update, ctx, text)
            return
        lang = await get_lang(uid)
        await msg.reply_text(
            t(lang, "url_detected", icon=icon, platform=h(plat)),
            parse_mode=HTML, reply_markup=action_kb(k))
        return

    # ── Fallback ──────────────────────────────────────────────────────────
    lang = await get_lang(uid)
    await msg.reply_text(t(lang, "fallback"), reply_markup=main_kb(lang))


# ═══════════════════════════════════════════════════════════════════════════
#  FILE HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

async def on_photo_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update): return
    msg = update.effective_message
    uid = update.effective_user.id
    if not msg.photo: return

    cap  = msg.caption or ""
    pend = waiting_for.get(uid)

    if cap.startswith("/broadcast") and is_admin_authed(uid):
        caption_text = cap[len("/broadcast"):].strip() or None
        users = await db.db_all_users()
        await _do_broadcast(ctx, msg, users, caption_text)
        return

    if pend == "admin_broadcast_text" and is_admin_authed(uid):
        waiting_for.pop(uid)
        users = await db.db_all_users()
        await _do_broadcast(ctx, msg, users, cap or None)
        return

    if pend == "ad_wizard_media" and is_admin_authed(uid):
        file_id = msg.photo[-1].file_id
        pending_op[uid] = {**pending_op.get(uid, {}),
                           "media_type": "photo", "file_id": file_id}
        waiting_for[uid] = "ad_wizard_caption"
        await msg.reply_text(
            "✅ Photo received!\nStep 3/4 — Send caption (or <code>skip</code>):",
            parse_mode=HTML, reply_markup=cancel_btn())


async def on_animation_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update): return
    msg = update.effective_message
    uid = update.effective_user.id
    if not msg.animation: return

    cap  = msg.caption or ""
    pend = waiting_for.get(uid)

    if cap.startswith("/broadcast") and is_admin_authed(uid):
        caption_text = cap[len("/broadcast"):].strip() or None
        users = await db.db_all_users()
        await _do_broadcast(ctx, msg, users, caption_text)
        return

    if pend == "admin_broadcast_text" and is_admin_authed(uid):
        waiting_for.pop(uid)
        users = await db.db_all_users()
        await _do_broadcast(ctx, msg, users, cap or None)
        return

    if pend == "ad_wizard_media" and is_admin_authed(uid):
        pending_op[uid] = {**pending_op.get(uid, {}),
                           "media_type": "animation", "file_id": msg.animation.file_id}
        waiting_for[uid] = "ad_wizard_caption"
        await msg.reply_text(
            "✅ GIF received!\nStep 3/4 — Send caption (or <code>skip</code>):",
            parse_mode=HTML, reply_markup=cancel_btn())


async def on_video_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update): return
    msg  = update.effective_message
    uid  = update.effective_user.id
    tgf  = msg.video or msg.document
    if not tgf: return
    size = getattr(tgf, "file_size", 0) or 0
    cap  = msg.caption or ""
    pend = waiting_for.get(uid)

    if cap.startswith("/broadcast") and is_admin_authed(uid):
        caption_text = cap[len("/broadcast"):].strip() or None
        users = await db.db_all_users()
        await _do_broadcast(ctx, msg, users, caption_text)
        return

    if pend == "admin_broadcast_text" and is_admin_authed(uid):
        waiting_for.pop(uid)
        caption_text = cap if cap and not cap.startswith("/broadcast") else None
        users = await db.db_all_users()
        await _do_broadcast(ctx, msg, users, caption_text)
        return

    if pend == "ad_wizard_media" and is_admin_authed(uid):
        pending_op[uid] = {**pending_op.get(uid, {}),
                           "media_type": "video", "file_id": tgf.file_id}
        waiting_for[uid] = "ad_wizard_caption"
        await msg.reply_text(
            "✅ Video received!\nStep 3/4 — Send caption (or <code>skip</code>):",
            parse_mode=HTML, reply_markup=cancel_btn())
        return

    if size > MAX_MB * 1024 * 1024:
        await msg.reply_text(
            f"⚠️ <b>File too large</b> ({fmt_sz(size)})\n"
            f"Bots can only handle files up to {MAX_MB} MB.",
            parse_mode=HTML, reply_markup=main_kb())
        return

    name = getattr(tgf, "file_name", None) or "video"
    k    = cb_put(tgf.file_id)

    if pend == "file_audio":
        waiting_for.pop(uid)
        await act_file_audio(update, ctx, tgf.file_id)
    elif pend == "compress":
        waiting_for.pop(uid)
        pending_op[uid] = {"file_id": tgf.file_id}
        await msg.reply_text(
            f"📄 <code>{h(name)}</code>  │  📦 {fmt_sz(size)}\n\nChoose compression level:",
            parse_mode=HTML, reply_markup=compress_kb(k))
    elif pend == "convert":
        waiting_for.pop(uid)
        pending_op[uid] = {"file_id": tgf.file_id}
        await msg.reply_text(
            f"📄 <code>{h(name)}</code>  │  📦 {fmt_sz(size)}\n\nChoose output format:",
            parse_mode=HTML, reply_markup=convert_kb(k))
    elif pend == "remove_audio":
        waiting_for.pop(uid)
        await act_remove_audio(update, ctx, tgf.file_id)
    elif pend == "speed":
        waiting_for.pop(uid)
        pending_op[uid] = {"file_id": tgf.file_id}
        await msg.reply_text(
            f"⚡ <b>Video received!</b>  📦 {fmt_sz(size)}\n\nChoose speed:",
            parse_mode=HTML, reply_markup=speed_kb(k))
    elif pend == "reverse":
        waiting_for.pop(uid)
        await act_reverse(update, ctx, tgf.file_id)
    elif pend == "media_info":
        waiting_for.pop(uid)
        await act_media_info(update, ctx, tgf.file_id)
    elif pend == "trim":
        waiting_for[uid] = "trim_ts"
        pending_op[uid]  = {"file_id": tgf.file_id}
        await msg.reply_text(
            f"✂️ <b>Video received!</b>  📦 {fmt_sz(size)}\n\n"
            "Send <b>start and end time</b>:\n"
            "<code>0:30 - 1:45</code>  or  <code>30 105</code>",
            parse_mode=HTML, reply_markup=cancel_btn())
    elif pend == "screenshot":
        waiting_for[uid] = "ss_ts"
        pending_op[uid]  = {"file_id": tgf.file_id}
        await msg.reply_text(
            f"📸 <b>Video received!</b>  📦 {fmt_sz(size)}\n\n"
            "Send the <b>timestamp</b>:\n<code>1:23</code>  or  <code>83</code>",
            parse_mode=HTML, reply_markup=cancel_btn())
    elif pend == "gif":
        waiting_for[uid] = "gif_ts"
        pending_op[uid]  = {"file_id": tgf.file_id}
        await msg.reply_text(
            f"🎞️ <b>Video received!</b>  📦 {fmt_sz(size)}\n\n"
            "Send <b>start and end time</b> (max 15s):\n<code>0:10 - 0:20</code>",
            parse_mode=HTML, reply_markup=cancel_btn())
    elif pend == "merge_video":
        waiting_for[uid] = "merge_audio"
        pending_op[uid]  = {"video_id": tgf.file_id}
        await msg.reply_text(
            f"✅ Video received!  📦 {fmt_sz(size)}\n\n"
            "Now send the <b>audio file</b> to merge.",
            parse_mode=HTML, reply_markup=cancel_btn())
    else:
        await msg.reply_text(
            f"🎬 <b>Video received!</b>\n"
            f"📄 <code>{h(name)}</code>  │  📦 {fmt_sz(size)}\n\n"
            "What would you like to do?",
            parse_mode=HTML, reply_markup=file_kb(k))


async def on_audio_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update): return
    msg  = update.effective_message
    uid  = update.effective_user.id
    tgf  = msg.audio or msg.voice
    if not tgf: return
    size = getattr(tgf, "file_size", 0) or 0
    pend = waiting_for.get(uid)

    if pend == "music_file":
        if size > MAX_MB * 1024 * 1024:
            await msg.reply_text("⚠️ Audio too large (50 MB limit).", reply_markup=main_kb())
            return
        waiting_for.pop(uid)
        await act_music_file(update, ctx, tgf.file_id, tgf)
    elif pend == "merge_audio":
        op  = pending_op.get(uid, {})
        vid = op.get("video_id")
        waiting_for.pop(uid)
        pending_op.pop(uid, None)
        if vid:
            await act_merge(update, ctx, vid, tgf.file_id)
        else:
            await msg.reply_text("⚠️ Session expired. Start again.", reply_markup=main_kb())
    else:
        k = cb_put(tgf.file_id)
        await msg.reply_text(
            "🎵 <b>Audio received!</b>\n\nIdentify this music?",
            parse_mode=HTML,
            reply_markup=IKM([
                [Btn("🔍 Identify Music", callback_data=f"ra|{k}")],
                [Btn("❌ Cancel",         callback_data="cancel")],
            ]))


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: C901
    if not await guard(update): return
    q    = update.callback_query
    await q.answer()
    data = q.data or ""
    uid  = update.effective_user.id
    msg  = update.effective_message

    async def expired():
        return await msg.reply_text("⚠️ Session expired. Start again.", reply_markup=main_kb())

    if data == "cancel":
        lang = await get_lang(uid)
        waiting_for.pop(uid, None)
        pending_op.pop(uid, None)
        await sdel(q.message)
        await msg.reply_text(t(lang, "cancelled"), reply_markup=main_kb(lang))
        return

    if data.startswith("setlang|"):
        chosen = data[8:]
        if chosen not in LANGS:
            await q.answer("Unknown language", show_alert=True)
            return
        was_choosing = waiting_for.pop(uid, None) == "choosing_lang"
        await db.db_set_lang(uid, chosen)
        _lang_cache[uid] = chosen
        await q.answer(t(chosen, "lang_set"))
        await sdel(q.message)
        if was_choosing:
            # First-time setup complete — show welcome
            await _send_welcome(update, uid, chosen)
            await db.db_track("commands")
        else:
            # User changed language from menu
            await msg.reply_text(
                t(chosen, "lang_changed"),
                reply_markup=main_kb(chosen))
        return

    if data.startswith("ba|"):
        url = cb_get(data[3:])
        if not url: await expired(); return
        plat, icon = detect_platform(url)
        k = cb_put(url)
        await sedit(q.message,
            f"{icon} <b>{h(plat)}</b>\n\nWhat would you like to do?",
            reply_markup=action_kb(k))
        return

    if data.startswith("mv|"):
        url = cb_get(data[3:])
        if not url: await expired(); return
        plat, icon = detect_platform(url)
        if plat in ("YouTube", "Facebook", "Twitter/X"):
            # Fetch available formats and show only what exists
            await sedit(q.message, "⏳ Checking available resolutions…")
            try:
                loop = asyncio.get_running_loop()
                info = await asyncio.wait_for(
                    loop.run_in_executor(_executor, _dl_info, url), timeout=20)
                fmts = info.get("formats", []) if info else []
                heights = sorted(set(
                    f.get("height") for f in fmts
                    if isinstance(f.get("height"), int) and f["height"] > 0
                ), reverse=True)
                title = h((info.get("title") or plat)[:80]) if info else h(plat)
                dur   = fmt_dur(info.get("duration")) if info else ""
                dur_s = f"  ⏱ {dur}" if dur else ""
                avail = [h for h in heights if h in (360, 480, 720, 1080, 1440, 2160)]
                if not avail:
                    avail = [720]  # fallback
                header = f"{icon} <b>{title}</b>{dur_s}\n\n📺 Choose quality:"
                await sedit(q.message, header,
                            reply_markup=quality_kb_avail(data[3:], avail))
            except Exception:
                # Info fetch failed — show default picker
                await sedit(q.message, "📺 <b>Choose quality:</b>",
                            reply_markup=quality_kb(data[3:]))
        else:
            # Instagram, TikTok, Pinterest — best available directly
            await sdel(q.message)
            await act_video(update, ctx, url, 2160)
        return

    if data.startswith("dv|"):
        parts = data.split("|", 2)
        if len(parts) != 3: return
        _, q_str, key = parts
        url = cb_get(key)
        if not url: await expired(); return
        _VALID_Q = {360, 720, 1080, 2160}
        try: q_int = int(q_str)
        except (ValueError, TypeError): return
        if q_int not in _VALID_Q: return
        await sdel(q.message)
        wait = rate_check(uid, RATE_SEC)
        if wait:
            await msg.reply_text(f"⏳ Wait <b>{wait}s</b>.", parse_mode=HTML, reply_markup=main_kb())
            return
        await act_video(update, ctx, url, q_int)
        return

    if data.startswith("au|"):
        url = cb_get(data[3:])
        if not url: await expired(); return
        await sdel(q.message)
        await act_audio(update, ctx, url)
        return

    if data.startswith("ms|"):
        src = data[3:]
        waiting_for[uid] = {"link": "music_link", "file": "music_file",
                             "text": "music_text"}.get(src, "music_link")
        lang = await get_lang(uid)
        prompts = {
            "link": t(lang, "prompt_music_link"),
            "file": t(lang, "prompt_music_file"),
            "text": t(lang, "prompt_music_text"),
        }
        await sedit(q.message, prompts.get(src, t(lang, "prompt_music_link")), reply_markup=cancel_btn())
        return

    if data.startswith("ml|"):
        url = cb_get(data[3:])
        if not url: await expired(); return
        await sdel(q.message)
        await act_music_url(update, ctx, url)
        return

    if data.startswith("vi|"):
        url = cb_get(data[3:])
        if not url: await expired(); return
        await sdel(q.message)
        await act_info(update, ctx, url)
        return

    if data.startswith("xf|"):
        fid = cb_get(data[3:])
        if not fid: await expired(); return
        await sdel(q.message)
        await act_file_audio(update, ctx, fid)
        return

    if data.startswith("ra|"):
        fid = cb_get(data[3:])
        if not fid: await expired(); return
        await sdel(q.message)
        await act_music_file(update, ctx, fid)
        return

    if data.startswith("ra2|"):
        fid = cb_get(data[4:])
        if not fid: await expired(); return
        await sdel(q.message)
        await act_remove_audio(update, ctx, fid)
        return

    if data.startswith("mi|"):
        fid = cb_get(data[3:])
        if not fid: await expired(); return
        await sdel(q.message)
        await act_media_info(update, ctx, fid)
        return

    if data.startswith("tr|"):
        fid = cb_get(data[3:])
        if not fid: await expired(); return
        await sdel(q.message)
        waiting_for[uid] = "trim_ts"
        pending_op[uid]  = {"file_id": fid}
        await msg.reply_text(
            "✂️ Send <b>start and end time</b>:\n"
            "<code>0:30 - 1:45</code>  or  <code>30 105</code>",
            parse_mode=HTML, reply_markup=cancel_btn())
        return

    if data.startswith("cp|"):
        fid = cb_get(data[3:])
        if not fid: await expired(); return
        pending_op[uid] = {"file_id": fid}
        await sedit(q.message, "🗜️ Choose compression level:",
                    reply_markup=compress_kb(data[3:]))
        return

    if data.startswith("cpdo|"):
        parts = data.split("|", 2)
        if len(parts) != 3: return
        _, height_str, key = parts
        _VALID_H = {360, 480, 720}
        try: h_int = int(height_str)
        except (ValueError, TypeError): return
        if h_int not in _VALID_H: return
        fid = cb_get(key) or pending_op.get(uid, {}).get("file_id")
        if not fid: await expired(); return
        await sdel(q.message)
        await act_compress(update, ctx, fid, h_int)
        return

    if data.startswith("ss|"):
        fid = cb_get(data[3:])
        if not fid: await expired(); return
        await sdel(q.message)
        waiting_for[uid] = "ss_ts"
        pending_op[uid]  = {"file_id": fid}
        await msg.reply_text(
            "📸 Send the <b>timestamp</b>:\n<code>1:23</code>  or  <code>83</code>",
            parse_mode=HTML, reply_markup=cancel_btn())
        return

    if data.startswith("gf|"):
        fid = cb_get(data[3:])
        if not fid: await expired(); return
        await sdel(q.message)
        waiting_for[uid] = "gif_ts"
        pending_op[uid]  = {"file_id": fid}
        await msg.reply_text(
            "🎞️ Send <b>start and end time</b> (max 15s):\n<code>0:10 - 0:20</code>",
            parse_mode=HTML, reply_markup=cancel_btn())
        return

    if data.startswith("cv|"):
        fid = cb_get(data[3:])
        if not fid: await expired(); return
        pending_op[uid] = {"file_id": fid}
        await sedit(q.message, "🔄 Choose output format:", reply_markup=convert_kb(data[3:]))
        return

    if data.startswith("cvdo|"):
        parts = data.split("|", 2)
        if len(parts) != 3: return
        _, fmt, key = parts
        _VALID_FMT = {"mp4", "mkv", "webm", "mov", "avi"}
        if fmt not in _VALID_FMT: return
        fid = cb_get(key) or pending_op.get(uid, {}).get("file_id")
        if not fid: await expired(); return
        await sdel(q.message)
        await act_convert(update, ctx, fid, fmt)
        return

    if data.startswith("pr|"):
        parts = data.split("|", 2)
        if len(parts) != 3: return
        username = cb_get(parts[2])
        if not username: await expired(); return
        await sdel(q.message)
        await act_my_profile(update, ctx)
        return

    if data == "noop":
        return

    # ── MovieBox pagination ───────────────────────────────────────────────
    if data.startswith("mvpage|"):
        page = int(data.split("|")[1])
        results = _movie_results.get(uid)
        if not results: return
        _movie_page[uid] = page
        await sedit(msg,
            _movie_page_text(uid, page),
            reply_markup=_movie_page_kb(uid, page, len(results)))
        return

    if data.startswith("mvdirect|"):
        import urllib.parse
        parts   = data.split("|", 2)
        if len(parts) < 3: return
        title   = urllib.parse.unquote(parts[1])
        quality = parts[2]
        lang    = await get_lang(uid)
        await sedit(msg,
            t(lang, "movie_downloading", title=h(title), quality=quality))
        loop = asyncio.get_running_loop()
        path, info = await asyncio.wait_for(
            mb_download(title, "movie", quality),
            timeout=600)
        if not path:
            await sedit(msg, "❌ Download failed. Check the title and try again.",
                        reply_markup=main_kb(lang))
            return
        size    = os.path.getsize(path)
        caption = f"🎬 <b>{h(info.get('title', title))}</b>\n📦 {fmt_sz(size)}\n\n📣 {BRAND}"
        if size > TG_MAX_MB * 1024 * 1024:
            upl_msg = await msg.reply_text(f"📦 {fmt_sz(size)} — uploading…", parse_mode=HTML)
            link, host = await _upload_file(path, upl_msg)
            clean(path)
            retention = {"Gofile": "10 days", "Litterbox": "72 hours", "0x0.st": "30 days"}.get(host, "limited")
            if link:
                await sedit(upl_msg,
                    f"{caption}\n\n⬇️ <a href=\"{link}\">Download</a> <i>({host} · {retention})</i>",
                    disable_web_page_preview=True)
            else:
                await sedit(upl_msg, "❌ Upload failed.", reply_markup=main_kb(lang))
        else:
            await msg.reply_video(path, caption=caption, parse_mode=HTML,
                                  reply_markup=menu_btn(), supports_streaming=True)
            clean(path)
        return

    if data.startswith("mvpick|"):
        idx = int(data.split("|")[1])
        results = _movie_results.get(uid, [])
        if idx >= len(results): return
        r = results[idx]
        title = h(r.get("title", "?"))
        year  = r.get("year", "")
        await sedit(msg,
            f"🎬 <b>{title}</b> ({year})\n\nChoose quality:",
            reply_markup=_movie_quality_kb(idx))
        return

    if data.startswith("mvback|"):
        page = _movie_page.get(uid, 0)
        results = _movie_results.get(uid, [])
        await sedit(msg,
            _movie_page_text(uid, page),
            reply_markup=_movie_page_kb(uid, page, len(results)))
        return

    if data.startswith("mvdl|"):
        parts   = data.split("|")
        idx     = int(parts[1])
        quality = parts[2]
        results = _movie_results.get(uid, [])
        if idx >= len(results): return
        r       = results[idx]
        item_id = str(r.get("id", ""))
        mtype   = r.get("type", "movie")
        title   = r.get("title", "Video")
        lang    = await get_lang(uid)
        lang = await get_lang(uid)
        await sedit(msg,
            t(lang, "movie_downloading", title=h(title), quality=quality)
        )
        loop = asyncio.get_running_loop()
        path, info = await asyncio.wait_for(
            mb_download(item_id, mtype, quality),
            timeout=600)
        if not path:
            await sedit(msg, "❌ Download failed. Try another quality.", reply_markup=main_kb(lang))
            return
        size    = os.path.getsize(path)
        caption = f"🎬 <b>{h(title)}</b>\n📦 {fmt_sz(size)}\n\n📣 {BRAND}"
        if size > TG_MAX_MB * 1024 * 1024:
            upl_msg = await msg.reply_text(f"📦 {fmt_sz(size)} — uploading…", parse_mode=HTML)
            link, host = await _upload_file(path, upl_msg)
            clean(path)
            if link:
                retention = {"Gofile": "10 days", "Litterbox": "72 hours", "0x0.st": "30 days"}.get(host, "limited")
                await sedit(upl_msg,
                    f"{caption}\n\n⬇️ <a href=\"{link}\">Download link</a>\n<i>via {host} · {retention}</i>",
                    disable_web_page_preview=True)
            else:
                await sedit(upl_msg, "❌ Upload failed.", reply_markup=main_kb(lang))
        else:
            await msg.reply_video(path, caption=caption, parse_mode=HTML,
                                  reply_markup=menu_btn(), supports_streaming=True)
            clean(path)
        return

    if data.startswith("mpage|"):
        try: page = int(data[6:])
        except ValueError: return
        results = _music_results.get(uid)
        if not results:
            await q.answer("Session expired. Search again.", show_alert=True)
            return
        _music_page[uid] = page
        await sedit(q.message,
            _music_page_text(uid, page),
            reply_markup=_music_page_kb(uid, page, len(results)))
        return

    if data.startswith("mdown|"):
        try: idx = int(data[6:])
        except (ValueError, TypeError): return
        results = _music_results.get(uid)
        if not results or idx >= len(results):
            await q.answer("Session expired. Search again.", show_alert=True)
            return
        r   = results[idx]
        url = r.get("youtube_url")
        if not url:
            await q.answer("No download link.", show_alert=True)
            return
        await q.answer(f"⬇️ Downloading: {r['title'][:30]}")
        await act_audio(update, ctx, url)
        return

    if data.startswith("rev|"):
        fid = cb_get(data[4:])
        if not fid: await expired(); return
        await sdel(q.message)
        await act_reverse(update, ctx, fid)
        return

    if data.startswith("spd|"):
        parts = data.split("|", 2)
        if len(parts) != 3: return
        _, speed_str, key = parts
        if speed_str == "pick":
            await sedit(q.message, "⚡ Choose playback speed:", reply_markup=speed_kb(key))
            return
        try: speed = float(speed_str)
        except ValueError: return
        if speed <= 0 or speed > 8: return
        fid = cb_get(key) or pending_op.get(uid, {}).get("file_id")
        if not fid: await expired(); return
        await sdel(q.message)
        await act_speed(update, ctx, fid, speed)
        return

    if data.startswith("adm_ban|") and is_admin_authed(uid):
        try: target = int(data.split("|")[1])
        except (ValueError, IndexError): return
        await db.db_ban(target, "Banned via admin panel")
        await q.answer("🚫 Banned!")
        await sedit(q.message, f"🚫 User <code>{target}</code> banned.")
        try: await ctx.bot.send_message(target, "🚫 You have been banned from this bot.")
        except Exception: pass
        return

    if data.startswith("adm_unban|") and is_admin_authed(uid):
        try: target = int(data.split("|")[1])
        except (ValueError, IndexError): return
        await db.db_unban(target)
        await q.answer("✅ Unbanned!")
        await sedit(q.message, f"✅ User <code>{target}</code> unbanned.")
        try: await ctx.bot.send_message(target, "✅ You have been unbanned!")
        except Exception: pass
        return


# ═══════════════════════════════════════════════════════════════════════════
#  ERROR HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    stats["errors"] += 1
    uid = None
    if isinstance(update, Update) and update.effective_user:
        uid = update.effective_user.id
    log.error(f"Unhandled exception (uid={uid}): {ctx.error}", exc_info=ctx.error)
    if uid:
        await db.db_log_error(uid, "unhandled", str(ctx.error))
        await db.db_track("errors")

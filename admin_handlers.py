"""
admin_handlers.py — Admin-panel command and callback handlers.

Import chain (no circular imports):
  state.py  ←  handlers.py  ←  admin_handlers.py
"""
import asyncio
import logging
from datetime import datetime

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as IKM, Update
from telegram.ext import ContextTypes

import database as db
from config import *                       # noqa: F401,F403 — BRAND, MAX_MB, etc.
from keyboards import *                    # noqa: F401,F403 — all keyboard builders
from database import db_schedule_ad, db_expire_ads, rank_ad_interval
from utils import HTML, h, sedit, sdel, fmt_sz

# ── Shared runtime state and auth helpers ─────────────────────────────────
from state import (
    waiting_for, pending_op, stats,
    _admin_auth, _fail_counts, _fail_times,
    is_admin, is_admin_authed,
)

from shared import guard, require_auth, _auth_prompt_msg, _do_broadcast

log = logging.getLogger("bot.admin")


# ═══════════════════════════════════════════════════════════════════════════
#  ADMIN PANEL ENTRY
# ═══════════════════════════════════════════════════════════════════════════

async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point — /admin command."""
    if not await require_auth(update): return
    total  = await db.db_total_users()
    banned = await db.db_total_banned()
    ads    = await db.db_ad_stats()
    text = (
        "🛡 <b>Admin Panel</b>\n\n"
        f"👥 Users     : <code>{total:,}</code>\n"
        f"🚫 Banned    : <code>{banned:,}</code>\n"
        f"📢 Active ads: <code>{ads['active_ads']}</code>\n"
        f"🎬 Videos    : <code>{stats['videos']}</code>\n"
        f"🎵 Audios    : <code>{stats['audios']}</code>\n"
        f"❌ Errors    : <code>{stats['errors']}</code>"
    )
    await update.effective_message.reply_text(
        text, parse_mode=HTML, reply_markup=admin_main_kb())


async def _admin_home(msg) -> None:
    """Redraw the admin home panel on an existing message."""
    total  = await db.db_total_users()
    banned = await db.db_total_banned()
    ads    = await db.db_ad_stats()
    text = (
        "🛡 <b>Admin Panel</b>\n\n"
        f"👥 Users     : <code>{total:,}</code>\n"
        f"🚫 Banned    : <code>{banned:,}</code>\n"
        f"📢 Active ads: <code>{ads['active_ads']}</code>\n"
        f"🎬 Videos    : <code>{stats['videos']}</code>\n"
        f"🎵 Audios    : <code>{stats['audios']}</code>\n"
        f"❌ Errors    : <code>{stats['errors']}</code>"
    )
    await sedit(msg, text, reply_markup=admin_main_kb())


# ═══════════════════════════════════════════════════════════════════════════
#  ADMIN CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def on_admin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all adp| callbacks for admin panel buttons."""
    if not await guard(update): return
    q   = update.callback_query
    uid = update.effective_user.id
    msg = q.message
    await q.answer()

    if not is_admin_authed(uid):
        await q.answer("🔐 Not authenticated.", show_alert=True)
        return

    action = q.data[4:]   # strip "adp|"

    # ── Home ──────────────────────────────────────────────────────────────
    if action == "home":
        await _admin_home(msg)
        return

    # ── Exit ──────────────────────────────────────────────────────────────
    if action == "exit":
        _admin_auth.pop(uid, None)
        await sedit(msg, "🔒 <b>Admin session ended.</b>")
        await msg.reply_text("You have been logged out.", reply_markup=main_kb())
        return

    # ── Stats ──────────────────────────────────────────────────────────────
    if action == "stats":
        wait = await msg.reply_text("📊 Loading…")
        try:
            d   = await db.db_stats_overview()
            u   = d["users"]
            a   = d["ads"]
            t   = d["today"]
            sec = d["sec_events_24h"]
            ts  = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            lines = [
                "📊 <b>Advanced Stats</b>",
                f"<code>{ts}</code>", "",
                "👥 <b>Users</b>",
                f"  Total      : <code>{int(u['total']):,}</code>",
                f"  Today      : <code>{int(u['today']):,}</code>",
                f"  This week  : <code>{int(u['week']):,}</code>",
                f"  This month : <code>{int(u['month']):,}</code>",
                f"  Banned     : <code>{int(u['banned']):,}</code>",
                f"  Downloads  : <code>{int(u['total_downloads']):,}</code>",
                f"  Avg/user   : <code>{float(u['avg_downloads']):.1f}</code>", "",
                "📅 <b>Today</b>",
                f"  New users   : <code>{t.get('new_users',0)}</code>",
                f"  Videos      : <code>{t.get('videos',0)}</code>",
                f"  Audios      : <code>{t.get('audios',0)}</code>",
                f"  Music       : <code>{t.get('music',0)}</code>",
                f"  Errors      : <code>{t.get('errors',0)}</code>", "",
                "📢 <b>Ads</b>",
                f"  Active : <code>{a['active_ads']}</code>",
                f"  Imps   : <code>{int(a['impressions']):,}</code>", "",
                "🔐 <b>Security (24h)</b>",
                f"  Events : <code>{sec}</code>" + ("  ⚠️" if sec > 5 else ""),
            ]
            if d["top_users"]:
                lines += ["", "🏆 <b>Top Users</b>"]
                for i, usr in enumerate(d["top_users"], 1):
                    name = h(usr["full_name"] or usr["username"] or str(usr["uid"]))
                    lines.append(f"  {i}. {name} — <code>{usr['downloads']}</code>")
            if d["week_growth"]:
                lines += ["", "📈 <b>Last 7 Days</b>"]
                for row in d["week_growth"]:
                    nu  = int(row["new_users"] or 0)
                    bar = "█" * min(nu, 10) + "░" * (10 - min(nu, 10))
                    lines.append(
                        f"  {str(row['day'])[5:]} |{bar}| +{nu}u {row['videos']}v {row['audios']}a")
            await sdel(wait)
            await msg.reply_text("\n".join(lines), parse_mode=HTML,
                                 reply_markup=back_to_admin())
        except Exception as e:
            log.error(f"admin stats: {e}")
            await sedit(wait, "❌ Failed to load stats.", reply_markup=back_to_admin())
        return

    # ── Users menu ────────────────────────────────────────────────────────
    if action == "users":
        total  = await db.db_total_users()
        banned = await db.db_total_banned()
        await sedit(msg,
            f"👥 <b>User Management</b>\n\n"
            f"Total : <code>{total:,}</code>\n"
            f"Banned: <code>{banned:,}</code>\n\n"
            "Choose an action:",
            reply_markup=admin_users_kb())
        return

    if action == "topusers":
        try:
            pool = await db.get_pool()
        except RuntimeError:
            await sedit(msg, "❌ Database not connected.", reply_markup=admin_users_kb())
            return
        async with pool.acquire() as c:
            rows = await c.fetch("""
                SELECT uid, username, full_name, downloads
                FROM users ORDER BY downloads DESC LIMIT 10
            """)
        lines = ["🏆 <b>Top 10 Users</b>", ""]
        for i, r in enumerate(rows, 1):
            name = h(r["full_name"] or r["username"] or str(r["uid"]))
            lines.append(
                f"{i}. {name}  —  <code>{r['downloads']}</code> dl  │  <code>{r['uid']}</code>")
        await sedit(msg, "\n".join(lines), reply_markup=admin_users_kb())
        return

    if action in ("finduser", "banuser", "unbanuser"):
        prompts = {
            "finduser":  "🔍 Send the <b>user ID</b> to look up:",
            "banuser":   "🚫 Send <b>user ID</b> to ban:\n<i>Optionally add reason after a space</i>\n<code>123456 spamming</code>",
            "unbanuser": "✅ Send the <b>user ID</b> to unban:",
        }
        waiting_for[uid] = f"admin_{action}"
        await sedit(msg, prompts[action],
                    reply_markup=IKM([[Btn("❌ Cancel", callback_data="adp|users")]]))
        return

    # ── Logs ──────────────────────────────────────────────────────────────
    if action == "logs":
        rows = await db.db_recent_logs(25)
        if not rows:
            await sedit(msg, "📋 No logs yet.", reply_markup=back_to_admin())
            return
        lines = ["📋 <b>Recent Activity</b>", ""]
        for r in rows:
            ts     = str(r["ts"])[:16]
            detail = h(r["detail"][:50]) if r["detail"] else ""
            lines.append(
                f"<code>{ts}</code> │ <code>{r['uid']}</code> │ {h(r['action'])}"
                + (f" — {detail}" if detail else ""))
        await sedit(msg, "\n".join(lines), reply_markup=back_to_admin())
        return

    # ── Security log ──────────────────────────────────────────────────────
    if action == "security":
        try:
            pool = await db.get_pool()
        except RuntimeError:
            await sedit(msg, "❌ Database not connected.", reply_markup=back_to_admin())
            return
        async with pool.acquire() as c:
            rows = await c.fetch("""
                SELECT uid, event, detail, ts::TEXT AS ts
                FROM security_log ORDER BY id DESC LIMIT 20
            """)
        if not rows:
            await sedit(msg, "🔐 No security events.", reply_markup=back_to_admin())
            return
        lines = ["🔐 <b>Security Log</b>", ""]
        for r in rows:
            lines.append(
                f"<code>{str(r['ts'])[:16]}</code> │ <code>{r['uid']}</code> │ {h(r['event'])}")
        await sedit(msg, "\n".join(lines), reply_markup=back_to_admin())
        return

    # ── Errors ────────────────────────────────────────────────────────────
    if action == "errors":
        rows = await db.db_recent_errors(25)
        if not rows:
            await sedit(msg, "No errors logged yet.", reply_markup=back_to_admin())
            return
        lines_out = ["<b>Recent Errors (last 25)</b>", ""]
        for r in rows:
            ts    = str(r["ts"])[:16]
            hnd   = h(r["handler"] or "")
            uid_v = r["uid"] or 0
            err   = h(str(r["error"] or "")[:100])
            lines_out.append(f"<code>{ts}</code> <b>{hnd}</b> uid:<code>{uid_v}</code>")
            lines_out.append(f"  {err}")
            lines_out.append("")
        text_out = "\n".join(lines_out)
        if len(text_out) > 3500:
            text_out = "\n".join(lines_out[:60]) + "\n…"
        await sedit(msg, text_out, reply_markup=back_to_admin())
        return

    # ── Broadcast ─────────────────────────────────────────────────────────
    if action == "broadcast":
        waiting_for[uid] = "admin_broadcast_text"
        await sedit(msg,
            "📣 <b>Broadcast</b>\n\n"
            "Send your message now.\n"
            "Supports text, photo, video, or GIF.\n\n"
            "<i>For media: send the file with caption as your message.</i>",
            reply_markup=IKM([[Btn("❌ Cancel", callback_data="adp|home")]]))
        return

    # ── Ads menu ──────────────────────────────────────────────────────────
    if action == "ads":
        ads_list = await db.db_list_ads()
        stats_d  = await db.db_ad_stats()
        lines    = [
            "📢 <b>Ad Management</b>", "",
            f"📊 Total ads    : {stats_d['total_ads']}",
            f"🟢 Active       : {stats_d['active_ads']}",
            f"👁 Impressions  : {int(stats_d['total_impressions']):,}", "",
        ]
        if ads_list:
            for ad in ads_list[:10]:
                status = "🟢" if ad["active"] else "🔴"
                cap    = h((ad["caption"] or "")[:40])
                lines.append(
                    f"{status} #{ad['id']} [{ad['media_type']}] 👁{ad['impressions']} — {cap}")
        await sedit(msg, "\n".join(lines), reply_markup=admin_ads_kb())
        return

    if action == "addad":
        waiting_for[uid] = "ad_wizard_name"
        pending_op[uid]  = {"wizard": "admin_ad"}
        await sedit(msg,
            "📢 Create Ad — Step 1/4\n\n"
            "Give this ad an internal name (only you see it):\n"
            "e.g. <i>Summer promo June</i>",
            parse_mode=HTML,
            reply_markup=IKM([[Btn("❌ Cancel", callback_data="adp|ads")]]))
        return

    if action.startswith("sndone|"):
        try:
            ad_id = int(action[7:])
        except ValueError:
            return
        ads_list = await db.db_list_ads()
        ad = next((a for a in ads_list if a["id"] == ad_id), None)
        if not ad:
            await q.answer("Ad not found", show_alert=True)
            return
        if not ad["active"]:
            await q.answer("⛔ This ad is paused. Activate it first.", show_alert=True)
            return
        users = await db.db_all_users()
        cap = ad.get("caption") or ""
        mt  = ad.get("media_type", "text")
        kb  = None
        if ad.get("url") and ad.get("button_label"):
            kb = IKM([[Btn(str(ad["button_label"]), url=str(ad["url"]))]])
        ok = fail = 0
        status = await msg.reply_text(
            f"📢 Sending <b>Ad #{ad_id}</b> to <b>{len(users)}</b> users…",
            parse_mode=HTML)
        for i, row in enumerate(users):
            t = row["uid"]
            try:
                if   mt == "photo"     and ad.get("file_id"):
                    await ctx.bot.send_photo(t, ad["file_id"], caption=cap, reply_markup=kb, parse_mode=HTML)
                elif mt == "video"     and ad.get("file_id"):
                    await ctx.bot.send_video(t, ad["file_id"], caption=cap, reply_markup=kb, parse_mode=HTML)
                elif mt == "animation" and ad.get("file_id"):
                    await ctx.bot.send_animation(t, ad["file_id"], caption=cap, reply_markup=kb, parse_mode=HTML)
                elif cap:
                    await ctx.bot.send_message(t, cap, reply_markup=kb, parse_mode=HTML)
                ok += 1
                await db.db_imp_ad(ad_id)
            except Exception:
                fail += 1
            await asyncio.sleep(1.0 if (i > 0 and i % 25 == 0) else 0.04)
        await sedit(status,
            f"✅ <b>Ad #{ad_id} sent!</b>\n✅ {ok} delivered  │  ❌ {fail} failed")
        await db.db_log(uid, "send_ad", f"id={ad_id} ok={ok} fail={fail}")
        return

    if action.startswith("tog|"):
        try:
            ad_id = int(action[4:])
        except ValueError:
            return
        ads = await db.db_list_ads()
        ad  = next((a for a in ads if a["id"] == ad_id), None)
        if not ad:
            await q.answer("Ad not found", show_alert=True)
            return
        new_state = not ad["active"]
        await db.db_toggle_ad(ad_id, new_state)
        await db.db_log(uid, "togglead", f"id={ad_id} active={new_state}")
        label = "🟢 Resumed" if new_state else "🔴 Paused"
        await q.answer(f"Ad #{ad_id} {label}")
        await sedit(msg, f"{label} — Ad #{ad_id}")
        return

    if action.startswith("del|"):
        try: ad_id = int(action[4:])
        except ValueError: return
        await db.db_delete_ad(ad_id)
        await db.db_log(uid, "deletead", f"id={ad_id}")
        await q.answer(f"Ad #{ad_id} deleted")
        await sedit(msg, f"🗑 Ad #{ad_id} deleted.")
        return

    if action == "listads":
        ads_list = await db.db_list_ads()
        if not ads_list:
            await sedit(msg, "📢 No ads yet.", reply_markup=admin_ads_kb())
            return
        for ad in ads_list:
            is_active = ad["active"]
            st   = "🟢 Active" if is_active else "🔴 Paused"
            cap  = h((ad["caption"] or "")[:60])
            name = h(ad["name"] or "")
            text = (
                f"{st} — <b>#{ad['id']} {name}</b> [{ad['media_type']}]\n"
                f"👁 {ad['impressions']} impressions\n"
                f"📝 {cap}\n"
                f"📅 {str(ad['created_at'])[:10]}"
            )
            tog_label = "🔴 Pause" if is_active else "🟢 Resume"
            # Send button only appears for active ads
            row = [
                Btn(tog_label,  callback_data=f"adp|tog|{ad['id']}"),
                Btn("🗑 Delete", callback_data=f"adp|del|{ad['id']}"),
            ]
            if is_active:
                row.insert(0, Btn("📢 Send All", callback_data=f"adp|sndone|{ad['id']}"))
            sched_row = [Btn("⏰ Schedule", callback_data=f"adp|schedmenu|{ad['id']}")]
            await msg.reply_text(text, parse_mode=HTML, reply_markup=IKM([row, sched_row]))
        await msg.reply_text("─────────────────", reply_markup=admin_ads_kb())
        return

    if action == "sendad":
        ads_list = await db.db_list_ads()
        active   = [a for a in ads_list if a["active"]]
        paused   = [a for a in ads_list if not a["active"]]
        if not ads_list:
            await sedit(msg, "No ads exist yet.", reply_markup=admin_ads_kb())
            return
        lines = ["📢 <b>Send Ad to All Users</b>", ""]
        if active:
            lines.append("🟢 <b>Active ads</b> (can be sent):")
            for ad in active:
                lines.append(f"  • <code>{ad['id']}</code> — {h(ad['name'] or 'Unnamed')}")
        if paused:
            lines.append("")
            lines.append("🔴 <b>Paused ads</b> (activate first to send):")
            for ad in paused:
                lines.append(f"  • <code>{ad['id']}</code> — {h(ad['name'] or 'Unnamed')}")
        if not active:
            lines.append("\n⚠️ No active ads to send. Resume an ad first.")
            await sedit(msg, "\n".join(lines), reply_markup=admin_ads_kb())
            return
        lines.append("\nReply with the <b>Ad ID</b> to send:")
        waiting_for[uid] = "adp_send_ad_id"
        await sedit(msg, "\n".join(lines),
                    reply_markup=IKM([[Btn("❌ Cancel", callback_data="adp|ads")]]))
        return

    if action.startswith("schedmenu|"):
        try: ad_id = int(action[10:])
        except ValueError: return
        ads_list = await db.db_list_ads()
        ad = next((a for a in ads_list if a["id"] == ad_id), None)
        if not ad:
            await q.answer("Ad not found", show_alert=True)
            return
        exp = ad["expires_at"]
        exp_str = f"Current: ⏰ {str(exp)[:16]}" if exp else "Current: ♾ No expiry"
        await sedit(msg,
            f"⏰ <b>Schedule Ad #{ad_id}</b>\n\n"
            f"{exp_str}\n\n"
            "Choose how long this ad stays active:",
            reply_markup=schedule_ad_kb(ad_id))
        return

    if action.startswith("sched|"):
        parts = action.split("|")
        if len(parts) < 3: return
        try: ad_id = int(parts[1])
        except ValueError: return
        days_str = parts[2]
        if days_str == "custom":
            pending_op[uid]  = {"sched_ad_id": ad_id}
            waiting_for[uid] = "adp_sched_custom"
            await sedit(msg,
                f"⏰ <b>Custom Duration — Ad #{ad_id}</b>\n\n"
                "Send the number of days (e.g. <code>14</code>):",
                reply_markup=IKM([[Btn("❌ Cancel", callback_data="adp|listads")]]))
            return
        days = int(days_str)
        if days == 0:
            await db_schedule_ad(ad_id, None)
            await db.db_toggle_ad(ad_id, True)
            await q.answer("♾ Ad set to run forever", show_alert=True)
        else:
            await db_schedule_ad(ad_id, days)
            await q.answer(f"⏰ Ad scheduled for {days} day(s)", show_alert=True)
        await db.db_log(uid, "sched_ad", f"id={ad_id} days={days_str}")
        await sedit(msg, f"✅ Ad #{ad_id} scheduled for {'forever' if days==0 else str(days)+' days'}.")
        return

    if action.startswith("edit|"):
        try: ad_id = int(action[5:])
        except ValueError: return
        ads_list = await db.db_list_ads()
        ad = next((a for a in ads_list if a["id"] == ad_id), None)
        if not ad:
            await q.answer("Ad not found", show_alert=True)
            return
        pending_op[uid]  = {"edit_ad_id": ad_id}
        waiting_for[uid] = "adp_edit_ad_field"
        name_txt = h(ad["name"] or "")
        cap_txt  = h((ad["caption"] or "")[:80])
        url_txt  = h(ad["url"] or "none")
        await sedit(msg,
            f"✏️ <b>Edit Ad #{ad_id} — {name_txt}</b>\n\n"
            f"📝 Caption: {cap_txt}\n"
            f"🔗 URL    : {url_txt}\n\n"
            "Type field + new value:\n"
            "<code>name   New name</code>\n"
            "<code>caption New caption text</code>\n"
            "<code>url   https://example.com</code>\n"
            "<code>label  Button Label</code>",
            reply_markup=IKM([[Btn("❌ Cancel", callback_data="adp|listads")]]))
        return


# ═══════════════════════════════════════════════════════════════════════════
#  ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

async def cmd_stats_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Advanced stats dashboard — /stats command."""
    if not await require_auth(update): return
    wait = await update.effective_message.reply_text("📊 Loading...")
    try:
        d   = await db.db_stats_overview()
        u   = d["users"]
        a   = d["ads"]
        t   = d["today"]
        sec = d["sec_events_24h"]
        ts  = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            "📊 <b>Advanced Stats Dashboard</b>",
            f"<code>{ts}</code>", "",
            "👥 <b>Users</b>",
            f"  Total      : <code>{int(u['total']):,}</code>",
            f"  Today      : <code>{int(u['today']):,}</code>",
            f"  This week  : <code>{int(u['week']):,}</code>",
            f"  This month : <code>{int(u['month']):,}</code>",
            f"  Banned     : <code>{int(u['banned']):,}</code>",
            f"  Downloads  : <code>{int(u['total_downloads']):,}</code>",
            f"  Avg/user   : <code>{float(u['avg_downloads']):.1f}</code>", "",
            "📅 <b>Today Activity</b>",
            f"  New users   : <code>{t.get('new_users',0)}</code>",
            f"  Videos      : <code>{t.get('videos',0)}</code>",
            f"  Audios      : <code>{t.get('audios',0)}</code>",
            f"  Music       : <code>{t.get('music',0)}</code>",
            f"  Screenshots : <code>{t.get('screenshots',0)}</code>",
            f"  GIFs        : <code>{t.get('gifs',0)}</code>",
            f"  Errors      : <code>{t.get('errors',0)}</code>", "",
            "📢 <b>Ads</b>",
            f"  Active : <code>{a['active_ads']}</code>",
            f"  Total  : <code>{a['total_ads']}</code>",
            f"  Imps   : <code>{int(a['impressions']):,}</code>", "",
            "🔐 <b>Security (24h)</b>",
            f"  Events : <code>{sec}</code>" + ("  ⚠️" if sec > 5 else ""),
        ]
        if d["top_users"]:
            lines += ["", "🏆 <b>Top Users</b>"]
            for i, usr in enumerate(d["top_users"], 1):
                name = h(usr["full_name"] or usr["username"] or str(usr["uid"]))
                lines.append(f"  {i}. {name} — <code>{usr['downloads']}</code>")
        if d["week_growth"]:
            lines += ["", "📈 <b>Last 7 Days</b>"]
            for row in d["week_growth"]:
                nu  = int(row["new_users"] or 0)
                bar = "█" * min(nu, 10) + "░" * (10 - min(nu, 10))
                lines.append(
                    f"  {str(row['day'])[5:]} |{bar}| +{nu}u {row['videos']}v {row['audios']}a")
        await sdel(wait)
        await update.effective_message.reply_text(
            "\n".join(lines), parse_mode=HTML, reply_markup=back_to_admin())
    except Exception as e:
        log.error(f"cmd_stats_admin: {e}")
        await sedit(wait, "❌ Could not load stats.", reply_markup=menu_btn())


async def cmd_logout(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin logout — /logout or /exit."""
    uid = update.effective_user.id
    if not is_admin(uid): return
    _admin_auth.pop(uid, None)
    _auth_prompt_msg.pop(uid, None)
    await update.effective_message.reply_text(
        "🔒 <b>Admin session ended.</b>\n"
        "Passcode required to access panel again.",
        parse_mode=HTML, reply_markup=main_kb())


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update): return
    msg = update.effective_message
    rep = msg.reply_to_message
    if not ctx.args and not rep:
        await msg.reply_text(
            "📣 <b>How to broadcast:</b>\n\n"
            "1️⃣ Text: <code>/broadcast Hello!</code>\n"
            "2️⃣ Reply to media with caption: <code>/broadcast Ad text</code>",
            parse_mode=HTML)
        return
    caption = " ".join(ctx.args) if ctx.args else None
    users   = await db.db_all_users()
    source  = rep if rep else msg
    await _do_broadcast(ctx, source, users, caption)

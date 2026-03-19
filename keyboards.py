from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as IKM
from telegram import ReplyKeyboardMarkup
from utils import cb_put
from translations import t, LANGS

def main_kb(lang: str = "en") -> ReplyKeyboardMarkup:
    _ = lambda k: t(lang, k)
    return ReplyKeyboardMarkup([
        [_("btn_download"),      _("btn_extract_audio")],
        [_("btn_file_audio"),    _("btn_find_music")],
        [_("btn_profile"),       _("btn_batch")],
        [_("btn_trim"),          _("btn_compress")],
        [_("btn_screenshot"),    _("btn_gif")],
        [_("btn_convert"),       _("btn_remove_audio")],
        [_("btn_merge"),         _("btn_media_info")],
        [_("btn_speed"),         _("btn_reverse")],
        [_("btn_post_info"),     _("btn_stats")],
        [_("btn_help"),          _("btn_language")],
    ], resize_keyboard=True, is_persistent=True)

def action_kb(k: str) -> IKM:
    return IKM([
        [Btn("⬇️ Download",   callback_data=f"mv|{k}"),
         Btn("🎵 Audio",       callback_data=f"au|{k}")],
        [Btn("🔍 Find Music",  callback_data=f"ml|{k}"),
         Btn("ℹ️ Info",        callback_data=f"vi|{k}")],
        [Btn("❌ Cancel",      callback_data="cancel")],
    ])

def quality_kb(k: str) -> IKM:
    return IKM([
        [Btn("📱 360p",  callback_data=f"dv|360|{k}"),
         Btn("📺 720p",  callback_data=f"dv|720|{k}"),
         Btn("🖥 1080p", callback_data=f"dv|1080|{k}")],
        [Btn("✨ Best",  callback_data=f"dv|2160|{k}")],
        [Btn("🔙 Back",  callback_data=f"ba|{k}"),
         Btn("❌ Cancel",callback_data="cancel")],
    ])

def music_src_kb() -> IKM:
    return IKM([
        [Btn("🔗 By Video Link",    callback_data="ms|link")],
        [Btn("🎤 Send Audio/Voice", callback_data="ms|file")],
        [Btn("✏️ Type Song/Artist", callback_data="ms|text")],
        [Btn("❌ Cancel",           callback_data="cancel")],
    ])

def file_kb(k: str) -> IKM:
    return IKM([
        [Btn("🎵 Extract Audio",   callback_data=f"xf|{k}"),
         Btn("📋 Media Info",      callback_data=f"mi|{k}")],
        [Btn("✂️ Trim",            callback_data=f"tr|{k}"),
         Btn("🗜️ Compress",        callback_data=f"cp|{k}")],
        [Btn("📸 Screenshot",      callback_data=f"ss|{k}"),
         Btn("🎞️ To GIF",          callback_data=f"gf|{k}")],
        [Btn("🔄 Convert",         callback_data=f"cv|{k}"),
         Btn("🔇 Remove Audio",    callback_data=f"ra2|{k}")],
        [Btn("⚡ Change Speed",    callback_data=f"spd|pick|{k}"),
         Btn("🔁 Reverse",         callback_data=f"rev|{k}")],
        [Btn("❌ Cancel",          callback_data="cancel")],
    ])

def convert_kb(k: str) -> IKM:
    return IKM([
        [Btn("MP4",  callback_data=f"cvdo|mp4|{k}"),
         Btn("MKV",  callback_data=f"cvdo|mkv|{k}"),
         Btn("WEBM", callback_data=f"cvdo|webm|{k}")],
        [Btn("MOV",  callback_data=f"cvdo|mov|{k}"),
         Btn("AVI",  callback_data=f"cvdo|avi|{k}")],
        [Btn("❌ Cancel", callback_data="cancel")],
    ])

def compress_kb(k: str) -> IKM:
    return IKM([
        [Btn("🟢 Light (720p)",  callback_data=f"cpdo|720|{k}"),
         Btn("🟡 Medium (480p)", callback_data=f"cpdo|480|{k}")],
        [Btn("🔴 Heavy (360p)",  callback_data=f"cpdo|360|{k}")],
        [Btn("❌ Cancel", callback_data="cancel")],
    ])


def result_kb(yt=None, sp=None) -> IKM:
    row = []
    if yt: row.append(Btn("▶️ YouTube", url=yt))
    if sp: row.append(Btn("🎧 Spotify", url=sp))
    rows = [row] if row else []
    rows.append([Btn("🏠 Menu", callback_data="cancel")])
    return IKM(rows)

def menu_btn() -> IKM:
    return IKM([[Btn("🏠 Menu", callback_data="cancel")]])

def cancel_btn() -> IKM:
    return IKM([[Btn("❌ Cancel", callback_data="cancel")]])


def lang_kb() -> IKM:
    """Inline keyboard for language selection."""
    return IKM([[Btn(label, callback_data=f"setlang|{code}")]
                for code, label in LANGS.items()])

def change_lang_kb(lang: str = "en") -> IKM:
    """Shown in settings — shows current lang and lets user change."""
    rows = [[Btn(f"{'✅ ' if code == lang else ''}{label}",
                 callback_data=f"setlang|{code}")]
            for code, label in LANGS.items()]
    rows.append([Btn("🏠 Menu", callback_data="cancel")])
    return IKM(rows)

# ══════════════════════════════════════════════════════════════════════════
#  ADMIN KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════
def admin_main_kb() -> IKM:
    return IKM([
        [Btn("📊 Stats",        callback_data="adp|stats"),
         Btn("👥 Users",        callback_data="adp|users")],
        [Btn("📢 Ads",          callback_data="adp|ads"),
         Btn("📋 Logs",         callback_data="adp|logs")],
        [Btn("📣 Broadcast",    callback_data="adp|broadcast"),
         Btn("🔐 Security",     callback_data="adp|security")],
        [Btn("❌ Errors",        callback_data="adp|errors"),
         Btn("🔒 Exit Panel",   callback_data="adp|exit")],
    ])

def admin_ads_kb() -> IKM:
    return IKM([
        [Btn("➕ Add Ad",           callback_data="adp|addad"),
         Btn("📋 List Ads",         callback_data="adp|listads")],
        [Btn("📢 Send Ad to All",   callback_data="adp|sendad")],
        [Btn("🔙 Back",             callback_data="adp|home")],
    ])

def admin_users_kb() -> IKM:
    return IKM([
        [Btn("🔍 Find User",    callback_data="adp|finduser"),
         Btn("🚫 Ban User",     callback_data="adp|banuser")],
        [Btn("✅ Unban User",   callback_data="adp|unbanuser"),
         Btn("📊 Top Users",    callback_data="adp|topusers")],
        [Btn("🔙 Back",         callback_data="adp|home")],
    ])

def speed_kb(k: str) -> IKM:
    return IKM([
        [Btn("0.25x 🐢", callback_data=f"spd|0.25|{k}"),
         Btn("0.5x 🐌",  callback_data=f"spd|0.5|{k}"),
         Btn("1.5x 🚶",  callback_data=f"spd|1.5|{k}")],
        [Btn("2x 🏃",    callback_data=f"spd|2.0|{k}"),
         Btn("4x 🚀",    callback_data=f"spd|4.0|{k}")],
        [Btn("❌ Cancel", callback_data="cancel")],
    ])

def schedule_ad_kb(ad_id: int) -> IKM:
    """Keyboard for scheduling ad activation duration."""
    return IKM([
        [Btn("1 day",    callback_data=f"adp|sched|{ad_id}|1"),
         Btn("3 days",   callback_data=f"adp|sched|{ad_id}|3"),
         Btn("7 days",   callback_data=f"adp|sched|{ad_id}|7")],
        [Btn("30 days",  callback_data=f"adp|sched|{ad_id}|30"),
         Btn("♾ Forever", callback_data=f"adp|sched|{ad_id}|0")],
        [Btn("✏️ Custom days", callback_data=f"adp|sched|{ad_id}|custom")],
        [Btn("🔙 Back",  callback_data="adp|listads")],
    ])

def back_to_admin() -> IKM:
    return IKM([[Btn("🔙 Back to Panel", callback_data="adp|home")]])

def ad_item_kb(ad_id: int, is_active: bool) -> IKM:
    tog = "🔴 Pause" if is_active else "🟢 Resume"
    return IKM([[
        Btn(tog,         callback_data=f"adp|tog|{ad_id}"),
        Btn("✏️ Edit",   callback_data=f"adp|edit|{ad_id}"),
        Btn("🗑 Delete", callback_data=f"adp|del|{ad_id}"),
    ]])

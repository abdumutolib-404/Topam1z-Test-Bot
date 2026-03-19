import asyncpg
import logging
import asyncio
from functools import wraps
from config import DATABASE_URL

log = logging.getLogger("bot.database")

_pool: asyncpg.Pool = None   # global pool, created once at startup


def db_retry(max_attempts=3, delay=0.5):
    """Decorator to retry database operations on transient failures."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (asyncpg.TooManyConnectionsError,
                        asyncpg.CannotConnectNowError,
                        asyncio.TimeoutError) as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        log.warning(f"{func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        log.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
                except Exception as e:
                    # Non-retryable errors — fail immediately
                    log.error(f"{func.__name__} non-retryable error: {e}")
                    raise
            # If we exhausted all attempts, raise the last exception
            if last_exception:
                raise last_exception
        return wrapper
    return decorator

async def db_create_pool():
    global _pool
    if not DATABASE_URL:
        log.error("DATABASE_URL is not set. Database functionality will be disabled.")
        return
    try:
        # asyncpg does not accept any query-string params — strip everything after ?
        # Neon adds ?sslmode=require&channel_binding=require which both break asyncpg
        import re as _re
        url = _re.sub(r"\?.*$", "", DATABASE_URL.strip().strip("'\""))
        ssl = "require" if "neon.tech" in url or "supabase" in url else None
        _pool = await asyncpg.create_pool(
            url,
            ssl=ssl,
            min_size=2,          # Neon free tier: keep low to stay within connection limit
            max_size=10,
            max_queries=50000,  # Recycle connections after 50k queries
            max_inactive_connection_lifetime=300,  # Close idle connections after 5 minutes
            command_timeout=30,
            timeout=20,  # Connection acquisition timeout
            statement_cache_size=100,
            # Health check on connection initialization
            init=lambda conn: conn.execute("SELECT 1"),
        )
        log.info("DB     : ✓  asyncpg pool ready (SSL=%s, connections=2-10)", ssl or "off")
    except Exception as e:
        log.error(f"DB     : ✗  Could not connect ({e})")
        log.error("DB     : Bot will run WITHOUT database — downloads work, stats/bans disabled.")
        _pool = None

async def db_init():
    """
    Create all tables from scratch.
    Uses DROP + CREATE on the users table to fix stale schemas from failed
    previous runs. Safe on first boot — no data exists yet.
    All other tables use CREATE IF NOT EXISTS (they are append-only logs).
    """
    if not _pool: return
    async with _pool.acquire() as c:

        # ── Check if users table has the correct primary key ─────────────
        # If uid column is missing, the table is from a broken earlier run.
        # Drop and recreate it — there is no real user data to lose yet.
        has_uid = await c.fetchval("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name='users' AND column_name='uid'
        """)
        if not has_uid:
            log.warning("DB: users table has wrong schema — dropping and recreating")
            await c.execute("DROP TABLE IF EXISTS users CASCADE")

        await c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            uid         BIGINT PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            joined_at   TIMESTAMPTZ DEFAULT NOW(),
            downloads   INTEGER DEFAULT 0,
            edits       INTEGER DEFAULT 0,
            recognitions INTEGER DEFAULT 0,
            lang        TEXT    DEFAULT NULL,
            is_banned   BOOLEAN DEFAULT FALSE,
            ban_reason  TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);

        CREATE TABLE IF NOT EXISTS ads (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL DEFAULT 'Unnamed Ad',
            media_type   TEXT NOT NULL DEFAULT 'text',
            file_id      TEXT,
            caption      TEXT,
            button_label TEXT,
            url          TEXT,
            active       BOOLEAN DEFAULT TRUE,
            impressions  INTEGER DEFAULT 0,
            expires_at   TIMESTAMPTZ DEFAULT NULL,
            created_at   TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_ads_active ON ads(active);
        CREATE INDEX IF NOT EXISTS idx_ads_expires ON ads(expires_at);

        CREATE TABLE IF NOT EXISTS logs (
            id        BIGSERIAL PRIMARY KEY,
            uid       BIGINT,
            action    TEXT,
            detail    TEXT,
            ts        TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts DESC);

        CREATE TABLE IF NOT EXISTS security_log (
            id        BIGSERIAL PRIMARY KEY,
            uid       BIGINT,
            event     TEXT,
            detail    TEXT,
            ip        TEXT,
            ts        TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            day          DATE PRIMARY KEY DEFAULT CURRENT_DATE,
            new_users    INTEGER DEFAULT 0,
            videos       INTEGER DEFAULT 0,
            audios       INTEGER DEFAULT 0,
            music        INTEGER DEFAULT 0,
            gifs         INTEGER DEFAULT 0,
            screenshots  INTEGER DEFAULT 0,
            errors       INTEGER DEFAULT 0,
            commands     INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_daily_stats_day ON daily_stats(day DESC);

        CREATE TABLE IF NOT EXISTS error_log (
            id        BIGSERIAL PRIMARY KEY,
            uid       BIGINT,
            handler   TEXT,
            error     TEXT,
            ts        TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_error_log_ts ON error_log(ts DESC);
        """)

             # ── Users: add any columns missing from old schema ────────────────
        for _col in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS lang       TEXT    DEFAULT NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned  BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason TEXT    DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS downloads     INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS edits         INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS recognitions  INTEGER DEFAULT 0",
        ]:
            try:
                await c.execute(_col)
            except Exception:
                pass

   # ── Safe column migrations for ads table ─────────────────────────
        await c.execute("""
            ALTER TABLE ads DROP COLUMN IF EXISTS ad_type;
            ALTER TABLE ads DROP COLUMN IF EXISTS advertiser_name;
            ALTER TABLE ads DROP COLUMN IF EXISTS budget;
            ALTER TABLE ads DROP COLUMN IF EXISTS cost_per_imp;
            ALTER TABLE ads DROP COLUMN IF EXISTS total_earned;
            ALTER TABLE ads ADD COLUMN IF NOT EXISTS name       TEXT NOT NULL DEFAULT 'Unnamed Ad';
            ALTER TABLE ads ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ DEFAULT NULL;
        """)

    log.info("DB     : ✓  tables & indexes ready")


async def db_get_lang(uid: int) -> str | None:
    """Return the user's saved language code, or None if they never chose one."""
    if not _pool: return None
    async with _pool.acquire() as c:
        val = await c.fetchval("SELECT lang FROM users WHERE uid=$1", uid)
    return val  # None means "never set"; "en"/"ru"/"uz" means explicitly chosen

async def db_set_lang(uid: int, lang: str):
    """Save the user's chosen language."""
    if not _pool: return
    async with _pool.acquire() as c:
        await c.execute(
            "UPDATE users SET lang=$1 WHERE uid=$2", lang, uid)


@db_retry(max_attempts=3)
async def db_register(uid: int, username: str, full_name: str):
    if not _pool: return
    try:
        async with _pool.acquire() as c:
            result = await c.execute("""
                INSERT INTO users (uid, username, full_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (uid) DO UPDATE
                SET username=EXCLUDED.username, full_name=EXCLUDED.full_name
            """, uid, username or "", full_name or "")
            if result == "INSERT 0 1":   # new user
                await db_track("new_users")
    except Exception as e:
        log.error(f"db_register uid={uid}: {e}")

async def db_is_banned(uid: int) -> bool:
    if not _pool: return False
    async with _pool.acquire() as c:
        r = await c.fetchrow("SELECT is_banned FROM users WHERE uid=$1", uid)
        return bool(r and r["is_banned"])

async def db_get_ban_reason(uid: int) -> str:
    """Return ban reason, or empty string if not banned."""
    if not _pool: return ""
    async with _pool.acquire() as c:
        r = await c.fetchrow("SELECT ban_reason FROM users WHERE uid=$1", uid)
        return (r["ban_reason"] or "") if r else ""

async def db_inc_edits(uid: int) -> int:
    if not _pool: return 0
    async with _pool.acquire() as c:
        r = await c.fetchrow(
            "UPDATE users SET edits=edits+1 WHERE uid=$1 RETURNING edits", uid)
        return r["edits"] if r else 0

async def db_inc_recognitions(uid: int) -> int:
    if not _pool: return 0
    async with _pool.acquire() as c:
        r = await c.fetchrow(
            "UPDATE users SET recognitions=recognitions+1 WHERE uid=$1 RETURNING recognitions", uid)
        return r["recognitions"] if r else 0

async def db_ban(uid: int, reason: str = ""):
    if not _pool: return
    async with _pool.acquire() as c:
        await c.execute(
            "UPDATE users SET is_banned=TRUE, ban_reason=$1 WHERE uid=$2",
            reason, uid)

async def db_unban(uid: int):
    if not _pool: return
    async with _pool.acquire() as c:
        await c.execute(
            "UPDATE users SET is_banned=FALSE, ban_reason='' WHERE uid=$1", uid)

async def db_inc_downloads(uid: int) -> int:
    if not _pool: return 0
    async with _pool.acquire() as c:
        r = await c.fetchrow("""
            UPDATE users SET downloads=downloads+1 WHERE uid=$1
            RETURNING downloads
        """, uid)
        return r["downloads"] if r else 0

async def db_get_user(uid: int):
    if not _pool: return None
    async with _pool.acquire() as c:
        return await c.fetchrow("SELECT * FROM users WHERE uid=$1", uid)

async def db_all_users() -> list:
    if not _pool: return []
    async with _pool.acquire() as c:
        return await c.fetch("SELECT uid FROM users WHERE is_banned=FALSE")

async def db_total_users() -> int:
    if not _pool: return 0
    async with _pool.acquire() as c:
        return await c.fetchval("SELECT COUNT(*) FROM users")

async def db_total_banned() -> int:
    if not _pool: return 0
    async with _pool.acquire() as c:
        return await c.fetchval("SELECT COUNT(*) FROM users WHERE is_banned=TRUE")

async def db_log(uid: int, action: str, detail: str = ""):
    if not _pool: return
    try:
        async with _pool.acquire() as c:
            await c.execute(
                "INSERT INTO logs (uid,action,detail) VALUES ($1,$2,$3)",
                uid, action, detail[:500])
    except Exception as e:
        log.debug(f"db_log: {e}")

async def db_recent_logs(limit: int = 20) -> list:
    if not _pool: return []
    async with _pool.acquire() as c:
        return await c.fetch("""
            SELECT uid, action, detail, ts::TEXT AS ts
            FROM logs ORDER BY id DESC LIMIT $1
        """, limit)

_TRACK_COLS = frozenset({
    "new_users","videos","audios","music",
    "gifs","screenshots","errors","commands"
})

async def db_track(col: str):
    """Increment a column in today's daily_stats row atomically."""
    if not _pool: return
    # SECURITY: Use pre-built query mapping to eliminate SQL injection risk entirely
    # Each column has its own prepared query - no string interpolation
    _QUERIES = {
        "new_users": """INSERT INTO daily_stats (day, new_users) VALUES (CURRENT_DATE, 1)
                        ON CONFLICT (day) DO UPDATE SET new_users = daily_stats.new_users + 1""",
        "videos": """INSERT INTO daily_stats (day, videos) VALUES (CURRENT_DATE, 1)
                     ON CONFLICT (day) DO UPDATE SET videos = daily_stats.videos + 1""",
        "audios": """INSERT INTO daily_stats (day, audios) VALUES (CURRENT_DATE, 1)
                     ON CONFLICT (day) DO UPDATE SET audios = daily_stats.audios + 1""",
        "music": """INSERT INTO daily_stats (day, music) VALUES (CURRENT_DATE, 1)
                    ON CONFLICT (day) DO UPDATE SET music = daily_stats.music + 1""",
        "gifs": """INSERT INTO daily_stats (day, gifs) VALUES (CURRENT_DATE, 1)
                   ON CONFLICT (day) DO UPDATE SET gifs = daily_stats.gifs + 1""",
        "screenshots": """INSERT INTO daily_stats (day, screenshots) VALUES (CURRENT_DATE, 1)
                          ON CONFLICT (day) DO UPDATE SET screenshots = daily_stats.screenshots + 1""",
        "errors": """INSERT INTO daily_stats (day, errors) VALUES (CURRENT_DATE, 1)
                     ON CONFLICT (day) DO UPDATE SET errors = daily_stats.errors + 1""",
        "commands": """INSERT INTO daily_stats (day, commands) VALUES (CURRENT_DATE, 1)
                       ON CONFLICT (day) DO UPDATE SET commands = daily_stats.commands + 1""",
    }

    query = _QUERIES.get(col)
    if not query:
        log.warning(f"db_track: invalid col {col!r}")
        return

    try:
        async with _pool.acquire() as c:
            await c.execute(query)
    except Exception as e:
        log.error(f"db_track {col}: {e}")

async def db_stats_overview() -> dict:
    """Full stats for admin panel."""
    if not _pool: return {
        "users": {"total":0,"banned":0,"today":0,"week":0,"month":0,"total_downloads":0,"avg_downloads":0.0},
        "ads":   {"total_ads":0,"active_ads":0,"impressions":0},
        "top_users": [], "week_growth": [], "today": {}, "sec_events_24h": 0,
    }
    async with _pool.acquire() as c:
        users = await c.fetchrow("""
            SELECT
                COUNT(*)                                          AS total,
                COUNT(*) FILTER (WHERE is_banned)                AS banned,
                COUNT(*) FILTER (WHERE joined_at::DATE = CURRENT_DATE) AS today,
                COUNT(*) FILTER (WHERE joined_at >= NOW()-'7 days'::INTERVAL) AS week,
                COUNT(*) FILTER (WHERE joined_at >= NOW()-'30 days'::INTERVAL) AS month,
                COALESCE(SUM(downloads), 0)                       AS total_downloads,
                COALESCE(AVG(downloads), 0)                       AS avg_downloads
            FROM users
        """)
        ads = await c.fetchrow("""
            SELECT
                COUNT(*)                           AS total_ads,
                COUNT(*) FILTER (WHERE active)     AS active_ads,
                COALESCE(SUM(impressions), 0)      AS impressions
            FROM ads
        """)
        top_users = await c.fetch("""
            SELECT uid, username, full_name, downloads
            FROM users
            WHERE downloads > 0
            ORDER BY downloads DESC LIMIT 5
        """)
        week_growth = await c.fetch("""
            SELECT day::TEXT, new_users, videos, audios, music, errors
            FROM daily_stats
            WHERE day >= CURRENT_DATE - 7
            ORDER BY day DESC
        """)
        today = await c.fetchrow("""
            SELECT * FROM daily_stats WHERE day = CURRENT_DATE
        """)
        sec_events = await c.fetchval(
            "SELECT COUNT(*) FROM security_log WHERE ts >= NOW()-'24 hours'::INTERVAL"
        )
    return {
        "users": dict(users),
        "ads":   dict(ads),
        "top_users": [dict(r) for r in top_users],
        "week_growth": [dict(r) for r in week_growth],
        "today": dict(today) if today else {},
        "sec_events_24h": sec_events or 0,
    }

async def db_security_log(uid: int, event: str, detail: str = ""):
    if not _pool: return
    try:
        async with _pool.acquire() as c:
            await c.execute(
                "INSERT INTO security_log (uid,event,detail) VALUES ($1,$2,$3)",
                uid, event, detail[:500])
    except Exception as e:
        log.debug(f"db_security_log: {e}")

async def db_log_error(uid: int, handler: str, error: str):
    if not _pool: return
    try:
        async with _pool.acquire() as c:
            await c.execute(
                "INSERT INTO error_log (uid,handler,error) VALUES ($1,$2,$3)",
                uid, handler, str(error)[:1000])
    except Exception as e:
        log.debug(f"db_log_error: {e}")

async def db_recent_errors(limit: int = 20) -> list:
    if not _pool: return []
    async with _pool.acquire() as c:
        return await c.fetch("""
            SELECT uid, handler, error, ts::TEXT AS ts
            FROM error_log ORDER BY id DESC LIMIT $1
        """, limit)

# ── AD SYSTEM ──────────────────────────────────────────────────────────────
async def db_add_admin_ad(name: str, media_type: str, caption: str,
                          file_id: str = None, url: str = None,
                          button_label: str = None) -> int:
    if not _pool: return 0
    async with _pool.acquire() as c:
        r = await c.fetchrow("""
            INSERT INTO ads (name, media_type, file_id, caption, url, button_label)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """, name, media_type, file_id, caption, url, button_label)
        return r["id"]

async def db_update_ad(ad_id: int, name: str = None, caption: str = None,
                       url: str = None, button_label: str = None):
    """Update editable fields of an ad."""
    if not _pool: return
    async with _pool.acquire() as c:
        if name is not None:
            await c.execute("UPDATE ads SET name=$1 WHERE id=$2", name, ad_id)
        if caption is not None:
            await c.execute("UPDATE ads SET caption=$1 WHERE id=$2", caption, ad_id)
        if url is not None:
            await c.execute("UPDATE ads SET url=$1 WHERE id=$2", url, ad_id)
        if button_label is not None:
            await c.execute("UPDATE ads SET button_label=$1 WHERE id=$2", button_label, ad_id)
        await c.execute("UPDATE ads SET url=NULLIF(url,'') WHERE id=$1", ad_id)

async def db_delete_ad(ad_id: int):
    if not _pool: return
    async with _pool.acquire() as c:
        await c.execute("DELETE FROM ads WHERE id=$1", ad_id)

async def db_toggle_ad(ad_id: int, active: bool):
    if not _pool: return
    async with _pool.acquire() as c:
        await c.execute("UPDATE ads SET active=$1 WHERE id=$2", active, ad_id)

async def db_get_active_ads() -> list:
    """Return active, non-expired ads (max 3 chosen randomly)."""
    if not _pool: return []
    async with _pool.acquire() as c:
        rows = await c.fetch(
            "SELECT * FROM ads WHERE active=TRUE "
            "AND (expires_at IS NULL OR expires_at > NOW()) "
            "ORDER BY RANDOM() LIMIT 3"
        )
    return list(rows)

async def db_expire_ads():
    """Deactivate ads whose expiry time has passed. Called by job queue."""
    if not _pool: return
    async with _pool.acquire() as c:
        changed = await c.execute(
            "UPDATE ads SET active=FALSE "
            "WHERE active=TRUE AND expires_at IS NOT NULL AND expires_at <= NOW()"
        )
    if changed != "UPDATE 0":
        log.info(f"DB: expired ads deactivated ({changed})")

async def db_schedule_ad(ad_id: int, days: int | None):
    """Set or clear expiry date on an ad. days=None clears schedule (runs forever)."""
    if not _pool: return
    async with _pool.acquire() as c:
        if days is None:
            await c.execute("UPDATE ads SET expires_at=NULL WHERE id=$1", ad_id)
        else:
            await c.execute(
                "UPDATE ads SET expires_at=NOW() + ($1 || ' days')::INTERVAL, active=TRUE WHERE id=$2",
                str(days), ad_id
            )

async def db_purge_old_logs():
    """Delete logs/errors/security older than 7 days. Never touches users table.
    Called by hourly job queue — keeps DB lean without touching user data.
    """
    if not _pool: return
    async with _pool.acquire() as c:
        r1 = await c.execute("DELETE FROM logs         WHERE ts < NOW() - INTERVAL '7 days'")
        r2 = await c.execute("DELETE FROM error_log    WHERE ts < NOW() - INTERVAL '7 days'")
        r3 = await c.execute("DELETE FROM security_log WHERE ts < NOW() - INTERVAL '7 days'")
        r4 = await c.execute("DELETE FROM daily_stats  WHERE day < CURRENT_DATE - 30")
    log.info(f"DB purge: logs={r1} errors={r2} security={r3} stats={r4}")

# ── RANK → AD INTERVAL ──────────────────────────────────────────────────
def rank_ad_interval(total_actions: int) -> int:
    """Return how many actions between ads based on user rank.
    Higher rank = fewer ads. 0 = no ads (Legend).
    """
    if total_actions < 10:   return 5   # Newcomer:   every 5 actions
    if total_actions < 50:   return 10  # Beginner:   every 10
    if total_actions < 200:  return 25  # Regular:    every 25
    if total_actions < 500:  return 50  # Active:     every 50
    if total_actions < 2000: return 100 # Power User: every 100
    return 0                            # Legend:     no ads

async def db_imp_ad(ad_id: int):
    if not _pool: return
    async with _pool.acquire() as c:
        await c.execute(
            "UPDATE ads SET impressions = impressions + 1 WHERE id = $1",
            ad_id)

async def db_list_ads() -> list:
    if not _pool: return []
    async with _pool.acquire() as c:
        return await c.fetch(
            "SELECT * FROM ads ORDER BY id DESC")

async def db_ad_stats() -> dict:
    if not _pool: return {"total_ads": 0, "active_ads": 0, "total_impressions": 0}
    async with _pool.acquire() as c:
        r = await c.fetchrow("""
            SELECT
                COUNT(*)                   AS total_ads,
                COUNT(*) FILTER (WHERE active=TRUE) AS active_ads,
                COALESCE(SUM(impressions), 0)        AS total_impressions
            FROM ads
        """)
        return dict(r)

async def get_pool():
    if _pool is None:
        raise RuntimeError("Database pool not initialised — check DATABASE_URL and connection.")
    return _pool

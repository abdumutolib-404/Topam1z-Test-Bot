"""
state.py — Shared mutable runtime state.

Imported by both handlers.py and admin_handlers.py.
Keeps auth, session, and stats data in one place
so neither module needs to import the other (avoids circular imports).
"""
from config import ADMIN_IDS  # noqa: F401 – re-exported for convenience

# ── Per-user session state ────────────────────────────────────────────────
waiting_for:  dict[int, str]   = {}   # uid → what the bot is waiting for
pending_op:   dict[int, dict]  = {}   # uid → cached operation data

# ── Runtime stats (in-memory counters, reset on restart) ─────────────────
stats: dict[str, int] = {
    "videos":      0,
    "audios":      0,
    "music":       0,
    "gifs":        0,
    "screenshots": 0,
    "errors":      0,
}

# ── Admin authentication ──────────────────────────────────────────────────
_admin_auth:  dict[int, bool]  = {}   # uid → True if session authenticated
_fail_counts: dict[int, int]   = {}   # uid → consecutive wrong-password count
_fail_times:  dict[int, float] = {}   # uid → timestamp of first failure in window

# ── Global rate-limit state ───────────────────────────────────────────────
_global_rate: dict[int, float] = {}   # uid → last-request timestamp
GLOBAL_RATE_SEC = 3                   # minimum seconds between requests

# ── Advanced rate limiting per action type ────────────────────────────────
_action_rate: dict[str, dict[int, list[float]]] = {
    "download": {},      # Video/audio downloads
    "convert": {},       # Format conversions
    "profile": {},       # Profile lookups
    "music": {},         # Music recognition
}
ACTION_LIMITS = {
    "download": (10, 60),   # 10 downloads per 60 seconds
    "convert": (5, 60),     # 5 conversions per 60 seconds
    "profile": (5, 60),     # 5 profile lookups per 60 seconds
    "music": (10, 60),      # 10 music searches per 60 seconds
}


def is_admin(uid: int) -> bool:
    """Return True if uid is in the configured ADMIN_IDS set."""
    return uid in ADMIN_IDS


def is_admin_authed(uid: int) -> bool:
    """Return True only if uid is an admin AND has passed the passcode check."""
    return uid in ADMIN_IDS and bool(_admin_auth.get(uid))


def check_action_rate_limit(uid: int, action: str) -> tuple[bool, int]:
    """
    Check if user has exceeded rate limit for a specific action.

    Returns:
        (allowed: bool, wait_seconds: int)
        - If allowed=True, user can proceed
        - If allowed=False, user must wait wait_seconds before retry
    """
    import time

    # Admins bypass rate limits
    if is_admin(uid):
        return (True, 0)

    if action not in ACTION_LIMITS:
        return (True, 0)

    max_actions, window = ACTION_LIMITS[action]
    now = time.time()

    # Initialize tracking for this user/action if needed
    if action not in _action_rate:
        _action_rate[action] = {}
    if uid not in _action_rate[action]:
        _action_rate[action][uid] = []

    # Remove timestamps older than the window
    timestamps = _action_rate[action][uid]
    timestamps[:] = [ts for ts in timestamps if now - ts < window]

    # Check if limit exceeded
    if len(timestamps) >= max_actions:
        oldest = timestamps[0]
        wait = int(window - (now - oldest)) + 1
        return (False, wait)

    # Record this action
    timestamps.append(now)
    return (True, 0)


# ── Per-user download queue (max 3 concurrent per user) ───────────────────
import asyncio as _asyncio

# Global semaphore: max 8 concurrent heavy operations across ALL users
_global_sem = _asyncio.Semaphore(8)

# Per-user semaphore: max 2 concurrent per user
_user_sems: dict[int, _asyncio.Semaphore] = {}

def get_user_sem(uid: int) -> _asyncio.Semaphore:
    if uid not in _user_sems:
        _user_sems[uid] = _asyncio.Semaphore(2)
    return _user_sems[uid]

"""
moviebox_tools.py — MovieBox movie/series download

Official API (from docs.github.com/Simatwa/moviebox-api):
    from moviebox_api import MovieAuto
    movie_file, subtitle_file = await auto.run("Avatar")
    # movie_file.saved_to  →  Path to downloaded file

MovieAuto.run() handles: search → pick best match → download.
There is NO separate search method.
"""
import asyncio
import logging
import os

from config import TMPDIR

log = logging.getLogger("bot.moviebox")


def _run_sync(coro):
    """Run coroutine in a fresh event loop — safe inside ThreadPoolExecutor."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def mb_search(query: str, limit: int = 20) -> list[dict]:
    """MovieAuto has no search-only method.
    We return a single synthetic result so the bot can show the
    movie name and let the user confirm before downloading.
    """
    # Return a fake single-item result — the actual download happens
    # via mb_download which calls auto.run(query) directly.
    return [{
        "title":  query,
        "year":   "",
        "type":   "movie",
        "id":     query,      # id IS the search query for MovieAuto
        "rating": "",
    }]


async def mb_download(item_id: str, media_type: str = "movie",
                      quality: str = "1080p") -> tuple[str | None, dict]:
    """Download movie/series using MovieAuto.run(title).

    item_id here is the movie title (set by mb_search above).
    quality: "480p" | "720p" | "1080p" | best
    """
    import uuid
    loop = asyncio.get_running_loop()
    uid  = uuid.uuid4().hex
    dest = os.path.join(TMPDIR, f"mb_{uid}")
    os.makedirs(dest, exist_ok=True)

    def _download():
        async def _do():
            from moviebox_api import MovieAuto
            # Map quality: "best" → None (auto), others pass as-is
            q = None if quality == "best" else quality
            kwargs = dict(
                quality=q,
                download_dir=dest,
            )
            # Remove None values
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            auto = MovieAuto(**kwargs)
            movie_file, _subtitle = await auto.run(item_id)
            path = str(movie_file.saved_to)
            if os.path.exists(path) and os.path.getsize(path) > 1024:
                title = os.path.splitext(os.path.basename(path))[0]
                return path, {"title": title}
            return None, {}
        return _run_sync(_do())

    try:
        path, info = await loop.run_in_executor(None, _download)
        return path, info
    except Exception as e:
        log.error(f"mb_download [{item_id}]: {e}")
        return None, {}

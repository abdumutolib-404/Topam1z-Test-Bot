"""
moviebox_tools.py — MovieBox via MovieAuto (official API)

From docs:
    auto = MovieAuto(quality="720p", download_dir="path")
    movie_file, subtitle_file = await auto.run("Avatar")
    path = movie_file.saved_to
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
    """MovieAuto handles search internally in .run().
    Return a single result so the bot shows the quality picker.
    """
    return [{
        "title":  query,
        "year":   "",
        "type":   "movie",
        "id":     query,
        "rating": "",
    }]


async def mb_download(item_id: str, media_type: str = "movie",
                      quality: str = "1080p") -> tuple[str | None, dict]:
    """Download using exact API from official docs:
        auto = MovieAuto(quality="1080p", download_dir=dest)
        movie_file, subtitle_file = await auto.run(title)
        path = movie_file.saved_to
    """
    import uuid
    loop = asyncio.get_running_loop()
    uid  = uuid.uuid4().hex
    dest = os.path.join(TMPDIR, f"mb_{uid}")
    os.makedirs(dest, exist_ok=True)

    q = None if quality == "best" else quality

    def _download():
        async def _do():
            from moviebox_api import MovieAuto

            # Build kwargs — only pass quality if specified
            kwargs = {"download_dir": dest}
            if q:
                kwargs["quality"] = q

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

"""
moviebox_tools.py — MovieBox movie/series search/download via MovieAuto
"""
import asyncio
import logging
import os
import glob

from config import TMPDIR

log = logging.getLogger("bot.moviebox")


def _run_in_new_loop(coro):
    """Run an async coroutine in a brand-new event loop (safe for threads)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def mb_search(query: str, limit: int = 20) -> list[dict]:
    """Search MovieBox. Returns list of {title, year, type, id, rating}"""
    loop = asyncio.get_running_loop()
    try:
        from moviebox_api import MovieAuto

        def _search():
            async def _do():
                auto = MovieAuto()
                results = await auto.search(query)
                out = []
                for r in (results or [])[:limit]:
                    out.append({
                        "title":  getattr(r, "title",  str(r)),
                        "year":   str(getattr(r, "year",   "") or ""),
                        "type":   getattr(r, "type",   "movie"),
                        "id":     str(getattr(r, "id",    "") or ""),
                        "rating": str(getattr(r, "rating", "") or ""),
                    })
                return out
            return _run_in_new_loop(_do())

        return await loop.run_in_executor(None, _search)
    except Exception as e:
        log.error(f"mb_search: {e}")
        return []


async def mb_download(item_id: str, media_type: str = "movie",
                      quality: str = "best") -> tuple[str | None, dict]:
    """Download a movie/episode using MovieAuto.run()."""
    import uuid
    loop = asyncio.get_running_loop()
    uid  = uuid.uuid4().hex
    dest = os.path.join(TMPDIR, f"mb_{uid}")
    os.makedirs(dest, exist_ok=True)

    try:
        from moviebox_api import MovieAuto

        def _download():
            async def _do():
                auto = MovieAuto(directory=dest, confirm=True)
                result = await auto.run(item_id, quality=quality)
                movie_file = result[0] if isinstance(result, (list, tuple)) else result
                path = getattr(movie_file, "saved_to",
                        getattr(movie_file, "path", None))
                if path and os.path.exists(path) and os.path.getsize(path) > 1024:
                    return path, {"title": item_id}
                # Fallback: scan dest directory
                files = [
                    f for f in glob.glob(f"{dest}/**/*", recursive=True)
                    if os.path.isfile(f) and os.path.getsize(f) > 1024
                ]
                if files:
                    return max(files, key=os.path.getsize), {"title": item_id}
                return None, {}

            return _run_in_new_loop(_do())

        path, info = await loop.run_in_executor(None, _download)
        return path, info
    except Exception as e:
        log.error(f"mb_download {item_id}: {e}")
        return None, {}

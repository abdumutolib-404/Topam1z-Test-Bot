"""
moviebox_tools.py — MovieBox movie/series download via MovieAuto

Correct API: from moviebox_api import MovieAuto
MovieAuto is fully async, downloads movie + subtitle in one call.
"""
import asyncio
import logging
import os
import glob

from config import TMPDIR

log = logging.getLogger("bot.moviebox")


async def mb_search(query: str, limit: int = 20) -> list[dict]:
    """Search MovieBox. Returns list of {title, year, type, id}"""
    loop = asyncio.get_running_loop()
    try:
        from moviebox_api import MovieAuto

        def _search():
            import asyncio as _a
            auto = MovieAuto()
            # MovieAuto.search returns a coroutine — run it synchronously
            results = _a.get_event_loop().run_until_complete(auto.search(query))
            out = []
            for r in (results or [])[:limit]:
                out.append({
                    "title":  getattr(r, "title",  str(r)),
                    "year":   str(getattr(r, "year", "") or ""),
                    "type":   getattr(r, "type",   "movie"),
                    "id":     str(getattr(r, "id",    "") or ""),
                    "rating": str(getattr(r, "rating", "") or ""),
                })
            return out

        return await loop.run_in_executor(None, _search)
    except Exception as e:
        log.error(f"mb_search: {e}")
        return []


async def mb_download(item_id: str, media_type: str = "movie",
                      quality: str = "best") -> tuple[str | None, dict]:
    """Download a movie/episode using MovieAuto.

    MovieAuto.run(title) handles search + download automatically.
    Returns (filepath, info_dict) or (None, {}) on failure.
    """
    import uuid
    loop = asyncio.get_running_loop()
    uid  = uuid.uuid4().hex
    dest = os.path.join(TMPDIR, f"mb_{uid}")
    os.makedirs(dest, exist_ok=True)

    try:
        from moviebox_api import MovieAuto

        def _download():
            import asyncio as _a

            async def _run():
                auto = MovieAuto(directory=dest, confirm=True)
                # run() returns (movie_file, subtitle_file)
                result = await auto.run(item_id, quality=quality)
                return result

            try:
                movie_file, _ = _a.get_event_loop().run_until_complete(_run())
                path = getattr(movie_file, "saved_to", None)
                if path and os.path.exists(path) and os.path.getsize(path) > 1024:
                    return path, {"title": item_id}
            except Exception as e:
                log.error(f"mb_download _run: {e}")

            # Fallback: find any downloaded file in dest
            files = [f for f in glob.glob(f"{dest}/**/*", recursive=True)
                     if os.path.isfile(f) and os.path.getsize(f) > 1024]
            if files:
                return max(files, key=os.path.getsize), {"title": item_id}
            return None, {}

        path, info = await loop.run_in_executor(None, _download)
        return path, info
    except Exception as e:
        log.error(f"mb_download {item_id}: {e}")
        return None, {}

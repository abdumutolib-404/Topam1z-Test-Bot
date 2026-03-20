"""
moviebox_tools.py — MovieBox.ph movie & TV series search/download

No API key required. Wraps the unofficial moviebox-api library.
Async-first, uses thread executor for blocking calls.
"""
import asyncio
import logging
import os

from config import TMPDIR

log = logging.getLogger("bot.moviebox")


async def mb_search(query: str, limit: int = 10) -> list[dict]:
    """Search movies and TV series on MovieBox.
    Returns list of dicts: {id, title, year, type, poster, rating}
    """
    loop = asyncio.get_running_loop()
    try:
        from moviebox_api import MovieBox
        def _search():
            mb = MovieBox()
            results = mb.search(query)
            out = []
            for r in (results or [])[:limit]:
                out.append({
                    "id":     getattr(r, "id",     None),
                    "title":  getattr(r, "title",  str(r)),
                    "year":   getattr(r, "year",   ""),
                    "type":   getattr(r, "type",   "movie"),
                    "poster": getattr(r, "poster", ""),
                    "rating": getattr(r, "rating", ""),
                })
            return out
        return await loop.run_in_executor(None, _search)
    except Exception as e:
        log.error(f"mb_search: {e}")
        return []


async def mb_get_streams(item_id: str, media_type: str = "movie") -> list[dict]:
    """Get available stream/download URLs for a title.
    Returns list of dicts: {quality, url, size}
    """
    loop = asyncio.get_running_loop()
    try:
        from moviebox_api import MovieBox
        def _streams():
            mb = MovieBox()
            if media_type == "movie":
                detail = mb.get_movie(item_id)
            else:
                detail = mb.get_series(item_id)
            streams = []
            sources = getattr(detail, "sources", []) or getattr(detail, "streams", []) or []
            for s in sources:
                streams.append({
                    "quality": getattr(s, "quality", getattr(s, "resolution", "?")),
                    "url":     getattr(s, "url",     getattr(s, "link",  "")),
                    "size":    getattr(s, "size",    ""),
                })
            return streams
        return await loop.run_in_executor(None, _streams)
    except Exception as e:
        log.error(f"mb_get_streams {item_id}: {e}")
        return []


async def mb_download(item_id: str, media_type: str = "movie",
                      quality: str = "1080p") -> tuple[str | None, dict]:
    """Download a movie/episode to TMPDIR.
    Returns (filepath, info_dict) or (None, {}) on failure.
    """
    import uuid
    loop = asyncio.get_running_loop()
    uid  = uuid.uuid4().hex
    dest = os.path.join(TMPDIR, uid)
    os.makedirs(dest, exist_ok=True)

    try:
        from moviebox_api import MovieBox
        def _download():
            mb    = MovieBox()
            title = "video"
            if media_type == "movie":
                result = mb.download_movie(
                    item_id,
                    quality=quality,
                    directory=dest,
                    confirm=True,
                )
            else:
                result = mb.download_episode(
                    item_id,
                    quality=quality,
                    directory=dest,
                    confirm=True,
                )
            # Find the downloaded file
            files = [os.path.join(dest, f) for f in os.listdir(dest)
                     if os.path.getsize(os.path.join(dest, f)) > 1024]
            if not files:
                return None, {}
            path  = max(files, key=os.path.getsize)
            info  = {
                "title": getattr(result, "title", os.path.basename(path)),
                "year":  getattr(result, "year",  ""),
            }
            return path, info
        path, info = await loop.run_in_executor(None, _download)
        return path, info
    except Exception as e:
        log.error(f"mb_download {item_id}: {e}")
        return None, {}

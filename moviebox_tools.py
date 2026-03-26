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
from typing import Any

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
    """Search MovieBox for movies/series.
    
    Returns list of results with: title, year, type, id, rating
    
    Note: MovieAuto.run() handles search internally, so we return a simplified
    result that triggers download when user selects quality.
    """
    try:
        # MovieAuto doesn't expose search separately from download
        # Return query as single result - MovieAuto.run() will search when downloading
        return [{
            "title":  query,
            "year":   "",
            "type":   "movie",
            "id":     query,  # Query is used as ID for MovieAuto.run()
            "rating": "",
        }]
    except Exception as e:
        log.error(f"mb_search [{query}]: {e}")
        return []


async def mb_download(item_id: str, media_type: str = "movie",
                      quality: str = "1080p") -> tuple[str | None, dict]:
    """Download movie/series using MovieAuto API.
    
    Args:
        item_id: Movie title or ID (MovieAuto uses title for search)
        media_type: "movie" or "tv" (not used - kept for compatibility)
        quality: "480p", "720p", "1080p", or "best"
    
    Returns:
        (path, info_dict) where path is local file, info has title
    """
    import uuid
    loop = asyncio.get_running_loop()
    uid  = uuid.uuid4().hex
    dest = os.path.join(TMPDIR, f"mb_{uid}")
    os.makedirs(dest, exist_ok=True)

    # Normalize quality parameter
    q = (quality or "best").strip().lower()
    
    # MovieAuto expects quality as "720p" format or None for best
    if q in ("best", "highest", "max"):
        q = None  # Let MovieAuto pick best available
    elif q.endswith("p"):
        # Already in correct format: "720p", "1080p", etc.
        pass
    elif q.isdigit():
        # User sent just number: "720" -> "720p"
        q = f"{q}p"
    else:
        # Invalid format - use best
        log.warning(f"Invalid quality '{quality}', using best")
        q = None

    def _download():
        """Sync wrapper for MovieAuto download."""
        async def _do():
            try:
                from moviebox_api import MovieAuto

                # Build kwargs - only pass quality if specified
                kwargs: dict[str, Any] = {"download_dir": dest}
                if q:
                    kwargs["quality"] = q

                log.info(f"MovieAuto download: '{item_id}' quality={q or 'best'}")
                auto = MovieAuto(**kwargs)
                
                # MovieAuto.run() searches and downloads in one call
                # Timeout: 10 minutes max (large files can take time)
                movie_file, _subtitle = await asyncio.wait_for(
                    auto.run(item_id), 
                    timeout=600
                )
                
                if not movie_file or not movie_file.saved_to:
                    log.error(f"MovieAuto returned no file for '{item_id}'")
                    return None, {}
                
                path = str(movie_file.saved_to)
                
                # Verify file exists and has content
                if not os.path.exists(path):
                    log.error(f"MovieAuto returned path {path} but file doesn't exist")
                    return None, {}
                
                file_size = os.path.getsize(path)
                if file_size < 1024:
                    log.error(f"MovieAuto file too small: {file_size} bytes")
                    return None, {}
                
                # Extract title from filename
                title = os.path.splitext(os.path.basename(path))[0]
                
                log.info(f"MovieAuto success: {path} ({file_size:,} bytes)")
                return path, {"title": title, "size": file_size}
                
            except asyncio.TimeoutError:
                log.error(f"MovieAuto timeout (10min) for '{item_id}'")
                return None, {}
            except ImportError as e:
                log.error(f"MovieAuto import failed: {e}")
                return None, {}
            except Exception as e:
                log.error(f"MovieAuto error for '{item_id}': {type(e).__name__}: {e}")
                return None, {}

        return _run_sync(_do())

    try:
        path, info = await loop.run_in_executor(None, _download)
        return path, info
    except Exception as e:
        log.error(f"mb_download outer exception [{item_id}]: {e}")
        return None, {}

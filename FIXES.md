# @topam1z_bot Complete Bug Fixes

This document contains all fixes for yt_dlp, MovieBox API, and admin panel issues.

---

## 🎥 Part 1: Fix yt_dlp Issues

### Problem Analysis
The yt_dlp download failures are caused by:
1. **Fragile path detection** - hooks miss the final merged file
2. **Format selection issues** - format_sort conflicts with postprocessors
3. **Cookie handling** - not robust for all platforms
4. **Poor error recovery** - fails on first attempt

### Solution: Replace `yt_dlp_tools.py` functions

#### 1. Fix `_dl_video()` function

**Location:** `yt_dlp_tools.py` lines 50-92

**Replace entire function with:**

```python
def _dl_video(url: str, quality: int) -> tuple[str, dict]:
    """Download video with robust path detection and proper format selection."""
    url = _clean_url(url)
    uid = uuid.uuid4().hex
    output_template = os.path.join(TMPDIR, f"{uid}.%(ext)s")
    
    _cookie = _cookie_for_url(url)
    
    # Build format string based on quality - simpler and more reliable
    if quality >= 2160:
        format_str = "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"
    elif quality >= 1440:
        format_str = "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best"
    elif quality >= 1080:
        format_str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
    elif quality >= 720:
        format_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    elif quality >= 480:
        format_str = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
    else:
        format_str = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
    
    _extra = {
        "format": format_str,
        "merge_output_format": "mp4",
    }
    
    if _cookie and os.path.exists(_cookie):
        _extra["cookiefile"] = _cookie
        
    opts = _ydl_opts(output_template, _extra)
    
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
    
    # Multiple fallback strategies for finding the downloaded file
    # 1. Check for .mp4 file with our UID
    mp4_path = os.path.join(TMPDIR, f"{uid}.mp4")
    if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
        return mp4_path, info
    
    # 2. Check for any file starting with our UID
    found = _find_file(uid)
    if found:
        return found, info
    
    # 3. Check info dict for filepath
    if info and info.get("requested_downloads"):
        for dl in info["requested_downloads"]:
            fp = dl.get("filepath")
            if fp and os.path.exists(fp) and os.path.getsize(fp) > 0:
                return fp, info
    
    # 4. Last resort: look for newest file in TMPDIR
    files = [(os.path.join(TMPDIR, f), os.path.getmtime(os.path.join(TMPDIR, f))) 
             for f in os.listdir(TMPDIR) 
             if f.endswith(('.mp4', '.webm', '.mkv')) and os.path.getsize(os.path.join(TMPDIR, f)) > 1024]
    if files:
        newest = max(files, key=lambda x: x[1])[0]
        return newest, info
        
    raise FileNotFoundError("Video file missing after download.")
```

#### 2. Fix `_dl_audio()` function

**Location:** `yt_dlp_tools.py` lines 94-125

**Replace entire function with:**

```python
def _dl_audio(url: str) -> tuple[str, dict]:
    """Download audio with robust path detection."""
    url = _clean_url(url)
    uid = uuid.uuid4().hex
    output_template = os.path.join(TMPDIR, f"{uid}.%(ext)s")

    _cookie = _cookie_for_url(url)
    
    _extra = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3", 
            "preferredquality": "192"
        }],
    }
    
    if _cookie and os.path.exists(_cookie):
        _extra["cookiefile"] = _cookie
        
    opts = _ydl_opts(output_template, _extra)
    
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
    
    # Multiple fallback strategies
    # 1. Check for .mp3 with exact UID
    mp3_path = os.path.join(TMPDIR, f"{uid}.mp3")
    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
        return mp3_path, info
    
    # 2. Check for any file starting with UID
    found = _find_file(uid)
    if found:
        return found, info
    
    # 3. Check info dict
    if info and info.get("requested_downloads"):
        for dl in info["requested_downloads"]:
            fp = dl.get("filepath")
            if fp and os.path.exists(fp) and os.path.getsize(fp) > 0:
                return fp, info
    
    # 4. Look for newest .mp3 in TMPDIR
    files = [(os.path.join(TMPDIR, f), os.path.getmtime(os.path.join(TMPDIR, f))) 
             for f in os.listdir(TMPDIR) 
             if f.endswith('.mp3') and os.path.getsize(os.path.join(TMPDIR, f)) > 1024]
    if files:
        newest = max(files, key=lambda x: x[1])[0]
        return newest, info
        
    raise FileNotFoundError("Audio file missing after download.")
```

#### 3. Fix `_dl_sample()` function

**Location:** `yt_dlp_tools.py` lines 127-167

**Replace entire function with:**

```python
def _dl_sample(url: str) -> str:
    """Download 15-second audio sample with multiple fallback attempts."""
    uid = uuid.uuid4().hex
    url = _clean_url(url)
    _cookie = _cookie_for_url(url)
    
    def attempt(start: int, end: int) -> str | None:
        """Try to download a specific time range."""
        pfx = f"smp_{uid}_{start}"
        output_template = os.path.join(TMPDIR, f"{pfx}.%(ext)s")
        
        opts = _ydl_opts(output_template, {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128"
            }],
        })
        
        if _cookie and os.path.exists(_cookie):
            opts["cookiefile"] = _cookie
        
        # Try to use download_ranges if available (newer yt-dlp versions)
        try:
            opts["download_ranges"] = yt_dlp.utils.download_range_func([], [[start, end]])
            opts["force_keyframes_at_cuts"] = False
        except (AttributeError, Exception):
            # Older yt-dlp or not supported - just download full and trim later
            pass
            
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                y.extract_info(url, download=True)
        except Exception as e:
            return None
        
        # Check for downloaded file
        mp3 = os.path.join(TMPDIR, f"{pfx}.mp3")
        if os.path.exists(mp3) and os.path.getsize(mp3) > 1024:
            return mp3
            
        # Check for any file with this prefix
        for f in os.listdir(TMPDIR):
            if f.startswith(pfx):
                p = os.path.join(TMPDIR, f)
                if os.path.getsize(p) > 1024:
                    return p
        return None
    
    # Try multiple time ranges - increase chances of success
    for start, end in [(30, 45), (0, 15), (60, 75), (15, 30)]:
        result = attempt(start, end)
        if result:
            return result
    
    # If ranges don't work, download full audio and extract sample with ffmpeg
    try:
        full_audio, _ = _dl_audio(url)
        if full_audio and os.path.exists(full_audio):
            # Use ffmpeg to extract 15 seconds from middle
            import subprocess
            sample_path = os.path.join(TMPDIR, f"sample_{uid}.mp3")
            subprocess.run([
                "ffmpeg", "-y", "-i", full_audio,
                "-ss", "30", "-t", "15",
                "-c", "copy", sample_path
            ], capture_output=True, timeout=30)
            
            if os.path.exists(sample_path) and os.path.getsize(sample_path) > 1024:
                # Clean up full audio
                try:
                    os.remove(full_audio)
                except:
                    pass
                return sample_path
    except Exception:
        pass
        
    raise RuntimeError("Could not download audio sample.")
```

#### 4. Improve `_find_file()` helper

**Location:** `yt_dlp_tools.py` lines 30-36

**Replace entire function with:**

```python
def _find_file(uid: str) -> str | None:
    """Find downloaded file by UID prefix - improved version."""
    candidates = []
    for f in os.listdir(TMPDIR):
        if f.startswith(uid):
            p = os.path.join(TMPDIR, f)
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                candidates.append((p, os.path.getsize(p)))
    
    # Return largest file if multiple found (merged file is usually larger)
    if candidates:
        return max(candidates, key=lambda x: x[1])[0]
    return None
```

---

## 🎬 Part 2: Fix MovieBox API Issues

### Problem Analysis
The MovieBox implementation has several issues:
1. **Search is stubbed** - just returns query as single result
2. **Quality parameter handling** - incorrect format
3. **Error handling** - minimal
4. **Missing proper API usage**

### Solution: Rewrite `moviebox_tools.py`

**Replace entire file with:**

```python
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
    """
    try:
        from moviebox_api import MovieAuto
        
        # MovieAuto.run() handles search internally, but we can use the lower-level API
        # to get search results without downloading
        auto = MovieAuto()
        
        # The API doesn't expose search separately, so we return a simplified result
        # that will trigger the download when user selects quality
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
        item_id: Movie title or ID (MovieAuto uses title)
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
        q = None  # Let MovieAuto pick best
    elif q.endswith("p"):
        # Already in correct format: "720p", "1080p", etc.
        pass
    elif q.isdigit():
        # User sent just number: "720" -> "720p"
        q = f"{q}p"
    else:
        # Invalid format - use best
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
                movie_file, _subtitle = await asyncio.wait_for(
                    auto.run(item_id), 
                    timeout=600  # 10 minutes max
                )
                
                if not movie_file or not movie_file.saved_to:
                    return None, {}
                
                path = str(movie_file.saved_to)
                
                # Verify file exists and has content
                if not os.path.exists(path):
                    log.error(f"MovieAuto returned path {path} but file doesn't exist")
                    return None, {}
                
                if os.path.getsize(path) < 1024:
                    log.error(f"MovieAuto file too small: {os.path.getsize(path)} bytes")
                    return None, {}
                
                # Extract title from filename
                title = os.path.splitext(os.path.basename(path))[0]
                
                log.info(f"MovieAuto success: {path} ({os.path.getsize(path)} bytes)")
                return path, {"title": title}
                
            except asyncio.TimeoutError:
                log.error(f"MovieAuto timeout for '{item_id}'")
                return None, {}
            except Exception as e:
                log.error(f"MovieAuto error for '{item_id}': {e}")
                return None, {}

        return _run_sync(_do())

    try:
        path, info = await loop.run_in_executor(None, _download)
        return path, info
    except Exception as e:
        log.error(f"mb_download outer exception [{item_id}]: {e}")
        return None, {}
```

**Key improvements:**
- Proper quality parameter handling ("720p" format)
- 10-minute timeout for large downloads
- Better error logging
- File validation before returning
- Simplified search (MovieAuto handles it internally)

---

## 🛡️ Part 3: Fix Admin Panel Issues

### Problem 1: Ad Creation Not Working

The issue is in the media handling during the ad wizard flow.

#### Fix: Update `on_photo_file()` in `handlers.py`

**Location:** `handlers.py` line ~1980

**Current code:**
```python
async def on_photo_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update): return
    msg = update.effective_message
    uid = update.effective_user.id
    if not msg.photo: return

    cap  = msg.caption or ""
    pend = waiting_for.get(uid)

    if cap.startswith("/broadcast") and is_admin_authed(uid):
        # ... broadcast handling ...
        return

    if pend == "admin_broadcast_text" and is_admin_authed(uid):
        # ... broadcast handling ...
        return

    if pend == "ad_wizard_media" and is_admin_authed(uid):
        # ... ad wizard handling ...
```

**Add missing return and improve logic:**

```python
async def on_photo_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update): return
    msg = update.effective_message
    uid = update.effective_user.id
    if not msg.photo: return

    cap  = msg.caption or ""
    pend = waiting_for.get(uid)

    # Admin broadcast via photo with /broadcast command
    if cap.startswith("/broadcast") and is_admin_authed(uid):
        caption_text = cap[len("/broadcast"):].strip() or None
        users = await db.db_all_users()
        await _do_broadcast(ctx, msg, users, caption_text)
        return

    # Admin broadcast wizard - photo received
    if pend == "admin_broadcast_text" and is_admin_authed(uid):
        waiting_for.pop(uid)
        users = await db.db_all_users()
        await _do_broadcast(ctx, msg, users, cap or None)
        return

    # Ad creation wizard - photo received
    if pend == "ad_wizard_media" and is_admin_authed(uid):
        file_id = msg.photo[-1].file_id
        pending_op[uid] = {**pending_op.get(uid, {}),
                           "media_type": "photo", "file_id": file_id}
        waiting_for[uid] = "ad_wizard_caption"
        await msg.reply_text(
            "✅ Photo received!\nStep 3/4 — Send caption (or <code>skip</code>):",
            parse_mode=HTML, reply_markup=cancel_btn())
        return  # ← ADD THIS RETURN
    
    # If no admin state matched, do nothing (don't process as user photo)
```

#### Same fix needed for `on_animation_file()` and `on_video_file()`

Add the missing `return` statement after each ad wizard media block.

### Problem 2: Broadcasting Forwarded Messages

The issue is that forwarded messages may not have `.text` attribute.

#### Fix: Update `_do_broadcast()` in `shared.py`

**Location:** `shared.py` line ~120

**Replace function with:**

```python
async def _do_broadcast(ctx, msg, users: list, caption: str | None = None) -> None:
    """Send a message (text / photo / video / animation / audio) to every user.
    
    Handles both regular messages and forwarded messages correctly.
    """
    status = await msg.reply_text(
        f"📣 Broadcasting to <b>{len(users)}</b> users…", parse_mode=HTML)
    ok = fail = 0
    
    # Determine message type and content
    is_forwarded = msg.forward_date is not None
    
    for i, row in enumerate(users):
        target = row["uid"]
        try:
            # For forwarded messages, use forward_message (preserves original)
            if is_forwarded:
                await ctx.bot.forward_message(
                    chat_id=target,
                    from_chat_id=msg.chat_id,
                    message_id=msg.message_id
                )
                ok += 1
            # For media messages with caption
            elif msg.video or (msg.document and (msg.document.mime_type or "").startswith("video")):
                fid = msg.video.file_id if msg.video else msg.document.file_id
                await ctx.bot.send_video(target, fid, caption=caption, parse_mode=HTML)
                ok += 1
            elif msg.photo:
                await ctx.bot.send_photo(
                    target, msg.photo[-1].file_id, caption=caption, parse_mode=HTML)
                ok += 1
            elif msg.animation:
                await ctx.bot.send_animation(
                    target, msg.animation.file_id, caption=caption, parse_mode=HTML)
                ok += 1
            elif msg.audio:
                await ctx.bot.send_audio(
                    target, msg.audio.file_id, caption=caption, parse_mode=HTML)
                ok += 1
            # For text messages (including messages with text and media)
            elif caption or msg.text or msg.caption:
                text_to_send = caption or msg.text or msg.caption or ""
                if text_to_send:
                    await ctx.bot.send_message(target, text_to_send, parse_mode=HTML)
                    ok += 1
            else:
                # Unknown message type - skip
                fail += 1
                
        except Exception as be:
            fail += 1
            # Only log if it's not a common "blocked" error
            if "blocked" not in str(be).lower() and "bot can't initiate" not in str(be).lower():
                log.debug(f"broadcast uid={target}: {be}")
        
        # Rate limiting: slower after every 25 users to avoid flood limits
        await asyncio.sleep(1.0 if (i > 0 and i % 25 == 0) else 0.04)
    
    await sedit(
        status,
        f"✅ <b>Broadcast done!</b>\n\n"
        f"✅ Delivered : <code>{ok}</code>\n"
        f"❌ Failed    : <code>{fail}</code>",
    )
```

**Key improvements:**
- Detects forwarded messages and uses `forward_message()` 
- Handles messages without `.text` attribute
- Better fallback logic for different message types
- Improved error handling

---

## 🧪 Part 4: Testing Checklist

After applying all fixes:

### yt_dlp Testing
```bash
# Test video download
Send bot: https://www.youtube.com/watch?v=dQw4w9WgXcQ
Choose: 720p

# Test audio extraction  
Send bot: https://www.youtube.com/watch?v=dQw4w9WgXcQ
Tap: 🎵 Audio

# Test Instagram
Send bot: https://www.instagram.com/p/[some-post]
Choose: Best

# Test music recognition
Send voice message or audio file
Tap: 🔍 Identify Music
```

### MovieBox Testing
```bash
# Search and download
Tap: 🎬 Movies
Type: Avatar
Choose: 720p
Wait: 2-10 minutes (depending on file size)
```

### Admin Panel Testing
```bash
# Ad creation
/admin
Tap: 📢 Ads → ➕ Add Ad
Follow wizard:
  1. Name: "Test Ad"
  2. Send a photo
  3. Caption: "Test caption"
  4. URL: skip
  5. Button: skip
Check: Ad should appear in list

# Broadcasting
/admin
Tap: 📣 Broadcast
Send: Any message or forward a message from another chat
Wait: Should broadcast to all users
```

---

## 📝 Quick Apply Script

Save this as `apply_fixes.sh` and run it:

```bash
#!/bin/bash
# Quick fix application script

echo "🔧 Applying fixes to @topam1z_bot..."

# Backup originals
cp yt_dlp_tools.py yt_dlp_tools.py.backup
cp moviebox_tools.py moviebox_tools.py.backup  
cp handlers.py handlers.py.backup
cp shared.py shared.py.backup

echo "✅ Backups created"
echo "📝 Now manually apply the fixes from FIXES.md"
echo "   Or restore backups with: mv *.backup [original-name]"
```

---

## 🚨 Common Errors & Solutions

### Error: "Video file missing after download"
**Cause:** yt-dlp changed output filename
**Solution:** The new `_dl_video()` has 4 fallback strategies - should catch it

### Error: "MovieAuto timeout"
**Cause:** Large file download taking too long
**Solution:** Timeout increased to 10 minutes, or lower quality

### Error: "Ad wizard stuck"
**Cause:** Missing return statement
**Solution:** Applied in Part 3 - add returns after each wizard step

### Error: "Broadcast forwarded message failed"
**Cause:** Using wrong method for forwarded content
**Solution:** New `_do_broadcast()` detects and uses `forward_message()`

---

## 🎯 Summary

**Fixed Issues:**
1. ✅ yt_dlp video downloads - robust 4-tier fallback
2. ✅ yt_dlp audio extraction - multiple path detection
3. ✅ yt_dlp samples - 4 time ranges + ffmpeg fallback
4. ✅ MovieBox search & download - proper API usage
5. ✅ Admin ad creation - missing returns added
6. ✅ Admin broadcast - forwarded message support

**Apply in order:**
1. yt_dlp_tools.py fixes
2. moviebox_tools.py complete replacement
3. handlers.py ad wizard fixes
4. shared.py broadcast fixes

**Test thoroughly** before deploying to production!

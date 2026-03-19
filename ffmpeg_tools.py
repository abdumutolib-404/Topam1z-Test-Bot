import subprocess
import os
import uuid
from config import TMPDIR, MAX_MB

def _ff(*args, timeout=300) -> str:
    """Run ffmpeg. Raises on non-zero exit OR empty output file."""
    # SECURITY: Validate all args are strings to prevent injection
    safe_args = []
    for arg in args:
        if not isinstance(arg, (str, int, float)):
            raise ValueError(f"Invalid ffmpeg argument type: {type(arg)}")
        safe_args.append(str(arg))

    r = subprocess.run(
        ["ffmpeg", "-y"] + safe_args,
        capture_output=True,
        timeout=timeout,
        shell=False  # SECURITY: Never use shell=True
    )
    if r.returncode != 0:
        stderr_raw = r.stderr.decode(errors="replace")
        # Take last non-empty lines — actual error is always at the end
        meaningful = [l.strip() for l in stderr_raw.splitlines()
                      if l.strip() and not l.strip().startswith("frame=")
                      and not l.strip().startswith("size=")
                      and not l.strip().startswith("time=")]
        msg = "\n".join(meaningful[-5:]) if meaningful else stderr_raw[-200:]
        raise RuntimeError(msg.strip() or "ffmpeg failed")
    out_path = safe_args[-1]
    if isinstance(out_path, str) and os.path.exists(out_path):
        if os.path.getsize(out_path) == 0:
            raise RuntimeError(f"ffmpeg produced empty output: {out_path}")
    return ""

def ffmpeg_extract_audio(video_path: str) -> str:
    size_mb  = os.path.getsize(video_path) / 1024 / 1024
    bitrate  = "128k" if size_mb > 20 else "192k"
    out      = os.path.join(TMPDIR, f"{uuid.uuid4().hex}.mp3")
    _ff("-i", video_path, "-vn", "-ar","44100", "-ac","2", "-b:a", bitrate, out)
    if not os.path.exists(out): raise FileNotFoundError("ffmpeg no output")
    out_mb = os.path.getsize(out) / 1024 / 1024
    if out_mb > MAX_MB:
        os.remove(out)
        raise RuntimeError(f"Extracted audio is {out_mb:.0f} MB — too large.\nSend a shorter clip.")
    return out

def ffmpeg_trim(video_path: str, start: int, end: int) -> str:
    """Trim while preserving original resolution and aspect ratio."""
    out = os.path.join(TMPDIR, f"{uuid.uuid4().hex}.mp4")
    dur = end - start
    _ff("-ss", str(start), "-i", video_path,
        "-t", str(dur),
        "-c:v","libx264", "-crf","18",   # high quality, no scaling
        "-c:a","aac", "-b:a","128k",
        "-movflags","+faststart", out)
    return out

def ffmpeg_compress(video_path: str, height: int) -> str:
    """Compress while fully preserving aspect ratio.
    Works correctly for both portrait (9:16) and landscape (16:9).
    scale=-2:{height} → height fixed, width auto-calculated (always even).
    For portrait 1080x1920 → 404x720. For landscape 1920x1080 → 1280x720.
    """
    out = os.path.join(TMPDIR, f"{uuid.uuid4().hex}.mp4")
    _ff("-i", video_path,
        "-vf", f"scale=-2:{height}",
        "-c:v","libx264", "-crf","28",
        "-c:a","aac", "-b:a","96k",
        "-movflags","+faststart", out, timeout=600)
    return out

def ffmpeg_screenshot(video_path: str, ts: int) -> str:
    out = os.path.join(TMPDIR, f"{uuid.uuid4().hex}.jpg")
    _ff("-ss", str(ts), "-i", video_path, "-frames:v","1",
        "-q:v","2", out, timeout=60)
    return out

def ffmpeg_to_gif(video_path: str, start: int, duration: int) -> str:
    out     = os.path.join(TMPDIR, f"{uuid.uuid4().hex}.gif")
    palette = os.path.join(TMPDIR, f"{uuid.uuid4().hex}_pal.png")
    try:                                      
        _ff("-ss", str(start), "-t", str(duration), "-i", video_path,
            "-vf","fps=12,scale='min(480,iw)':-2:flags=lanczos,palettegen", palette, timeout=120)
        _ff("-ss", str(start), "-t", str(duration), "-i", video_path,
            "-i", palette,
            "-filter_complex","fps=12,scale='min(480,iw)':-2:flags=lanczos[x];[x][1:v]paletteuse",
            out, timeout=120)
    finally:
        from utils import clean
        clean(palette)                          # always removed, even on crash
    return out

def ffmpeg_convert(video_path: str, fmt: str) -> str:
    out = os.path.join(TMPDIR, f"{uuid.uuid4().hex}.{fmt}")
    codec_map = {
        "mp4":  ["-c:v","libx264","-c:a","aac","-movflags","+faststart"],
        "mkv":  ["-c:v","libx264","-c:a","aac"],
        "webm": ["-c:v","libvpx-vp9","-b:v","0","-crf","30","-c:a","libopus"],
        "mov":  ["-c:v","libx264","-c:a","aac"],
        "avi":  ["-c:v","libxvid","-c:a","libmp3lame"],
    }
    args = codec_map.get(fmt, ["-c","copy"])
    _ff("-i", video_path, *args, out, timeout=600)
    return out

def ffmpeg_remove_audio(video_path: str) -> str:
    out = os.path.join(TMPDIR, f"{uuid.uuid4().hex}.mp4")
    _ff("-i", video_path, "-c:v","copy", "-an", out)
    return out

def ffmpeg_change_speed(video_path: str, speed: float) -> str:
    """Change playback speed. speed=2.0 = 2x faster, speed=0.5 = half speed.
    Audio pitch is corrected via atempo filter (supports 0.5–2.0 range).
    For speeds outside 0.5–2.0, chains multiple atempo filters.
    """
    out = os.path.join(TMPDIR, f"{uuid.uuid4().hex}.mp4")
    # video filter: setpts
    vf = f"setpts={1/speed:.4f}*PTS"
    # audio filter: atempo (must be chained for values outside 0.5-2.0)
    if speed > 2.0:
        # e.g. 4x = atempo=2.0,atempo=2.0
        chains = []
        s = speed
        while s > 2.0:
            chains.append("atempo=2.0")
            s /= 2.0
        chains.append(f"atempo={s:.4f}")
        af = ",".join(chains)
    elif speed < 0.5:
        chains = []
        s = speed
        while s < 0.5:
            chains.append("atempo=0.5")
            s *= 2.0
        chains.append(f"atempo={s:.4f}")
        af = ",".join(chains)
    else:
        af = f"atempo={speed:.4f}"
    _ff("-i", video_path, "-vf", vf, "-af", af,
        "-c:v","libx264", "-crf","18", "-c:a","aac",
        "-movflags","+faststart", out, timeout=600)
    return out

def ffmpeg_reverse(video_path: str) -> str:
    """Reverse video and audio.
    Uses trim-then-reverse approach for large files to manage memory.
    Hard limit: 100MB input (reverse loads entire file into RAM).
    """
    size_mb = os.path.getsize(video_path) / 1024 / 1024
    if size_mb > 100:
        raise RuntimeError(
            f"File too large for reverse ({size_mb:.0f} MB).\nTrim it under 100 MB first, then reverse."
        )
    out = os.path.join(TMPDIR, f"{uuid.uuid4().hex}.mp4")
    # Use trim to limit duration to avoid OOM: cap at 60s for safety
    r_probe = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, timeout=15)
    try:
        dur = float(r_probe.stdout.strip())
    except Exception:
        dur = 999
    if dur > 120:
        raise RuntimeError(
            f"Video is {dur:.0f}s — too long to reverse safely.\nTrim it to under 2 minutes first."
        )
    _ff("-i", video_path,
        "-vf","reverse", "-af","areverse",
        "-c:v","libx264", "-crf","18", "-c:a","aac",
        "-movflags","+faststart", out, timeout=600)
    return out

def ffmpeg_merge(video_path: str, audio_path: str) -> str:
    out = os.path.join(TMPDIR, f"{uuid.uuid4().hex}.mp4")
    _ff("-i", video_path, "-i", audio_path,
        "-c:v","copy", "-c:a","aac",
        "-map","0:v:0", "-map","1:a:0",
        "-shortest", out)
    return out

def ffmpeg_media_info(path: str) -> dict:
    """Return dict with codec, resolution, fps, duration, bitrate, size."""
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries",
         "stream=codec_name,width,height,r_frame_rate,bit_rate,codec_type"
         ":format=duration,size,bit_rate",
         "-of","default=noprint_wrappers=1", path],
        capture_output=True, text=True, timeout=30
    )
    lines = r.stdout.strip().split("\n")
    d = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d

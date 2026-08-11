import json
import re
import subprocess
from pathlib import Path

from app.config import settings


def probe_media(path: Path) -> dict:
    command = [settings.ffprobe_binary, "-v", "error", "-show_entries", "format=duration,size:stream=width,height", "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
    payload = json.loads(result.stdout)
    video_stream = next((stream for stream in payload.get("streams", []) if stream.get("width")), {})
    return {"duration": float(payload.get("format", {}).get("duration", 0)), "size": int(payload.get("format", {}).get("size", path.stat().st_size)), "width": video_stream.get("width"), "height": video_stream.get("height")}


def seconds_to_srt(value: float) -> str:
    milliseconds = int(value * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, ms = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def write_srt(segments: list[dict], start: float, end: float, output: Path) -> None:
    blocks: list[str] = []
    for segment in segments:
        segment_start, segment_end = float(segment.get("start", 0)), float(segment.get("end", 0))
        if segment_end <= start or segment_start >= end:
            continue
        local_start, local_end = max(0, segment_start - start), min(end - start, segment_end - start)
        text = re.sub(r"\s+", " ", str(segment.get("text", ""))).strip()
        if text:
            blocks.append(f"{len(blocks) + 1}\n{seconds_to_srt(local_start)} --> {seconds_to_srt(local_end)}\n{text}\n")
    output.write_text("\n".join(blocks), encoding="utf-8")


def render_vertical_clip(*, source: Path, output: Path, subtitle: Path | None, start: float, end: float) -> dict:
    duration = end - start
    if duration <= 0: raise ValueError("Invalid clip range")
    output.parent.mkdir(parents=True, exist_ok=True)
    video_filter = f"scale={settings.output_width}:{settings.output_height}:force_original_aspect_ratio=increase,crop={settings.output_width}:{settings.output_height}"
    if subtitle and subtitle.exists() and subtitle.stat().st_size:
        escaped = str(subtitle).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        video_filter += f",subtitles='{escaped}':force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=96'"
    command = [settings.ffmpeg_binary, "-hide_banner", "-y", "-ss", str(start), "-i", str(source), "-t", str(duration), "-vf", video_filter, "-c:v", settings.output_video_codec, "-preset", "medium", "-crf", "20", "-c:a", settings.output_audio_codec, "-b:a", "192k", "-movflags", "+faststart", "-metadata", "comment=Created with AFTER OURS from an authorised source", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=max(300, int(duration * 10)))
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-4000:] or "FFmpeg render failed")
    info = probe_media(output)
    if not output.exists() or output.stat().st_size < 1024 or info["duration"] <= 0:
        raise RuntimeError("Rendered file failed validation")
    return info


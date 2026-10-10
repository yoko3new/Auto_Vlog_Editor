"""Shared ffmpeg/ffprobe helpers for the style lab tools."""

from __future__ import annotations

import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np


def probe(path: str | Path) -> dict:
    """Return duration, display size, frame rate and audio presence of a media file."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, check=True, text=True,
    ).stdout
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    info = {
        "duration_s": float(data["format"].get("duration", 0.0)),
        "has_video": video is not None,
        "has_audio": audio is not None,
        "tags": {k.lower(): v for k, v in data["format"].get("tags", {}).items()},
    }
    if video is not None:
        width, height = int(video["width"]), int(video["height"])
        rotation = 0
        for side in video.get("side_data_list", []):
            if "rotation" in side:
                rotation = int(side["rotation"]) % 360
        if rotation in (90, 270):
            width, height = height, width
        info.update(
            width=width,
            height=height,
            rotation=rotation,
            fps=float(Fraction(video.get("avg_frame_rate") or video["r_frame_rate"]))
            if video.get("avg_frame_rate", "0/0") != "0/0" else float(Fraction(video["r_frame_rate"])),
            video_codec=video.get("codec_name"),
            color_transfer=video.get("color_transfer"),
        )
    if audio is not None:
        info.update(audio_codec=audio.get("codec_name"), sample_rate=int(audio.get("sample_rate", 0)))
    return info


def read_frames(path: str | Path, width: int, height: int, fps: float | None = None) -> np.ndarray:
    """Decode frames at a small size (every frame, or resampled to ``fps``).

    Returns a uint8 array (frames, height, width, 3).
    """
    rate = f"fps={fps}," if fps else ""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"{rate}scale={width}:{height},format=rgb24",
         "-vsync", "passthrough", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, height, width, 3)


def read_audio(path: str | Path, sr: int = 22050) -> np.ndarray:
    """Decode the first audio stream as mono float32 at the given sample rate."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.float32).copy()


def loudness(path: str | Path) -> dict:
    """EBU R128 integrated loudness, loudness range and true peak of the audio stream."""
    err = subprocess.run(
        ["ffmpeg", "-nostats", "-v", "info", "-i", str(path), "-vn", "-af", "ebur128=peak=true",
         "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    summary = err[err.rfind("Summary:"):]

    def grab(label: str) -> float | None:
        match = re.search(rf"{label}:\s+(-?[\d.]+|-inf)", summary)
        if not match or match.group(1) == "-inf":
            return None
        return float(match.group(1))

    return {
        "integrated_lufs": grab("I"),
        "loudness_range_lu": grab("LRA"),
        "true_peak_dbtp": grab("Peak"),
    }


def extract_frames(path: str | Path, frame_indices: list[int], width: int, out_dir: Path) -> list[Path]:
    """Write the given frame numbers as JPEG files scaled to the given width."""
    out_dir.mkdir(parents=True, exist_ok=True)
    expr = "+".join(f"eq(n\\,{i})" for i in frame_indices)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf", f"select='{expr}',scale={width}:-2",
         "-vsync", "0", "-q:v", "3", str(out_dir / "frame_%04d.jpg")],
        check=True,
    )
    return sorted(out_dir.glob("frame_*.jpg"))

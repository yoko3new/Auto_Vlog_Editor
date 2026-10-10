"""Decoding, probing and loudness helpers for styles, using Vlogii's FFmpeg discovery."""

import re
import subprocess
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..media import Tools
from ..storage import VlogiiError

HDR_TRANSFERS = {"arib-std-b67": "hlg", "smpte2084": "pq"}


@lru_cache(maxsize=1)
def tools() -> Tools:
    return Tools()


def _run(arguments: list[str], timeout: float = 600) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [tools().ffmpeg, "-hide_banner", "-nostdin", *arguments],
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise VlogiiError(f"FFmpeg failed: {result.stderr.decode(errors='replace')[-1200:]}")
    return result


def probe(path: str | Path) -> dict:
    """Duration, display size, frame rate, colour, tags and audio presence of a media file."""
    data = tools().probe(Path(path))
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    info = {
        "duration_s": float(data.get("format", {}).get("duration", 0.0)),
        "has_video": video is not None,
        "has_audio": audio is not None,
        "tags": {k.lower(): v for k, v in data.get("format", {}).get("tags", {}).items()},
    }
    if video is not None:
        width, height = int(video["width"]), int(video["height"])
        rotation = 0
        for side in video.get("side_data_list", []):
            if "rotation" in side:
                rotation = int(side["rotation"]) % 360
        if rotation in (90, 270):
            width, height = height, width
        rate = video.get("avg_frame_rate", "0/0")
        info.update(
            width=width,
            height=height,
            rotation=rotation,
            fps=float(Fraction(rate if rate != "0/0" else video["r_frame_rate"])),
            video_codec=video.get("codec_name"),
            color=HDR_TRANSFERS.get(video.get("color_transfer"), "sdr"),
        )
    if audio is not None:
        info.update(
            audio_codec=audio.get("codec_name"), sample_rate=int(audio.get("sample_rate", 0))
        )
    return info


def read_frames(path: str | Path, width: int, height: int, fps: float | None = None) -> np.ndarray:
    """Decode frames at a small size (every frame, or resampled to ``fps``) as uint8 RGB."""
    rate = f"fps={fps}," if fps else ""
    raw = _run(
        [
            "-i",
            str(path),
            "-vf",
            f"{rate}scale={width}:{height},format=rgb24",
            "-fps_mode",
            "passthrough",
            "-f",
            "rawvideo",
            "-",
        ]
    ).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, height, width, 3)


def read_audio(
    path: str | Path,
    sr: int = 22050,
    channels: int = 1,
    start: float | None = None,
    duration: float | None = None,
) -> np.ndarray:
    """Decode the first audio stream as float32: mono, or shaped (samples, channels).

    With ``duration`` the result is padded with silence or cut to exactly that length.
    """
    window = []
    if start:
        window += ["-ss", f"{start:.4f}"]
    if duration is not None:
        window += ["-t", f"{duration:.4f}"]
    raw = _run(
        [*window, "-i", str(path), "-vn", "-ac", str(channels), "-ar", str(sr), "-f", "f32le", "-"]
    ).stdout
    audio = np.frombuffer(raw, np.float32).astype(np.float64)
    if channels > 1:
        audio = audio.reshape(-1, channels)
    if duration is not None:
        n = int(round(duration * sr))
        pad = [(0, max(0, n - len(audio)))] + [(0, 0)] * (audio.ndim - 1)
        audio = np.pad(audio, pad)[:n]
    return audio


def loudness(path: str | Path) -> dict:
    """EBU R128 integrated loudness, loudness range and true peak of the audio stream."""
    result = subprocess.run(
        [
            tools().ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-nostats",
            "-i",
            str(path),
            "-vn",
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    summary = result.stderr[result.stderr.rfind("Summary:") :]

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


def extract_frames(path: str | Path, frame_indices: list[int], width: int, out_dir: Path):
    """Write the given frame numbers as JPEG files scaled to ``width``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    expr = "+".join(f"eq(n\\,{i})" for i in frame_indices)
    _run(
        [
            "-y",
            "-i",
            str(path),
            "-vf",
            f"select='{expr}',scale={width}:-2",
            "-fps_mode",
            "passthrough",
            "-q:v",
            "3",
            str(out_dir / "frame_%04d.jpg"),
        ]
    )
    return sorted(out_dir.glob("frame_*.jpg"))

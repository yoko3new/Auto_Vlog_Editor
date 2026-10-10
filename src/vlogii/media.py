"""FFmpeg execution, probing, and normalization without shell interpolation."""

import hashlib
import json
import os
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from .models import Clip
from .storage import VlogiiError


class Tools:
    def __init__(self):
        self.ffmpeg = self._find("ffmpeg", "VLOGII_FFMPEG")
        sibling = Path(self.ffmpeg).parent / "ffprobe"
        self.ffprobe = os.environ.get("VLOGII_FFPROBE") or (
            str(sibling) if sibling.is_file() else self._find("ffprobe", "VLOGII_FFPROBE")
        )

    @staticmethod
    def _find(name, variable):
        if explicit := os.environ.get(variable):
            if not Path(explicit).is_file():
                raise VlogiiError(f"{variable} points to a missing executable.")
            return explicit
        for prefix in ("/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin"):
            candidate = Path(prefix) / name
            if candidate.is_file():
                return str(candidate)
        found = shutil.which(name)
        if not found:
            raise VlogiiError(f"{name} is missing. On macOS: brew install ffmpeg-full")
        return found

    def run(self, arguments: list[str], log: Path, timeout=600):
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(
                [self.ffmpeg, "-hide_banner", "-nostdin", "-y", *arguments],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stderr = exc.stderr or b""
            log.write_text(stderr.decode(errors="replace") if isinstance(stderr, bytes) else stderr)
            raise VlogiiError(f"FFmpeg timed out. Full log: {log}") from exc
        log.write_text(result.stderr, encoding="utf-8")
        if result.returncode:
            raise VlogiiError(f"FFmpeg failed:\n{result.stderr[-1800:]}\nFull log: {log}")
        return result

    def probe(self, path: Path) -> dict:
        result = subprocess.run(
            [
                self.ffprobe,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode:
            raise VlogiiError(f"Cannot probe {path.name}: {result.stderr[-1000:]}")
        try:
            return json.loads(result.stdout)
        except ValueError as exc:
            raise VlogiiError(f"Invalid probe response for {path.name}.") from exc

    def capability(self, flag: str) -> set[str]:
        result = subprocess.run(
            [self.ffmpeg, "-hide_banner", flag],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return {
            parts[1]
            for line in result.stdout.splitlines()
            if len(parts := line.split()) >= 3 and parts[0] != "="
        }

    def require_filters(self, names):
        missing = set(names) - self.capability("-filters")
        if missing:
            raise VlogiiError(
                f"{self.ffmpeg} lacks filters: {', '.join(sorted(missing))}. "
                "Install ffmpeg-full or set VLOGII_FFMPEG."
            )

    def encoder(self, color: str, mode: str):
        software = "libx265" if color == "hlg" else "libx264"
        available = self.capability("-encoders")
        hardware = "hevc_videotoolbox" if color == "hlg" else "h264_videotoolbox"
        codec = hardware if mode == "auto" and hardware in available else software
        if codec not in available:
            raise VlogiiError(f"FFmpeg lacks the required encoder {codec}.")
        return codec


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_clip(tools: Tools, path: Path) -> Clip:
    data = tools.probe(path)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        raise VlogiiError(f"{path.name} has no video stream.")
    duration = float(video.get("duration") or data.get("format", {}).get("duration", 0))
    fps = float(Fraction(video.get("avg_frame_rate") or video.get("r_frame_rate") or "30/1"))
    width, height = video["width"], video["height"]
    rotation = float(video.get("tags", {}).get("rotate", 0))
    for side in video.get("side_data_list", []):
        rotation = float(side.get("rotation", rotation))
    if round(abs(rotation)) % 180 == 90:
        width, height = height, width
    transfer = video.get("color_transfer")
    color = "hlg" if transfer == "arib-std-b67" else "pq" if transfer == "smpte2084" else "sdr"
    digest = sha256(path)
    return Clip(
        id="c_" + digest[:16],
        path=str(path.resolve()),
        sha256=digest,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        audio=any(s.get("codec_type") == "audio" for s in streams),
        color=color,
    )


def tone_map(clip: Clip, color: str) -> list[str]:
    if clip.color == "sdr" or color == "hlg":
        return []
    return [
        "zscale=transfer=linear:npl=100",
        "format=gbrpf32le",
        "zscale=primaries=bt709",
        "tonemap=tonemap=hable:desat=0",
        "zscale=transfer=bt709:matrix=bt709:range=limited",
    ]


def color_args(color, codec):
    if color == "hlg":
        flags = [
            "-pix_fmt",
            "yuv420p10le",
            "-color_primaries",
            "bt2020",
            "-color_trc",
            "arib-std-b67",
            "-colorspace",
            "bt2020nc",
        ]
        if codec == "libx265":
            flags += ["-x265-params", "colorprim=9:transfer=18:colormatrix=9:range=limited"]
        return flags
    return [
        "-pix_fmt",
        "yuv420p",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
    ]


def codec_args(codec):
    if codec.endswith("_videotoolbox"):
        return ["-c:v", codec, "-b:v", "8M", "-allow_sw", "1"]
    return ["-c:v", codec, "-preset", "fast", "-crf", "23"]


def build_proxy(tools: Tools, clip: Clip, output: Path):
    filters = tone_map(clip, "sdr") + [
        "scale=480:480:force_original_aspect_ratio=decrease",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "fps=12",
    ]
    if clip.color != "sdr":
        tools.require_filters({"zscale", "tonemap"})
    arguments = [
        "-i",
        clip.path,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        ",".join(filters),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        *color_args("sdr", "libx264"),
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        str(output),
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.stem + ".pending.mp4")
    arguments[-1] = str(temporary)
    tools.run(arguments, output.with_suffix(".ffmpeg.log"))
    tools.probe(temporary)
    temporary.replace(output)

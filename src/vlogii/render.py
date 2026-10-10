"""Normalize all segments, render real text, and publish only verified exports."""

import os
import shutil
import tempfile
import textwrap
import unicodedata
from fractions import Fraction
from pathlib import Path

from .media import Tools, codec_args, color_args, sha256, tone_map
from .models import Plan, Project, Review, Text
from .storage import VlogiiError, read_json, write_json
from .timeline import compile_timeline, resolve_color

FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


def wrapped_text(text: str) -> str:
    """Keep full-width glyphs within the same safe area as Latin text."""
    lines = []
    for line in textwrap.wrap(text, width=32, break_long_words=True):
        current, cells = "", 0
        for char in line:
            width = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
            if cells + width > 32:
                lines.append(current)
                current, cells = "", 0
            current += char
            cells += width
        if current:
            lines.append(current)
    return "\n".join(lines[:3])


def draw_text(item: Text, path: Path, height: int, caption: bool) -> str:
    # Content and font paths stay in a safe temporary folder, outside filter syntax from user input.
    path.write_text(wrapped_text(item.text), encoding="utf-8")
    configured = os.environ.get("VLOGII_FONT")
    if configured and not Path(configured).is_file():
        raise VlogiiError("VLOGII_FONT must point to an existing font file.")
    font = (
        Path(configured)
        if configured
        else next((Path(value) for value in FONT_CANDIDATES if Path(value).is_file()), None)
    )
    font_filter = ""
    if font:
        local_font = path.parent / ("font" + font.suffix)
        if not local_font.exists():
            shutil.copyfile(font, local_font)
        font_filter = f"fontfile='{local_font}':"
    elif any(unicodedata.east_asian_width(char) in {"W", "F"} for char in item.text):
        raise VlogiiError(
            "CJK captions require a suitable font. Install fonts-noto-cjk on Linux "
            "or set VLOGII_FONT to a font supporting your caption language."
        )
    size = max(18, round(height * (0.026 if caption else 0.034)))
    y = "h*0.82-th/2" if caption else "h*0.17-th/2"
    return (
        f"drawtext={font_filter}textfile='{path}':expansion=none:fontcolor=white:fontsize={size}:"
        f"borderw=2:bordercolor=black:box=1:boxcolor=black@0.45:boxborderw=8:"
        f"x=(w-tw)/2:y={y}:enable='between(t,{item.start:.6f},{item.end:.6f})'"
    )


def render(project_dir: Path, project: Project, plan: Plan, reviews: list[Review], progress=print):
    tools = Tools()
    timeline = compile_timeline(project, plan, reviews)
    color = resolve_color(project)
    codec = tools.encoder(color, project.settings.encoder)
    if any(s.overlays or s.captions for s in timeline.segments):
        tools.require_filters({"drawtext"})
    if color == "sdr" and any(c.color != "sdr" for c in project.clips):
        tools.require_filters({"zscale", "tonemap"})
    clips = {c.id: c for c in project.clips}
    for clip_id in {s.clip_id for s in timeline.segments}:
        clip = clips[clip_id]
        if not Path(clip.path).is_file() or sha256(Path(clip.path)) != clip.sha256:
            raise VlogiiError(f"Source clip {clip_id} is missing or changed. Import it again.")
    cuts = project_dir / "cuts"
    cuts.mkdir(exist_ok=True)
    number = max([int(p.name[4:]) for p in cuts.glob("cut_*") if p.name[4:].isdigit()] + [0]) + 1
    version = cuts / f"cut_{number:03d}"
    version.mkdir()
    write_json(version / "project.json", project)
    write_json(version / "plan.json", plan)
    write_json(version / "timeline.json", timeline)
    write_json(version / "state.json", {"status": "rendering"})
    fps = timeline.fps
    fmt = project.settings
    try:
        # A generated temporary directory avoids user paths inside FFmpeg filter syntax.
        with tempfile.TemporaryDirectory(prefix="vlogii-render-") as temporary:
            work = Path(temporary)
            segment_paths = []
            for index, segment in enumerate(timeline.segments):
                progress(f"Rendering {index + 1}/{len(timeline.segments)}: {segment.purpose}")
                clip = clips[segment.clip_id]
                duration = segment.frames / fps
                filters = tone_map(clip, color) + [
                    f"fps={fps}",
                    f"trim=end_frame={segment.frames}",
                    "setpts=PTS-STARTPTS",
                    f"scale={fmt.width}:{fmt.height}:force_original_aspect_ratio=decrease:force_divisible_by=2",
                    f"pad={fmt.width}:{fmt.height}:(ow-iw)/2:(oh-ih)/2:color=black",
                    "setsar=1",
                    "format=yuv420p10le" if color == "hlg" else "format=yuv420p",
                ]
                if fmt.warmth:
                    filters.append(f"colorbalance=rs={0.04 * fmt.warmth}:bs={-0.03 * fmt.warmth}")
                for kind, entries in (("overlay", segment.overlays), ("caption", segment.captions)):
                    for item_index, item in enumerate(entries):
                        filters.append(
                            draw_text(
                                item,
                                work / f"text-{index}-{kind}-{item_index}.txt",
                                fmt.height,
                                kind == "caption",
                            )
                        )
                output = work / f"seg-{index:04d}.mp4"
                args = ["-ss", str(segment.source_start / fps), "-i", clip.path]
                if not clip.audio:
                    args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                args += [
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0" if clip.audio else "1:a:0",
                    "-vf",
                    ",".join(filters),
                    "-af",
                    f"aresample=48000:async=1:first_pts=0,apad,atrim=duration={duration},asetpts=PTS-STARTPTS",
                    *codec_args(codec),
                    *color_args(color, codec),
                    "-threads",
                    "2",
                    "-frames:v",
                    str(segment.frames),
                    "-t",
                    str(duration),
                    "-metadata:s:v:0",
                    "rotate=0",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-video_track_timescale",
                    "90000",
                ]
                if color == "hlg":
                    args += ["-tag:v", "hvc1"]
                args += [str(output)]
                tools.run(args, version / "logs" / f"segment-{index:04d}.log")
                verify(tools, output, project, color, duration)
                segment_paths.append(output)
            listing = work / "concat.txt"
            listing.write_text("".join(f"file '{p}'\n" for p in segment_paths))
            progress("Joining segments")
            pending = version / "pending.mp4"
            tools.run(
                [
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(listing),
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(pending),
                ],
                version / "logs" / "concat.log",
            )
            evidence = verify(tools, pending, project, color, timeline.total_frames / fps)
            progress("Checking video and audio")
            tools.run(
                ["-v", "error", "-xerror", "-i", str(pending), "-f", "null", "-"],
                version / "logs" / "decode.log",
            )
            pending.replace(version / "film.mp4")
        write_json(version / "verification.json", evidence)
        write_json(version / "state.json", {"status": "complete", "color": color, "encoder": codec})
        latest_path = project_dir / "latest.json"
        history = read_json(latest_path).get("history", []) if latest_path.exists() else []
        write_json(latest_path, {"cut": version.name, "history": [*history, version.name]})
        progress(f"Complete: {version / 'film.mp4'}")
        return version
    except BaseException:
        write_json(version / "state.json", {"status": "failed"})
        raise


def verify(tools: Tools, path: Path, project: Project, color: str, duration: float):
    data = tools.probe(path)
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), {})
    audio = next((s for s in data["streams"] if s.get("codec_type") == "audio"), {})
    fmt = project.settings
    expected_pixel = "yuv420p10le" if color == "hlg" else "yuv420p"
    errors = []
    if (video.get("width"), video.get("height")) != (fmt.width, fmt.height):
        errors.append("resolution")
    if video.get("pix_fmt") != expected_pixel:
        errors.append("pixel format")
    if abs(float(Fraction(video.get("r_frame_rate", "0/1"))) - fmt.fps) > 0.001:
        errors.append("frame rate")
    if not audio:
        errors.append("audio stream")
    if color == "hlg" and (
        video.get("color_transfer") != "arib-std-b67" or video.get("color_primaries") != "bt2020"
    ):
        errors.append("HLG metadata")
    actual_duration = float(data.get("format", {}).get("duration", 0))
    if abs(actual_duration - duration) > max(0.15, 2 / fmt.fps):
        errors.append("duration")
    if errors:
        raise VlogiiError(f"Export verification failed ({', '.join(errors)}): {path.name}")
    return {
        "duration": actual_duration,
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": video.get("r_frame_rate"),
        "codec": video.get("codec_name"),
        "pixel_format": expected_pixel,
        "color_transfer": video.get("color_transfer"),
        "color_primaries": video.get("color_primaries"),
        "audio_codec": audio.get("codec_name"),
    }

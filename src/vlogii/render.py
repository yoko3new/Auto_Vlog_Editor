"""Normalize all segments, render real text, and publish only verified exports."""

import hashlib
import json
import os
import shutil
import tempfile
import unicodedata
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .chapters import version_chapters
from .cover import apply_cover
from .grading import filter_args
from .media import Tools, codec_args, color_args, sha256, tone_map
from .models import Plan, Project, Review, Text
from .music import mix_music, speech_ranges
from .presets import asset_path, music_source, supports_text
from .storage import VlogiiError, read_json, write_json
from .timeline import compile_timeline, resolve_color


def wrapped_text(text: str, font=None, max_width=None) -> str:
    """Wrap using measured glyph widths; never drop trailing lines."""
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for char in paragraph:
            candidate = current + char
            width = (
                font.getlength(candidate)
                if font
                else sum(
                    2 if unicodedata.east_asian_width(c) in {"W", "F"} else 1 for c in candidate
                )
            )
            if current and width > (max_width if max_width is not None else 32):
                # Prefer a word boundary for Latin text; split long words only when needed.
                if font and " " in current and not char.isspace():
                    left, right = current.rsplit(" ", 1)
                    if left:
                        lines.append(left)
                        current = right + char
                        continue
                lines.append(current.rstrip())
                current = char.lstrip()
            else:
                current = candidate
        lines.append(current.rstrip())
    return "\n".join(lines)


def font_path(text: str, preset="default"):
    configured = os.environ.get("VLOGII_FONT") if preset == "default" else None
    if configured and not Path(configured).is_file():
        raise VlogiiError("VLOGII_FONT must point to an existing font file.")
    font = (
        Path(configured)
        if configured
        else asset_path("fonts", "noto-sans" if preset == "default" else preset, verify_hash=False)
    )
    if not supports_text(font, text):
        font = asset_path("fonts", "noto-sans", verify_hash=False)
        if not supports_text(font, text):
            raise VlogiiError(
                "A caption contains unsupported font glyphs. Remove emoji or use supported text."
            )
    return font


def text_layout(text: str, width: int, height: int, caption: bool, preset="default"):
    """Fit complete text within the actual output rectangle in either orientation."""
    path = font_path(text, preset)
    margin = max(2, round(width * 0.05))
    stroke = max(0, round(min(width, height) * 0.001))
    box_padding = max(1, round(min(width, height) * 0.004))
    available = max(1, width - 2 * (margin + stroke + box_padding))
    maximum_height = max(1, round(height * (0.34 if caption else 0.42)))
    preferred = max(2, round(min(height * (0.026 if caption else 0.034), width * 0.06)))
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    for size in range(preferred, 1, -1):
        font = ImageFont.truetype(str(path), size=size)
        wrapped = wrapped_text(text, font, available)
        spacing = max(1, round(size * 0.2))
        bbox = measure.multiline_textbbox(
            (0, 0), wrapped, font=font, spacing=spacing, stroke_width=stroke
        )
        if bbox[2] - bbox[0] <= available and bbox[3] - bbox[1] <= maximum_height:
            return wrapped, size, spacing, stroke, box_padding, margin, bbox
    raise VlogiiError("Text cannot fit this output size. Use a larger output or a shorter title.")


def draw_text(
    item: Text, path: Path, height: int, caption: bool, width: int | None = None, preset="default"
) -> str:
    width = width or round(height * 9 / 16)
    text, size, spacing, stroke, padding, margin, _ = text_layout(
        item.text, width, height, caption, preset
    )
    path.write_text(text, encoding="utf-8")
    font = font_path(item.text, preset)
    local_font = path.parent / (
        "font-" + hashlib.sha256(str(font).encode()).hexdigest()[:12] + font.suffix
    )
    if not local_font.exists():
        shutil.copyfile(font, local_font)
    anchor = "h*0.82-th/2" if caption else "h*0.17-th/2"
    vertical_margin = max(2, round(height * 0.05))
    y = f"max({vertical_margin},min(h-th-{vertical_margin},{anchor}))"
    return (
        f"drawtext=fontfile='{local_font}':textfile='{path}':expansion=none:"
        f"fontcolor=white:fontsize={size}:line_spacing={spacing}:"
        f"borderw={stroke}:bordercolor=black:box=1:boxcolor=black@0.45:boxborderw={padding}:"
        f"x=(w-tw)/2:y='{y}':enable='between(t,{item.start:.6f},{item.end:.6f})'"
    )


def audio_tempo(speed: float) -> str:
    """Chain 0.5–2x steps so extreme speeds preserve pitch without sample skipping."""
    steps = []
    while speed > 2:
        steps.append(2)
        speed /= 2
    while speed < 0.5:
        steps.append(0.5)
        speed /= 0.5
    steps.append(speed)
    return ",".join(f"atempo={value:.12g}" for value in steps)


def check_sources(project: Project, clip_ids: set[str]) -> None:
    clips = {c.id: c for c in project.clips}
    for clip_id in clip_ids:
        clip = clips[clip_id]
        if not Path(clip.path).is_file() or sha256(Path(clip.path)) != clip.sha256:
            raise VlogiiError(f"Source clip {clip_id} is missing or changed. Import it again.")


def new_version(project_dir: Path) -> Path:
    cuts = project_dir / "cuts"
    cuts.mkdir(exist_ok=True)
    number = max([int(p.name[4:]) for p in cuts.glob("cut_*") if p.name[4:].isdigit()] + [0]) + 1
    version = cuts / f"cut_{number:03d}"
    version.mkdir()
    return version


def publish(project_dir: Path, version: Path) -> None:
    """Make a verified version current; earlier versions stay available for undo."""
    latest_path = project_dir / "latest.json"
    history = read_json(latest_path).get("history", []) if latest_path.exists() else []
    write_json(latest_path, {"cut": version.name, "history": [*history, version.name]})


def render(project_dir: Path, project: Project, plan: Plan, reviews: list[Review], progress=print):
    tools = Tools()
    timeline = compile_timeline(project, plan, reviews)
    color = resolve_color(project)
    codec = tools.encoder(color, project.settings.encoder)
    appearance = project.settings.appearance
    if appearance.font != "default" or not os.environ.get("VLOGII_FONT"):
        asset_path("fonts", "noto-sans" if appearance.font == "default" else appearance.font)
    font = font_path("", appearance.font)
    font_hash = sha256(font)
    font_digests = {font: font_hash}
    fallback_used = False
    for segment in timeline.segments:
        for item in segment.overlays + segment.captions:
            actual = font_path(item.text, appearance.font)
            if actual not in font_digests:
                if actual == asset_path("fonts", "noto-sans", verify_hash=False):
                    asset_path("fonts", "noto-sans")
                font_digests[actual] = sha256(actual)
            fallback_used |= actual != font
    selected_music, music, _ = music_source(project_dir, appearance.music, plan.mute_source_audio)
    duck_ranges = speech_ranges(project, plan, reviews) if music and appearance.duck_music else []
    if project.settings.cover and project.settings.cover.show_intro:
        duck_ranges = [[start + 1, end + 1] for start, end in duck_ranges]
    if any(s.overlays or s.captions for s in timeline.segments):
        tools.require_filters({"drawtext"})
    if color == "sdr" and any(c.color != "sdr" for c in project.clips):
        tools.require_filters({"zscale", "tonemap"})
    clips = {c.id: c for c in project.clips}
    check_sources(project, {s.clip_id for s in timeline.segments})
    version = new_version(project_dir)
    write_json(version / "project.json", project)
    write_json(version / "plan.json", plan)
    write_json(version / "timeline.json", timeline)
    write_json(version / "state.json", {"status": "rendering"})
    write_json(
        version / "assets.json",
        {
            "requested": appearance.model_dump(mode="json"),
            "font": {
                "id": appearance.font
                if appearance.font != "default"
                else ("configured" if os.environ.get("VLOGII_FONT") else "noto-sans"),
                "sha256": font_hash,
            },
            "music": {"id": selected_music, "sha256": sha256(music)} if music else None,
            "duck_ranges": duck_ranges,
            "font_fallback": "noto-sans" if fallback_used else None,
        },
    )
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
                source_audio = clip.audio and not (
                    plan.mute_source_audio or segment.mute_source_audio
                )
                duration = segment.frames / fps
                source_duration = segment.source_frames / fps
                effective_speed = segment.source_frames / segment.frames
                # Select output frames before expensive HDR tone mapping.
                filters = (
                    [
                        f"trim=duration={source_duration:.12g}",
                        f"setpts=(PTS-STARTPTS)/{effective_speed:.12g}",
                        f"fps={fps}",
                        f"tpad=stop_mode=clone:stop_duration={1 / fps:.12g}",
                        f"trim=end_frame={segment.frames}",
                        "setpts=PTS-STARTPTS",
                    ]
                    + tone_map(clip, color)
                    + [
                        f"scale={fmt.width}:{fmt.height}:force_original_aspect_ratio=decrease:force_divisible_by=2",
                        f"pad={fmt.width}:{fmt.height}:(ow-iw)/2:(oh-ih)/2:color=black",
                        "setsar=1",
                        "format=yuv420p10le" if color == "hlg" else "format=yuv420p",
                    ]
                )
                filters.extend(filter_args(fmt.video_filter))
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
                                width=fmt.width,
                                preset=appearance.font,
                            )
                        )
                output = work / f"seg-{index:04d}.mp4"
                font_hashes = sorted(
                    {
                        font_digests[font_path(item.text, appearance.font)]
                        for item in segment.overlays + segment.captions
                    }
                )
                fingerprint = hashlib.sha256(
                    json.dumps(
                        {
                            "renderer_revision": 8,
                            "mute_source_audio": plan.mute_source_audio,
                            "clip": clip.sha256,
                            "settings": project.settings.model_dump(
                                mode="json", exclude={"appearance", "cover"}
                            ),
                            "segment": segment.model_dump(mode="json"),
                            "color": color,
                            "codec": codec,
                            "fonts": font_hashes,
                        },
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode()
                ).hexdigest()
                cache = project_dir / "render-cache" / f"{fingerprint}.mp4"
                cache_meta = cache.with_suffix(".json")
                if cache.is_file() and cache_meta.is_file():
                    try:
                        if read_json(cache_meta).get("sha256") == sha256(cache):
                            verify(tools, cache, project, color, duration)
                            progress(f"Rendering cached {index + 1}/{len(timeline.segments)}")
                            shutil.copyfile(cache, output)
                            segment_paths.append(output)
                            continue
                    except (VlogiiError, ValueError, OSError):
                        pass
                args = ["-ss", str(segment.source_start / fps), "-i", clip.path]
                if not source_audio:
                    args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                args += [
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0" if source_audio else "1:a:0",
                    "-vf",
                    ",".join(filters),
                    "-af",
                    f"aresample=48000:async=1:first_pts=0,atrim=duration={source_duration:.12g},asetpts=PTS-STARTPTS,"
                    + (audio_tempo(effective_speed) if source_audio else "anull")
                    + f",apad,atrim=duration={duration:.12g},asetpts=PTS-STARTPTS",
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
                cache.parent.mkdir(parents=True, exist_ok=True)
                pending_cache = cache.with_suffix(".pending.mp4")
                shutil.copyfile(output, pending_cache)
                pending_cache.replace(cache)
                write_json(cache_meta, {"sha256": sha256(cache)})
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
            duration = timeline.total_frames / fps
            duration = apply_cover(
                tools, pending, version, project, duration, color, codec, work, progress
            )
            if music:
                progress("Mixing background music")
                mixed = version / "mixed.mp4"
                mix_music(
                    tools,
                    pending,
                    music,
                    mixed,
                    duration,
                    appearance.music_volume,
                    duck_ranges,
                    version / "logs" / "music.log",
                    work,
                )
                mixed.replace(pending)
            evidence = verify(tools, pending, project, color, duration)
            progress("Checking video and audio")
            tools.run(
                ["-v", "error", "-xerror", "-i", str(pending), "-f", "null", "-"],
                version / "logs" / "decode.log",
            )
            pending.replace(version / "film.mp4")
        write_json(version / "verification.json", evidence)
        write_json(version / "state.json", {"status": "complete", "color": color, "encoder": codec})
        write_json(
            version / "chapters.json", [c.model_dump() for c in version_chapters(version, reviews)]
        )
        publish(project_dir, version)
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

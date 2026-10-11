"""Render a local cover PNG and prepend one fixed second to a fresh body export."""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .media import Tools, codec_args, color_args
from .models import Cover, Project, SpeedRange, TimeRange
from .presets import asset_path
from .storage import VlogiiError, read_json, write_json


def intro_seconds(version: Path) -> float:
    metadata = version / "cover.json"
    return float(read_json(metadata)["intro_seconds"]) if metadata.exists() else 0


def body_ranges(version: Path, removed: list[TimeRange], sped: list[SpeedRange]):
    """Convert player coordinates to body coordinates; covers have their own editor."""
    offset = intro_seconds(version)
    for interval in [*removed, *sped]:
        if interval.start < offset - 1e-6:
            raise VlogiiError("Edit the opening cover in the cover editor.")
    return tuple(
        [
            item.model_copy(update={"start": max(0, item.start - offset), "end": item.end - offset})
            for item in entries
        ]
        for entries in (removed, sped)
    )


def poster(
    tools: Tools,
    body: Path,
    destination: Path,
    cover: Cover,
    project: Project,
    duration: float,
    color: str,
    logs: Path,
    work: Path,
    offset: float = 0,
):
    # Imported lazily because normal rendering owns the shared glyph-aware font helpers.
    from .render import font_path, wrapped_text

    fmt = project.settings
    frame = min(math.floor(cover.frame_seconds * fmt.fps) / fmt.fps, max(0, duration - 1 / fmt.fps))
    raw = work / "cover-frame.png"
    filters = []
    if color == "hlg":
        filters = [
            "zscale=transfer=linear:npl=100",
            "format=gbrpf32le",
            "zscale=primaries=bt709",
            "tonemap=tonemap=hable:desat=0",
            "zscale=transfer=bt709:matrix=bt709:range=limited",
        ]
    filters += [f"scale={fmt.width}:{fmt.height}", "format=rgb24"]
    tools.run(
        [
            "-ss",
            str(offset + frame),
            "-i",
            str(body),
            "-vf",
            ",".join(filters),
            "-frames:v",
            "1",
            str(raw),
        ],
        logs / "cover-frame.log",
    )
    image = Image.open(raw).convert("RGBA")
    width, height = image.size
    layer = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(layer)
    # A gentle central vignette keeps white text legible without flattening the whole photo.
    for y in range(height):
        strength = math.exp(-(((y / height - 0.50) / 0.30) ** 2))
        draw.line((0, y, width, y), fill=(0, 0, 0, round(82 * strength)))
    image = Image.alpha_composite(image, layer)
    layer = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(layer)
    margin = max(4, round(width * 0.09))
    available = width - 2 * margin
    text_records = []

    def fit(text, preferred, max_height, role):
        path = font_path(text, cover.font)
        if path.is_relative_to(asset_path("fonts", "noto-sans", verify_hash=False).parent):
            # Manifest integrity is checked for both the selected font and any fallback.
            asset_path(
                "fonts",
                "noto-sans"
                if path.name == asset_path("fonts", "noto-sans", verify_hash=False).name
                else cover.font,
            )
        for size in range(max(2, preferred), 1, -1):
            font = ImageFont.truetype(str(path), size)
            wrapped = wrapped_text(text, font, available)
            if (
                role == "title"
                and "\n" in wrapped
                and font.getlength(wrapped.splitlines()[-1]) < size * 1.5
            ):
                continue
            spacing = max(1, round(size * 0.2))
            box = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
            if box[2] - box[0] <= available and box[3] - box[1] <= max_height:
                return wrapped, font, spacing, box, path.name
        raise VlogiiError(
            "Text cannot fit this output size. Use a larger output or a shorter title."
        )

    entries = []
    for role, text, size, room in (
        ("kicker", cover.kicker, min(width * 0.035, height * 0.026), height * 0.10),
        ("title", cover.title, min(width * 0.12, height * 0.09), height * 0.30),
        ("subtitle", cover.subtitle, min(width * 0.043, height * 0.032), height * 0.14),
    ):
        if text:
            wrapped, font, spacing, box, name = fit(text, round(size), room, role)
            entries.append((role, wrapped, font, spacing, box, name))
    gap = max(3, round(min(width, height) * 0.04))
    total = sum(entry[4][3] - entry[4][1] for entry in entries) + gap * (len(entries) - 1)
    y = (height - total) / 2
    for role, text, font, spacing, box, name in entries:
        tw, th = box[2] - box[0], box[3] - box[1]
        x = (width - tw) / 2
        if cover.style == "editorial" and role == "kicker":
            pad = max(2, round(width * 0.016))
            draw.rounded_rectangle(
                (x - pad, y - pad, x + tw + pad, y + th + pad),
                radius=pad / 2,
                fill=(242, 233, 212, 238),
            )
        fill = (
            (46, 62, 56, 255)
            if cover.style == "editorial" and role == "kicker"
            else (255, 255, 248, 255)
        )
        shadow = max(1, round(min(width, height) * 0.002))
        position = (x - box[0], y - box[1])
        draw.multiline_text(
            (position[0] + shadow, position[1] + shadow),
            text,
            font=font,
            spacing=spacing,
            align="center",
            fill=(0, 0, 0, 170),
        )
        draw.multiline_text(position, text, font=font, spacing=spacing, align="center", fill=fill)
        text_records.append(
            {
                "role": role,
                "font_file": name,
                "font_size": font.size,
                "bounds": [x, y, x + tw, y + th],
                "lines": len(text.splitlines()),
            }
        )
        y += th + gap
    if cover.style == "playful":
        # Original vector stickers, drawn locally and requiring no third-party image assets.
        for cx, cy, radius in (
            (width * 0.14, height * 0.26, width * 0.055),
            (width * 0.84, height * 0.71, width * 0.045),
        ):
            points = []
            for index in range(8):
                angle = -math.pi / 2 + index * math.pi / 4
                r = radius if index % 2 == 0 else radius * 0.28
                points.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
            draw.polygon(points, fill=(255, 219, 117, 255))
            draw.line(
                [*points, points[0]], fill=(255, 255, 255, 255), width=max(1, round(width * 0.005))
            )
    Image.alpha_composite(image, layer).convert("RGB").save(destination, "PNG")
    return {"frame_seconds": frame, "text": text_records}


def apply_cover(
    tools: Tools,
    pending: Path,
    version: Path,
    project: Project,
    duration: float,
    color: str,
    codec: str,
    work: Path,
    progress,
):
    cover = project.settings.cover
    if cover is None:
        return duration
    progress("Creating cover")
    metadata = poster(
        tools,
        pending,
        version / "cover.png",
        cover,
        project,
        duration,
        color,
        version / "logs",
        work,
    )
    seconds = 1 if cover.show_intro else 0
    write_json(
        version / "cover.json",
        {
            "settings": cover.model_dump(),
            "intro_seconds": seconds,
            "body_duration_seconds": duration,
            **metadata,
        },
    )
    if not seconds:
        return duration
    fps = project.settings.fps
    frames = round(duration * fps)
    filters = ["setsar=1", "format=yuv420p"]
    if color == "hlg":
        filters = [
            "format=gbrpf32le",
            "zscale=primariesin=bt709:transferin=iec61966-2-1:matrixin=gbr:rangein=full:primaries=bt2020:transfer=arib-std-b67:matrix=bt2020nc:range=limited",
            "format=yuv420p10le",
            "setsar=1",
        ]
    # Reset both video clocks and trim by frames. MP4/AAC priming can otherwise insert
    # a gap at a stream-copy boundary and change r_frame_rate despite a 30 fps plan.
    graph = (
        f"[0:v]{','.join(filters)},fps={fps},trim=end_frame={fps},setpts=PTS-STARTPTS[cover];"
        f"[1:v]fps={fps},trim=end_frame={frames},setpts=PTS-STARTPTS[body];"
        f"[cover][body]concat=n=2:v=1:a=0,fps={fps},trim=end_frame={frames + fps}[video];"
        f"[1:a]aresample=48000:async=1:first_pts=0,atrim=duration={duration:.12g},asetpts=PTS-STARTPTS,adelay=1000:all=1,apad,atrim=duration={duration + 1:.12g}[audio]"
    )
    output = work / "cover-joined.mp4"
    args = [
        "-loop",
        "1",
        "-framerate",
        str(fps),
        "-i",
        str(version / "cover.png"),
        "-i",
        str(pending),
        "-filter_complex_threads",
        "1",
        "-filter_complex",
        graph,
        "-map",
        "[video]",
        "-map",
        "[audio]",
        *codec_args(codec),
        *color_args(color, codec),
        "-threads",
        "2",
        "-frames:v",
        str(frames + fps),
        "-t",
        str(duration + 1),
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
        "-movflags",
        "+faststart",
    ]
    if color == "hlg":
        args += ["-tag:v", "hvc1"]
    tools.run([*args, str(output)], version / "logs" / "cover-intro.log")
    import shutil

    shutil.copyfile(output, pending)
    return duration + seconds

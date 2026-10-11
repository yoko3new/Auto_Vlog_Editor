"""Execute a style plan with FFmpeg.

Per-shot trims and grades, ASS text set in the bundled fonts, music normalised to the
template loudness under a true-peak ceiling (re-measured after AAC encoding), and an
optional voiceover that ducks the music.
"""

import math
import shutil
import subprocess
import unicodedata
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import ImageFont

from ..grading import filter_args
from ..media import color_args, tone_map
from ..models import Appearance
from ..presets import asset_path
from ..render import font_path
from ..storage import VlogiiError
from . import media

FONT_DIR = Path(__file__).resolve().parent / "fonts"
BUNDLED_FAMILIES = {
    "Poppins",
    "Poppins Medium",
    "Poppins Black",
    "DM Serif Display",
    "Share Tech Mono",
}
AUDIO_SR = 48000
DECLICK_S = 0.03
LIMIT_HOLD_S = 0.04
ENCODE_MARGIN_DB = 0.5  # first guess; AAC overshoot is measured and the ceiling lowered to fit
AAC = ["-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_SR)]


def installed_families() -> set[str]:
    """Bundled fonts plus whatever fontconfig reports (fontconfig is optional on macOS)."""
    families = set(BUNDLED_FAMILIES)
    if shutil.which("fc-list"):
        listing = subprocess.run(
            ["fc-list", ":", "family"], capture_output=True, text=True, check=False, timeout=30
        ).stdout
        families |= {name.strip() for line in listing.splitlines() for name in line.split(",")}
    return families


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(frame: int, fps: int) -> str:
    cs = frame * 100 // fps  # floor keeps the event on exactly [start_frame, end_frame)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def fit_text(text: str, size_px: float, frame_width: int) -> tuple[str, float]:
    """Break a long line at the middle space, then shrink until it fits 88% of the frame.

    Width is estimated (0.56 em per Latin character, 1 em for full-width glyphs).
    """
    limit = 0.88 * frame_width

    def widest(value: str) -> float:
        return (
            max(
                sum(1.0 if unicodedata.east_asian_width(c) in {"W", "F"} else 0.56 for c in line)
                for line in value.split("\n")
            )
            * size_px
        )

    if "\n" not in text and " " in text.strip() and widest(text) > limit:
        middle = len(text) / 2
        cut = min((i for i, c in enumerate(text) if c == " "), key=lambda i: abs(i - middle))
        text = text[:cut] + "\n" + text[cut + 1 :]
    return text, min(1.0, limit / max(widest(text), 1.0))


def ass_text(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\\", "/").replace("\n", "\\N")


def write_ass(plan: dict, template: dict, path: Path, font_preset="default") -> dict:
    width, height = plan["output"]["width"], plan["output"]["height"]
    fps = plan["output"]["fps"]
    families = installed_families()
    chosen, styles = {}, []
    for name, role in template["text"]["roles"].items():
        font = next((f for f in role["fonts"] if f in families), role["fonts"][-1])
        chosen[name] = font
        box = role["box"]
        border_style = 3 if box else 1
        outline_colour = ass_color(box) if box else ass_color("#000000", 0x40)
        back = ass_color(box) if box else ass_color("#000000", 0x90)
        # Outline and shadow are authored for a 1280-pixel-tall frame.
        scale = height / 1280
        styles.append(
            f"Style: {name},{font},{round(role['size'] * height)},{ass_color(role['color'])},"
            f"{ass_color(role['color'])},{outline_colour},{back},{-1 if role['bold'] else 0},"
            f"0,0,0,100,100,{role['spacing'] * scale:.2f},0,{border_style},"
            f"{role['outline'] * scale:.2f},{role['shadow'] * scale:.2f},5,10,10,10,1"
        )
    events = []
    for overlay in plan["overlays"]:
        role = template["text"]["roles"][overlay["role"]]
        text = overlay["text"].upper() if role["uppercase"] else overlay["text"]
        font_override = ""
        if font_preset != "default" or any(
            unicodedata.east_asian_width(c) in {"W", "F"} for c in text
        ):
            selected = font_path(text, "noto-sans" if font_preset == "default" else font_preset)
            family = ImageFont.truetype(str(selected), 20).getname()[0]
            chosen[f"{overlay['role']}:preset"] = family
            font_override = f"\\fn{family}"
        text, scale = fit_text(text, role["size"] * height, width)
        shrink = f"\\fscx{scale * 100:.0f}\\fscy{scale * 100:.0f}" if scale < 1 else ""
        pos = f"{{\\an5\\pos({round(overlay['x'] * width)},{round(overlay['y'] * height)}){shrink}{font_override}}}"
        a, b = overlay["start_frame"], overlay["end_frame"]
        if overlay["reveal"] == "typewriter" and len(text) > 1:
            per_char = max(1, min(2, int(0.4 * (b - a) / len(text))))
            for k in range(1, len(text)):
                fa = a + (k - 1) * per_char
                events.append((fa, fa + per_char, overlay["role"], pos + ass_text(text[:k]) + "|"))
            a = a + (len(text) - 1) * per_char
        events.append((a, b, overlay["role"], pos + ass_text(text)))
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        *styles,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    lines += [
        f"Dialogue: 0,{ass_time(a, fps)},{ass_time(b, fps)},{style},,0,0,0,,{text}"
        for a, b, style, text in events
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return chosen


def grade_filter(grade: dict) -> str:
    parts = [f"eq=brightness={grade['brightness']}:saturation={grade['saturation']}"]
    if w := grade["warmth_shift"]:
        parts.append(f"colorbalance=rm={w}:bm={-w}")
    return ",".join(parts)


def render_video(plan: dict, work: Path, logs: Path, progress) -> Path:
    tools = media.tools()
    width, height, fps = plan["output"]["width"], plan["output"]["height"], plan["output"]["fps"]
    encode = [
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "14",
        *color_args("sdr", "libx264"),
        "-r",
        str(fps),
    ]
    segments = []
    for shot in plan["shots"]:
        progress(f"Rendering {shot['index'] + 1}/{len(plan['shots'])}: style shot")
        frames = shot["end_frame"] - shot["start_frame"]
        segment = work / f"shot_{shot['index']:04d}.mp4"
        filters = tone_map(SimpleNamespace(color=shot["color"]), "sdr") + [
            f"fps={fps}",
            f"scale={width}:{height}:force_original_aspect_ratio=increase",
            f"crop={width}:{height}",
            "setsar=1",
            grade_filter(shot["grade"]),
            *filter_args(plan.get("video_filter", "none")),
            "format=yuv420p",
        ]
        tools.run(
            [
                "-ss",
                f"{shot['source_in_s']:.4f}",
                "-i",
                shot["clip"],
                "-frames:v",
                str(frames),
                "-vf",
                ",".join(filters),
                *encode,
                str(segment),
            ],
            logs / f"style-shot-{shot['index']:04d}.log",
        )
        segments.append(segment)
    if card := plan["end_card"]:
        segment = work / "end_card.mp4"
        tools.run(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c={card['background'].replace('#', '0x')}:s={width}x{height}:r={fps}",
                "-frames:v",
                str(card["end_frame"] - card["start_frame"]),
                "-vf",
                "format=yuv420p",
                *encode,
                str(segment),
            ],
            logs / "style-end-card.log",
        )
        segments.append(segment)
    listing = work / "segments.txt"
    listing.write_text("".join(f"file '{s}'\n" for s in segments), encoding="utf-8")
    joined = work / "video.mp4"
    tools.run(
        ["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)],
        logs / "style-concat.log",
    )
    return joined


def write_wav(path: Path, audio: np.ndarray) -> None:
    """32-bit float WAV through FFmpeg, so no extra audio library is needed."""
    raw = np.ascontiguousarray(audio, dtype=np.float32)
    subprocess.run(
        [
            media.tools().ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-f",
            "f32le",
            "-ar",
            str(AUDIO_SR),
            "-ac",
            str(raw.shape[1]),
            "-i",
            "-",
            "-c:a",
            "pcm_f32le",
            str(path),
        ],
        input=raw.tobytes(),
        capture_output=True,
        check=True,
        timeout=600,
    )


def measured_lufs(audio: np.ndarray, work: Path, name: str) -> float | None:
    path = work / f"{name}.wav"
    write_wav(path, audio)
    return media.loudness(path)["integrated_lufs"]


def ramp(n: int, seconds: float) -> np.ndarray:
    k = min(n, max(1, int(seconds * AUDIO_SR)))
    return 0.5 - 0.5 * np.cos(np.linspace(0, math.pi, k))


def duck_envelope(voice: np.ndarray, duck_db: float) -> np.ndarray:
    """Music gain in dB: duck while the voice is active, 80 ms attack, 300 ms release."""
    win = int(0.02 * AUDIO_SR)
    mono = voice.mean(axis=1)
    usable = mono[: len(mono) // win * win].reshape(-1, win)
    rms_db = 20 * np.log10(np.maximum(np.sqrt((usable**2).mean(axis=1)), 1e-9))
    gain, out = 0.0, np.empty(rms_db.size)
    for i, on in enumerate(rms_db > -45):
        target, tau = (duck_db, 0.08) if on else (0.0, 0.3)
        gain += (target - gain) * (1 - math.exp(-0.02 / tau))
        out[i] = gain
    env = np.repeat(out, win)
    return np.pad(env, (0, len(mono) - len(env)), mode="edge")[:, None]


def true_peak_limit(audio: np.ndarray, ceiling_db: float) -> tuple[np.ndarray, np.ndarray]:
    """Hold-and-smooth limiter on a 4x oversampled peak estimate.

    The gain at every peak is never above what that peak needs. Returns audio and gain.
    """
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    from scipy.signal import resample_poly

    oversampled = np.abs(resample_poly(audio, 4, 1, axis=0)).max(axis=1)
    peak = oversampled[: len(audio) * 4].reshape(-1, 4).max(axis=1)
    need = np.minimum(1.0, 10 ** (ceiling_db / 20) / np.maximum(peak, 1e-12))
    hold = int(LIMIT_HOLD_S * AUDIO_SR)
    gain = uniform_filter1d(minimum_filter1d(need, size=2 * hold + 1), size=hold + 1)
    return audio * gain[:, None], gain


def master(mix: np.ndarray, target_lufs: float, ceiling_db: float, work: Path) -> tuple:
    """Reach the loudness target under a true-peak ceiling (limit, re-measure, adjust)."""
    gain_db, out, measured = 0.0, mix, None
    for _ in range(4):
        out, limiter = true_peak_limit(mix * 10 ** (gain_db / 20), ceiling_db)
        measured = measured_lufs(out, work, "master")
        if measured is None or abs(measured - target_lufs) <= 0.3:
            break
        gain_db += target_lufs - measured
    reduction = -20 * np.log10(np.maximum(limiter, 1e-9))
    return out, {
        "master_gain_db": round(gain_db, 2),
        "pre_encode_lufs": measured,
        "limiter_max_reduction_db": round(float(reduction.max()), 1),
        "limiter_active_fraction": round(float((reduction > 1).mean()), 3),
    }


def render_audio(plan: dict, work: Path, logs: Path, volume: float = 1) -> tuple[Path, dict]:
    spec = plan["music"]
    duration = plan["total_frames"] / plan["output"]["fps"]
    music = media.read_audio(spec["path"], AUDIO_SR, 2, spec["start_s"], duration)
    notes = {}
    measured = measured_lufs(music, work, "music_raw")
    if measured is not None:
        music *= 10 ** ((spec["target_lufs"] - measured) / 20)
    notes["music_gain_db"] = None if measured is None else round(spec["target_lufs"] - measured, 2)
    fade_in = ramp(len(music), max(spec["fade_in_s"], DECLICK_S))
    fade_out = ramp(len(music), max(spec["fade_out_s"], DECLICK_S))[::-1]
    music[: len(fade_in)] *= fade_in[:, None]
    music[len(music) - len(fade_out) :] *= fade_out[:, None]
    mix = music
    voice_spec = plan["voiceover"]
    if voice_spec:
        voice = media.read_audio(voice_spec["path"], AUDIO_SR, 2, None, duration)
        voice_lufs = measured_lufs(voice, work, "voice_raw")
        if voice_lufs is not None:
            voice *= 10 ** ((voice_spec["target_lufs"] - voice_lufs) / 20)
        env = duck_envelope(voice, voice_spec["music_duck_db"])
        mix = music * 10 ** (env / 20) + voice
        notes["voice_gain_db"] = (
            None if voice_lufs is None else round(voice_spec["target_lufs"] - voice_lufs, 2)
        )
        notes["ducked_fraction"] = round(float((env < voice_spec["music_duck_db"] / 2).mean()), 3)
    target = voice_spec["target_lufs"] if voice_spec else spec["target_lufs"]
    if volume > 0:
        target += 20 * math.log10(volume)
    ceiling = spec["true_peak_dbtp"]
    margin = ENCODE_MARGIN_DB
    encoded = work / "mix.m4a"
    for _ in range(4):
        if volume == 0:
            mastered, mastering = np.zeros_like(mix), {"user_volume": 0}
        else:
            mastered, mastering = master(mix, target, ceiling - margin, work)
        wav = work / "mix.wav"
        write_wav(wav, mastered)
        media.tools().run(["-i", str(wav), *AAC, str(encoded)], logs / "style-audio.log")
        peak = media.loudness(encoded)["true_peak_dbtp"]
        if peak is None or peak <= ceiling:
            break
        margin += peak - ceiling + 0.1
    notes.update(mastering, encode_margin_db=round(margin, 2))
    return encoded, notes


def render(
    plan: dict,
    template: dict,
    out: Path,
    work: Path,
    logs: Path,
    progress=print,
    appearance: Appearance | None = None,
) -> dict:
    """Write ``out`` from ``plan``. ``work`` must be a generated temporary directory.

    Its path is placed inside FFmpeg filter syntax, so it must not come from user input.
    """
    if template["revision"] != plan["template"]["revision"]:
        raise VlogiiError("The plan was made with another revision of this style. Plan again.")
    tools = media.tools()
    filters = {"ass"}
    if any(shot["color"] != "sdr" for shot in plan["shots"]):
        filters |= {"zscale", "tonemap"}
    tools.require_filters(filters)
    video = render_video(plan, work, logs, progress)
    progress("Setting the titles")
    subs = work / "text.ass"
    fonts = write_ass(plan, template, subs, appearance.font if appearance else "default")
    shutil.copytree(FONT_DIR, work / "fonts")
    shutil.copyfile(asset_path("fonts", "noto-sans"), work / "fonts" / "NotoSansCJKsc-Regular.otf")
    if appearance and appearance.font != "default":
        selected_font = asset_path("fonts", appearance.font)
        shutil.copyfile(selected_font, work / "fonts" / selected_font.name)
    progress("Mixing the music")
    mix, audio_notes = render_audio(plan, work, logs, appearance.music_volume if appearance else 1)
    progress("Finishing the film")
    tools.run(
        [
            "-i",
            str(video),
            "-i",
            str(mix),
            "-filter_complex",
            f"[0:v]ass=filename='{subs}':fontsdir='{work / 'fonts'}'[v]",
            "-map",
            "[v]",
            "-map",
            "1:a",
            "-frames:v",
            str(plan["total_frames"]),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            *color_args("sdr", "libx264"),
            "-r",
            str(plan["output"]["fps"]),
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(out),
        ],
        logs / "style-final.log",
    )
    return {
        "template": plan["template"],
        "planned_duration_s": round(plan["total_frames"] / plan["output"]["fps"], 3),
        "loudness": media.loudness(out),
        "audio": audio_notes,
        "fonts": fonts,
        "music": {k: plan["music"][k] for k in ("tempo_bpm", "start_s", "downbeat_confidence")},
        "checks": plan["checks"],
        "warnings": plan["warnings"],
    }

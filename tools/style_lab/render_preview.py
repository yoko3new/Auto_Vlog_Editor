"""Render a style plan to an MP4 preview with FFmpeg (prototype, not the product renderer).

It executes the plan exactly: per-shot trims and grades, ASS text, music normalised to
the template loudness, optional voiceover with music ducking, and a true-peak limiter.

    python tools/style_lab/render_preview.py work/me/plan.json --out work/me/preview.mp4
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import media  # noqa: E402
import templates  # noqa: E402

AUDIO_SR = 48000
DECLICK_S = 0.03
LIMIT_HOLD_S = 0.04
ENCODE_MARGIN_DB = 0.5  # first guess; AAC overshoot is measured and the ceiling lowered until it fits
AAC = ["-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_SR)]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd[:6])} ...\n{result.stderr[-2000:]}")


def installed_families() -> set[str]:
    out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout
    return {name.strip() for line in out.splitlines() for name in line.split(",")}


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(frame: int, fps: int) -> str:
    cs = frame * 100 // fps  # floor keeps the event on exactly [start_frame, end_frame)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def ass_text(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", "\\N")


def write_ass(plan: dict, template: dict, path: Path) -> dict:
    width, height, fps = plan["output"]["width"], plan["output"]["height"], plan["output"]["fps"]
    families = installed_families()
    chosen, styles = {}, []
    for name, role in template["text"]["roles"].items():
        font = next((f for f in role["fonts"] if f in families), role["fonts"][-1])
        chosen[name] = font
        box = role["box"]
        border_style, outline_colour = (3, ass_color(box)) if box else (1, ass_color("#000000", 0x40))
        back = ass_color(box) if box else ass_color("#000000", 0x90)
        styles.append(
            f"Style: {name},{font},{round(role['size'] * height)},{ass_color(role['color'])},{ass_color(role['color'])},"
            f"{outline_colour},{back},{-1 if role['bold'] else 0},0,0,0,100,100,{role['spacing']},0,{border_style},"
            f"{role['outline']},{role['shadow']},5,10,10,10,1"
        )
    events = []
    for overlay in plan["overlays"]:
        role = template["text"]["roles"][overlay["role"]]
        text = overlay["text"].upper() if role["uppercase"] else overlay["text"]
        pos = f"{{\\an5\\pos({round(overlay['x'] * width)},{round(overlay['y'] * height)})}}"
        a, b = overlay["start_frame"], overlay["end_frame"]
        if overlay["reveal"] == "typewriter" and len(text) > 1:
            per_char = max(1, min(2, int(0.4 * (b - a) / len(text))))
            for k in range(1, len(text)):
                fa = a + (k - 1) * per_char
                events.append((fa, fa + per_char, overlay["role"], pos + ass_text(text[:k]) + "|"))
            a = a + (len(text) - 1) * per_char
        events.append((a, b, overlay["role"], pos + ass_text(text)))
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        *styles, "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    lines += [f"Dialogue: 0,{ass_time(a, fps)},{ass_time(b, fps)},{style},,0,0,0,,{text}" for a, b, style, text in events]
    path.write_text("\n".join(lines) + "\n")
    return chosen


def grade_filter(grade: dict) -> str:
    parts = [f"eq=brightness={grade['brightness']}:saturation={grade['saturation']}"]
    if grade["warmth_shift"]:
        w = grade["warmth_shift"]
        parts.append(f"colorbalance=rm={w}:bm={-w}")
    return ",".join(parts)


def render_video(plan: dict, work: Path) -> Path:
    width, height, fps = plan["output"]["width"], plan["output"]["height"], plan["output"]["fps"]
    encode = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", "-r", str(fps)]
    segments = []
    for shot in plan["shots"]:
        frames = shot["end_frame"] - shot["start_frame"]
        seg = work / f"shot_{shot['index']:04d}.mp4"
        vf = (f"fps={fps},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
              f"setsar=1,{grade_filter(shot['grade'])}")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{shot['source_in_s']:.4f}", "-i", shot["clip"],
             "-frames:v", str(frames), "-vf", vf, *encode, str(seg)])
        segments.append(seg)
    if plan["end_card"]:
        card = plan["end_card"]
        seg = work / "end_card.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             f"color=c={card['background'].replace('#', '0x')}:s={width}x{height}:r={fps}",
             "-frames:v", str(card["end_frame"] - card["start_frame"]), *encode, str(seg)])
        segments.append(seg)
    listing = work / "segments.txt"
    listing.write_text("".join(f"file '{s.name}'\n" for s in segments))
    joined = work / "video.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])
    return joined


def decode(path: str, start: float, duration: float) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start:.4f}", "-t", f"{duration:.4f}", "-i", path, "-vn",
         "-ac", "2", "-ar", str(AUDIO_SR), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    audio = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
    n = int(round(duration * AUDIO_SR))
    return np.pad(audio, ((0, max(0, n - len(audio))), (0, 0)))[:n]


def measured_lufs(audio: np.ndarray, work: Path, name: str) -> float | None:
    path = work / f"{name}.wav"
    sf.write(path, audio, AUDIO_SR, subtype="FLOAT")
    return media.loudness(path)["integrated_lufs"]


def ramp(n: int, seconds: float) -> np.ndarray:
    k = min(n, max(1, int(seconds * AUDIO_SR)))
    return 0.5 - 0.5 * np.cos(np.linspace(0, math.pi, k))


def duck_envelope(voice: np.ndarray, duck_db: float) -> np.ndarray:
    """Music gain in dB: duck while the voice is active, 80 ms attack, 300 ms release."""
    win = int(0.02 * AUDIO_SR)
    mono = voice.mean(axis=1)
    usable = mono[: len(mono) // win * win].reshape(-1, win)
    active = 20 * np.log10(np.maximum(np.sqrt((usable ** 2).mean(axis=1)), 1e-9)) > -45
    gain, out = 0.0, np.empty(active.size)
    for i, on in enumerate(active):
        target, tau = (duck_db, 0.08) if on else (0.0, 0.3)
        gain += (target - gain) * (1 - math.exp(-0.02 / tau))
        out[i] = gain
    env = np.repeat(out, win)
    return np.pad(env, (0, len(mono) - len(env)), mode="edge")[:, None]


def true_peak_limit(audio: np.ndarray, ceiling_db: float) -> tuple[np.ndarray, np.ndarray]:
    """Hold-and-smooth limiter on a 4x oversampled peak estimate; the gain never exceeds what a peak needs.

    Returns the limited audio and the gain curve.
    """
    oversampled = np.abs(resample_poly(audio, 4, 1, axis=0)).max(axis=1)
    peak = oversampled[: len(audio) * 4].reshape(-1, 4).max(axis=1)
    need = np.minimum(1.0, 10 ** (ceiling_db / 20) / np.maximum(peak, 1e-12))
    hold = int(LIMIT_HOLD_S * AUDIO_SR)
    gain = uniform_filter1d(minimum_filter1d(need, size=2 * hold + 1), size=hold + 1)
    return audio * gain[:, None], gain


def master(mix: np.ndarray, target_lufs: float, ceiling_db: float, work: Path) -> tuple[np.ndarray, dict]:
    """Reach the loudness target under a true-peak ceiling (limit, re-measure, adjust, up to 4 passes)."""
    gain_db, out = 0.0, mix
    for _ in range(4):
        out, limiter = true_peak_limit(mix * 10 ** (gain_db / 20), ceiling_db)
        measured = measured_lufs(out, work, "master")
        if measured is None or abs(measured - target_lufs) <= 0.3:
            break
        gain_db += target_lufs - measured
    reduction = -20 * np.log10(np.maximum(limiter, 1e-9))
    return out, {"master_gain_db": round(gain_db, 2), "pre_encode_lufs": measured,
                 "limiter_max_reduction_db": round(float(reduction.max()), 1),
                 "limiter_active_fraction": round(float((reduction > 1).mean()), 3)}


def render_audio(plan: dict, work: Path) -> tuple[Path, dict]:
    music_spec = plan["music"]
    duration = plan["total_frames"] / plan["output"]["fps"]
    music = decode(music_spec["path"], music_spec["start_s"], duration)
    notes = {}
    measured = measured_lufs(music, work, "music_raw")
    if measured is not None:
        music *= 10 ** ((music_spec["target_lufs"] - measured) / 20)
    notes["music_gain_db"] = None if measured is None else round(music_spec["target_lufs"] - measured, 2)
    fade_in = ramp(len(music), max(music_spec["fade_in_s"], DECLICK_S))
    fade_out = ramp(len(music), max(music_spec["fade_out_s"], DECLICK_S))[::-1]
    music[: len(fade_in)] *= fade_in[:, None]
    music[len(music) - len(fade_out):] *= fade_out[:, None]
    mix = music
    voice_spec = plan["voiceover"]
    if voice_spec:
        voice = decode(voice_spec["path"], 0.0, duration)
        voice_lufs = measured_lufs(voice, work, "voice_raw")
        if voice_lufs is not None:
            voice *= 10 ** ((voice_spec["target_lufs"] - voice_lufs) / 20)
        env = duck_envelope(voice, voice_spec["music_duck_db"])
        mix = music * 10 ** (env / 20) + voice
        notes["voice_gain_db"] = None if voice_lufs is None else round(voice_spec["target_lufs"] - voice_lufs, 2)
        notes["ducked_fraction"] = round(float((env < voice_spec["music_duck_db"] / 2).mean()), 3)
    target = voice_spec["target_lufs"] if voice_spec else music_spec["target_lufs"]
    ceiling = music_spec["true_peak_dbtp"]
    margin = ENCODE_MARGIN_DB
    for _ in range(4):
        mastered, mastering = master(mix, target, ceiling - margin, work)
        wav, encoded = work / "mix.wav", work / "mix.m4a"
        sf.write(wav, mastered.astype(np.float32), AUDIO_SR, subtype="FLOAT")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), *AAC, str(encoded)])
        peak = media.loudness(encoded)["true_peak_dbtp"]
        if peak is None or peak <= ceiling:
            break
        margin += peak - ceiling + 0.1
    notes.update(mastering, encode_margin_db=round(margin, 2))
    return encoded, notes


def render(plan_path: Path, out: Path, keep: bool) -> dict:
    plan = json.loads(plan_path.read_text())
    template = templates.load(plan["template"]["id"])
    if template["revision"] != plan["template"]["revision"]:
        raise RuntimeError("plan was made with another template revision; re-run plan_edit.py")
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="style_preview_", dir=out.parent))
    video = render_video(plan, work)
    subs = work / "text.ass"
    fonts = write_ass(plan, template, subs)
    mix, audio_notes = render_audio(plan, work)
    # Relative names inside the work folder keep the filter string free of path characters like ':'.
    run(["ffmpeg", "-v", "error", "-y", "-i", video.name, "-i", mix.name,
         "-filter_complex", f"[0:v]ass={subs.name}[v]", "-map", "[v]", "-map", "1:a", "-frames:v", str(plan["total_frames"]),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(plan["output"]["fps"]),
         "-c:a", "copy", "-movflags", "+faststart", str(out)], cwd=work)
    info = media.probe(out)
    report = {
        "output": str(out),
        "plan": str(plan_path),
        "template": plan["template"],
        "duration_s": round(info["duration_s"], 3),
        "planned_duration_s": round(plan["total_frames"] / plan["output"]["fps"], 3),
        "size": [info["width"], info["height"]],
        "loudness": media.loudness(out),
        "audio": audio_notes,
        "fonts": fonts,
        "plan_warnings": plan["warnings"],
    }
    if not keep:
        for item in sorted(work.iterdir()):
            item.unlink()
        work.rmdir()
    out.with_suffix(".report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keep-work", action="store_true", help="Keep per-shot files, ASS and mix.wav")
    args = parser.parse_args()
    report = render(args.plan, args.out, args.keep_work)
    print(json.dumps({k: report[k] for k in ("output", "duration_s", "size", "loudness", "fonts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Measure the editing style of a reference reel: cuts, beat sync, soundtrack mix and colour.

Writes a JSON profile with measurements only plus a local contact sheet for visual review.
Keep the downloaded reel and the contact sheet under work/; they are third-party media.

    uv sync --extra dev --extra style-lab
    uv run python tools/style_lab/analyze_reference.py work/references/REEL.mp4 \
        --url https://www.instagram.com/reel/REEL/ --out-dir work/style_lab/REEL
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import librosa
import numpy as np
from PIL import Image, ImageDraw

from vlogii.style import beats, media

SMALL_W, SMALL_H = 72, 128
AUDIO_SR = 22050
SYNC_TOLERANCE_S = 0.06
PROFILE_VERSION = 1


def cut_scores(frames: np.ndarray) -> np.ndarray:
    """Score each frame transition: half colour-histogram change, half luma pixel change."""
    quant = frames // 64
    bins = quant[..., 0].astype(np.int32) * 16 + quant[..., 1] * 4 + quant[..., 2]
    hist = np.stack([np.bincount(b.ravel(), minlength=64) for b in bins]).astype(np.float64)
    hist /= hist.sum(axis=1, keepdims=True)
    hist_change = np.abs(np.diff(hist, axis=0)).sum(axis=1) / 2
    luma = frames.astype(np.float32).mean(axis=-1)
    pixel_change = np.abs(np.diff(luma, axis=0)).mean(axis=(1, 2)) / 255
    return 0.5 * hist_change + 0.5 * np.minimum(pixel_change * 4, 1.0)


def detect_cuts(scores: np.ndarray, fps: float) -> list[int]:
    """Return frame indices where a new shot starts (hard cuts only)."""
    min_gap = max(2, int(round(fps * 0.06)))
    cuts: list[int] = []
    for i, s in enumerate(scores):
        lo, hi = max(0, i - 15), min(scores.size, i + 16)
        neighbours = np.concatenate([scores[lo:i], scores[i + 1:hi]])
        local = float(np.median(neighbours)) if neighbours.size else 0.0
        is_peak = s >= scores[max(0, i - 2): i + 3].max()
        strong = s >= 0.30 and s >= 3 * local
        soft = s >= 0.15 and s >= 6 * max(local, 0.01)
        if is_peak and (strong or soft):
            frame = i + 1
            if cuts and frame - cuts[-1] < min_gap:
                continue
            cuts.append(frame)
    return cuts


def colour_stats(frames: np.ndarray) -> dict:
    rgb = frames.astype(np.float32) / 255
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    cmax, cmin = rgb.max(axis=-1), rgb.min(axis=-1)
    sat = np.where(cmax > 0, (cmax - cmin) / np.maximum(cmax, 1e-6), 0)
    return {
        "luma": round(float(luma.mean()), 3),
        "contrast": round(float(luma.std()), 3),
        "saturation": round(float(sat.mean()), 3),
        "warmth": round(float((r - b).mean()), 3),
    }


def nearest_offsets(times: np.ndarray, grid: np.ndarray) -> np.ndarray:
    if grid.size == 0 or times.size == 0:
        return np.full(times.shape, np.inf)
    idx = np.clip(np.searchsorted(grid, times), 1, grid.size - 1)
    left, right = grid[idx - 1], grid[idx]
    return np.where(np.abs(times - left) <= np.abs(times - right), times - left, times - right)


def subdivide(beat_times: np.ndarray, parts: int) -> np.ndarray:
    if beat_times.size < 2:
        return beat_times
    pts = [beat_times[:-1] + (beat_times[1:] - beat_times[:-1]) * k / parts for k in range(parts)]
    return np.sort(np.concatenate(pts + [beat_times[-1:]]))


def sync_report(cut_times: np.ndarray, music: dict, duration: float) -> dict:
    beat_times = np.array(music["beats_s"])
    period = music["beat_period_s"]
    grids = {
        "downbeat": (np.array(music["downbeats_s"]), period * 4),
        "beat": (beat_times, period),
        "half_beat": (subdivide(beat_times, 2), period / 2),
        "quarter_beat": (subdivide(beat_times, 4), period / 4),
    }
    report = {"tolerance_s": SYNC_TOLERANCE_S, "cuts_measured": int(cut_times.size)}
    for name, (grid, spacing) in grids.items():
        off = nearest_offsets(cut_times, grid)
        hits = np.abs(off) <= SYNC_TOLERANCE_S
        report[name] = {
            "hit_rate": round(float(hits.mean()), 3) if cut_times.size else None,
            "chance_rate": round(min(1.0, 2 * SYNC_TOLERANCE_S / spacing), 3),
            "median_offset_s_of_hits": round(float(np.median(off[hits])), 3) if hits.any() else None,
        }
    onsets = np.array(music["onsets_s"])
    off = nearest_offsets(cut_times, onsets)
    density = onsets.size / max(duration, 1e-6)
    report["any_onset"] = {
        "hit_rate": round(float((np.abs(off) <= SYNC_TOLERANCE_S).mean()), 3) if cut_times.size else None,
        "chance_rate": round(float(1 - np.exp(-density * 2 * SYNC_TOLERANCE_S)), 3),
    }
    accents = np.array(music["strong_accents_s"])
    off = nearest_offsets(cut_times, accents)
    density = accents.size / max(duration, 1e-6)
    report["strong_accent"] = {
        "hit_rate": round(float((np.abs(off) <= SYNC_TOLERANCE_S).mean()), 3) if cut_times.size else None,
        "chance_rate": round(float(1 - np.exp(-density * 2 * SYNC_TOLERANCE_S)), 3),
    }
    return report


def accent_alignment(cut_times: np.ndarray, y: np.ndarray, sr: int, duration: float) -> dict:
    """Tempo-free sync test: mean onset strength around the cuts versus random cut sets.

    Beat-grid hit rates depend on a correct tempo estimate; this does not. ``locked`` is
    true only when the onset strength peak near the cuts beats 95% of random placements.
    """
    hop = 256
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    env = (env - env.mean()) / (env.std() or 1.0)
    lags = np.arange(-0.25, 0.2501, hop / sr)

    def curve(times: np.ndarray) -> np.ndarray:
        idx = np.round((times[:, None] + lags[None, :]) * sr / hop).astype(int)
        return env[np.clip(idx, 0, env.size - 1)].mean(axis=0)

    if cut_times.size < 4:
        return {"locked": None, "reason": "fewer than four cuts"}
    observed = curve(cut_times)
    near = np.abs(lags) <= SYNC_TOLERANCE_S
    peak = float(observed[near].max())
    rng = np.random.default_rng(0)
    null = np.array([curve(rng.uniform(0.3, duration - 0.3, cut_times.size))[near].max() for _ in range(300)])
    threshold = float(np.percentile(null, 95))
    return {
        "onset_z_near_cuts": round(peak, 3),
        "random_p95": round(threshold, 3),
        "best_lag_s": round(float(lags[near][observed[near].argmax()]), 3),
        "locked": bool(peak > threshold),
    }


def detect_voice(y16k: np.ndarray) -> dict:
    """Speech-like segments via the Silero VAD bundled with faster-whisper, if installed."""
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps
    except ImportError:
        return {"status": "not_run", "reason": "faster-whisper not installed"}
    stamps = get_speech_timestamps(y16k, VadOptions(min_speech_duration_ms=250, min_silence_duration_ms=300))
    segments = [[round(s["start"] / 16000, 2), round(s["end"] / 16000, 2)] for s in stamps]
    total = sum(e - s for s, e in segments)
    return {
        "status": "ok",
        "voice_ratio": round(total / max(y16k.size / 16000, 1e-6), 3),
        "segments_s": segments,
        "note": "Sung vocals also count as voice; confirm narration by listening or captions.",
    }


def structure(shots: list[dict]) -> dict:
    """Find a fast opening montage (hook) and a dark closing card."""
    durations = np.array([s["duration_s"] for s in shots])
    body_median = float(np.median(durations[len(durations) // 4:])) if len(durations) > 4 else float(np.median(durations))
    hook_shots = 0
    for d in durations:
        if d <= 0.6 * body_median:
            hook_shots += 1
        else:
            break
    hook = None
    if hook_shots >= 4:
        hook = {
            "shots": hook_shots,
            "end_s": round(shots[hook_shots - 1]["start_s"] + shots[hook_shots - 1]["duration_s"], 3),
            "median_shot_s": round(float(np.median(durations[:hook_shots])), 3),
        }
    last = shots[-1]
    end_card = {"duration_s": last["duration_s"]} if last["luma"] < 0.06 and len(shots) > 1 else None
    return {"hook": hook, "body_median_shot_s": round(body_median, 3), "end_card": end_card}


def summarise_durations(durations: np.ndarray) -> dict:
    return {
        "count": int(durations.size),
        "mean_s": round(float(durations.mean()), 3),
        "median_s": round(float(np.median(durations)), 3),
        "p10_s": round(float(np.percentile(durations, 10)), 3),
        "p90_s": round(float(np.percentile(durations, 90)), 3),
        "min_s": round(float(durations.min()), 3),
        "max_s": round(float(durations.max()), 3),
    }


def contact_sheet(video: Path, shots: list[dict], fps: float, out_path: Path, columns: int = 8) -> None:
    mids = [int((s["start_frame"] + s["end_frame"]) // 2) for s in shots]
    with tempfile.TemporaryDirectory() as tmp:
        files = media.extract_frames(video, mids, 180, Path(tmp))
        thumbs = [Image.open(f).convert("RGB") for f in files]
        if not thumbs:
            return
        tw, th = thumbs[0].size
        label_h = 18
        rows = (len(thumbs) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * tw, rows * (th + label_h)), "white")
        draw = ImageDraw.Draw(sheet)
        for k, (img, shot) in enumerate(zip(thumbs, shots, strict=False)):
            x, y = (k % columns) * tw, (k // columns) * (th + label_h)
            sheet.paste(img.resize((tw, th)), (x, y + label_h))
            draw.text((x + 3, y + 3), f"#{shot['index']} {shot['start_s']:.2f}s +{shot['duration_s']:.2f}", fill="black")
        sheet.save(out_path, quality=85)


def analyze(video: Path, url: str | None, out_dir: Path, start_bpm: float) -> dict:
    info = media.probe(video)
    fps = info["fps"]
    frames = media.read_frames(video, SMALL_W, SMALL_H)
    scores = cut_scores(frames)
    cuts = detect_cuts(scores, fps)
    bounds = [0] + cuts + [len(frames)]

    shots = []
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        seg = frames[a:b]
        luma = seg.astype(np.float32).mean(axis=-1)
        motion = float(np.abs(np.diff(luma, axis=0)).mean() / 255) if len(seg) > 1 else 0.0
        shots.append({
            "index": k,
            "start_frame": a,
            "end_frame": b,
            "start_s": round(a / fps, 3),
            "duration_s": round((b - a) / fps, 3),
            "motion": round(motion, 4),
            **colour_stats(seg[:: max(1, len(seg) // 6)]),
        })
    durations = np.array([s["duration_s"] for s in shots])
    cut_times = np.array(cuts, dtype=float) / fps

    profile: dict = {
        "profile_version": PROFILE_VERSION,
        "source": {
            "url": url,
            "file_name": video.name,
            "note": "Measurements of a third-party reel for style reference only; the media is not stored in Git.",
        },
        "media": info,
        "shots": summarise_durations(durations),
        "structure": structure(shots),
        "pacing_by_window": [],
        "colour": colour_stats(frames[:: max(1, len(frames) // 200)]),
    }

    window = 5.0
    for w0 in np.arange(0, info["duration_s"], window):
        in_win = [s for s in shots if w0 <= s["start_s"] < w0 + window]
        if in_win:
            profile["pacing_by_window"].append({
                "start_s": round(float(w0), 1),
                "shots": len(in_win),
                "median_shot_s": round(float(np.median([s["duration_s"] for s in in_win])), 3),
            })

    if info["has_audio"]:
        y = media.read_audio(video, AUDIO_SR)
        music = beats.analyze_music(y, AUDIO_SR, start_bpm=start_bpm)
        for shot in shots:
            shot["duration_beats"] = round(shot["duration_s"] / music["beat_period_s"], 2)
        beat_lengths = np.array([s["duration_beats"] for s in shots[1:-1]] or [0.0])
        rounded = np.round(beat_lengths * 2) / 2
        values, counts = np.unique(rounded, return_counts=True)
        profile["audio"] = {
            "loudness": media.loudness(video),
            "mix_shape": beats.mix_shape(y, AUDIO_SR),
            "voice": detect_voice(media.read_audio(video, 16000)),
            "music": {k: music[k] for k in ("tempo_bpm", "beat_period_s", "beat_interval_cv",
                                             "downbeat_phase", "downbeat_confidence")},
        }
        profile["cut_sync"] = sync_report(cut_times, music, info["duration_s"])
        profile["cut_sync"]["accent_alignment"] = accent_alignment(cut_times, y, AUDIO_SR, info["duration_s"])
        profile["shots"]["duration_beats_histogram"] = {
            f"{v:g}": int(c) for v, c in sorted(zip(values, counts, strict=True), key=lambda vc: -vc[1])[:10]
        }
        profile["beat_grid"] = {k: music[k] for k in ("beats_s", "downbeats_s", "strong_accents_s")}

    profile["shot_list"] = shots
    out_dir.mkdir(parents=True, exist_ok=True)
    contact_sheet(video, shots, fps, out_dir / "contact_sheet.jpg")
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("video", type=Path)
    parser.add_argument("--url", help="Public URL of the reference, recorded in the profile")
    parser.add_argument("--out-dir", type=Path, required=True, help="Folder for profile.json and contact_sheet.jpg")
    parser.add_argument("--start-bpm", type=float, default=120.0, help="Tempo prior for the beat tracker")
    args = parser.parse_args()
    profile = analyze(args.video, args.url, args.out_dir, args.start_bpm)
    (args.out_dir / "profile.json").write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    shots = profile["shots"]
    print(f"{args.video.name}: {shots['count']} shots, median {shots['median_s']}s", end="")
    if "audio" in profile:
        sync = profile["cut_sync"]
        print(f", {profile['audio']['music']['tempo_bpm']} BPM, beat hit rate "
              f"{sync['beat']['hit_rate']} (chance {sync['beat']['chance_rate']}), "
              f"cuts locked to accents: {sync['accent_alignment'].get('locked')}")
    else:
        print()


if __name__ == "__main__":
    main()

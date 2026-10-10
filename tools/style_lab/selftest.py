"""End-to-end check on synthetic media whose beat grid is known.

Builds a 100 BPM drum track, coloured test clips carrying a 1234 Hz tone, and a
synthetic voiceover; plans and renders every template; then re-measures the MP4:
cuts on the true beat grid, duration, loudness, muted clip audio and ducking.
Synthetic media proves the mechanics only, not the look on real footage.

    uv run python tools/style_lab/selftest.py --work work/style_lab/selftest
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_reference  # noqa: E402

from vlogii.style import beats, media, planner, templates  # noqa: E402
from vlogii.style.render import render  # noqa: E402

BPM, LEAD_S, BARS, SR = 100.0, 0.5, 40, 44100
BEAT = 60.0 / BPM
TONE_HZ = 1234.0
COLOURS = ["0xC0392B", "0x2980B9", "0x27AE60", "0x8E44AD", "0xF39C12", "0x16A085", "0xD35400",
           "0x2C3E50", "0xE84393", "0x00CEC9", "0x6C5CE7", "0xFDCB6E", "0x55EFC4", "0xB2BEC3"]
PAD_HZ = (2093.0, 2637.0, 3136.0)
VOICE_SEGMENTS = [(1.0, 4.0), (6.0, 9.5), (12.0, 15.0), (18.0, 22.0), (25.0, 28.0), (31.0, 35.0)]


def true_beats() -> np.ndarray:
    return LEAD_S + np.arange(BARS * 4) * BEAT


def make_music(path: Path) -> None:
    n = int((LEAD_S + BARS * 4 * BEAT + 1.0) * SR)
    out = np.zeros(n)
    rng = np.random.default_rng(1)

    def add(at: float, signal: np.ndarray) -> None:
        i = int(at * SR)
        out[i: i + len(signal)] += signal[: max(0, n - i)]

    t_kick = np.arange(int(0.25 * SR)) / SR
    kick = np.sin(2 * np.pi * (50 * t_kick + 70 * (1 - np.exp(-t_kick * 30)) / 30)) * np.exp(-t_kick * 18)
    t_snare = np.arange(int(0.15 * SR)) / SR
    snare = rng.standard_normal(t_snare.size) * np.exp(-t_snare * 30)
    t_hat = np.arange(int(0.04 * SR)) / SR
    hat = np.diff(rng.standard_normal(t_hat.size + 1)) * np.exp(-t_hat * 90)
    roots = [55.0, 65.4, 49.0, 73.4]
    for k, beat in enumerate(true_beats()):
        position = k % 4
        if position in (0, 2):
            add(beat, kick * (0.6 if position == 0 else 0.4))
        else:
            add(beat, snare * 0.25)
        add(beat, hat * 0.08)
        add(beat + BEAT / 2, hat * 0.05)
        if position == 0:
            t = np.arange(int(4 * BEAT * SR)) / SR
            swell = np.minimum(1, t * 20) * np.minimum(1, (4 * BEAT - t) * 20)
            add(beat, 0.15 * np.sin(2 * np.pi * roots[(k // 4) % 4] * t) * swell)
            # a steady high pad, above the synthetic voice's harmonics, to measure ducking against
            add(beat, sum(0.05 * np.sin(2 * np.pi * f * t) for f in PAD_HZ) * swell)
    sf.write(path, 0.8 * out / np.abs(out).max(), SR)


def make_clips(folder: Path) -> list[dict]:
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    for i, colour in enumerate(COLOURS):
        portrait = i % 3 != 1
        size = "720x1280" if portrait else "1280x720"
        rate = 60 if i == 5 else 30
        duration = 4.0 + (i * 7 % 4)
        hour, minute = 8 + i * 10 // 14, (i * 17) % 60
        path = folder / f"clip_{i:02d}.mov"
        subprocess.run([
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={colour}:s={size}:r={rate}:d={duration}",
            "-f", "lavfi", "-i", f"sine=frequency={TONE_HZ}:sample_rate=48000:duration={duration}",
            "-vf", f"drawtext=text='CLIP {i} %{{pts\\:hms}}':fontcolor=white:fontsize=48:x=(w-tw)/2:y=h/3,"
                   f"drawbox=x='mod(t*300,w)':y=2*h/3:w=80:h=80:color=white:t=fill",
            "-metadata", f"com.apple.quicktime.creationdate=2026-10-10T{hour:02d}:{minute:02d}:00-0400",
            "-movflags", "use_metadata_tags", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            "-shortest", str(path)], check=True)
        entries.append({"path": path.name, "label": f"moment {i}"})
    return entries


def make_voice(path: Path, transcript_path: Path) -> None:
    n = int(40 * SR)
    t = np.arange(n) / SR
    voice = np.zeros(n)
    sentences = []
    for k, (a, b) in enumerate(VOICE_SEGMENTS):
        mask = (t >= a) & (t < b)
        syllables = 0.5 + 0.5 * np.sin(2 * np.pi * 4 * t[mask])
        voice[mask] = sum(np.sin(2 * np.pi * f * t[mask]) / (j + 1) for j, f in enumerate((200, 400, 600, 800))) * syllables
        words = ["this", "is", "a", "test", "sentence", "number", str(k + 1)]
        step = (b - a) / len(words)
        sentences.append({"sentence_id": f"sentence_{k}", "asset_id": "voiceover_01", "in_seconds": a,
                          "out_seconds": b, "text": " ".join(words),
                          "words": [{"text": w, "in_seconds": round(a + j * step, 3),
                                     "out_seconds": round(a + (j + 1) * step, 3)} for j, w in enumerate(words)]})
    sf.write(path, 0.3 * voice / np.abs(voice).max(), SR)
    transcript_path.write_text(json.dumps({"schema_version": "1.0.0", "document_type": "transcript",
                                           "project_id": "style_selftest", "sentences": sentences}, indent=2))


def band_db(audio: np.ndarray, sr: int, lo: float, hi: float) -> float:
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(audio.size))) ** 2
    freqs = np.fft.rfftfreq(audio.size, 1 / sr)
    return 10 * np.log10(spectrum[(freqs >= lo) & (freqs < hi)].mean() + 1e-20)


def pad_level_db(audio: np.ndarray, sr: int, mask: np.ndarray) -> float:
    """Median level of the pad band over 50 ms windows inside ``mask`` (robust to drum hits)."""
    win = int(0.05 * sr)
    levels = []
    for start in range(0, audio.size - win, win):
        if mask[start: start + win].all():
            levels.append(band_db(audio[start: start + win], sr, PAD_HZ[0] - 60, PAD_HZ[-1] + 60))
    return float(np.median(levels))


def check_template(template_id: str, work: Path, music: Path, manifest: Path, voice: Path, transcript: Path) -> dict:
    template = templates.load(template_id)
    narrated = template["voiceover"]["supported"]
    out_dir = work / template_id
    inputs, text = planner.load_manifest(manifest)
    plan = planner.plan(template, music, inputs, text, voiceover=voice if narrated else None,
                        transcript=json.loads(transcript.read_text()) if narrated else None)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=2))
    with tempfile.TemporaryDirectory(prefix="vlogii-style-") as temporary:
        report = render(plan, template, out_dir / "preview.mp4", Path(temporary), out_dir / "logs",
                        progress=lambda _: None)
    fps = plan["output"]["fps"]
    result = {"template": template_id, "shots": len(plan["shots"]), "planned_s": report["planned_duration_s"],
              "rendered_s": round(media.probe(out_dir / "preview.mp4")["duration_s"], 3),
              "loudness": report["loudness"], "audio": report["audio"], "warnings": plan["warnings"]}

    # Cuts in the plan sit on the true beat grid (beat tracker + start choice + frame rounding).
    grid = np.concatenate([true_beats()[:-1, None] + BEAT * np.array([0, 0.25, 0.5, 0.75])[None, :]]).ravel()
    music_start = plan["music"]["start_s"]
    planned_cuts = np.array([s["start_frame"] for s in plan["shots"][1:]] +
                            ([plan["end_card"]["start_frame"]] if plan["end_card"] else [])) / fps
    offsets = analyze_reference.nearest_offsets(planned_cuts + music_start, np.sort(grid))
    result["max_planned_cut_offset_ms"] = round(float(np.abs(offsets).max() * 1000), 1)

    # Cuts detected in the rendered MP4 match the plan.
    frames = media.read_frames(out_dir / "preview.mp4", 72, 128)
    detected = np.array(analyze_reference.detect_cuts(analyze_reference.cut_scores(frames), fps)) / fps
    clip_change = [s["start_frame"] / fps for prev, s in zip(plan["shots"], plan["shots"][1:], strict=False) if prev["clip"] != s["clip"]]
    to_plan = analyze_reference.nearest_offsets(detected, np.sort(planned_cuts))
    result["detected_cuts"] = int(detected.size)
    result["detected_on_planned_cut"] = round(float((np.abs(to_plan) <= 1.01 / fps).mean()), 3) if detected.size else None
    recall = analyze_reference.nearest_offsets(np.array(clip_change), np.sort(detected))
    result["clip_change_cuts_found"] = round(float((np.abs(recall) <= 1.01 / fps).mean()), 3)

    # Clip audio is muted and, for narration, music ducks under the voice.
    audio = media.read_audio(out_dir / "preview.mp4", 48000)
    tone = band_db(audio, 48000, TONE_HZ - 4, TONE_HZ + 4)
    around = band_db(audio, 48000, TONE_HZ - 80, TONE_HZ - 20)
    result["tone_above_neighbours_db"] = round(tone - around, 1)
    if narrated:
        t = np.arange(audio.size) / 48000
        inside = np.zeros(audio.size, bool)
        for a, b in VOICE_SEGMENTS:
            inside |= (t >= a + 0.5) & (t < b - 0.2)
        outside = np.zeros(audio.size, bool)
        for (_, b), (a, _) in zip(VOICE_SEGMENTS, VOICE_SEGMENTS[1:], strict=False):
            outside |= (t >= b + 0.7) & (t < a - 0.1)
        result["music_drop_under_voice_db"] = round(
            pad_level_db(audio, 48000, inside) - pad_level_db(audio, 48000, outside), 1)
        result["captions"] = sum(o["kind"] == "caption" for o in plan["overlays"])
    result["stamps"] = sum(o["kind"] == "stamp" for o in plan["overlays"])

    target = template["voiceover"]["target_lufs"] if narrated else template["music"]["target_lufs"]
    checks = {
        "duration_matches_plan": abs(result["rendered_s"] - report["planned_duration_s"]) <= 1.5 / fps,
        "planned_cuts_on_true_beat_grid": result["max_planned_cut_offset_ms"] <= 1000 / fps / 2 + 15,
        "rendered_cuts_match_plan": (result["detected_on_planned_cut"] or 0) >= 0.95,
        "clip_changes_visible": result["clip_change_cuts_found"] >= 0.95,
        "loudness_on_target": abs((report["loudness"]["integrated_lufs"] or -99) - target) <= 1.0,
        "true_peak_under_ceiling": (report["loudness"]["true_peak_dbtp"] or 0) <= template["music"]["true_peak_dbtp"] + 0.5,
        "clip_audio_muted": result["tone_above_neighbours_db"] < 6,
    }
    if narrated:
        duck = template["voiceover"]["music_duck_db"]
        checks["music_ducks_under_voice"] = duck - 4 <= result["music_drop_under_voice_db"] <= duck + 4
        checks["captions_from_transcript"] = result["captions"] > 0
    if template["text"]["stamps"]["mode"] != "none":
        checks["stamps_present"] = result["stamps"] > 0
    result["checks"] = {name: bool(ok) for name, ok in checks.items()}
    result["passed"] = all(result["checks"].values())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--template", action="append", help="Limit to these template ids")
    args = parser.parse_args()
    work = args.work.resolve()
    media_dir = work / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    music, voice, transcript = media_dir / "drums_100bpm.wav", media_dir / "voice.wav", media_dir / "transcript.json"
    make_music(music)
    make_voice(voice, transcript)
    entries = make_clips(media_dir / "clips")
    manifest = media_dir / "manifest.json"
    manifest.write_text(json.dumps({"clips": [dict(e, path=f"clips/{e['path']}") for e in entries],
                                    "text": {"subtitle": "synthetic test day", "location": "TEST CITY"}}, indent=2))

    y = media.read_audio(music, planner.AUDIO_SR)
    detected = np.array(beats.analyze_music(y, planner.AUDIO_SR)["beats_s"])
    truth = true_beats()
    hits = np.abs(analyze_reference.nearest_offsets(truth, detected)) <= 0.07
    precision = np.abs(analyze_reference.nearest_offsets(detected, truth)) <= 0.07
    summary = {"beat_tracking": {"recall": round(float(hits.mean()), 3), "precision": round(float(precision.mean()), 3),
                                 "tempo_bpm": round(60 / float(np.median(np.diff(detected))), 2), "true_bpm": BPM}}
    ids = args.template or [p.stem for p in templates.template_paths()]
    summary["templates"] = [check_template(t, work, music, manifest, voice, transcript) for t in ids]
    summary["passed"] = bool(summary["beat_tracking"]["recall"] >= 0.95 and summary["beat_tracking"]["precision"] >= 0.95
                             and all(t["passed"] for t in summary["templates"]))
    (work / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

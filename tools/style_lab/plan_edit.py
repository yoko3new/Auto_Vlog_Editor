"""Turn footage + music + a style template into a beat-locked style plan (JSON).

The template supplies shot lengths in seconds learned from a reference reel; the plan
snaps every cut onto the user's own beat grid, so the rhythm is imitated and the cuts
land on the music. AI (or the user) only chooses clips, order, labels and text through
the manifest; this code computes every frame position.

    python tools/style_lab/plan_edit.py --template ig_city_day_in_life \
        --music work/me/song.mp3 --manifest work/me/manifest.json --out work/me/plan.json

Manifest (paths relative to the manifest; every key except "path" is optional):
    {"clips": [{"path": "IMG_0001.MOV", "label": "making coffee", "in_s": 0.5, "out_s": 6,
                "clock": "08:05"}],
     "text": {"kicker": "...", "title": "...", "subtitle": "...", "time_range": "...",
              "location": "...", "end_card": "..."}}
``clock`` is 24-hour local time; without it the QuickTime creation date is used if present.
``--clips DIR`` instead uses every video in DIR ordered by capture time, without labels.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import beats  # noqa: E402
import media  # noqa: E402
import templates  # noqa: E402

PLAN_VERSION = 1
AUDIO_SR = 22050
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
EDGE_TRIM_S = 0.15


class PlanError(RuntimeError):
    pass


@dataclass
class Clip:
    path: Path
    duration_s: float
    usable_in: float
    usable_out: float
    label: str | None
    clock: str | None
    clock_minutes: int | None
    grade: dict = field(default_factory=dict)

    @property
    def usable_s(self) -> float:
        return self.usable_out - self.usable_in


class Grid:
    """Beat positions (in beats from the chosen start) mapped to music time and output frames."""

    def __init__(self, beat_times: np.ndarray, start_index: int, fps: int):
        self.beats = beat_times
        self.i0 = start_index
        self.fps = fps
        self.period = float(np.median(np.diff(beat_times)))

    def time(self, pos: float) -> float:
        k = self.i0 + pos
        i = int(math.floor(k))
        if i + 1 < self.beats.size:
            return float(self.beats[i] + (k - i) * (self.beats[i + 1] - self.beats[i]))
        return float(self.beats[-1] + (k - (self.beats.size - 1)) * self.period)

    def seconds(self, a: float, b: float) -> float:
        return self.time(b) - self.time(a)

    def frame(self, pos: float) -> int:
        return int(round((self.time(pos) - self.time(0)) * self.fps))


def clock_text(minutes: int) -> str:
    return f"{minutes // 60 % 12 or 12}:{minutes % 60:02d}"


def capture_minutes(tags: dict) -> int | None:
    """Local wall-clock minutes from the QuickTime creation date (it carries the UTC offset).

    Plain ``creation_time`` is UTC without the shooting time zone, so it is not used.
    """
    raw = tags.get("com.apple.quicktime.creationdate")
    if not raw:
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp.hour * 60 + stamp.minute


def manifest_minutes(text: str, path: Path) -> int:
    """Manifest clocks are 24-hour HH:MM so that 1:30 and 13:30 stay distinct."""
    try:
        hours, minutes = (int(part) for part in text.split(":"))
        if 0 <= hours < 24 and 0 <= minutes < 60:
            return hours * 60 + minutes
    except ValueError:
        pass
    raise PlanError(f"{path.name}: clock {text!r} must be 24-hour HH:MM")


def load_clips(args) -> tuple[list[Clip], dict]:
    entries, text = [], {}
    if args.manifest:
        manifest = json.loads(args.manifest.read_text())
        base = args.manifest.parent
        text = manifest.get("text", {})
        entries = [dict(item, path=(base / item["path"]).resolve()) for item in manifest["clips"]]
    else:
        files = [p for p in sorted(args.clips.iterdir()) if p.suffix.lower() in VIDEO_EXTS]
        entries = [{"path": p.resolve()} for p in files]
    clips, captured = [], []
    for item in entries:
        info = media.probe(item["path"])
        if not info["has_video"]:
            raise PlanError(f"{item['path']}: no video stream")
        dur = info["duration_s"]
        trim = min(EDGE_TRIM_S, dur * 0.05)
        start = float(item.get("in_s", trim))
        end = float(item.get("out_s", dur - trim))
        if not 0 <= start < end <= dur + 1e-3:
            raise PlanError(f"{item['path']}: in_s/out_s outside 0..{dur:.2f}")
        minutes = manifest_minutes(item["clock"], item["path"]) if item.get("clock") else capture_minutes(info["tags"])
        clock = clock_text(minutes) if minutes is not None else None
        clips.append(Clip(item["path"], dur, start, end, item.get("label"), clock, minutes))
        captured.append(info["tags"].get("com.apple.quicktime.creationdate") or info["tags"].get("creation_time") or "")
    if not args.manifest:
        clips = [c for _, _, c in sorted(zip(captured, [c.path.name for c in clips], clips))]
    if not clips:
        raise PlanError("no clips found")
    return clips, text


def grade_for(clip: Clip, template: dict) -> dict:
    """Move a clip part of the way toward the reference's measured brightness, saturation and warmth."""
    frames = media.read_frames(clip.path, 48, 64, fps=2).astype(np.float32) / 255
    if frames.size == 0:
        return {"brightness": 0.0, "saturation": 1.0, "warmth_shift": 0.0}
    r, g, b = frames[..., 0], frames[..., 1], frames[..., 2]
    luma = float((0.2126 * r + 0.7152 * g + 0.0722 * b).mean())
    cmax, cmin = frames.max(axis=-1), frames.min(axis=-1)
    sat = float(np.where(cmax > 0, (cmax - cmin) / np.maximum(cmax, 1e-6), 0).mean())
    warmth = float((r - b).mean())
    target, k = template["grade"]["target"], template["grade"]["strength"]
    return {
        "brightness": round(float(np.clip((target["luma"] - luma) * k, -0.15, 0.15)), 3),
        "saturation": round(float(np.clip((target["saturation"] / max(sat, 0.02)) ** k, 0.6, 1.5)), 3),
        "warmth_shift": round(float(np.clip((target["warmth"] - warmth) * k, -0.2, 0.2)), 3),
        "measured": {"luma": round(luma, 3), "saturation": round(sat, 3), "warmth": round(warmth, 3)},
    }


def round_beats(seconds: float, period: float, step: float) -> float:
    return max(step, step * round(seconds / period / step))


def choose_start(music: dict, y: np.ndarray, policy: str, total_beats: float, music_dur: float) -> int:
    beat_times = np.array(music["beats_s"])
    phase = music["downbeat_phase"]
    candidates = [i for i in range(phase, beat_times.size, beats.BEATS_PER_BAR)]
    grid_ok = [i for i in candidates if Grid(beat_times, i, 30).time(total_beats) <= music_dur - 0.05]
    if not grid_ok:
        raise PlanError("music is too short for the minimum duration of this template")
    if policy == "first_downbeat":
        return grid_ok[0]
    times, db = beats.level_envelope(y, AUDIO_SR)
    scores = []
    for i in grid_ok:
        a, b = beat_times[i], Grid(beat_times, i, 30).time(total_beats)
        scores.append(float(db[(times >= a) & (times < b)].mean()))
    return grid_ok[int(np.argmax(scores))]


def shot_lengths(grid: Grid, start: float, end: float, section: dict, rng: np.random.Generator) -> list[float]:
    """Shot lengths in beats that fill [start, end) exactly, near the reference's shot seconds."""
    multiples = sorted(section["beat_multiples"])
    rule = section["shot"]
    lengths, pos = [], start
    while end - pos > 1e-9:
        noise = math.exp(rng.normal(0, section["variation"])) if section["variation"] else 1.0
        target = min(max(rule["target_s"] * noise, rule["min_s"]), rule["max_s"])
        inside = [m for m in multiples if rule["min_s"] <= grid.seconds(pos, pos + m) <= rule["max_s"]]
        shortest_inside = min(inside) if inside else multiples[0]
        options = []
        for m in multiples:
            rest = end - pos - m
            if rest < -1e-9 or 1e-9 < rest < multiples[0] - 1e-9:
                continue
            length = grid.seconds(pos, pos + m)
            options.append((
                1e-9 < rest < shortest_inside - 1e-9,          # avoid leaving a stub shorter than the style allows
                not rule["min_s"] <= length <= rule["max_s"],  # stay inside the reference's shot range
                abs(length - target),
                m,
            ))
        m = min(options)[-1]
        lengths.append(m)
        pos += m
    return lengths


def make_shot(grid: Grid, clip_index: int, pos: float, beats_len: float, source_in: float) -> dict:
    start_frame, end_frame = grid.frame(pos), grid.frame(pos + beats_len)
    return {"clip_index": clip_index, "source_in_s": round(source_in, 4),
            "source_out_s": round(source_in + (end_frame - start_frame) / grid.fps, 4),
            "start_frame": start_frame, "end_frame": end_frame, "beat_position": pos, "beats": beats_len}


def place_hook(grid: Grid, start: float, lengths: list[float], clips: list[Clip]) -> list[dict]:
    """Quick previews spread across the day, taken late in each clip so the body can open it."""
    count = len(lengths)
    order = list(range(len(clips)))
    if len(clips) > count:
        order = [int(round(i * (len(clips) - 1) / max(count - 1, 1))) for i in range(count)]
    shots, pos, n = [], start, 0
    for m in lengths:
        seconds = (grid.frame(pos + m) - grid.frame(pos)) / grid.fps
        for _ in range(len(order)):
            index = order[n % len(order)]
            n += 1
            clip = clips[index]
            if clip.usable_s >= seconds:
                centre = clip.usable_in + clip.usable_s * (0.75, 0.9, 0.6)[(n - 1) // len(order) % 3]
                source_in = min(max(clip.usable_in, centre - seconds / 2), clip.usable_out - seconds)
                shots.append(make_shot(grid, index, pos, m, source_in))
                break
        else:
            raise PlanError("every clip is shorter than one hook shot")
        pos += m
    return shots


def place_body(grid: Grid, start: float, lengths: list[float], clips: list[Clip], warnings: list[str]) -> list[dict]:
    """Keep clip order; give each clip consecutive shots in proportion to its length, spread across it."""
    indices = list(range(len(clips)))
    if len(clips) > len(lengths):
        indices = sorted({int(round(i * (len(clips) - 1) / max(len(lengths) - 1, 1))) for i in range(len(lengths))})
        skipped = [clips[i].path.name for i in range(len(clips)) if i not in indices]
        warnings.append(f"not enough time for every clip; skipped {', '.join(skipped)}")
    usable = np.array([clips[i].usable_s for i in indices])
    raw = np.maximum(1.0, len(lengths) * usable / usable.sum())
    counts = np.floor(raw).astype(int)
    while counts.sum() > len(lengths):
        counts[np.argmax(np.where(counts > 1, counts - raw, -np.inf))] -= 1
    for i in np.argsort(-(raw - counts))[: len(lengths) - counts.sum()]:
        counts[i] += 1
    seconds = [grid.seconds(p, p + m) for p, m in zip(np.cumsum([start] + lengths[:-1]), lengths)]

    def demand() -> np.ndarray:
        bounds = np.concatenate([[0], np.cumsum(counts)])
        return np.array([sum(seconds[bounds[k]:bounds[k + 1]]) for k in range(len(counts))])

    for _ in range(4 * len(lengths)):
        over = demand() - 0.95 * usable
        if (over <= 0).all():
            break
        k = int(np.argmax(over))
        slack = 0.95 * usable - demand()
        neighbours = [j for j in (k - 1, k + 1) if 0 <= j < len(counts)]
        if counts[k] <= 1 or not neighbours:
            raise PlanError(f"{clips[indices[k]].path.name} is too short for its shots; trim less or add footage")
        counts[k] -= 1
        counts[max(neighbours, key=lambda j: slack[j])] += 1
    else:
        raise PlanError("footage too short to place every shot without repeating frames")

    shots, pos, n = [], start, 0
    for k, count in zip(indices, counts):
        clip = clips[k]
        mine = lengths[n:n + count]
        spans = seconds[n:n + count]
        gap = max(0.0, clip.usable_s - sum(spans)) / count
        cursor = clip.usable_in + gap / 2
        for m, span in zip(mine, spans):
            shots.append(make_shot(grid, k, pos, m, cursor))
            cursor += span + gap
            pos += m
        n += count
    return shots


def caption_chunks(transcript: dict, max_words: int) -> list[tuple[float, float, str]]:
    chunks = []
    for sentence in transcript.get("sentences", []):
        words = sentence.get("words") or []
        if not words:
            tokens = sentence["text"].split()
            step = (sentence["out_seconds"] - sentence["in_seconds"]) / max(len(tokens), 1)
            words = [{"text": w, "in_seconds": sentence["in_seconds"] + i * step,
                      "out_seconds": sentence["in_seconds"] + (i + 1) * step} for i, w in enumerate(tokens)]
        for i in range(0, len(words), max_words):
            group = words[i: i + max_words]
            chunks.append((group[0]["in_seconds"], group[-1]["out_seconds"], " ".join(w["text"] for w in group)))
    return chunks


def plan(args) -> dict:
    template = templates.load(args.template)
    fps = template["output"]["fps"]
    warnings: list[str] = []
    clips, text = load_clips(args)
    text = {**template["text"]["defaults"], **{k: v for k, v in text.items() if v}}

    y = media.read_audio(args.music, AUDIO_SR)
    music_dur = y.size / AUDIO_SR
    music = beats.analyze_music(y, AUDIO_SR)
    beat_times = np.array(music["beats_s"])
    if beat_times.size < 16:
        raise PlanError("could not find a steady beat in the music")
    if music["beat_interval_cv"] and music["beat_interval_cv"] > 0.1:
        warnings.append(f"beat grid is irregular (cv {music['beat_interval_cv']}); listen to the cuts")
    if music["downbeat_confidence"] < 0.1:
        warnings.append("downbeat estimate is weak; sections may change on beat 2 or 3 instead of beat 1")
    period = float(np.median(np.diff(beat_times)))

    sections = template["sections"]
    step = 2.0
    fixed = {s["role"]: round_beats(s["length_s"], period, step) for s in sections if s["length_s"]}
    end_card_beats = round_beats(template["end_card"]["length_s"], period, step) if template["end_card"] else 0.0
    dur = template["duration"]
    target_s = min(max(args.duration or dur["target_s"], dur["min_s"]), dur["max_s"])
    body_rule = next(s for s in sections if s["role"] == "body")
    material = sum(c.usable_s for c in clips)
    needed_shots = len(clips)
    body_target_s = max(target_s - (sum(fixed.values()) + end_card_beats) * period, 0)
    if needed_shots * body_rule["shot"]["target_s"] > body_target_s:
        grown = min(dur["max_s"], target_s + needed_shots * body_rule["shot"]["target_s"] - body_target_s)
        if grown > target_s:
            warnings.append(f"duration raised from {target_s:.1f}s to {grown:.1f}s so every clip gets a shot")
            target_s = grown

    def total_for(seconds: float) -> float:
        return round_beats(seconds, period, beats.BEATS_PER_BAR)

    total_beats = total_for(target_s)
    min_beats = total_for(dur["min_s"])
    first_downbeat = beat_times[music["downbeat_phase"]]
    music_beats = beats.BEATS_PER_BAR * math.floor((music_dur - 0.05 - first_downbeat) / period / beats.BEATS_PER_BAR)
    if music_beats < total_beats:
        if music_beats < min_beats:
            raise PlanError(f"music is {music_dur:.1f}s; this template needs at least {dur['min_s']}s after the first downbeat")
        warnings.append(f"shortened to {music_beats * period:.1f}s to fit the music")
        total_beats = music_beats
    body_beats = total_beats - sum(fixed.values()) - end_card_beats
    music_limited = total_beats
    while body_beats * period > material and total_beats > min_beats:
        total_beats -= beats.BEATS_PER_BAR
        body_beats = total_beats - sum(fixed.values()) - end_card_beats
    if body_beats * period > material:
        raise PlanError(f"footage too short: body needs {body_beats * period:.1f}s, clips give {material:.1f}s")
    if total_beats < music_limited:
        warnings.append(f"shortened to {total_beats * period:.1f}s because the footage runs out")

    start_index = choose_start(music, y, args.music_start or template["music"]["start"], total_beats, music_dur)
    grid = Grid(beat_times, start_index, fps)
    rng = np.random.default_rng(sum(map(ord, template["id"])))

    shots, section_rows, pos = [], [], 0.0
    for section in sections:
        beats_here = fixed.get(section["role"], body_beats)
        start, end = pos, pos + beats_here
        lengths = shot_lengths(grid, start, end, section, rng)
        if section["role"] == "hook":
            placed = place_hook(grid, start, lengths, clips)
        else:
            placed = place_body(grid, start, lengths, clips, warnings)
        for shot in placed:
            shot["section"] = section["role"]
        shots += placed
        section_rows.append({"role": section["role"], "start_frame": grid.frame(start), "end_frame": grid.frame(end),
                             "beats": beats_here})
        pos = end
    for i in sorted({shot["clip_index"] for shot in shots}):
        clips[i].grade = grade_for(clips[i], template)

    end_card = None
    if template["end_card"]:
        end_card = {"start_frame": grid.frame(pos), "end_frame": grid.frame(pos + end_card_beats),
                    "background": template["end_card"]["background"]}
        pos += end_card_beats
    total_frames = grid.frame(pos)

    overlays = build_overlays(template, text, clips, shots, section_rows, end_card, fps, warnings, args)
    cut_error = max(abs(s["start_frame"] / fps - (grid.time(s["beat_position"]) - grid.time(0))) for s in shots)
    for shot in shots:
        clip = clips[shot.pop("clip_index")]
        shot.update(clip=str(clip.path), label=clip.label,
                    grade={k: v for k, v in clip.grade.items() if k != "measured"})
    for i, shot in enumerate(shots):
        shot["index"] = i

    voice = None
    if args.voiceover:
        if not template["voiceover"]["supported"]:
            raise PlanError(f"{template['id']} has no voiceover mix; pick a narrated template")
        voice_dur = media.probe(args.voiceover)["duration_s"]
        if voice_dur > total_frames / fps:
            warnings.append(f"voiceover is {voice_dur:.1f}s but the edit is {total_frames / fps:.1f}s; it will be cut")
        voice = {"path": str(args.voiceover.resolve()), "start_s": 0.0,
                 "target_lufs": template["voiceover"]["target_lufs"],
                 "music_duck_db": template["voiceover"]["music_duck_db"]}

    return {
        "plan_version": PLAN_VERSION,
        "template": {"id": template["id"], "revision": template["revision"]},
        "output": template["output"],
        "total_frames": total_frames,
        "music": {
            "path": str(Path(args.music).resolve()),
            "start_s": round(grid.time(0), 4),
            "duration_s": round(total_frames / fps, 4),
            "tempo_bpm": music["tempo_bpm"],
            "beat_period_s": round(period, 4),
            "downbeat_confidence": music["downbeat_confidence"],
            "fade_in_s": template["music"]["fade_in_s"],
            "fade_out_s": template["music"]["fade_out_s"],
            "target_lufs": template["music"]["target_lufs"],
            "true_peak_dbtp": template["music"]["true_peak_dbtp"],
            "beat_grid_s": [round(grid.time(b) - grid.time(0), 4) for b in np.arange(0, pos + 1e-9, 1.0)],
        },
        "voiceover": voice,
        "sections": section_rows,
        "shots": shots,
        "end_card": end_card,
        "overlays": overlays,
        "checks": {"shots": len(shots), "max_cut_offset_from_grid_s": round(cut_error, 4),
                   "cuts_on_grid": cut_error <= 0.5 / fps + 1e-6},
        "warnings": warnings,
    }


def build_overlays(template, text, clips, shots, sections, end_card, fps, warnings, args) -> list[dict]:
    rules = template["text"]
    overlays = []
    title = rules["title"]
    hook = next((s for s in sections if s["role"] == "hook"), None)
    if title["show_until_s"] == "hook_end":
        title_end = hook["end_frame"]
    else:
        wanted = int(round(title["show_until_s"] * fps))
        title_end = next((s["start_frame"] for s in shots if s["start_frame"] >= wanted), shots[-1]["end_frame"])
    if "time_range" not in text:
        clocks = [c for c in clips if c.clock_minutes is not None]
        if len(clocks) >= 2:
            first, last = min(clocks, key=lambda c: c.clock_minutes), max(clocks, key=lambda c: c.clock_minutes)
            text["time_range"] = f"{fmt_ampm(first.clock_minutes)} - {fmt_ampm(last.clock_minutes)}"
    for line in title["lines"]:
        value = text.get(line["field"])
        if value:
            overlays.append({"kind": "title", "role": line["role"], "text": value, "x": 0.5, "y": line["y"],
                             "reveal": line["reveal"], "start_frame": 0, "end_frame": title_end})
    if any(o["kind"] == "title" for o in overlays):
        for deco in title["decorations"]:
            overlays.append({"kind": "decoration", "role": deco["role"], "text": deco["glyph"], "x": deco["x"],
                             "y": deco["y"], "reveal": "cut", "start_frame": 0, "end_frame": title_end})

    stamps = rules["stamps"]
    if stamps["mode"] != "none":
        runs: list[list] = []
        for shot in shots:
            if shot["start_frame"] < title_end:
                continue
            clip = clips[shot["clip_index"]]
            key = clip.label if stamps["mode"] == "label" else (clip.clock, clip.label)
            if (stamps["mode"] == "label" and not clip.label) or (stamps["mode"] == "clock" and not clip.clock):
                runs.append([None, shot])
                continue
            if runs and runs[-1][0] == key and runs[-1][-1]["end_frame"] == shot["start_frame"]:
                runs[-1].append(shot)
            else:
                runs.append([key, shot])
        for key, *run in runs:
            if key is None:
                continue
            a, b = run[0]["start_frame"], run[-1]["end_frame"]
            if stamps["mode"] == "label":
                overlays.append({"kind": "stamp", "role": stamps["role"], "text": key + stamps["suffix"],
                                 "x": 0.5, "y": stamps["y"], "reveal": "cut", "start_frame": a, "end_frame": b})
            else:
                clock, label = key
                overlays.append({"kind": "stamp", "role": stamps["role"], "text": clock + stamps["suffix"],
                                 "x": 0.5, "y": stamps["y"], "reveal": "cut", "start_frame": a, "end_frame": b})
                if label:
                    overlays.append({"kind": "stamp", "role": stamps["caption_role"], "text": label, "x": 0.5,
                                     "y": stamps["y"] + 0.03, "reveal": "cut", "start_frame": a, "end_frame": b})
        if not any(o["kind"] == "stamp" for o in overlays):
            source = "labels" if stamps["mode"] == "label" else "capture times (QuickTime creationdate) or clock values"
            warnings.append(f"no stamps: the clips have no {source}")

    captions = rules["captions"]
    if captions["mode"] == "transcript":
        if args.transcript and args.voiceover:
            transcript = json.loads(args.transcript.read_text())
            limit = end_card["start_frame"] if end_card else shots[-1]["end_frame"]
            title_ys = [o["y"] for o in overlays if o["kind"] == "title"]
            for a, b, words in caption_chunks(transcript, captions["max_words"]):
                fa, fb = int(round(a * fps)), min(int(round(b * fps)), limit)
                y = captions["y"]
                if fa < title_end and any(abs(y - ty) < 0.03 for ty in title_ys):
                    y += 0.05  # the reference drops captions below the title while it is on screen
                if fb > fa:
                    overlays.append({"kind": "caption", "role": captions["role"], "text": words, "x": 0.5,
                                     "y": round(y, 3), "reveal": "cut", "start_frame": fa, "end_frame": fb})
        else:
            warnings.append("no captions: this template captions the voiceover; pass --voiceover and --transcript")

    if end_card and text.get("end_card"):
        overlays.append({"kind": "end_card", "role": template["end_card"]["text_role"], "text": text["end_card"],
                         "x": 0.5, "y": 0.5, "reveal": "cut", "start_frame": end_card["start_frame"],
                         "end_frame": end_card["end_frame"]})
    return overlays


def fmt_ampm(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    return f"{hours % 12 or 12}:{mins:02d} {'AM' if hours < 12 else 'PM'}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--template", required=True, help="Template id or path")
    parser.add_argument("--music", required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--clips", type=Path, help="Folder of clips, ordered by capture time")
    parser.add_argument("--voiceover", type=Path, help="Narration audio (narrated templates only)")
    parser.add_argument("--transcript", type=Path, help="transcript.json for the voiceover (contract format)")
    parser.add_argument("--duration", type=float, help="Target seconds, clamped to the template range")
    parser.add_argument("--music-start", choices=["first_downbeat", "most_energetic"])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = plan(args)
    except (PlanError, templates.TemplateError) as exc:
        sys.exit(f"plan failed: {exc}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(result['shots'])} shots, {result['total_frames'] / 30:.2f}s at {result['music']['tempo_bpm']} BPM, "
          f"music from {result['music']['start_s']}s, cuts on grid: {result['checks']['cuts_on_grid']}")
    for warning in result["warnings"]:
        print(f"warning: {warning}")


if __name__ == "__main__":
    main()

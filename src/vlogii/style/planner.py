"""Turn footage + music + a style template into a beat-locked style plan.

The template supplies shot lengths in seconds learned from a reference reel; the plan
snaps every cut onto the user's own beat grid, so the rhythm is imitated and the cuts
land on the music. AI (or the user) only chooses clips, order, labels and text; this
code computes every frame position.

Manifest files for the CLI (paths relative to the manifest; only "path" is required):
    {"clips": [{"path": "IMG_0001.MOV", "label": "making coffee", "in_s": 0.5, "out_s": 6,
                "clock": "08:05"}],
     "text": {"kicker": "...", "title": "...", "subtitle": "...", "time_range": "...",
              "location": "...", "end_card": "..."}}
``clock`` is 24-hour local time; without it the QuickTime creation date is used if present.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from ..storage import VlogiiError
from . import beats, media

PLAN_VERSION = 1
AUDIO_SR = 22050
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
EDGE_TRIM_S = 0.15
# Shots use at most this share of each clip, leaving gaps so cuts read as cuts.
FILL = 0.9
TEXT_FIELDS = ("kicker", "title", "subtitle", "time_range", "location", "end_card")


class PlanError(VlogiiError):
    pass


class FitError(PlanError):
    """The shots cannot be split over the clips at this length; a shorter film may fit."""


@dataclass
class ClipInput:
    """One clip chosen for the film, in edit order."""

    path: Path
    label: str | None = None
    in_s: float | None = None
    out_s: float | None = None
    clock: str | None = None
    clip_id: str | None = None
    name: str | None = None


@dataclass
class Clip:
    path: Path
    name: str
    clip_id: str | None
    color: str
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


def manifest_minutes(text: str, name: str) -> int:
    """Manifest clocks are 24-hour HH:MM so that 1:30 and 13:30 stay distinct."""
    try:
        hours, minutes = (int(part) for part in text.split(":"))
        if 0 <= hours < 24 and 0 <= minutes < 60:
            return hours * 60 + minutes
    except ValueError:
        pass
    raise PlanError(f"{name}: clock {text!r} must be 24-hour HH:MM")


def load_manifest(path: Path) -> tuple[list[ClipInput], dict]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    clips = [
        ClipInput(
            path=(base / item["path"]).resolve(),
            label=item.get("label"),
            in_s=item.get("in_s"),
            out_s=item.get("out_s"),
            clock=item.get("clock"),
        )
        for item in manifest["clips"]
    ]
    return clips, manifest.get("text", {})


def clips_from_folder(folder: Path) -> list[ClipInput]:
    """Every video in ``folder`` ordered by capture time, then name, without labels."""
    entries = []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() in VIDEO_EXTS:
            tags = media.probe(path)["tags"]
            captured = tags.get("com.apple.quicktime.creationdate") or tags.get("creation_time")
            entries.append((captured or "", path.name, path.resolve()))
    return [ClipInput(path=path) for _, _, path in sorted(entries)]


def prepare_clips(inputs: list[ClipInput]) -> list[Clip]:
    clips = []
    for item in inputs:
        name = item.name or Path(item.path).name
        info = media.probe(item.path)
        if not info["has_video"]:
            raise PlanError(f"{name}: no video stream")
        dur = info["duration_s"]
        trim = min(EDGE_TRIM_S, dur * 0.05)
        start = float(item.in_s) if item.in_s is not None else trim
        end = float(item.out_s) if item.out_s is not None else dur - trim
        if not 0 <= start < end <= dur + 1e-3:
            raise PlanError(f"{name}: in/out outside 0..{dur:.2f}s")
        if item.clock:
            minutes = manifest_minutes(item.clock, name)
        else:
            minutes = capture_minutes(info["tags"])
        clips.append(
            Clip(
                path=Path(item.path),
                name=name,
                clip_id=item.clip_id,
                color=info.get("color", "sdr"),
                usable_in=start,
                usable_out=end,
                label=item.label,
                clock=clock_text(minutes) if minutes is not None else None,
                clock_minutes=minutes,
            )
        )
    if not clips:
        raise PlanError("No clips to edit.")
    return clips


def grade_for(clip: Clip, template: dict, warmth: float) -> dict:
    """Move a clip part of the way toward the reference's measured brightness, saturation and warmth.

    ``warmth`` (0..1) is the user's "a little warmer" request on top of the template.
    """
    frames = media.read_frames(clip.path, 48, 64, fps=2).astype(np.float32) / 255
    if frames.size == 0:
        return {"brightness": 0.0, "saturation": 1.0, "warmth_shift": round(0.06 * warmth, 3)}
    r, g, b = frames[..., 0], frames[..., 1], frames[..., 2]
    luma = float((0.2126 * r + 0.7152 * g + 0.0722 * b).mean())
    cmax, cmin = frames.max(axis=-1), frames.min(axis=-1)
    sat = float(np.where(cmax > 0, (cmax - cmin) / np.maximum(cmax, 1e-6), 0).mean())
    tint = float((r - b).mean())
    target, k = template["grade"]["target"], template["grade"]["strength"]
    shift = float(np.clip((target["warmth"] - tint) * k, -0.2, 0.2)) + 0.06 * warmth
    return {
        "brightness": round(float(np.clip((target["luma"] - luma) * k, -0.15, 0.15)), 3),
        "saturation": round(
            float(np.clip((target["saturation"] / max(sat, 0.02)) ** k, 0.6, 1.5)), 3
        ),
        "warmth_shift": round(min(shift, 0.25), 3),
    }


def round_beats(seconds: float, period: float, step: float) -> float:
    return max(step, step * round(seconds / period / step))


def choose_start(
    music: dict, y: np.ndarray, policy: str, total_beats: float, music_dur: float
) -> int:
    beat_times = np.array(music["beats_s"])
    phase = music["downbeat_phase"]
    candidates = list(range(phase, beat_times.size, beats.BEATS_PER_BAR))
    grid_ok = [
        i for i in candidates if Grid(beat_times, i, 30).time(total_beats) <= music_dur - 0.05
    ]
    if not grid_ok:
        raise PlanError("The music is too short for this style.")
    if policy == "first_downbeat":
        return grid_ok[0]
    times, db = beats.level_envelope(y, AUDIO_SR)
    scores = []
    for i in grid_ok:
        a, b = beat_times[i], Grid(beat_times, i, 30).time(total_beats)
        scores.append(float(db[(times >= a) & (times < b)].mean()))
    return grid_ok[int(np.argmax(scores))]


def shot_lengths(
    grid: Grid, start: float, end: float, section: dict, rng: np.random.Generator
) -> list[float]:
    """Shot lengths in beats that fill [start, end) exactly, near the reference's shot seconds."""
    multiples = sorted(section["beat_multiples"])
    rule = section["shot"]
    lengths, pos = [], start
    while end - pos > 1e-9:
        noise = math.exp(rng.normal(0, section["variation"])) if section["variation"] else 1.0
        target = min(max(rule["target_s"] * noise, rule["min_s"]), rule["max_s"])
        inside = [
            m for m in multiples if rule["min_s"] <= grid.seconds(pos, pos + m) <= rule["max_s"]
        ]
        shortest_inside = min(inside) if inside else multiples[0]
        options = []
        for m in multiples:
            rest = end - pos - m
            if rest < -1e-9 or 1e-9 < rest < multiples[0] - 1e-9:
                continue
            length = grid.seconds(pos, pos + m)
            options.append(
                (
                    1e-9
                    < rest
                    < shortest_inside - 1e-9,  # avoid a stub shorter than the style allows
                    not rule["min_s"]
                    <= length
                    <= rule["max_s"],  # stay inside the reference's range
                    abs(length - target),
                    m,
                )
            )
        m = min(options)[-1]
        lengths.append(m)
        pos += m
    return lengths


def make_shot(grid: Grid, clip_index: int, pos: float, beats_len: float, source_in: float) -> dict:
    start_frame, end_frame = grid.frame(pos), grid.frame(pos + beats_len)
    return {
        "clip_index": clip_index,
        "source_in_s": round(source_in, 4),
        "source_out_s": round(source_in + (end_frame - start_frame) / grid.fps, 4),
        "start_frame": start_frame,
        "end_frame": end_frame,
        "beat_position": pos,
        "beats": beats_len,
    }


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
                centre = (
                    clip.usable_in + clip.usable_s * (0.75, 0.9, 0.6)[(n - 1) // len(order) % 3]
                )
                source_in = min(
                    max(clip.usable_in, centre - seconds / 2), clip.usable_out - seconds
                )
                shots.append(make_shot(grid, index, pos, m, source_in))
                break
        else:
            raise PlanError("Every clip is shorter than one opening shot.")
        pos += m
    return shots


def split_shots(seconds: list[float], capacity: np.ndarray, ideal: np.ndarray) -> list[int] | None:
    """Split shots, in order, into one non-empty run per clip that fits the clip's capacity.

    Dynamic programming finds the split closest to ``ideal`` shot counts, so a valid split
    is always found when one exists. Returns shot counts per clip, or None.
    """
    clips, shots = len(capacity), len(seconds)
    prefix = np.concatenate([[0.0], np.cumsum(seconds)])
    best = np.full((clips + 1, shots + 1), np.inf)
    choice = np.zeros((clips + 1, shots + 1), dtype=int)
    best[0, 0] = 0.0
    for k in range(clips):
        for j in range(1, shots + 1):
            i = j - 1
            while i >= 0 and prefix[j] - prefix[i] <= capacity[k] + 1e-9:
                cost = best[k, i] + (j - i - ideal[k]) ** 2
                if cost < best[k + 1, j]:
                    best[k + 1, j], choice[k + 1, j] = cost, i
                i -= 1
    if not np.isfinite(best[clips, shots]):
        return None
    counts, j = [], shots
    for k in range(clips, 0, -1):
        i = choice[k, j]
        counts.append(j - i)
        j = i
    return counts[::-1]


def place_body(
    grid: Grid, start: float, lengths: list[float], clips: list[Clip], warnings: list[str]
) -> list[dict]:
    """Keep clip order; give each clip consecutive shots in proportion to its length."""
    indices = list(range(len(clips)))
    if len(clips) > len(lengths):
        indices = sorted(
            {
                int(round(i * (len(clips) - 1) / max(len(lengths) - 1, 1)))
                for i in range(len(lengths))
            }
        )
        skipped = [clips[i].name for i in range(len(clips)) if i not in indices]
        warnings.append(f"Not enough time for every clip; skipped {', '.join(skipped)}.")
    usable = np.array([clips[i].usable_s for i in indices])
    positions = np.cumsum([start] + lengths[:-1])
    seconds = [grid.seconds(p, p + m) for p, m in zip(positions, lengths, strict=True)]
    counts = split_shots(seconds, FILL * usable, len(lengths) * usable / usable.sum())
    if counts is None:
        raise FitError("The footage is too short to fill the film without repeating frames.")

    shots, pos, n = [], start, 0
    for k, count in zip(indices, counts, strict=True):
        clip = clips[k]
        spans = seconds[n : n + count]
        gap = max(0.0, clip.usable_s - sum(spans)) / count
        cursor = clip.usable_in + gap / 2
        for m, span in zip(lengths[n : n + count], spans, strict=True):
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
            words = [
                {
                    "text": w,
                    "in_seconds": sentence["in_seconds"] + i * step,
                    "out_seconds": sentence["in_seconds"] + (i + 1) * step,
                }
                for i, w in enumerate(tokens)
            ]
        for i in range(0, len(words), max_words):
            group = words[i : i + max_words]
            chunks.append(
                (
                    group[0]["in_seconds"],
                    group[-1]["out_seconds"],
                    " ".join(w["text"] for w in group),
                )
            )
    return chunks


def output_for(template: dict, size: tuple[int, int] | None) -> dict:
    """Template output, or the project's size when it has the same orientation."""
    out = dict(template["output"])
    if size:
        width, height = size
        if (height > width) != (out["height"] > out["width"]):
            orientation = "portrait" if out["height"] > out["width"] else "landscape"
            raise PlanError(f"This style is {orientation}. Create a {orientation} project.")
        if width % 2 or height % 2:
            raise PlanError("Output dimensions must be even.")
        out.update(width=width, height=height)
    return out


def lay_out(grid, sections, fixed, body_beats, clips, rng, warnings):
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
        section_rows.append(
            {
                "role": section["role"],
                "start_frame": grid.frame(start),
                "end_frame": grid.frame(end),
                "beats": beats_here,
            }
        )
        pos = end
    return shots, section_rows, pos


def plan(
    template: dict,
    music_path: Path,
    inputs: list[ClipInput],
    text: dict | None = None,
    *,
    size: tuple[int, int] | None = None,
    voiceover: Path | None = None,
    transcript: dict | None = None,
    duration: float | None = None,
    music_start: str | None = None,
    warmth: float = 0.0,
) -> dict:
    output = output_for(template, size)
    fps = output["fps"]
    warnings: list[str] = []
    clips = prepare_clips(inputs)
    given = {k: v for k, v in (text or {}).items() if k in TEXT_FIELDS and v}
    text = {**template["text"]["defaults"], **given}

    y = media.read_audio(music_path, AUDIO_SR)
    music_dur = y.size / AUDIO_SR
    if music_dur < 5:
        raise PlanError("The music track is shorter than five seconds.")
    music = beats.analyze_music(y, AUDIO_SR)
    beat_times = np.array(music["beats_s"])
    if beat_times.size < 16:
        raise PlanError("Could not find a steady beat in the music.")
    if music["beat_interval_cv"] and music["beat_interval_cv"] > 0.1:
        warnings.append("The beat grid is irregular; listen to the cuts.")
    if music["downbeat_confidence"] < 0.1:
        warnings.append("Weak downbeat estimate; sections may change on beat 2 or 3, not beat 1.")
    period = float(np.median(np.diff(beat_times)))

    sections = template["sections"]
    fixed = {s["role"]: round_beats(s["length_s"], period, 2.0) for s in sections if s["length_s"]}
    end_card_beats = (
        round_beats(template["end_card"]["length_s"], period, 2.0) if template["end_card"] else 0.0
    )
    dur = template["duration"]
    target_s = min(max(duration or dur["target_s"], dur["min_s"]), dur["max_s"])
    body_rule = next(s for s in sections if s["role"] == "body")
    material = FILL * sum(c.usable_s for c in clips)
    body_target_s = max(target_s - (sum(fixed.values()) + end_card_beats) * period, 0)
    if len(clips) * body_rule["shot"]["target_s"] > body_target_s:
        grown = min(
            dur["max_s"], target_s + len(clips) * body_rule["shot"]["target_s"] - body_target_s
        )
        if grown > target_s:
            warnings.append(
                f"Length raised from {target_s:.1f}s to {grown:.1f}s so every clip gets a shot."
            )
            target_s = grown

    def total_for(seconds: float) -> float:
        return round_beats(seconds, period, beats.BEATS_PER_BAR)

    total_beats = total_for(target_s)
    min_beats = total_for(dur["min_s"])
    first_downbeat = beat_times[music["downbeat_phase"]]
    music_beats = beats.BEATS_PER_BAR * math.floor(
        (music_dur - 0.05 - first_downbeat) / period / beats.BEATS_PER_BAR
    )
    if music_beats < total_beats:
        if music_beats < min_beats:
            raise PlanError(
                f"The music is {music_dur:.1f}s; this style needs at least {dur['min_s']}s "
                "after the first downbeat."
            )
        warnings.append(f"Shortened to {music_beats * period:.1f}s to fit the music.")
        total_beats = music_beats
    body_beats = total_beats - sum(fixed.values()) - end_card_beats
    music_limited = total_beats
    while body_beats * period > material and total_beats > min_beats:
        total_beats -= beats.BEATS_PER_BAR
        body_beats = total_beats - sum(fixed.values()) - end_card_beats
    if body_beats * period > material:
        raise PlanError(
            f"Not enough footage: this style needs {body_beats * period / FILL:.1f}s, "
            f"the selected clips give {material / FILL:.1f}s."
        )
    if total_beats < music_limited:
        warnings.append(f"Shortened to {total_beats * period:.1f}s because the footage runs out.")

    seed = sum(map(ord, template["id"]))
    fitted = total_beats
    while True:
        start_index = choose_start(
            music, y, music_start or template["music"]["start"], total_beats, music_dur
        )
        grid = Grid(beat_times, start_index, fps)
        attempt_warnings: list[str] = []
        try:
            shots, section_rows, pos = lay_out(
                grid,
                sections,
                fixed,
                body_beats,
                clips,
                np.random.default_rng(seed),
                attempt_warnings,
            )
            break
        except FitError:
            # Beat-length shots leave unusable remainders in short clips; try one bar less.
            if total_beats - beats.BEATS_PER_BAR < min_beats:
                raise
            total_beats -= beats.BEATS_PER_BAR
            body_beats -= beats.BEATS_PER_BAR
    warnings += attempt_warnings
    if total_beats < fitted:
        warnings.append(f"Shortened to {total_beats * period:.1f}s so every shot fits its clip.")
    for i in sorted({shot["clip_index"] for shot in shots}):
        clips[i].grade = grade_for(clips[i], template, warmth)

    end_card = None
    if template["end_card"]:
        end_card = {
            "start_frame": grid.frame(pos),
            "end_frame": grid.frame(pos + end_card_beats),
            "background": template["end_card"]["background"],
        }
        pos += end_card_beats
    total_frames = grid.frame(pos)

    voice = None
    if voiceover:
        if not template["voiceover"]["supported"]:
            raise PlanError("This style has no voiceover mix; pick a narrated style.")
        voice_dur = media.probe(voiceover)["duration_s"]
        if voice_dur > total_frames / fps:
            warnings.append(
                f"The voiceover is {voice_dur:.1f}s but the film is {total_frames / fps:.1f}s; "
                "it will be cut."
            )
        voice = {
            "path": str(Path(voiceover).resolve()),
            "start_s": 0.0,
            "target_lufs": template["voiceover"]["target_lufs"],
            "music_duck_db": template["voiceover"]["music_duck_db"],
        }

    overlays = build_overlays(
        template, text, clips, shots, section_rows, end_card, fps, warnings, transcript, voice
    )
    cut_error = max(
        abs(s["start_frame"] / fps - (grid.time(s["beat_position"]) - grid.time(0))) for s in shots
    )
    for index, shot in enumerate(shots):
        clip = clips[shot.pop("clip_index")]
        shot.update(
            index=index,
            clip=str(clip.path),
            clip_id=clip.clip_id,
            clip_name=clip.name,
            color=clip.color,
            label=clip.label,
            grade=clip.grade,
        )

    return {
        "plan_version": PLAN_VERSION,
        "template": {"id": template["id"], "revision": template["revision"]},
        "output": output,
        "total_frames": total_frames,
        "music": {
            "path": str(Path(music_path).resolve()),
            "start_s": round(grid.time(0), 4),
            "duration_s": round(total_frames / fps, 4),
            "tempo_bpm": music["tempo_bpm"],
            "beat_period_s": round(period, 4),
            "downbeat_confidence": music["downbeat_confidence"],
            "fade_in_s": template["music"]["fade_in_s"],
            "fade_out_s": template["music"]["fade_out_s"],
            "target_lufs": template["music"]["target_lufs"],
            "true_peak_dbtp": template["music"]["true_peak_dbtp"],
            "beat_grid_s": [
                round(grid.time(b) - grid.time(0), 4) for b in np.arange(0, pos + 1e-9, 1.0)
            ],
        },
        "voiceover": voice,
        "sections": section_rows,
        "shots": shots,
        "end_card": end_card,
        "overlays": overlays,
        "text": text,
        "checks": {
            "shots": len(shots),
            "max_cut_offset_from_grid_s": round(cut_error, 4),
            "cuts_on_grid": cut_error <= 0.5 / fps + 1e-6,
        },
        "warnings": warnings,
    }


def build_overlays(
    template, text, clips, shots, sections, end_card, fps, warnings, transcript, voice
) -> list[dict]:
    rules = template["text"]
    overlays = []
    title = rules["title"]
    if title["show_until_s"] == "hook_end":
        title_end = next(s for s in sections if s["role"] == "hook")["end_frame"]
    else:
        wanted = int(round(title["show_until_s"] * fps))
        title_end = next(
            (s["start_frame"] for s in shots if s["start_frame"] >= wanted), shots[-1]["end_frame"]
        )
    if "time_range" not in text:
        clocks = [c for c in clips if c.clock_minutes is not None]
        if len(clocks) >= 2:
            first = min(clocks, key=lambda c: c.clock_minutes)
            last = max(clocks, key=lambda c: c.clock_minutes)
            text["time_range"] = f"{fmt_ampm(first.clock_minutes)} - {fmt_ampm(last.clock_minutes)}"

    def add(kind, role, value, y, start, end, x=0.5, reveal="cut"):
        overlays.append(
            {
                "kind": kind,
                "role": role,
                "text": value,
                "x": x,
                "y": round(y, 3),
                "reveal": reveal,
                "start_frame": start,
                "end_frame": end,
            }
        )

    for line in title["lines"]:
        if value := text.get(line["field"]):
            add("title", line["role"], value, line["y"], 0, title_end, reveal=line["reveal"])
    if any(o["kind"] == "title" for o in overlays):
        for deco in title["decorations"]:
            add("decoration", deco["role"], deco["glyph"], deco["y"], 0, title_end, x=deco["x"])

    stamps = rules["stamps"]
    if stamps["mode"] != "none":
        runs: list[list] = []
        for shot in shots:
            if shot["start_frame"] < title_end:
                continue
            clip = clips[shot["clip_index"]]
            key = clip.label if stamps["mode"] == "label" else (clip.clock, clip.label)
            missing = not clip.label if stamps["mode"] == "label" else not clip.clock
            if missing:
                runs.append([None, shot])
            elif runs and runs[-1][0] == key and runs[-1][-1]["end_frame"] == shot["start_frame"]:
                runs[-1].append(shot)
            else:
                runs.append([key, shot])
        for key, *run in runs:
            if key is None:
                continue
            a, b = run[0]["start_frame"], run[-1]["end_frame"]
            if stamps["mode"] == "label":
                add("stamp", stamps["role"], key + stamps["suffix"], stamps["y"], a, b)
            else:
                clock, label = key
                add("stamp", stamps["role"], clock + stamps["suffix"], stamps["y"], a, b)
                if label:
                    add("stamp", stamps["caption_role"], label, stamps["y"] + 0.03, a, b)
        if not any(o["kind"] == "stamp" for o in overlays):
            source = "labels" if stamps["mode"] == "label" else "capture times or clock values"
            warnings.append(f"No stamps: the clips have no {source}.")

    captions = rules["captions"]
    if captions["mode"] == "transcript":
        if transcript and voice:
            title_ys = [o["y"] for o in overlays if o["kind"] == "title"]
            limit = end_card["start_frame"] if end_card else shots[-1]["end_frame"]
            for a, b, words in caption_chunks(transcript, captions["max_words"]):
                fa, fb = int(round(a * fps)), min(int(round(b * fps)), limit)
                y = captions["y"]
                if fa < title_end and any(abs(y - ty) < 0.03 for ty in title_ys):
                    y += 0.05  # the reference drops captions below the title while it is on screen
                if fb > fa:
                    add("caption", captions["role"], words, y, fa, fb)
        else:
            warnings.append("No captions: this style captions a voiceover with its transcript.")

    if end_card and text.get("end_card"):
        add(
            "end_card",
            template["end_card"]["text_role"],
            text["end_card"],
            0.5,
            end_card["start_frame"],
            end_card["end_frame"],
        )
    return overlays


def fmt_ampm(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    return f"{hours % 12 or 12}:{mins:02d} {'AM' if hours < 12 else 'PM'}"

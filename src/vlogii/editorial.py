"""Editing intent and frame-accurate changes to a validated plan."""

import math
import re

from pydantic import ValidationError

from .media import Tools
from .models import Plan, Project, Review, Segment, Selection, SpeedRange, Text, TimeRange
from .storage import VlogiiError, read_json, write_json
from .timeline import compile_timeline


def selection_intent(
    direction: str, mode="auto", target=None, remove_no_speech=False, speed=1, shot_seconds=0.5
) -> Selection:
    """Explicit controls take precedence; recognize common bilingual retention requests."""
    text = direction.lower()
    no_speech = remove_no_speech or bool(
        re.search(
            r"(?:删|去|不要).*(?:没有语音|无语音)|(?:没有语音|无语音).*(?:删|去|不要)|remove.*no speech",
            text,
        )
    )
    if mode == "auto":
        if re.search(r"全部保留|完整保留|全保留|不剪|keep (?:it )?all|full (?:video|length)", text):
            mode = "keep_all"
        elif re.search(r"大部分保留|保留大部分|keep most", text):
            mode = "keep_most"
        elif re.search(r"快剪|精华|highlight|opening montage|fast montage", text):
            mode = "highlights"
        elif no_speech:
            mode = "keep_most"
    if target is None and mode not in {"keep_all", "keep_most"}:
        # Do not infer duration from a requested deletion range.
        if not re.search(r"删除|删掉|去掉|remove|delete", text):
            duration = re.search(
                r"(?:(\d+(?:\.\d+)?)\s*(?:分钟|分|minutes?|mins?))"
                r"(?:\s*(\d+(?:\.\d+)?)\s*(?:秒钟|秒|seconds?|secs?))?"
                r"|(\d+(?:\.\d+)?)\s*(?:秒钟|秒|seconds?|secs?)",
                text,
            )
            if duration:
                minutes, seconds, seconds_only = duration.groups()
                target = float(minutes or 0) * 60 + float(seconds or seconds_only or 0)
    result = Selection(
        mode=mode,
        speed=speed,
        shot_seconds=shot_seconds,
        target_seconds=target,
        remove_no_speech=no_speech if mode == "keep_most" else False,
    )
    if mode in {"keep_all", "keep_most"} and target is not None:
        raise VlogiiError(
            "Retention modes have no target duration. Clear the target or choose AI auto/highlights."
        )
    return result


def merge_ranges(ranges):
    merged = []
    for start, end in sorted(ranges):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def subtract_ranges(start, end, removed):
    cursor = start
    kept = []
    for left, right in merge_ranges(removed):
        if right <= cursor or left >= end:
            continue
        if left > cursor:
            kept.append((cursor, min(left, end)))
        cursor = max(cursor, right)
    if cursor < end:
        kept.append((cursor, end))
    return kept


def retention_plan(project: Project, reviews: list[Review], selection: Selection, black):
    review_map = {r.clip_id: r for r in reviews}
    segments = []
    for clip in project.clips:
        removed = []
        if selection.mode == "keep_most":
            removed.extend(black.get(clip.id, []))
            speech = review_map[clip.id].speech
            if speech or selection.remove_no_speech:
                # Retain a small natural lead-in/out; trim pauses of at least 3 seconds.
                spoken = merge_ranges(
                    (max(0, s.start - 0.35), min(clip.duration, s.end + 0.35)) for s in speech
                )
                gaps = subtract_ranges(0, clip.duration, spoken)
                removed.extend((a, b) for a, b in gaps if selection.remove_no_speech or b - a >= 3)
        for start, end in subtract_ranges(0, clip.duration, removed):
            if round(end * project.settings.fps) > round(start * project.settings.fps):
                segments.append(
                    Segment(clip_id=clip.id, in_sec=start, out_sec=end, purpose="Preserved source")
                )
    if not segments:
        raise VlogiiError(
            "Nothing remains after removing black/no-speech ranges. Choose keep_all or AI auto."
        )
    return Plan(
        title=project.name,
        reasoning=(
            "All imported footage in import order; only explicit subsequent edits remove frames."
            if selection.mode == "keep_all"
            else "Import order, black intervals and long speech pauses removed; silent scenery retained unless explicitly excluded."
        ),
        segments=segments,
    )


def black_ranges(directory, clip):
    path = directory / "quality" / f"{clip.id}.json"
    fingerprint = {"sha256": clip.sha256, "revision": 1}
    if path.exists():
        data = read_json(path)
        if data.get("fingerprint") == fingerprint:
            return [tuple(r) for r in data["black"]]
    tools = Tools()
    proxy = directory / "proxies" / f"{clip.id}.mp4"
    result = tools.run(
        [
            "-i",
            str(proxy if proxy.exists() else clip.path),
            "-an",
            "-vf",
            "scale=160:160:force_original_aspect_ratio=decrease,blackdetect=d=0.3:pix_th=0.1:pic_th=0.98",
            "-f",
            "null",
            "-",
        ],
        directory / "quality" / f"{clip.id}.log",
    )
    ranges = []
    for start, end in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", result.stderr):
        left, right = max(0, float(start)), min(clip.duration, float(end))
        if math.isfinite(left) and math.isfinite(right) and right > left:
            ranges.append((left, right))
    write_json(path, {"fingerprint": fingerprint, "black": ranges})
    return ranges


TIME = r"(?:\d+:\d{2}(?::\d{2})?(?:\.\d+)?|\d+(?:\.\d+)?\s*分(?:\s*\d+(?:\.\d+)?\s*秒)?|\d+(?:\.\d+)?\s*秒|\d+(?:\.\d+)?)"
RANGE = re.compile(rf"(?P<start>{TIME})\s*(?:到|至|to|[-–—~～])\s*(?P<end>{TIME})", re.I)


def timestamp(value):
    value = value.strip()
    if ":" in value:
        parts = value.split(":")
        if any(float(p) >= 60 for p in parts[1:]):
            raise VlogiiError("Use valid timestamps such as 01:12 or 1分12秒.")
        return sum(float(part) * 60**index for index, part in enumerate(reversed(parts)))
    if "分" in value:
        minute, _, rest = value.partition("分")
        return float(minute.strip()) * 60 + float(rest.replace("秒", "").strip() or 0)
    return float(value.replace("秒", "").strip())


def parse_remove_ranges(text: str) -> list[TimeRange]:
    if not text.strip():
        return []
    matches = list(RANGE.finditer(text))
    remainder = RANGE.sub("", text.lower())
    remainder = re.sub(
        r"删掉|删除|去掉|移除|这段|这部分|的部分|不用|不要|成片|视频|和|以及|并|"
        r"\b(?:remove|delete|cut|out|from|the|video|and|then)\b|[\s,，;；。.!！]",
        "",
        remainder,
    )
    if not matches or remainder:
        raise VlogiiError(
            "Time edits support deletion ranges only, e.g. 删掉 00:12 到 00:18, 01:00-01:08. Other requests need generation controls."
        )
    if len(matches) > 50:
        raise VlogiiError("Choose at most 50 removal ranges.")
    try:
        return [TimeRange(start=timestamp(m["start"]), end=timestamp(m["end"])) for m in matches]
    except ValidationError as exc:
        raise VlogiiError("Time ranges need nonnegative start and end greater than start.") from exc


def parse_edit_instruction(text: str) -> tuple[list[TimeRange], list[SpeedRange]]:
    """Accept complete deletion/speed clauses; reject unsupported leftovers."""
    removed, sped = [], []
    if not text.strip():
        return removed, sped
    if not re.search(r"倍|[x×]|speed|faster|slower", text, re.I):
        return parse_remove_ranges(text), sped
    for clause in re.split(r"[;；,，]|\band\b|并且|然后", text, flags=re.I):
        if not clause.strip():
            continue
        if not re.search(r"倍|[x×]|speed|faster|slower", clause, re.I):
            removed.extend(parse_remove_ranges(clause))
            continue
        intervals = list(RANGE.finditer(clause))
        remainder = RANGE.sub("", clause.lower())
        factors = list(re.finditer(r"(\d+(?:\.\d+)?)\s*(?:倍(?:速)?|[x×])", remainder))
        if len(intervals) != 1 or len(factors) != 1:
            raise VlogiiError(
                "Speed edits need one time range and a rate, e.g. 00:12到00:18加速到2倍."
            )
        factor = float(factors[0][1])
        remainder = remainder[: factors[0].start()] + remainder[factors[0].end() :]
        remainder = re.sub(
            r"加快速度|加快|加速|减速|放慢|速度|调整为|设为|设置为|改为|到|用|以|播放|这段|这部分|的部分|成片|视频|把|将|\b(?:speed|up|slow|down|from|to|at|set|the|video|faster|slower)\b|[\s。.!！]",
            "",
            remainder,
        )
        if remainder:
            raise VlogiiError(
                "Time edits support deletion ranges or explicit speeds only. Other requests need generation controls."
            )
        match = intervals[0]
        try:
            sped.append(
                SpeedRange(
                    start=timestamp(match["start"]), end=timestamp(match["end"]), speed=factor
                )
            )
        except ValidationError as exc:
            raise VlogiiError("Use an ordered time range and a speed between 0.25 and 8.") from exc
    if len(removed) + len(sped) > 50:
        raise VlogiiError("Choose at most 50 time edits.")
    return removed, sped


def transform_output_ranges(
    project: Project,
    plan: Plan,
    ranges: list[TimeRange],
    speed_ranges: list[SpeedRange] | None = None,
    speed=None,
) -> Plan:
    """All coordinates use the original current film. Rates are absolute, not multipliers."""
    speed_ranges = [SpeedRange.model_validate(r) for r in speed_ranges or []]
    if speed is not None:
        speed = Selection(speed=speed).speed
    if not ranges and not speed_ranges and speed is None:
        return plan
    timeline = compile_timeline(project, plan, [])
    fps = timeline.fps

    def frame_range(item):
        start, end = round(item.start * fps), round(item.end * fps)
        if (
            item.end > timeline.total_frames / fps + 0.001
            or end > timeline.total_frames
            or start < 0
            or end <= start
        ):
            raise VlogiiError(
                f"Time ranges must be within the current film (0–{timeline.total_frames / fps:.3f}s) and span at least one frame."
            )
        return start, end

    removed = [frame_range(item) for item in ranges]
    sped = sorted((*frame_range(item), item.speed) for item in speed_ranges)
    if any(a[1] > b[0] for a, b in zip(sped, sped[1:], strict=False)):
        raise VlogiiError("Speed ranges must not overlap. Combine them or choose separate ranges.")
    segments = []
    for original, compiled in zip(plan.segments, timeline.segments, strict=True):
        boundaries = {compiled.start, compiled.start + compiled.frames}
        for left, right in removed + [(a, b) for a, b, _ in sped]:
            boundaries.update(
                point
                for point in (left, right)
                if compiled.start < point < compiled.start + compiled.frames
            )
        ordered = sorted(boundaries)
        for start, end in zip(ordered, ordered[1:], strict=False):
            if any(a <= start < b for a, b in removed):
                continue
            source_left = round((start - compiled.start) * compiled.source_frames / compiled.frames)
            source_right = round((end - compiled.start) * compiled.source_frames / compiled.frames)
            if source_right <= source_left:
                raise VlogiiError(
                    "Time edit is shorter than one source frame. Choose a wider range."
                )
            left, right = source_left / fps, source_right / fps
            rate = next(
                (rate for a, b, rate in sped if a <= start < b),
                speed if speed is not None else original.speed,
            )
            overlays = [
                Text(start=max(t.start, left) - left, end=min(t.end, right) - left, text=t.text)
                for t in original.overlays
                if min(t.end, right) > max(t.start, left)
            ]
            segments.append(
                Segment(
                    clip_id=original.clip_id,
                    in_sec=(compiled.source_start + source_left) / fps,
                    out_sec=(compiled.source_start + source_right) / fps,
                    purpose=original.purpose,
                    speed=rate,
                    overlays=overlays,
                )
            )
    if not segments:
        raise VlogiiError("Keep at least one frame. Removal ranges cover the entire film.")
    result = Plan.model_validate(plan.model_copy(update={"segments": segments}).model_dump())
    compile_timeline(project, result, [])
    return result


def remove_output_ranges(project: Project, plan: Plan, ranges: list[TimeRange]) -> Plan:
    return transform_output_ranges(project, plan, ranges)

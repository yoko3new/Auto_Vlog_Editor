"""Resolve chapter-relative refinement into validated current-film ranges."""

import re

from .editorial import parse_edit_instruction
from .models import Chapter, ChapterEdit, SpeedRange, TimeRange
from .storage import VlogiiError


def chapter_ranges(chapters: list[Chapter], edits: list[ChapterEdit]):
    removed, sped = [], []
    for item in edits:
        item = ChapterEdit.model_validate(item)
        if item.chapter_index >= len(chapters):
            raise VlogiiError(
                "Time edit refers to a chapter that no longer exists. Refresh the film."
            )
        chapter = chapters[item.chapter_index]
        if chapter.kind == "cover":
            raise VlogiiError("Edit the opening cover in the cover editor.")
        duration = chapter.end - chapter.start

        def absolute(interval, chapter=chapter, duration=duration):
            if interval.start < 0 or interval.end > duration + 0.000001:
                raise VlogiiError(f"Time range must stay inside this chapter (0–{duration:.3f}s).")
            return interval.model_copy(
                update={
                    "start": chapter.start + interval.start,
                    "end": min(chapter.end, chapter.start + interval.end),
                }
            )

        if item.action == "remove":
            removed.append(TimeRange(start=chapter.start, end=chapter.end))
        elif item.action == "remove_range":
            removed.append(absolute(TimeRange(start=item.start, end=item.end)))
        elif item.action == "speed":
            sped.append(
                absolute(
                    SpeedRange(
                        start=item.start or 0,
                        end=duration if item.end is None else item.end,
                        speed=item.speed,
                    )
                )
            )
        else:
            before = len(removed) + len(sped)
            # Whole-chapter shortcuts have a known target; other clauses use the existing parser.
            for clause in re.split(r"[;；]", item.instruction):
                text = clause.strip().rstrip("。.!！").strip()
                if not text:
                    continue
                if re.fullmatch(
                    r"(?:删除|删掉|去掉|移除)(?:整段|这一段|这段|整个片段)|(?:delete|remove) (?:(?:this|the) )?(?:whole |entire )?(?:clip|scene|chapter|segment|this segment)",
                    text,
                    re.I,
                ):
                    removed.append(TimeRange(start=chapter.start, end=chapter.end))
                    continue
                whole_speed = re.fullmatch(
                    r"(?:(?:这段|整段|整个片段)?(?:加速|减速|放慢|调速|调整速度|速度)(?:到|为|成)?|(?:speed(?: up)?|slow(?: down)?|set speed)(?: (?:to|at))?\s*)\s*(\d+(?:\.\d+)?)\s*(?:倍(?:速)?|[x×])",
                    text,
                    re.I,
                )
                if whole_speed:
                    rate = float(whole_speed[1])
                    if not 0.25 <= rate <= 8:
                        raise VlogiiError(
                            "Use an ordered time range and a speed between 0.25 and 8."
                        )
                    sped.append(SpeedRange(start=chapter.start, end=chapter.end, speed=rate))
                    continue
                text = re.sub(r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b", r"\1", text, flags=re.I)
                try:
                    local_removed, local_sped = parse_edit_instruction(text)
                except VlogiiError as exc:
                    if "Other requests need generation controls" in str(exc):
                        raise VlogiiError(
                            "Time edits support deletion ranges or explicit speeds only. Other requests need generation controls."
                        ) from exc
                    raise
                removed.extend(absolute(interval) for interval in local_removed)
                sped.extend(absolute(interval) for interval in local_sped)
            if len(removed) + len(sped) == before:
                raise VlogiiError("Choose at least one change.")
    if len(removed) + len(sped) > 50:
        raise VlogiiError("Time edits are limited to 50 operations per version.")
    return removed, sped

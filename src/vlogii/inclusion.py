"""Clip inclusion without losing recoverable scenes or current-film time coordinates."""

from .editorial import transform_output_ranges
from .models import Plan, Project, SpeedRange, TimeRange
from .storage import VlogiiError
from .timeline import compile_timeline


def included_ids(project: Project) -> list[str]:
    return (
        project.included_clip_ids
        if project.included_clip_ids is not None
        else [c.id for c in project.clips]
    )


def set_included(project: Project, ids: list[str] | None, excluded=()):
    selected = included_ids(project) if ids is None else ids
    if set(excluded) - {c.id for c in project.clips}:
        raise VlogiiError("An excluded clip is not part of this project.")
    selected = [identifier for identifier in selected if identifier not in excluded]
    if not selected:
        raise VlogiiError("Keep at least one selected clip.")
    if len(set(selected)) != len(selected) or set(selected) - {c.id for c in project.clips}:
        raise VlogiiError("Choose unique clips from this project.")
    # Import order, rather than checkbox click order, defines retention order.
    project.included_clip_ids = [c.id for c in project.clips if c.id in selected]


def selected_project(project: Project) -> Project:
    ids = included_ids(project)
    return project.model_copy(update={"clips": [c for c in project.clips if c.id in ids]})


def visible_plan(plan: Plan, ids: list[str]) -> Plan:
    segments = [s for s in plan.segments if s.clip_id in ids]
    if not segments:
        raise VlogiiError("Keep at least one selected clip.")
    return plan.model_copy(deep=True, update={"segments": segments})


def edit_recoverable(project, full, ids, ranges, sped, speed):
    """Validate against the visible cut, then translate edits across hidden scenes."""
    visible = visible_plan(full, ids)
    if not ranges and not sped:
        return transform_output_ranges(project, full, [], speed=speed)
    # This validates bounds, frame spans and overlapping speeds before mapping.
    transform_output_ranges(project, visible, ranges, sped)
    timeline = compile_timeline(project, full, [])
    fps = timeline.fps
    translated_removed, translated_sped = [], []
    visible_start = 0
    for segment in timeline.segments:
        if segment.clip_id not in ids:
            continue
        for items, destination, model in (
            (ranges, translated_removed, TimeRange),
            (sped, translated_sped, SpeedRange),
        ):
            for item in items:
                left = max(round(item.start * fps), visible_start)
                right = min(round(item.end * fps), visible_start + segment.frames)
                if right > left:
                    destination.append(
                        model(
                            start=(segment.start + left - visible_start) / fps,
                            end=(segment.start + right - visible_start) / fps,
                            **({"speed": item.speed} if model is SpeedRange else {}),
                        )
                    )
        visible_start += segment.frames
    return transform_output_ranges(project, full, translated_removed, translated_sped, speed)

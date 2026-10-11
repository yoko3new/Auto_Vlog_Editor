"""Chapters derived from the successful timeline and existing analysis, without new AI calls."""

from pathlib import Path

from .cover import intro_seconds
from .models import Chapter, Project, Review
from .storage import read_json


def version_chapters(version: Path, reviews: list[Review]) -> list[Chapter]:
    if not (version / "project.json").exists():
        return []
    project = Project.model_validate(read_json(version / "project.json"))
    clips = {c.id: c for c in project.clips}
    analysis = {r.clip_id: r for r in reviews}
    rows = []
    if (version / "timeline.json").exists():
        timeline = read_json(version / "timeline.json")
        fps = timeline["fps"]
        for s in timeline["segments"]:
            review = analysis.get(s["clip_id"])
            start = s["source_start"] / fps
            end = start + s["source_frames"] / fps
            details = (
                [h.text for h in review.highlights if h.end > start and h.start < end]
                if review
                else []
            )
            # Speech is useful content where no scene analysis was requested.
            if not details and review:
                details = [h.text for h in review.speech if h.end > start and h.start < end]
            description = " · ".join(dict.fromkeys(details)) or (review.summary if review else "")
            rows.append(
                Chapter(
                    start=s["start"] / fps,
                    end=(s["start"] + s["frames"]) / fps,
                    title=s["purpose"],
                    summary=description or Path(clips[s["clip_id"]].path).name,
                    clip_ids=[s["clip_id"]],
                    kind="hook" if s.get("mute_source_audio") else "scene",
                )
            )
    elif (version / "style-plan.json").exists():
        plan = read_json(version / "style-plan.json")
        fps = plan["output"]["fps"]
        for s in plan["shots"]:
            review = analysis.get(s.get("clip_id"))
            rows.append(
                Chapter(
                    start=s["start_frame"] / fps,
                    end=s["end_frame"] / fps,
                    title=s.get("label") or s.get("clip_name") or "Scene",
                    summary=review.summary if review else s.get("clip_name") or "",
                    clip_ids=[s["clip_id"]] if s.get("clip_id") else [],
                    kind=s.get("section", "body"),
                )
            )
        card = plan.get("end_card")
        if card:
            rows.append(
                Chapter(
                    start=card["start_frame"] / fps,
                    end=card["end_frame"] / fps,
                    title="End card",
                    summary=card.get("text", ""),
                    kind="end_card",
                )
            )
    # Adjacent shots of the same identified scene form one chapter; hook/body stay separate.
    merged = []
    for row in rows:
        if (
            merged
            and merged[-1].clip_ids == row.clip_ids
            and merged[-1].title == row.title
            and merged[-1].kind == row.kind
            and abs(merged[-1].end - row.start) < 1e-6
        ):
            merged[-1].end = row.end
        else:
            merged.append(row)
    offset = intro_seconds(version)
    if offset:
        for chapter in merged:
            chapter.start += offset
            chapter.end += offset
        metadata = read_json(version / "cover.json")["settings"]
        merged.insert(
            0,
            Chapter(
                start=0,
                end=offset,
                title=metadata["title"],
                summary=metadata["subtitle"],
                kind="cover",
            ),
        )
    return merged

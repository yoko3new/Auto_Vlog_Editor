"""Validate AI decisions and compute all output timing in integer frames."""

from .models import Plan, Project, Review, Text, Timeline, TimelineSegment
from .storage import VlogiiError


def compile_timeline(project: Project, plan: Plan, reviews: list[Review]) -> Timeline:
    clips = {clip.id: clip for clip in project.clips}
    review_map = {review.clip_id: review for review in reviews}
    fps = project.settings.fps
    segments = []
    cursor = 0
    for index, segment in enumerate(plan.segments):
        clip = clips.get(segment.clip_id)
        if clip is None:
            raise VlogiiError(f"Segment {index} references an unknown clip: {segment.clip_id}")
        if segment.out_sec > clip.duration + 0.001:
            raise VlogiiError(f"Segment {index} extends beyond its source clip.")
        start = round(segment.in_sec * fps)
        end = round(segment.out_sec * fps)
        if end <= start or end > round(clip.duration * fps):
            raise VlogiiError(f"Segment {index} has an invalid frame range.")
        source_frames = end - start
        frames = round(source_frames / segment.speed)
        if frames < 1:
            raise VlogiiError(f"Segment {index} is shorter than one output frame at this speed.")
        effective_speed = source_frames / frames
        duration = source_frames / fps
        for overlay in segment.overlays:
            if overlay.end > duration + 0.001:
                raise VlogiiError(f"Overlay in segment {index} extends beyond its segment.")
        captions = []
        review = review_map.get(clip.id) if plan.captions else None
        for speech in review.speech if review else []:
            if speech.end > clip.duration + 0.001:
                raise VlogiiError(f"Transcript extends beyond clip {clip.id}.")
            left = max(speech.start, start / fps)
            right = min(speech.end, end / fps)
            if right > left:
                captions.append(
                    Text(
                        start=(left - start / fps) / effective_speed,
                        end=(right - start / fps) / effective_speed,
                        text=speech.text,
                    )
                )
        segments.append(
            TimelineSegment(
                clip_id=clip.id,
                source_start=start,
                source_frames=source_frames,
                speed=segment.speed,
                start=cursor,
                frames=frames,
                purpose=segment.purpose,
                overlays=[
                    Text(start=t.start / effective_speed, end=t.end / effective_speed, text=t.text)
                    for t in segment.overlays
                ],
                captions=captions,
            )
        )
        cursor += frames
    return Timeline(title=plan.title, fps=fps, total_frames=cursor, segments=segments)


def resolve_color(project: Project) -> str:
    colors = {clip.color for clip in project.clips}
    requested = project.settings.color
    if requested == "hlg":
        if colors != {"hlg"}:
            raise VlogiiError(
                "HLG preservation requires every input to be HLG. Choose SDR for mixed footage."
            )
        return "hlg"
    if requested == "auto":
        return "hlg" if colors == {"hlg"} else "sdr"
    return "sdr"

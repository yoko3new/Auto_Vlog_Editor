"""Resumable local workflow shared by the CLI and the web application."""

import os
from pathlib import Path

from .ai import Director
from .editorial import (
    black_ranges,
    parse_edit_instruction,
    retention_plan,
    selection_intent,
    transform_output_ranges,
)
from .media import Tools, build_proxy, inspect_clip
from .models import Plan, Project, Review, Settings, SpeedRange, Text, TimeRange
from .render import render
from .speech import speech_config, transcribe
from .storage import VlogiiError, locked, read_json, write_json

EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv"}


def initialize(project_dir: Path, footage: Path, settings: Settings, progress=print):
    files = sorted(p for p in footage.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
    if not files:
        raise VlogiiError("No supported video files found.")
    if len(files) > 50:
        raise VlogiiError("The MVP accepts at most 50 clips per project.")
    if (project_dir / "project.json").exists():
        raise VlogiiError("Project already exists. Use a different name.")
    tools = Tools()
    clips = []
    seen = set()
    for index, file in enumerate(files):
        progress(f"Inspecting {index + 1}/{len(files)}")
        clip = inspect_clip(tools, file)
        if clip.sha256 not in seen:
            clips.append(clip)
            seen.add(clip.sha256)
    project = Project(name=project_dir.name, clips=clips, settings=settings)
    if sum(c.duration for c in clips) > 1800:
        raise VlogiiError("The MVP accepts at most 30 minutes of source footage.")
    write_json(project_dir / "project.json", project)
    return project


def load_project(project_dir: Path) -> Project:
    return Project.model_validate(read_json(project_dir / "project.json"))


def load_reviews(project_dir: Path) -> list[Review]:
    return [
        Review.model_validate(read_json(p))
        for p in sorted((project_dir / "reviews").glob("*.json"))
        if not p.name.endswith(".meta.json")
    ]


def cached_review(path: Path, fingerprint: dict, force=False):
    meta = path.with_suffix(".meta.json")
    if force or not path.is_file() or not meta.is_file():
        return None
    try:
        if read_json(meta) == fingerprint:
            return Review.model_validate(read_json(path))
    except (VlogiiError, ValueError):
        pass
    return None


def analyze(project_dir: Path, project: Project, progress=print, force=False, visual=True):
    tools = Tools()
    config = speech_config()
    model = os.environ.get("VLOGII_MODEL", "gemini-3.8-flash")
    director = None
    try:
        for index, clip in enumerate(project.clips):
            visual_path = project_dir / "visual-reviews" / f"{clip.id}.json"
            visual_meta = {
                "sha256": clip.sha256,
                "model": model,
                "revision": 2,
                "thinking": os.environ.get("VLOGII_THINKING", "medium"),
            }
            review = cached_review(visual_path, visual_meta, force)
            if review is None and not visual:
                review = Review(clip_id=clip.id, summary="Preserved source footage")
            elif review is None:
                progress(f"Preparing video {index + 1}/{len(project.clips)}")
                proxy = project_dir / "proxies" / f"{clip.id}.mp4"
                if not proxy.exists():
                    build_proxy(tools, clip, proxy)
                if director is None:
                    director = Director(project_dir / "ai-evidence")
                progress(f"AI analysis {index + 1}/{len(project.clips)}")
                review = director.review(clip, proxy, transcribe_speech=False)
                write_json(visual_path, review)
                write_json(visual_path.with_suffix(".meta.json"), visual_meta)
            else:
                progress(f"Analysis cached: {index + 1}/{len(project.clips)}")
            if clip.audio:
                speech_path = project_dir / "speech" / f"{clip.id}.json"
                speech_meta = {"sha256": clip.sha256, **config}
                speech = cached_review(speech_path, speech_meta, force)
                if speech is None:
                    progress(f"Speech recognition {index + 1}/{len(project.clips)}")
                    speech = Review(
                        clip_id=clip.id,
                        summary="Speech recognition",
                        speech=transcribe(clip, project_dir, config),
                    )
                    write_json(speech_path, speech)
                    write_json(speech_path.with_suffix(".meta.json"), speech_meta)
                else:
                    progress(f"Speech cached: {index + 1}/{len(project.clips)}")
                review = review.model_copy(update={"speech": speech.speech})
            write_json(project_dir / "reviews" / f"{clip.id}.json", review)
    finally:
        if director:
            director.close()


def make_plan(
    project_dir: Path,
    project: Project,
    direction: str,
    target: float | None,
    progress=print,
    mode="auto",
    remove_no_speech=False,
    speed=1,
    shot_seconds=0.5,
):
    reviews = load_reviews(project_dir)
    if {r.clip_id for r in reviews} != {c.id for c in project.clips}:
        raise VlogiiError("Analyze every clip before planning.")
    selection = selection_intent(direction, mode, target, remove_no_speech, speed, shot_seconds)
    if selection.mode in {"keep_all", "keep_most"}:
        black = {}
        if selection.mode == "keep_most":
            for index, clip in enumerate(project.clips):
                progress(f"Checking black frames {index + 1}/{len(project.clips)}")
                black[clip.id] = black_ranges(project_dir, clip)
        plan = retention_plan(project, reviews, selection, black)
        plan = transform_output_ranges(project, plan, [], speed=selection.speed)
        write_json(project_dir / "plan.json", plan)
        return plan
    director = Director(project_dir / "ai-evidence")
    try:
        progress("Planning your film")
        plan = director.plan(
            project,
            reviews,
            direction,
            selection.target_seconds,
            mode=selection.mode,
            speed=selection.speed,
            shot_seconds=selection.shot_seconds,
        )
        plan = transform_output_ranges(project, plan, [], speed=selection.speed)
        write_json(project_dir / "plan.json", plan)
        return plan
    finally:
        director.close()


def generate(
    project_dir: Path,
    direction: str,
    target: float | None = None,
    progress=print,
    resume=False,
    mode="auto",
    remove_no_speech=False,
    speed=1,
    shot_seconds=0.5,
):
    with locked(project_dir):
        project = load_project(project_dir)
        selection = selection_intent(direction, mode, target, remove_no_speech, speed, shot_seconds)
        context = {
            "direction": direction,
            "target": target,
            "selection": selection.model_dump(mode="json"),
            "planning_revision": 6,
            "project": project.model_dump(mode="json"),
            "model": os.environ.get("VLOGII_MODEL", "gemini-3.8-flash"),
            "speech": speech_config(),
            "thinking": os.environ.get("VLOGII_THINKING", "medium"),
        }
        checkpoint_path = project_dir / "generation.json"
        checkpoint = read_json(checkpoint_path) if resume and checkpoint_path.exists() else {}
        if checkpoint.get("context") != context:
            checkpoint = {"context": context, "status": "analyzing"}
            write_json(checkpoint_path, checkpoint)
        if checkpoint.get("status") == "complete":
            output = project_dir / "cuts" / checkpoint["cut"]
            if (output / "film.mp4").is_file():
                return output
        analyze(project_dir, project, progress, visual=selection.mode in {"auto", "highlights"})
        reviews = load_reviews(project_dir)
        review_data = [r.model_dump(mode="json") for r in reviews]
        if checkpoint.get("plan") and checkpoint.get("reviews") == review_data:
            progress("Resuming the saved plan")
            plan = Plan.model_validate(checkpoint["plan"])
        else:
            plan = make_plan(
                project_dir,
                project,
                direction,
                target,
                progress,
                mode=mode,
                remove_no_speech=remove_no_speech,
                speed=speed,
                shot_seconds=shot_seconds,
            )
            checkpoint.update(
                plan=plan.model_dump(mode="json"), reviews=review_data, status="rendering"
            )
            write_json(checkpoint_path, checkpoint)
        plan.mute_source_audio = selection.mode == "highlights"
        output = render(project_dir, project, plan, reviews, progress)
        write_json(output / "selection.json", selection)
        checkpoint.update(status="complete", cut=output.name)
        write_json(checkpoint_path, checkpoint)
        return output


def undo(project_dir: Path):
    with locked(project_dir):
        latest = read_json(project_dir / "latest.json")
        history = latest.get("history", [])
        if len(history) < 2:
            raise VlogiiError("No earlier successful version is available.")
        write_json(project_dir / "latest.json", {"cut": history[-2], "history": history[:-1]})
        return history[-2]


def edit(
    project_dir: Path,
    title: str | None,
    excluded: list[str],
    warmth: float | None,
    progress=print,
    resume=False,
    remove_ranges: list[TimeRange] | None = None,
    instruction: str = "",
    speed: float | None = None,
    speed_ranges: list[SpeedRange] | None = None,
):
    with locked(project_dir):
        latest = read_json(project_dir / "latest.json")
        checkpoint_path = project_dir / "edit-checkpoint.json"
        parsed_removed, parsed_sped = parse_edit_instruction(instruction)
        ranges = [TimeRange.model_validate(r) for r in remove_ranges or []] + parsed_removed
        sped = [SpeedRange.model_validate(r) for r in speed_ranges or []] + parsed_sped
        request = {
            "title": title,
            "excluded": excluded,
            "warmth": warmth,
            "remove_ranges": [r.model_dump() for r in ranges],
            "instruction": instruction,
            "speed": speed,
            "speed_ranges": [r.model_dump() for r in sped],
        }
        checkpoint = read_json(checkpoint_path) if resume and checkpoint_path.exists() else {}
        if checkpoint.get("request") == request and checkpoint.get("status") == "complete":
            if checkpoint.get("cut") == latest["cut"]:
                return project_dir / "cuts" / latest["cut"]
        if checkpoint.get("request") == request and checkpoint.get("base") != latest["cut"]:
            raise VlogiiError("The base version changed. Apply a new edit instead of retrying.")
        checkpoint = {"request": request, "base": latest["cut"], "status": "rendering"}
        write_json(checkpoint_path, checkpoint)
        version = project_dir / "cuts" / latest["cut"]
        project = Project.model_validate(read_json(version / "project.json"))
        plan = Plan.model_validate(read_json(version / "plan.json"))
        if (version / "selection.json").is_file() and read_json(version / "selection.json").get(
            "mode"
        ) == "highlights":
            plan.mute_source_audio = True
        if set(excluded) - {c.id for c in project.clips}:
            raise VlogiiError("An excluded clip is not part of this project.")
        # Ranges refer to the currently visible film, before simultaneous clip exclusions.
        plan = transform_output_ranges(project, plan, ranges, sped, speed)
        remaining = [s for s in plan.segments if s.clip_id not in excluded]
        if not remaining:
            raise VlogiiError("Keep at least one selected clip.")
        plan.segments = remaining
        if title:
            plan.title = title
            first = plan.segments[0]
            first.overlays = [Text(start=0, end=min(2, first.out_sec - first.in_sec), text=title)]
        if warmth is not None:
            if project.settings.color == "hlg":
                raise VlogiiError(
                    "Warmth adjustment is available for SDR output. Create an SDR project."
                )
            project.settings = Settings.model_validate(
                {**project.settings.model_dump(), "warmth": warmth}
            )
            # Applying warmth to HDR inputs uses the supported tone-mapped SDR path.
            project.settings.color = "sdr"
        output = render(project_dir, project, plan, load_reviews(project_dir), progress)
        if (version / "selection.json").exists():
            write_json(output / "selection.json", read_json(version / "selection.json"))
        checkpoint.update(status="complete", cut=output.name)
        write_json(checkpoint_path, checkpoint)
        return output

"""Resumable local workflow shared by the CLI and the web application."""

import os
from pathlib import Path

from .ai import Director
from .media import Tools, build_proxy, inspect_clip
from .models import Plan, Project, Review, Settings, Text
from .render import render
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


def analyze(project_dir: Path, project: Project, progress=print, force=False):
    tools = Tools()
    director = None
    try:
        for index, clip in enumerate(project.clips):
            review_path = project_dir / "reviews" / f"{clip.id}.json"
            meta_path = review_path.with_suffix(".meta.json")
            if review_path.exists() and meta_path.exists() and not force:
                meta = read_json(meta_path)
                if meta.get("sha256") == clip.sha256 and meta.get("model") == os.environ.get(
                    "VLOGII_MODEL", "gemini-3-flash-preview"
                ):
                    Review.model_validate(read_json(review_path))
                    progress(f"Analysis cached: {index + 1}/{len(project.clips)}")
                    continue
            progress(f"Preparing video {index + 1}/{len(project.clips)}")
            proxy = project_dir / "proxies" / f"{clip.id}.mp4"
            if not proxy.exists():
                build_proxy(tools, clip, proxy)
            if director is None:
                director = Director(project_dir / "ai-evidence")
            progress(f"AI analysis {index + 1}/{len(project.clips)}")
            review = director.review(clip, proxy)
            write_json(review_path, review)
            write_json(meta_path, {"sha256": clip.sha256, "model": director.model})
    finally:
        if director:
            director.close()


def make_plan(project_dir: Path, project: Project, direction: str, target: float, progress=print):
    reviews = load_reviews(project_dir)
    if {r.clip_id for r in reviews} != {c.id for c in project.clips}:
        raise VlogiiError("Analyze every clip before planning.")
    director = Director(project_dir / "ai-evidence")
    try:
        progress("Planning your film")
        plan = director.plan(project, reviews, direction, target)
        write_json(project_dir / "plan.json", plan)
        return plan
    finally:
        director.close()


def generate(project_dir: Path, direction: str, target: float, progress=print):
    with locked(project_dir):
        project = load_project(project_dir)
        analyze(project_dir, project, progress)
        plan = make_plan(project_dir, project, direction, target, progress)
        return render(project_dir, project, plan, load_reviews(project_dir), progress)


def undo(project_dir: Path):
    with locked(project_dir):
        latest = read_json(project_dir / "latest.json")
        history = latest.get("history", [])
        if len(history) < 2:
            raise VlogiiError("No earlier successful version is available.")
        write_json(project_dir / "latest.json", {"cut": history[-2], "history": history[:-1]})
        return history[-2]


def edit(
    project_dir: Path, title: str | None, excluded: list[str], warmth: float | None, progress=print
):
    with locked(project_dir):
        latest = read_json(project_dir / "latest.json")
        version = project_dir / "cuts" / latest["cut"]
        project = Project.model_validate(read_json(version / "project.json"))
        plan = Plan.model_validate(read_json(version / "plan.json"))
        if set(excluded) - {c.id for c in project.clips}:
            raise VlogiiError("An excluded clip is not part of this project.")
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
            project.settings.warmth = warmth
            # Applying warmth to HDR inputs uses the supported tone-mapped SDR path.
            project.settings.color = "sdr"
        return render(project_dir, project, plan, load_reviews(project_dir), progress)

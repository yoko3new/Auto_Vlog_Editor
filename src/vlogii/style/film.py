"""Style films inside a Vlogii project: music, moment selection, beat-locked render, edits.

AI chooses moments, labels and title text; the planner computes every cut on the music's
beat grid; the style renderer executes it. Each result is a normal Vlogii version, so
playback, download and undo work unchanged.
"""

import os
import tempfile
import uuid
from pathlib import Path

from ..media import sha256
from ..models import Music, Project, StyleMoment, StyleRequest, StyleSelection
from ..pipeline import analyze, load_project, load_reviews
from ..render import check_sources, new_version, publish, verify
from ..storage import VlogiiError, locked, read_json, write_json
from . import media, planner, templates
from .render import render as render_plan

MUSIC_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg"}
MUSIC_MAX_BYTES = 200 * 1024**2
MUSIC_SECONDS = (10, 15 * 60)


def ai_configured() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def music_folder(project_dir: Path) -> Path:
    return project_dir / "music"


def store_music(project_dir: Path, stream, original_name: str) -> Music:
    """Save an uploaded or local track under the project, then check it is usable music."""
    suffix = Path(original_name).suffix.lower()
    if suffix not in MUSIC_EXTENSIONS:
        raise VlogiiError("Use an MP3, M4A, AAC, WAV, FLAC or OGG music file.")
    folder = music_folder(project_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (uuid.uuid4().hex + suffix)
    size = 0
    try:
        with path.open("wb") as output:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > MUSIC_MAX_BYTES:
                    raise VlogiiError("Music files are limited to 200 MB.")
                output.write(chunk)
        info = media.probe(path)
        if not info["has_audio"]:
            raise VlogiiError("That file has no audio track.")
        low, high = MUSIC_SECONDS
        if not low <= info["duration_s"] <= high:
            raise VlogiiError(f"Use music between {low} seconds and {high // 60} minutes long.")
        music = Music(
            file=path.name,
            name=Path(original_name).name[:255] or path.name,
            sha256=sha256(path),
            duration=info["duration_s"],
        )
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    # Earlier tracks stay on disk: older versions may still be edited.
    write_json(project_dir / "music.json", music)
    return music


def load_music(project_dir: Path) -> Music | None:
    path = project_dir / "music.json"
    return Music.model_validate(read_json(path)) if path.exists() else None


def display_names(project_dir: Path) -> dict:
    path = project_dir / "upload-names.json"
    return read_json(path) if path.exists() else {}


def required_seconds(template: dict) -> float:
    """Footage the body needs at the template's shortest length, with the planner's gaps."""
    fixed = sum(s["length_s"] or 0 for s in template["sections"])
    fixed += template["end_card"]["length_s"] if template["end_card"] else 0
    return max(1.0, template["duration"]["min_s"] - fixed) / planner.FILL


def fallback_selection(project: Project) -> StyleSelection:
    """Without AI: every clip in import order, full length, template text."""
    return StyleSelection(
        reasoning="No Gemini key: clips in import order with the style's default text.",
        moments=[StyleMoment(clip_id=c.id, in_sec=0, out_sec=c.duration) for c in project.clips],
    )


def choose_moments(
    project_dir: Path, project: Project, template: dict, direction: str, progress, resume: bool
):
    if not ai_configured():
        progress("No Gemini key: using every clip in import order")
        return fallback_selection(project), False
    from ..ai import Director

    # Retry reuses the saved choice for the same project, style, music and direction.
    checkpoint_path = project_dir / "style-checkpoint.json"
    context = {
        "project": project.model_dump(mode="json"),
        "style": [template["id"], template["revision"]],
        "direction": direction,
        "model": os.environ.get("VLOGII_MODEL", "gemini-3.8-flash"),
    }
    if resume and checkpoint_path.exists():
        saved = read_json(checkpoint_path)
        if saved.get("context") == context:
            progress("Resuming the saved plan")
            return StyleSelection.model_validate(saved["selection"]), True
    # Clip sound is muted in style films, so only the pictures are analysed.
    analyze(project_dir, project, progress, with_speech=False)
    reviews = load_reviews(project_dir)
    director = Director(project_dir / "ai-evidence")
    try:
        progress("Choosing moments for the style")
        selection = director.style_selection(
            project, reviews, template, direction, required_seconds(template)
        )
    finally:
        director.close()
    write_json(
        checkpoint_path, {"context": context, "selection": selection.model_dump(mode="json")}
    )
    return selection, True


def render_style(project_dir: Path, project: Project, request: StyleRequest, progress) -> Path:
    template = templates.load(request.style_id)
    if template["revision"] != request.revision:
        raise VlogiiError("This style has changed since the version was made. Generate again.")
    clips = {c.id: c for c in project.clips}
    moments = [m for m in request.selection.moments if m.clip_id not in request.excluded]
    if not moments:
        raise VlogiiError("Keep at least one selected clip.")
    check_sources(project, {m.clip_id for m in moments})
    music_path = music_folder(project_dir) / request.music.file
    if not music_path.is_file():
        raise VlogiiError("The music file for this version is missing. Add the music again.")
    names = display_names(project_dir)
    inputs = [
        planner.ClipInput(
            path=Path(clips[m.clip_id].path),
            label=m.label,
            in_s=m.in_sec,
            out_s=min(m.out_sec, clips[m.clip_id].duration),
            clip_id=m.clip_id,
            name=names.get(Path(clips[m.clip_id].path).name, Path(clips[m.clip_id].path).name),
        )
        for m in moments
    ]
    text = request.selection.text.model_dump(exclude_none=True)
    version = new_version(project_dir)
    write_json(version / "project.json", project)
    write_json(version / "style.json", request)
    write_json(version / "state.json", {"status": "rendering"})
    try:
        progress("Finding the beat")
        plan = planner.plan(
            template,
            music_path,
            inputs,
            text,
            size=(project.settings.width, project.settings.height),
            warmth=request.warmth,
        )
        write_json(version / "style-plan.json", plan)
        fps = plan["output"]["fps"]
        duration = plan["total_frames"] / fps
        checked = project.model_copy(
            update={"settings": project.settings.model_copy(update={"fps": fps})}
        )
        # A generated temporary directory keeps user paths out of FFmpeg filter syntax.
        with tempfile.TemporaryDirectory(prefix="vlogii-style-") as temporary:
            pending = version / "pending.mp4"
            report = render_plan(
                plan, template, pending, Path(temporary), version / "logs", progress
            )
            progress("Checking video and audio")
            evidence = verify(media.tools(), pending, checked, "sdr", duration)
            media.tools().run(
                ["-v", "error", "-xerror", "-i", str(pending), "-f", "null", "-"],
                version / "logs" / "decode.log",
            )
            pending.replace(version / "film.mp4")
        write_json(version / "verification.json", {**evidence, "style": report})
        write_json(version / "state.json", {"status": "complete", "color": "sdr"})
        publish(project_dir, version)
        progress(f"Complete: {version.name}")
        return version
    except BaseException:
        write_json(version / "state.json", {"status": "failed"})
        raise


def generate_style(
    project_dir: Path, style_id: str, direction: str, progress=print, resume: bool = False
) -> Path:
    with locked(project_dir):
        project = load_project(project_dir)
        template = templates.load(style_id)
        planner.output_for(template, (project.settings.width, project.settings.height))
        music = load_music(project_dir)
        if music is None:
            raise VlogiiError("Add a music track before making a style film.")
        selection, ai = choose_moments(project_dir, project, template, direction, progress, resume)
        request = StyleRequest(
            style_id=style_id,
            revision=template["revision"],
            music=music,
            selection=selection,
            ai_selected=ai,
        )
        return render_style(project_dir, project, request, progress)


def edit_style(
    project_dir: Path,
    version: Path,
    title: str | None,
    excluded: list[str],
    warmth: float | None,
    progress,
) -> Path:
    """Title, warmth and clip exclusion on a style version; re-cut on the beat, no AI call."""
    project = Project.model_validate(read_json(version / "project.json"))
    request = StyleRequest.model_validate(read_json(version / "style.json"))
    if set(excluded) - {c.id for c in project.clips}:
        raise VlogiiError("An excluded clip is not part of this project.")
    request.excluded = sorted(set(request.excluded) | set(excluded))
    if title:
        if len(title) > 40:
            raise VlogiiError("Style titles are limited to 40 characters.")
        request.selection.text.title = title
    if warmth is not None:
        request.warmth = warmth
    return render_style(project_dir, project, request, progress)


def describe_version(version: Path) -> dict | None:
    """Style facts the web page shows for the current version."""
    style_path = version / "style.json"
    if not style_path.exists():
        return None
    request = StyleRequest.model_validate(read_json(style_path))
    verification = version / "verification.json"
    report = read_json(verification).get("style", {}) if verification.exists() else {}
    try:
        name = templates.load(request.style_id)["display_name"]
    except VlogiiError:
        name = request.style_id
    return {
        "id": request.style_id,
        "name": name,
        "ai_selected": request.ai_selected,
        "music": request.music.name,
        "tempo_bpm": report.get("music", {}).get("tempo_bpm"),
        "loudness_lufs": report.get("loudness", {}).get("integrated_lufs"),
        "warnings": report.get("warnings", []),
    }


def import_music(project_dir: Path, path: Path) -> Music:
    """CLI helper: copy a local track into the project."""
    with path.open("rb") as stream:
        return store_music(project_dir, stream, path.name)

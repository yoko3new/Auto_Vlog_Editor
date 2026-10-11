"""Current-film coordinates, reversible inclusion, filters and truthful chapter timing."""

import pytest
from fastapi.testclient import TestClient

from vlogii.api import create_app
from vlogii.chapters import version_chapters
from vlogii.grading import apply_filter
from vlogii.inclusion import edit_recoverable, set_included
from vlogii.media import Tools, inspect_clip
from vlogii.models import (
    Clip,
    Plan,
    Project,
    Review,
    Segment,
    Settings,
    SpeedRange,
    Text,
    TimeRange,
)
from vlogii.pipeline import edit, generate, undo
from vlogii.presets import ASSETS, manifest
from vlogii.render import render
from vlogii.storage import VlogiiError, read_json, write_json
from vlogii.timeline import compile_timeline


def fixture_project():
    project = Project(
        name="day",
        clips=[
            Clip(
                id=i,
                path=f"/private/{i}.mp4",
                sha256=i,
                duration=1,
                width=96,
                height=64,
                fps=30,
                audio=False,
            )
            for i in "abc"
        ],
        settings=Settings(width=96, height=64, color="sdr", encoder="software"),
    )
    plan = Plan(
        title="Day",
        reasoning="Fixture",
        captions=False,
        segments=[Segment(clip_id=i, in_sec=0, out_sec=1) for i in "abc"],
    )
    return project, plan


def test_time_edits_translate_across_hidden_clips_without_damaging_them():
    project, plan = fixture_project()
    changed = edit_recoverable(project, plan, ["a", "c"], [TimeRange(start=0.5, end=1.5)], [], None)
    assert [(s.clip_id, s.in_sec, s.out_sec) for s in changed.segments] == [
        ("a", 0, 0.5),
        ("b", 0, 1),
        ("c", 0.5, 1),
    ]
    sped = edit_recoverable(
        project, plan, ["a", "c"], [], [SpeedRange(start=0.5, end=1.5, speed=2)], None
    )
    assert [s.speed for s in sped.segments if s.clip_id == "b"] == [1]
    with pytest.raises(VlogiiError, match="current film"):
        edit_recoverable(project, plan, ["a", "c"], [TimeRange(start=1, end=2.5)], [], None)
    with pytest.raises(VlogiiError, match="must not overlap"):
        edit_recoverable(
            project,
            plan,
            ["a", "c"],
            [],
            [SpeedRange(start=0, end=1, speed=2), SpeedRange(start=0.5, end=1.5, speed=4)],
            None,
        )


def test_generation_only_analyzes_and_plans_checked_clips_with_cached_others(tmp_path, monkeypatch):
    project, _ = fixture_project()
    write_json(tmp_path / "project.json", project)
    for clip in project.clips:
        write_json(
            tmp_path / "reviews" / f"{clip.id}.json", Review(clip_id=clip.id, summary=clip.id)
        )
    analyzed = []
    monkeypatch.setattr(
        "vlogii.pipeline.analyze", lambda root, p, *a, **k: analyzed.extend(c.id for c in p.clips)
    )

    def capture(root, p, plan, reviews, progress):
        assert {r.clip_id for r in reviews} == {"a", "c"}
        assert [s.clip_id for s in plan.segments] == ["a", "c"]
        assert len(p.clips) == 3  # Full metadata stays available for future selection.
        output = root / "cuts" / "cut_001"
        write_json(output / "project.json", p)
        write_json(output / "plan.json", plan)
        return output

    monkeypatch.setattr("vlogii.pipeline.render", capture)
    generate(tmp_path, "", mode="keep_all", included_clip_ids=["c", "a"], video_filter="bright")
    assert analyzed == ["a", "c"]
    saved = read_json(tmp_path / "project.json")
    assert saved["included_clip_ids"] == ["a", "c"]
    assert saved["settings"]["video_filter"] == "bright"


def test_selection_validation_and_sdr_filter_requirement():
    project, _ = fixture_project()
    for ids in ([], ["unknown"], ["a", "a"]):
        with pytest.raises(VlogiiError):
            set_included(project, ids)
    project.settings.color = "hlg"
    with pytest.raises(VlogiiError, match="SDR"):
        apply_filter(project, "warm")
    apply_filter(project, "none")
    assert project.settings.color == "hlg"


@pytest.mark.media
def test_selection_restore_chapters_filters_and_undo_are_real_exports(tmp_path):
    tools = Tools()
    clips = []
    for color in ("red", "green", "blue"):
        path = tmp_path / f"{color}.mp4"
        tools.run(
            ["-f", "lavfi", "-i", f"color={color}:s=96x64:r=30:d=1", "-c:v", "libx264", str(path)],
            tmp_path / f"{color}.log",
        )
        clips.append(inspect_clip(tools, path))
    directory = tmp_path / "day"
    project = Project(
        name="day",
        clips=clips,
        settings=Settings(width=96, height=64, color="sdr", encoder="software"),
    )
    plan = Plan(
        title="Day",
        reasoning="Fixture",
        captions=False,
        segments=[Segment(clip_id=c.id, in_sec=0, out_sec=1) for c in clips],
    )
    reviews = [
        Review(
            clip_id=c.id,
            summary=f"{color} scene",
            highlights=[Text(start=0, end=1, text=f"{color} scene")],
        )
        for c, color in zip(clips, ("red", "green", "blue"), strict=True)
    ]
    write_json(directory / "project.json", project)
    for r in reviews:
        write_json(directory / "reviews" / f"{r.clip_id}.json", r)
    initial = render(directory, project, plan, reviews)
    write_json(initial / "recoverable-plan.json", plan)
    ids = [clips[0].id, clips[2].id]
    hidden = edit(directory, None, [], None, included_clip_ids=ids, video_filter="bright")
    assert read_json(hidden / "verification.json")["duration"] == pytest.approx(2, abs=0.1)
    chapters = version_chapters(hidden, reviews)
    assert [c.summary for c in chapters] == ["red scene", "blue scene"]
    assert [(c.start, c.end) for c in chapters] == [(0, 1), (1, 2)]
    removed = edit(
        directory,
        None,
        [],
        None,
        instruction="delete 00:00.50 to 00:01.50",
        video_filter="cool_white",
    )
    assert read_json(removed / "verification.json")["duration"] == pytest.approx(1, abs=0.1)
    restored = edit(
        directory, None, [], None, included_clip_ids=[c.id for c in clips], video_filter="warm"
    )
    saved = Plan.model_validate(read_json(restored / "plan.json"))
    assert [(s.clip_id, s.in_sec, s.out_sec) for s in saved.segments] == [
        (clips[0].id, 0, 0.5),
        (clips[1].id, 0, 1),
        (clips[2].id, 0.5, 1),
    ]
    assert compile_timeline(project, saved, []).total_frames == 60
    assert read_json(restored / "project.json")["settings"]["video_filter"] == "warm"
    assert (restored / "logs" / "segment-0000.log").exists()  # Filter invalidates video cache.
    before = read_json(directory / "latest.json")
    with pytest.raises(VlogiiError, match="selected clip"):
        edit(directory, None, [c.id for c in clips], None)
    assert read_json(directory / "latest.json") == before
    assert undo(directory) == removed.name
    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/api/vlogii/projects/day")
        assert response.status_code == 200
        data = response.json()
        assert data["included_clip_ids"] == ids
        assert data["settings"]["video_filter"] == "cool_white"
        assert data["chapters"][-1]["end"] == 1
        assert str(tmp_path) not in response.text
        assert (
            client.post("/api/vlogii/projects/day/edit", json={"included_clip_ids": []}).status_code
            == 422
        )
        assert (
            client.post(
                "/api/vlogii/projects/day/edit", json={"included_clip_ids": ["unknown"]}
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/vlogii/projects/day/edit", json={"video_filter": "unknown"}
            ).status_code
            == 422
        )


def test_all_bundled_font_licenses_and_hashes_are_preserved():
    fonts = manifest()["fonts"]
    assert len(fonts) == 14
    for font in fonts:
        identifier = font["id"]
        # Font hash verification is also exercised by the renderer tests.
        licenses = list((ASSETS / "licenses").glob(f"{identifier}*"))
        if identifier.startswith("noto"):
            licenses = list((ASSETS / "licenses").glob("*Noto*")) or list(
                (ASSETS / "licenses").glob("*noto*")
            )
        assert licenses, identifier
        assert any("SIL OPEN FONT LICENSE" in path.read_text() for path in licenses)

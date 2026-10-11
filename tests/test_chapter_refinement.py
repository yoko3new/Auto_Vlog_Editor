"""Chapter coordinates, repeated sources and durable version edits."""

import time

import pytest
from fastapi.testclient import TestClient

from vlogii.api import create_app
from vlogii.chapters import version_chapters
from vlogii.editorial import transform_output_ranges
from vlogii.models import Chapter, ChapterEdit, Clip, Plan, Project, Segment, Settings
from vlogii.pipeline import edit, undo
from vlogii.refinement import chapter_ranges
from vlogii.storage import VlogiiError, read_json, write_json
from vlogii.timeline import compile_timeline


@pytest.mark.parametrize("text", ["删除整段", "delete entire segment", "Remove this scene"])
def test_whole_segment_instruction_is_relative_to_its_chapter(text):
    removed, sped = chapter_ranges(
        [Chapter(start=10, end=14, title="Scene", summary="Scene")],
        [ChapterEdit(chapter_index=0, action="instruction", instruction=text)],
    )
    assert [(r.start, r.end) for r in removed] == [(10, 14)]
    assert not sped


@pytest.mark.parametrize(
    "text",
    ["加速到2倍；删掉1秒到2秒", "Speed up to 2x; delete 1 seconds to 2 seconds"],
)
def test_bilingual_instructions_map_all_clauses_against_same_original_chapter(text):
    removed, sped = chapter_ranges(
        [Chapter(start=10, end=14, title="Scene", summary="Scene")],
        [ChapterEdit(chapter_index=0, action="instruction", instruction=text)],
    )
    assert [(r.start, r.end) for r in removed] == [(11, 12)]
    assert [(r.start, r.end, r.speed) for r in sped] == [(10, 14, 2)]


@pytest.mark.parametrize(
    "payload",
    [
        {"chapter_index": 1, "action": "remove"},
        {"chapter_index": 0, "action": "remove_range", "start": 0, "end": 5},
        {"chapter_index": 0, "action": "instruction", "instruction": "make it cinematic"},
        {"chapter_index": 0, "action": "instruction", "instruction": ";；"},
        {"chapter_index": 0, "action": "instruction", "instruction": "speed up to 9x"},
    ],
)
def test_invalid_or_unsupported_chapter_edit_rejected(payload):
    with pytest.raises(VlogiiError):
        chapter_ranges(
            [Chapter(start=10, end=14, title="Scene", summary="Scene")], [ChapterEdit(**payload)]
        )


def seed(root):
    directory = root / "day"
    project = Project(
        name="day",
        clips=[
            Clip(
                id="a",
                path="/private/a.mp4",
                sha256="a",
                duration=4,
                width=96,
                height=64,
                fps=30,
                audio=False,
            )
        ],
        settings=Settings(width=96, height=64, color="sdr", encoder="software"),
    )
    plan = Plan(
        title="Day",
        reasoning="Fixture",
        captions=False,
        segments=[
            Segment(clip_id="a", in_sec=0, out_sec=1, purpose="Opening"),
            Segment(clip_id="a", in_sec=1, out_sec=4, purpose="Body"),
        ],
    )
    write_json(directory / "project.json", project)
    version = directory / "cuts/cut_001"
    write_json(version / "project.json", project)
    write_json(version / "plan.json", plan)
    write_json(version / "timeline.json", compile_timeline(project, plan, []))
    write_json(directory / "latest.json", {"cut": "cut_001", "history": ["cut_001"]})
    return directory, project, plan


def test_deleting_one_occurrence_keeps_same_source_elsewhere_and_all_delete_rejected(tmp_path):
    _, project, plan = seed(tmp_path)
    chapters = [
        Chapter(start=0, end=1, title="Opening", summary="Opening"),
        Chapter(start=1, end=4, title="Body", summary="Body"),
    ]
    removed, sped = chapter_ranges(
        chapters,
        [
            ChapterEdit(chapter_index=0, action="remove"),
            ChapterEdit(chapter_index=1, action="speed", start=1, end=2, speed=2),
        ],
    )
    result = transform_output_ranges(project, plan, removed, sped)
    assert [(s.in_sec, s.out_sec, s.speed) for s in result.segments] == [
        (1, 2, 1),
        (2, 3, 2),
        (3, 4, 1),
    ]
    assert compile_timeline(project, result, []).total_frames == 75
    removed, _ = chapter_ranges(
        chapters, [ChapterEdit(chapter_index=i, action="remove") for i in range(2)]
    )
    with pytest.raises(VlogiiError):
        transform_output_ranges(project, plan, removed)


def test_api_rejects_stale_version_and_bad_local_ranges_before_enqueue(tmp_path):
    directory, _, _ = seed(tmp_path)
    with TestClient(create_app(tmp_path)) as client:
        for body in [
            {"base_cut": "cut_000", "chapter_edits": [{"chapter_index": 0, "action": "remove"}]},
            {
                "base_cut": "cut_001",
                "chapter_edits": [
                    {"chapter_index": 1, "action": "remove_range", "start": 0, "end": 4}
                ],
            },
            {
                "base_cut": "cut_001",
                "chapter_edits": [
                    {
                        "chapter_index": 0,
                        "action": "instruction",
                        "instruction": "make it cinematic",
                    }
                ],
            },
        ]:
            assert client.post("/api/vlogii/projects/day/edit", json=body).status_code == 400
        assert not (directory / "job.json").exists()


def test_failed_chapter_batch_retries_exactly_and_completed_retry_is_idempotent(
    tmp_path, monkeypatch
):
    directory, _, _ = seed(tmp_path)
    calls = []

    def renderer(root, project, plan, *args):
        calls.append(plan.model_dump())
        if len(calls) == 1:
            raise RuntimeError("Injected render failure")
        output = root / "cuts/cut_002"
        write_json(output / "project.json", project)
        write_json(output / "plan.json", plan)
        write_json(root / "latest.json", {"cut": output.name, "history": ["cut_001", output.name]})
        return output

    monkeypatch.setattr("vlogii.pipeline.render", renderer)
    body = {
        "base_cut": "cut_001",
        "chapter_edits": [
            {"chapter_index": 0, "action": "remove"},
            {"chapter_index": 1, "action": "speed", "speed": 2},
        ],
    }

    def finish():
        for _ in range(200):
            job = read_json(directory / "job.json")
            if job["status"] in {"failed", "complete"}:
                return job
            time.sleep(0.01)
        pytest.fail("Job did not finish")

    with TestClient(create_app(tmp_path)) as client:
        assert client.post("/api/vlogii/projects/day/edit", json=body).status_code == 202
        assert finish()["status"] == "failed"
        assert read_json(directory / "latest.json")["cut"] == "cut_001"
        assert client.post("/api/vlogii/projects/day/retry").status_code == 202
        assert finish()["status"] == "complete"
    assert calls[0] == calls[1]
    assert [(s["in_sec"], s["out_sec"], s["speed"]) for s in calls[1]["segments"]] == [(1, 4, 2)]
    result = edit(
        directory,
        None,
        [],
        None,
        resume=True,
        chapter_edits=[ChapterEdit(**item) for item in body["chapter_edits"]],
        base_cut="cut_001",
    )
    assert result.name == "cut_002" and len(calls) == 2
    assert undo(directory) == "cut_001"
    assert len(version_chapters(directory / "cuts/cut_001", [])) == 2

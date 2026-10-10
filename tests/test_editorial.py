import pytest
from fastapi.testclient import TestClient

from vlogii import pipeline
from vlogii.ai import Director
from vlogii.api import create_app
from vlogii.editorial import (
    parse_remove_ranges,
    remove_output_ranges,
    retention_plan,
    selection_intent,
)
from vlogii.models import Clip, Plan, Project, Review, Segment, Selection, Settings, Text, TimeRange
from vlogii.storage import VlogiiError, read_json, write_json
from vlogii.timeline import compile_timeline


def project():
    return Project(
        name="日常",
        settings=Settings(fps=30),
        clips=[
            Clip(
                id=name,
                path=f"/{name}.mov",
                sha256=name,
                duration=10,
                width=64,
                height=64,
                fps=30,
                audio=True,
            )
            for name in ["one", "two", "three"]
        ],
    )


@pytest.mark.parametrize(
    "text,mode,target",
    [
        ("", "auto", None),
        ("全部保留", "keep_all", None),
        ("保留大部分", "keep_most", None),
        ("开头快剪，12秒", "highlights", 12),
        ("keep about 2 minutes", "auto", 120),
        ("保留1分30秒", "auto", 90),
        ("full video", "keep_all", None),
        ("opening montage", "highlights", None),
        ("没有语音的都删掉", "keep_most", None),
    ],
)
def test_natural_retention_and_duration(text, mode, target):
    intent = selection_intent(text)
    assert intent.mode == mode and intent.target_seconds == target


def test_explicit_controls_win_and_conflicting_retention_target_rejected():
    assert selection_intent("快剪30秒", "auto", 60).target_seconds == 60
    assert selection_intent("全部保留", "highlights").mode == "highlights"
    with pytest.raises(VlogiiError, match="Retention modes"):
        selection_intent("全部保留", target=30)


def test_keep_all_preserves_every_frame_and_most_keeps_scenery():
    p = project()
    reviews = [Review(clip_id=c.id, summary="fixture") for c in p.clips]
    reviews[0].speech = [Text(start=0.5, end=3, text="你好"), Text(start=7, end=9, text="再见")]
    all_plan = retention_plan(p, reviews, Selection(mode="keep_all"), {"one": [(0, 10)]})
    assert compile_timeline(p, all_plan, reviews).total_frames == 900
    most = retention_plan(p, reviews, Selection(mode="keep_most"), {"two": [(2, 4)]})
    assert [(s.in_sec, s.out_sec) for s in most.segments if s.clip_id == "one"] == [
        (0, 3.35),
        (6.65, 10),
    ]
    assert sum(s.out_sec - s.in_sec for s in most.segments if s.clip_id == "three") == 10
    only_speech = retention_plan(p, reviews, Selection(mode="keep_most", remove_no_speech=True), {})
    assert {s.clip_id for s in only_speech.segments} == {"one"}


@pytest.mark.parametrize(
    "text",
    [
        "删掉00:01到00:03，00:08-00:12不用",
        "remove 00:01 to 00:03 and 00:08-00:12",
        "删除1秒到3秒，8秒至12秒",
        "00:01-00:03; 00:08-00:12",
    ],
)
def test_time_range_language(text):
    assert [(r.start, r.end) for r in parse_remove_ranges(text)] == [(1, 3), (8, 12)]
    assert parse_remove_ranges("1分到1分8秒不用")[0].end == 68


@pytest.mark.parametrize(
    "text", ["删掉00:60到01:10", "删掉-1到3", "加bgm", "删掉1到3并加背景音乐", "删掉3到1"]
)
def test_ambiguous_or_unsupported_edits_are_not_partially_applied(text):
    with pytest.raises((VlogiiError, ValueError)):
        parse_remove_ranges(text)


def test_range_edits_cross_cuts_remap_sources_and_overlay_timing():
    p = project()
    original = Plan(
        title="日常",
        reasoning="fixture",
        segments=[
            Segment(
                clip_id="one", in_sec=2, out_sec=8, overlays=[Text(start=0, end=5, text="标题")]
            ),
            Segment(clip_id="two", in_sec=1, out_sec=9),
        ],
    )
    edited = remove_output_ranges(
        p, original, [TimeRange(start=3, end=8), TimeRange(start=4, end=9)]
    )
    assert [(s.clip_id, s.in_sec, s.out_sec) for s in edited.segments] == [
        ("one", 2, 5),
        ("two", 4, 9),
    ]
    assert edited.segments[0].overlays[0].end == 3
    assert compile_timeline(p, edited, []).total_frames == 240
    assert original.segments[0].out_sec == 8
    with pytest.raises(VlogiiError, match="current film"):
        remove_output_ranges(p, original, [TimeRange(start=0, end=15)])
    with pytest.raises(VlogiiError, match="Keep at least"):
        remove_output_ranges(p, original, [TimeRange(start=0, end=14)])


def test_full_generation_has_no_ai_planning_and_mode_change_invalidates_plan(tmp_path, monkeypatch):
    p = project()
    directory = tmp_path / p.name
    write_json(directory / "project.json", p)
    for c in p.clips:
        write_json(directory / "reviews" / f"{c.id}.json", Review(clip_id=c.id, summary="Fixture"))
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **kw: None)
    plans = []

    def render(directory, project, plan, *args):
        plans.append(plan)
        output = directory / "cuts" / f"cut_{len(plans):03}"
        output.mkdir(parents=True)
        (output / "film.mp4").write_bytes(b"fixture")
        return output

    monkeypatch.setattr(pipeline, "render", render)
    output = pipeline.generate(directory, "", mode="keep_all")
    assert compile_timeline(p, plans[0], []).total_frames == 900
    assert read_json(output / "selection.json")["mode"] == "keep_all"
    assert pipeline.generate(directory, "", mode="keep_all", resume=True) == output
    assert len(plans) == 1
    monkeypatch.setattr(pipeline, "black_ranges", lambda *a: [])
    pipeline.generate(directory, "", mode="keep_most", resume=True)
    assert len(plans) == 2


def test_auto_no_fixed_target_and_highlights_prompt_defines_short_shots(monkeypatch):
    p = project()
    reviews = [Review(clip_id=c.id, summary="Fixture") for c in p.clips]
    director = Director.__new__(Director)
    prompts = []

    def generate(parts, *a):
        prompts.append(parts[0])
        return Plan(
            title="日常",
            reasoning="fixture",
            segments=[Segment(clip_id="one", in_sec=0, out_sec=0.3)],
        )

    monkeypatch.setattr(director, "_generate", generate)
    director.plan(p, reviews, "", None)
    director.plan(p, reviews, "", None, mode="highlights")
    assert "NO default 30-second target" in prompts[0]
    assert "5.0 OUTPUT seconds" in prompts[1] and "0.50 OUTPUT seconds" in prompts[1]


def test_highlights_rejects_long_shots_and_requests_correction(monkeypatch):
    p = project()
    director = Director.__new__(Director)
    lengths = iter([8, 0.3])
    calls = []

    def generate(parts, *a):
        calls.append(parts[0])
        return Plan(
            title="日常",
            reasoning="fixture",
            segments=[Segment(clip_id="one", in_sec=0, out_sec=next(lengths))],
        )

    monkeypatch.setattr(director, "_generate", generate)
    result = director.plan(
        p, [Review(clip_id=c.id, summary="fixture") for c in p.clips], "", None, mode="highlights"
    )
    assert len(calls) == 2 and result.segments[0].out_sec == 0.3


def test_range_retry_preserves_exact_request_and_undo_base(tmp_path, monkeypatch):
    p = project()
    directory = tmp_path / p.name
    write_json(directory / "project.json", p)
    write_json(directory / "latest.json", {"cut": "cut_001", "history": ["cut_001"]})
    write_json(directory / "cuts/cut_001/project.json", p)
    write_json(
        directory / "cuts/cut_001/plan.json",
        retention_plan(
            p,
            [Review(clip_id=c.id, summary="fixture") for c in p.clips],
            Selection(mode="keep_all"),
            {},
        ),
    )
    calls = []

    def render(*args):
        calls.append(args[2])
        if len(calls) == 1:
            raise VlogiiError("Injected render failure")
        return directory / "cuts/cut_002"

    monkeypatch.setattr(pipeline, "render", render)
    with pytest.raises(VlogiiError):
        pipeline.edit(directory, None, [], None, instruction="删掉8秒到12秒")
    assert read_json(directory / "latest.json")["cut"] == "cut_001"
    pipeline.edit(directory, None, [], None, instruction="删掉8秒到12秒", resume=True)
    assert calls[0] == calls[1]
    assert compile_timeline(p, calls[1], []).total_frames == 780


def test_api_validates_modes_targets_and_range_instructions_before_enqueuing(tmp_path, monkeypatch):
    p = project()
    directory = tmp_path / p.name
    write_json(directory / "project.json", p)
    write_json(directory / "latest.json", {"cut": "cut_001", "history": ["cut_001"]})
    monkeypatch.setenv("GEMINI_API_KEY", "placeholder")
    with TestClient(create_app(tmp_path)) as client:
        url = "/api/vlogii/projects/日常"
        assert client.post(url + "/generate", json={"mode": "unknown"}).status_code == 422
        assert (
            client.post(
                url + "/generate", json={"mode": "keep_all", "target_seconds": 30}
            ).status_code
            == 400
        )
        assert (
            client.post(url + "/edit", json={"instruction": "删掉1到3，并加bgm"}).status_code == 400
        )
        assert (
            client.post(url + "/edit", json={"remove_ranges": [{"start": 3, "end": 1}]}).status_code
            == 422
        )
        assert not (directory / "job.json").exists()

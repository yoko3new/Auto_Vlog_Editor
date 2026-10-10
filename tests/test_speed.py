import math

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from vlogii import pipeline
from vlogii.api import EditRequest, GenerateRequest, create_app
from vlogii.editorial import parse_edit_instruction, transform_output_ranges
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
from vlogii.storage import VlogiiError, read_json, write_json
from vlogii.timeline import compile_timeline


def fixture():
    p = Project(
        name="speed",
        clips=[
            Clip(
                id="one",
                path="/fixture.mp4",
                sha256="a",
                duration=10,
                width=96,
                height=64,
                fps=30,
                audio=True,
            )
        ],
        settings=Settings(width=96, height=128, encoder="software", color="sdr"),
    )
    plan = Plan(
        title="speed",
        reasoning="fixture",
        segments=[
            Segment(
                clip_id="one", in_sec=0, out_sec=10, overlays=[Text(start=2, end=8, text="test")]
            )
        ],
    )
    return p, plan


@pytest.mark.parametrize("rate", [0, -1, 0.1, 9, float("inf"), float("nan")])
def test_invalid_rates_rejected(rate):
    with pytest.raises(ValidationError):
        GenerateRequest(speed=rate)
    with pytest.raises(ValidationError):
        EditRequest(speed=rate)
    with pytest.raises(ValidationError):
        SpeedRange(start=0, end=1, speed=rate)


@pytest.mark.parametrize(
    "instruction",
    [
        "00:02到00:08加速到2倍",
        "把0分2秒到0分8秒的部分加快速度到2倍",
        "speed up 00:02 to 00:08 to 2x",
        "set 2-8 to 2×",
    ],
)
def test_bilingual_speed_ranges(instruction):
    removed, sped = parse_edit_instruction(instruction)
    assert removed == [] and sped == [SpeedRange(start=2, end=8, speed=2)]


def test_instructions_refuse_partial_unknown_operation_and_validate_range():
    for instruction in ["00:02到00:08加速到2倍并加BGM", "speed up 2-8", "2-8 to 2x 4x"]:
        with pytest.raises(VlogiiError):
            parse_edit_instruction(instruction)
    with pytest.raises(VlogiiError):
        parse_edit_instruction("8-2 to 2x")
    removed, sped = parse_edit_instruction("删掉0秒到1秒；2秒到8秒加速到2倍")
    assert removed == [TimeRange(start=0, end=1)] and sped[0].speed == 2


def test_global_speed_subtitles_source_extent_and_overlay_timing():
    p, plan = fixture()
    plan.segments[0].speed = 2
    reviews = [Review(clip_id="one", summary="fixture", speech=[Text(start=2, end=6, text="你好")])]
    t = compile_timeline(p, plan, reviews)
    assert t.total_frames == 150 and t.segments[0].source_frames == 300
    assert t.segments[0].captions == [Text(start=1, end=3, text="你好")]
    assert t.segments[0].overlays == [Text(start=1, end=4, text="test")]


def test_partial_speed_then_delete_uses_current_film_not_original_source():
    p, plan = fixture()
    partial = transform_output_ranges(p, plan, [], [SpeedRange(start=2, end=8, speed=2)])
    assert compile_timeline(p, partial, []).total_frames == 210  # 2 + 6/2 + 2
    # Current 3–4 seconds maps to source 4–6 seconds in the accelerated segment.
    deleted = transform_output_ranges(p, partial, [TimeRange(start=3, end=4)])
    assert [(s.in_sec, s.out_sec, s.speed) for s in deleted.segments] == [
        (0, 2, 1),
        (2, 4, 2),
        (6, 8, 2),
        (8, 10, 1),
    ]
    assert compile_timeline(p, deleted, []).total_frames == 180
    assert deleted.segments[2].overlays == [Text(start=0, end=2, text="test")]
    restored = transform_output_ranges(p, partial, [], speed=1)
    assert compile_timeline(p, restored, []).total_frames == 300
    assert plan.segments[0].speed == 1 and len(plan.segments) == 1


def test_simultaneous_ranges_use_same_base_and_range_overrides_global():
    p, plan = fixture()
    result = transform_output_ranges(
        p, plan, [TimeRange(start=0, end=1)], [SpeedRange(start=2, end=8, speed=2)], speed=4
    )
    assert [(s.in_sec, s.out_sec, s.speed) for s in result.segments] == [
        (1, 2, 4),
        (2, 8, 2),
        (8, 10, 4),
    ]
    assert compile_timeline(p, result, []).total_frames == 113  # frame-rounded 0.25 + 3 + 0.5
    with pytest.raises(VlogiiError, match="overlap"):
        transform_output_ranges(
            p, plan, [], [SpeedRange(start=2, end=8, speed=2), SpeedRange(start=7, end=9, speed=4)]
        )
    with pytest.raises(VlogiiError, match="within"):
        transform_output_ranges(p, plan, [], [SpeedRange(start=2, end=11, speed=2)])


def test_speed_edit_failure_retry_preserves_rate_and_base(tmp_path, monkeypatch):
    p, plan = fixture()
    directory = tmp_path / p.name
    write_json(directory / "project.json", p)
    write_json(directory / "latest.json", {"cut": "cut_001", "history": ["cut_001"]})
    write_json(directory / "cuts/cut_001/project.json", p)
    write_json(directory / "cuts/cut_001/plan.json", plan)
    calls = []

    def render(directory, project, plan, *a):
        calls.append(plan.model_dump())
        if len(calls) == 1:
            raise VlogiiError("Injected failure")
        return directory / "cuts/cut_002"

    monkeypatch.setattr(pipeline, "render", render)
    with pytest.raises(VlogiiError):
        pipeline.edit(directory, None, [], None, instruction="2-8 to 2x")
    assert read_json(directory / "latest.json")["cut"] == "cut_001"
    pipeline.edit(directory, None, [], None, instruction="2-8 to 2x", resume=True)
    assert calls[0] == calls[1] and calls[1]["segments"][1]["speed"] == 2
    assert read_json(directory / "edit-checkpoint.json")["request"]["speed_ranges"][0]["speed"] == 2


def test_api_rejects_bad_speed_and_accepts_speed_only_edit(tmp_path, monkeypatch):
    p, plan = fixture()
    directory = tmp_path / p.name
    write_json(directory / "project.json", p)
    write_json(directory / "latest.json", {"cut": "cut_001", "history": ["cut_001"]})
    monkeypatch.setattr("vlogii.api.edit", lambda *a, **k: None)
    with TestClient(create_app(tmp_path)) as client:
        for body in [
            {"speed": 0},
            {"speed_ranges": [{"start": 0, "end": 1, "speed": 10}]},
            {"instruction": "0-1 to 2x add BGM"},
            {"instruction": "8-2 to 2x"},
            {"instruction": "2-8 to 9x"},
            {"instruction": "删除8秒到2秒"},
        ]:
            assert client.post("/api/vlogii/projects/speed/edit", json=body).status_code in {
                400,
                422,
            }
        assert client.post("/api/vlogii/projects/speed/edit", json={"speed": 2}).status_code == 202


@pytest.mark.media
@pytest.mark.parametrize(
    "speed,audio", [(0.25, True), (0.5, True), (1.5, True), (2, True), (8, True), (4, False)]
)
def test_real_speed_exports_frames_audio_and_pitch(tmp_path, speed, audio):
    from vlogii.media import Tools, inspect_clip
    from vlogii.render import render

    try:
        tools = Tools()
    except VlogiiError:
        pytest.skip("FFmpeg required")
    path = tmp_path / "source.mp4"
    args = ["-f", "lavfi", "-i", "testsrc2=s=96x64:r=30:d=2"]
    if audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2"]
    tools.run(
        args
        + ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        + (["-c:a", "aac", "-shortest"] if audio else [])
        + [str(path)],
        tmp_path / "source.log",
    )
    clip = inspect_clip(tools, path)
    p = Project(
        name="speed",
        clips=[clip],
        settings=Settings(width=96, height=128, color="sdr", encoder="software"),
    )
    plan = Plan(
        title="Speed",
        reasoning="fixture",
        segments=[Segment(clip_id=clip.id, in_sec=0, out_sec=2, speed=speed)],
    )
    reviews = [
        Review(
            clip_id=clip.id, summary="fixture", speech=[Text(start=0.4, end=1.4, text="你好 hello")]
        )
    ]
    directory = tmp_path / "project"
    write_json(directory / "project.json", p)
    out = render(directory, p, plan, reviews)
    t = read_json(out / "timeline.json")
    frames = round(60 / speed)
    assert t["total_frames"] == frames and t["segments"][0]["source_frames"] == 60
    evidence = read_json(out / "verification.json")
    assert evidence["duration"] == pytest.approx(frames / 30, abs=0.05)
    data = tools.probe(out / "film.mp4")
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    assert int(video["nb_frames"]) == frames
    assert next(s for s in data["streams"] if s["codec_type"] == "audio")["sample_rate"] == "48000"
    # Decode waveform to verify actual export tempo preserves source pitch.
    pcm = tmp_path / "audio.raw"
    tools.run(
        ["-i", str(out / "film.mp4"), "-vn", "-f", "f32le", "-ac", "1", "-ar", "48000", str(pcm)],
        tmp_path / "audio.log",
    )
    import array

    samples = array.array("f")
    samples.frombytes(pcm.read_bytes())
    if audio:
        samples = samples[: round(frames / 30 * 48000)]
        samples = samples[round(0.025 * 48000) : min(len(samples), 48000)][::8]

        def energy(frequency):
            real = sum(
                v * math.cos(2 * math.pi * frequency * i / 6000) for i, v in enumerate(samples)
            )
            imaginary = sum(
                v * math.sin(2 * math.pi * frequency * i / 6000) for i, v in enumerate(samples)
            )
            return real * real + imaginary * imaginary

        assert energy(440) > 10 * max(energy(220), energy(880))
    else:
        assert max(abs(v) for v in samples) < 1e-4


def test_flash_cadence_means_output_time_and_captions_remain_disabled(monkeypatch):
    from vlogii.ai import Director

    p, plan = fixture()
    plan.segments[0].out_sec = 0.6
    plan.segments[0].overlays = []
    director = Director.__new__(Director)
    monkeypatch.setattr(director, "_generate", lambda *a: plan)
    reviews = [
        Review(clip_id="one", summary="fixture", speech=[Text(start=0, end=0.5, text="hello")])
    ]
    result = director.plan(p, reviews, "", None, mode="highlights", speed=2)
    assert result.captions is False and result.mute_source_audio is True
    timeline = compile_timeline(p, result, reviews)
    assert timeline.total_frames == 9 and timeline.segments[0].captions == []
    restored = transform_output_ranges(p, result, [], speed=1)
    assert compile_timeline(p, restored, reviews).segments[0].captions == []

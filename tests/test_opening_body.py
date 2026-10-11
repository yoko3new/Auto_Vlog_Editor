"""A silent opening must preserve the complete body and remain editable."""

import array
import math

import pytest

from vlogii.editorial import selection_intent, transform_output_ranges
from vlogii.media import Tools, inspect_clip
from vlogii.models import Clip, Plan, Project, Review, Segment, Settings, Text, TimeRange
from vlogii.pipeline import make_plan
from vlogii.render import render
from vlogii.storage import VlogiiError, write_json
from vlogii.timeline import compile_timeline


def test_speed_transform_keeps_fractional_source_endpoints_inside_the_clip():
    clip = Clip(
        id="a", path="a", sha256="a", duration=6.722, width=96, height=64, fps=60, audio=True
    )
    project = Project(name="day", clips=[clip], settings=Settings(width=96, height=64, fps=30))
    plan = Plan(
        title="Day",
        reasoning="Fixture",
        segments=[Segment(clip_id="a", in_sec=0.018, out_sec=clip.duration)],
    )
    changed = transform_output_ranges(project, plan, [], speed=1)
    assert (changed.segments[0].in_sec, changed.segments[0].out_sec) == (0.018, 6.722)
    assert (
        compile_timeline(project, changed, []).total_frames
        == compile_timeline(project, plan, []).total_frames
    )
    changed = transform_output_ranges(project, plan, [TimeRange(start=1, end=2)], speed=2)
    assert changed.segments[-1].out_sec == clip.duration
    assert all(segment.out_sec <= clip.duration for segment in changed.segments)
    compile_timeline(project, changed, [])


def test_opening_preserves_body_order_and_speed_and_survives_edits(tmp_path, monkeypatch):
    project = Project(
        name="birthday",
        clips=[
            Clip(id=i, path=i, sha256=i, duration=1, width=96, height=64, fps=30, audio=True)
            for i in "abc"
        ],
        settings=Settings(width=96, height=64, color="sdr"),
    )
    reviews = [Review(clip_id=i, summary=i, speech=[Text(start=0, end=1, text=i)]) for i in "abc"]
    for review in reviews:
        write_json(tmp_path / "reviews" / f"{review.clip_id}.json", review)

    class Director:
        def __init__(self, *args):
            pass

        def plan(self, p, r, direction, target, **kwargs):
            assert target == 5 and kwargs["mode"] == "highlights" and kwargs["speed"] == 1
            return Plan(
                title="Birthday weekend",
                reasoning="Fixture",
                segments=[Segment(clip_id=i, in_sec=0.2, out_sec=0.7) for i in "ba"],
            )

        def close(self):
            pass

    monkeypatch.setattr("vlogii.pipeline.Director", Director)
    plan = make_plan(
        tmp_path,
        project,
        "A happy birthday",
        None,
        mode="keep_all",
        speed=2,
        opening_highlights=True,
    )
    assert [s.clip_id for s in plan.segments] == ["b", "a", "a", "b", "c"]
    assert [s.speed for s in plan.segments] == [1, 1, 2, 2, 2]
    assert [(s.in_sec, s.out_sec) for s in plan.segments[2:]] == [(0, 1)] * 3
    assert [s.mute_source_audio for s in plan.segments] == [True, True, False, False, False]
    timeline = compile_timeline(project, plan, reviews)
    assert timeline.total_frames == 75
    assert all(not s.captions for s in timeline.segments[:2])
    assert all(s.captions for s in timeline.segments[2:])
    edited = transform_output_ranges(project, plan, [TimeRange(start=0.25, end=0.75)], speed=1)
    assert [s.mute_source_audio for s in edited.segments] == [True, True, False, False, False]


def test_opening_requires_a_retained_body():
    assert selection_intent("", "keep_all", opening_highlights=True).opening_highlights
    with pytest.raises(VlogiiError, match="Keep everything"):
        selection_intent("", "highlights", opening_highlights=True)


def test_real_export_mutes_only_opening_audio(tmp_path):
    tools = Tools()
    source = tmp_path / "source.mp4"
    tools.run(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=96x64:r=30:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        tmp_path / "source.log",
    )
    clip = inspect_clip(tools, source)
    project = Project(
        name="birthday",
        clips=[clip],
        settings=Settings(width=96, height=64, color="sdr", encoder="software"),
    )
    plan = Plan(
        title="Birthday",
        reasoning="Fixture",
        segments=[
            Segment(clip_id=clip.id, in_sec=0, out_sec=0.5, mute_source_audio=True),
            Segment(clip_id=clip.id, in_sec=0, out_sec=1),
        ],
    )
    version = render(tmp_path, project, plan, [])
    decoded = tmp_path / "audio.pcm"
    tools.run(
        [
            "-i",
            str(version / "film.mp4"),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-f",
            "s16le",
            str(decoded),
        ],
        tmp_path / "audio.log",
    )
    audio = array.array("h", decoded.read_bytes())

    def rms(start, end):
        samples = audio[int(start * 48000) : int(end * 48000)]
        return math.sqrt(sum(x * x for x in samples) / len(samples)) / 32768

    assert rms(0.1, 0.4) < 0.0001
    assert rms(0.7, 1.2) > 0.04

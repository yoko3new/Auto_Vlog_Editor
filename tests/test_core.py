import pytest
from pydantic import ValidationError

from vlogii.models import Clip, Plan, Project, Review, Segment, Settings, Text
from vlogii.pipeline import load_reviews
from vlogii.storage import VlogiiError, locked, project_path, read_json, write_json
from vlogii.timeline import compile_timeline, resolve_color


def project(color="sdr"):
    return Project(
        name="day",
        clips=[
            Clip(
                id="one",
                path="/source.mov",
                sha256="abc",
                duration=4,
                width=100,
                height=100,
                fps=30,
                audio=True,
                color=color,
            )
        ],
    )


def plan(**updates):
    values = dict(clip_id="one", in_sec=1, out_sec=3)
    values.update(updates)
    return Plan(title="Day", reasoning="Test", segments=[Segment(**values)])


def test_timeline_is_frame_based_and_maps_captions():
    review = Review(
        clip_id="one",
        summary="Speech",
        speech=[Text(start=0.5, end=1.5, text="Hello"), Text(start=2.5, end=3.5, text="Bye")],
    )
    result = compile_timeline(project(), plan(), [review])
    assert result.total_frames == 60
    assert result.segments[0].source_start == 30
    assert [(s.start, s.end) for s in result.segments[0].captions] == [(0, 0.5), (1.5, 2)]


@pytest.mark.parametrize(
    "values",
    [
        {"clip_id": "unknown"},
        {"out_sec": 5},
        {"in_sec": 1, "out_sec": 1.001},
        {"overlays": [Text(start=0, end=3, text="Too long")]},
    ],
)
def test_invalid_plan_cannot_reach_renderer(values):
    with pytest.raises(VlogiiError):
        compile_timeline(project(), plan(**values), [])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_nonfinite_or_negative_times_are_rejected(value):
    with pytest.raises(ValidationError):
        Segment(clip_id="one", in_sec=value, out_sec=3)


def test_even_output_dimensions():
    with pytest.raises(ValidationError):
        Settings(width=1081)


def test_auto_preserves_only_all_hlg():
    assert resolve_color(project("hlg")) == "hlg"
    assert resolve_color(project("sdr")) == "sdr"
    mixed = project("hlg")
    mixed.clips.append(project("sdr").clips[0].model_copy(update={"id": "two"}))
    assert resolve_color(mixed) == "sdr"
    mixed.settings.color = "hlg"
    with pytest.raises(VlogiiError):
        resolve_color(mixed)


@pytest.mark.parametrize("name", ["../secret", "/tmp/secret", "a/b", ".", "a b"])
def test_project_path_rejects_traversal(tmp_path, name):
    with pytest.raises(VlogiiError):
        project_path(tmp_path, name)


def test_dead_process_cannot_leave_held_project_lock(tmp_path):
    with locked(tmp_path):
        with pytest.raises(VlogiiError), locked(tmp_path):
            pass
    with locked(tmp_path):
        pass


def test_review_metadata_is_not_loaded_as_review(tmp_path):
    review = Review(clip_id="one", summary="A clip")
    write_json(tmp_path / "reviews/one.json", review)
    write_json(tmp_path / "reviews/one.meta.json", {"sha256": "abc", "model": "test"})
    assert load_reviews(tmp_path) == [review]


def test_atomic_json_refuses_nan_and_keeps_previous_value(tmp_path):
    path = tmp_path / "state.json"
    write_json(path, {"status": "complete"})
    with pytest.raises(ValueError):
        write_json(path, {"duration": float("nan")})
    assert read_json(path) == {"status": "complete"}

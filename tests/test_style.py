import copy
import math
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from vlogii.ai import AiMoment, AiStyleChoice, check_selection, to_selection
from vlogii.api import create_app
from vlogii.media import Tools
from vlogii.models import Clip, Project, Settings
from vlogii.pipeline import edit, initialize, undo
from vlogii.storage import VlogiiError, read_json, write_json
from vlogii.style import beats, film, planner, templates
from vlogii.style.render import fit_text, write_wav

BPM = 100.0
BEAT = 60 / BPM
LEAD = 0.5


def drums(seconds: float, sr: int = 48000) -> np.ndarray:
    """Kick, snare and hats at 100 BPM after a 0.5 s lead-in; stereo float."""
    n = int(seconds * sr)
    out = np.zeros(n)
    rng = np.random.default_rng(3)
    t = np.arange(int(0.2 * sr)) / sr
    kick = np.sin(2 * np.pi * (50 * t + 70 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 18)
    snare = rng.standard_normal(t.size) * np.exp(-t * 30)
    pad_t = np.arange(n) / sr
    out += 0.05 * np.sin(2 * np.pi * 220 * pad_t)
    for k in range(int((seconds - LEAD) / BEAT)):
        i = int((LEAD + k * BEAT) * sr)
        hit = kick * (0.6 if k % 4 == 0 else 0.4) if k % 2 == 0 else snare * 0.25
        out[i : i + hit.size] += hit[: max(0, n - i)]
    out = 0.8 * out / np.abs(out).max()
    return np.stack([out, out], axis=1)


def true_beats(seconds: float) -> np.ndarray:
    return LEAD + np.arange(int((seconds - LEAD) / BEAT)) * BEAT


def test_templates_are_valid_and_reference_profiles_exist():
    ids = [p.stem for p in templates.template_paths()]
    assert ids == ["ig_city_day_in_life", "ig_cozy_night_study", "ig_narrated_college_day"]
    for template_id in ids:
        templates.load(template_id, check_files=True)
    summary = {item["id"]: item for item in templates.summaries()}
    assert summary["ig_narrated_college_day"]["voiceover"] is True
    assert summary["ig_cozy_night_study"]["orientation"] == "portrait"


@pytest.mark.parametrize(
    "change",
    [
        lambda t: t.update(extra=1),
        lambda t: t["sections"][0]["beat_multiples"].append(0.3),
        lambda t: t["sections"].append(copy.deepcopy(t["sections"][0])),
        lambda t: t["text"]["title"]["lines"][0].update(role="missing"),
        lambda t: t["duration"].update(min_s=30),
        lambda t: t["text"]["captions"].update(mode="transcript"),
        lambda t: t["output"].update(width=1280),
        lambda t: t["grade"].update(strength=True),
        lambda t: t.update(source_audio="keep"),
    ],
)
def test_invalid_templates_are_rejected(change):
    template = templates.load("ig_cozy_night_study")
    change(template)
    with pytest.raises(templates.TemplateError):
        templates.validate(template)


def test_unknown_or_unsafe_style_ids_are_rejected():
    for value in ("../secret", "nope_style", "A"):
        with pytest.raises(templates.TemplateError):
            templates.load(value)


def test_beat_tracking_matches_a_known_grid():
    seconds = 24.0
    y = drums(seconds, 22050)[:, 0]
    music = beats.analyze_music(y, 22050)
    assert abs(60 / music["beat_period_s"] - BPM) < 1.5
    found = np.array(music["beats_s"])
    truth = true_beats(seconds)
    nearest = np.abs(found[:, None] - truth[None, :]).min(axis=1)
    assert (nearest <= 0.03).mean() >= 0.9


def test_shot_lengths_fill_sections_exactly_on_the_grid():
    grid = planner.Grid(np.arange(0, 80) * BEAT, 0, 30)
    template = templates.load("ig_city_day_in_life")
    rng = np.random.default_rng(1)
    for section, beats_here in zip(template["sections"], (6.0, 40.0), strict=True):
        lengths = planner.shot_lengths(grid, 0.0, beats_here, section, rng)
        assert math.isclose(sum(lengths), beats_here)
        assert set(lengths) <= set(section["beat_multiples"])
    assert grid.frame(1.5) == round(1.5 * BEAT * 30)


def test_shots_split_over_clips_in_order_within_capacity():
    seconds = [0.9, 0.6, 0.6, 1.2, 0.6, 0.9]
    counts = planner.split_shots(seconds, np.full(3, 2.0), np.full(3, 2.0))
    assert counts is not None and sum(counts) == 6 and min(counts) >= 1
    bounds = np.concatenate([[0], np.cumsum(counts)])
    assert all(sum(seconds[bounds[k] : bounds[k + 1]]) <= 2.0 for k in range(3))
    # Ten one-second shots cannot fit three two-second clips without repeating frames.
    assert planner.split_shots([1.0] * 10, np.full(3, 2.0), np.full(3, 10 / 3)) is None


def test_project_size_must_match_style_orientation():
    template = templates.load("ig_cozy_night_study")
    assert planner.output_for(template, (1080, 1920))["width"] == 1080
    with pytest.raises(planner.PlanError, match="portrait"):
        planner.output_for(template, (1920, 1080))


def test_long_titles_are_broken_and_shrunk_to_fit():
    text, scale = fit_text("A Quiet Sunday Morning In The City", 0.085 * 1920, 1080)
    assert text == "A Quiet Sunday\nMorning In The City" and scale < 1
    assert fit_text("day in\nmy life", 0.06 * 1920, 1080) == ("day in\nmy life", 1.0)


def project(duration=4.0):
    return Project(
        name="day",
        clips=[
            Clip(
                id="one",
                path="/source.mov",
                sha256="abc",
                duration=duration,
                width=1080,
                height=1920,
                fps=30,
                audio=True,
            )
        ],
    )


def test_ai_choice_is_normalised_and_validated():
    choice = AiStyleChoice(
        title="day in my life",
        location=" ",
        moments=[AiMoment(clip_id="one", in_sec=0, out_sec=3, label="Making Coffee")],
    )
    selection = to_selection(choice)
    assert selection.text.location is None
    assert selection.moments[0].label == "making coffee"
    check_selection(project(), selection, 2)
    with pytest.raises(VlogiiError, match="at least"):
        check_selection(project(), selection, 10)
    bad = to_selection(
        AiStyleChoice(moments=[AiMoment(clip_id="two", in_sec=0, out_sec=1, label="")])
    )
    with pytest.raises(VlogiiError, match="unknown clip"):
        check_selection(project(), bad, 0)
    beyond = to_selection(AiStyleChoice(moments=[AiMoment(clip_id="one", in_sec=0, out_sec=9)]))
    with pytest.raises(VlogiiError, match="beyond"):
        check_selection(project(), beyond, 0)


def seed(root, width=1080, height=1920):
    directory = root / "day"
    write_json(
        directory / "project.json",
        project().model_copy(update={"settings": Settings(width=width, height=height)}),
    )
    return directory


def test_style_api_lists_styles_and_checks_music_and_orientation(tmp_path, monkeypatch):
    seed(tmp_path)
    landscape = seed(tmp_path / "wide", 1920, 1080)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        styles = client.get("/api/vlogii/styles").json()
        assert {s["id"] for s in styles} == {
            "ig_city_day_in_life",
            "ig_cozy_night_study",
            "ig_narrated_college_day",
        }
        url = "/api/vlogii/projects/day/generate"
        unknown = client.post(url, json={"style_id": "no_such_style"})
        assert unknown.status_code == 400
        missing = client.post(url, json={"style_id": "ig_cozy_night_study"})
        assert missing.status_code == 400 and "music" in missing.json()["detail"]
        assert client.post(url, json={"style_id": "../x"}).status_code == 422
        not_music = client.post(
            "/api/vlogii/projects/day/music", files={"file": ("notes.txt", b"hi", "text/plain")}
        )
        assert not_music.status_code == 400
        broken = client.post(
            "/api/vlogii/projects/day/music", files={"file": ("song.mp3", b"no", "audio/mpeg")}
        )
        assert broken.status_code == 400
        assert not list((tmp_path / "day" / "music").glob("*"))
    write_json(
        landscape / "music.json",
        {"file": "0" * 32 + ".mp3", "name": "song.mp3", "sha256": "x", "duration": 60},
    )
    with TestClient(create_app(tmp_path / "wide")) as client:
        wrong = client.post(
            "/api/vlogii/projects/day/generate", json={"style_id": "ig_cozy_night_study"}
        )
        assert wrong.status_code == 400 and "portrait" in wrong.json()["detail"]


def test_style_job_runs_without_a_key_and_reports_plan_errors(tmp_path, monkeypatch):
    directory = seed(tmp_path)
    write_json(
        directory / "music.json",
        {"file": "0" * 32 + ".mp3", "name": "song.mp3", "sha256": "x", "duration": 60},
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    def short(*args, **kwargs):
        raise planner.PlanError("Not enough footage: this style needs 10.0s.")

    monkeypatch.setattr("vlogii.api.style_film.generate_style", short)
    with TestClient(create_app(tmp_path)) as client:
        started = client.post(
            "/api/vlogii/projects/day/generate", json={"style_id": "ig_cozy_night_study"}
        )
        assert started.status_code == 202
        for _ in range(200):
            job = read_json(directory / "job.json")
            if job["status"] == "failed":
                break
            time.sleep(0.01)
        assert job["status"] == "failed"
        assert "Not enough footage" in job["message"] and job["retryable"] is False


def test_ai_choice_is_saved_and_reused_on_retry(tmp_path, monkeypatch):
    directory = seed(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    monkeypatch.setattr(film, "analyze", lambda *args, **kwargs: None)
    monkeypatch.setattr(film, "load_reviews", lambda *args, **kwargs: [])
    calls = []

    class Director:
        def __init__(self, evidence):
            pass

        def style_selection(self, project, reviews, template, direction, required):
            calls.append(direction)
            return to_selection(
                AiStyleChoice(
                    title="day in my life",
                    moments=[AiMoment(clip_id="one", in_sec=0, out_sec=3, label="Coffee")],
                )
            )

        def close(self):
            pass

    monkeypatch.setattr("vlogii.ai.Director", Director)
    project_model = Project.model_validate(read_json(directory / "project.json"))
    template = templates.load("ig_cozy_night_study")
    first, ai = film.choose_moments(directory, project_model, template, "", print, resume=False)
    assert ai and first.moments[0].label == "coffee"
    saved = read_json(directory / "style-checkpoint.json")
    assert saved["selection"]["text"]["title"] == "day in my life"
    again, _ = film.choose_moments(directory, project_model, template, "", print, resume=True)
    assert again == first and calls == [""]
    film.choose_moments(directory, project_model, template, "new idea", print, resume=True)
    assert calls == ["", "new idea"]


@pytest.fixture
def tools():
    try:
        result = Tools()
    except VlogiiError:
        pytest.skip("FFmpeg must be installed to run media integration tests.")
    if "ass" not in result.capability("-filters"):
        pytest.skip("FFmpeg needs libass for style titles.")
    return result


@pytest.mark.media
def test_real_style_film_on_the_beat_with_edits_and_undo(tmp_path, tools, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    footage = tmp_path / "footage"
    footage.mkdir()
    for index, colour in enumerate(["red", "blue", "green", "orange", "purple", "teal"]):
        tools.run(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c={colour}:s={'180x320' if index % 2 else '320x180'}:r=30:d=4",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1234:sample_rate=48000:duration=4",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(footage / f"clip_{index}.mp4"),
            ],
            tmp_path / "make.log",
        )
    directory = tmp_path / "day"
    initialize(directory, footage, Settings(width=180, height=320), progress=lambda _: None)
    song = tmp_path / "song.wav"
    write_wav(song, drums(30))
    film.import_music(directory, song)

    first = film.generate_style(directory, "ig_cozy_night_study", "", progress=lambda _: None)
    evidence = read_json(first / "verification.json")
    plan = read_json(first / "style-plan.json")
    assert (evidence["width"], evidence["height"], evidence["pixel_format"]) == (
        180,
        320,
        "yuv420p",
    )
    assert abs(evidence["duration"] - plan["total_frames"] / 30) <= 0.1
    assert plan["checks"]["cuts_on_grid"]
    starts = np.array([s["start_frame"] for s in plan["shots"][1:]]) / 30 + plan["music"]["start_s"]
    halves = LEAD + np.arange(200) * BEAT / 2
    assert np.abs(starts[:, None] - halves[None, :]).min(axis=1).max() <= 0.05
    loudness = evidence["style"]["loudness"]
    assert abs(loudness["integrated_lufs"] - -14) <= 1.0
    assert loudness["true_peak_dbtp"] <= -1.0
    assert read_json(first / "style.json")["ai_selected"] is False

    clip_id = read_json(first / "project.json")["clips"][0]["id"]
    second = edit(directory, "slow sunday", [clip_id], 0.5, progress=lambda _: None)
    request = read_json(second / "style.json")
    assert request["selection"]["text"]["title"] == "slow sunday"
    assert request["excluded"] == [clip_id] and request["warmth"] == 0.5
    assert clip_id not in {s["clip_id"] for s in read_json(second / "style-plan.json")["shots"]}
    with pytest.raises(VlogiiError, match="Style films"):
        edit(directory, None, [], None, progress=lambda _: None, speed=2)
    assert undo(directory) == first.name
    assert (first / "film.mp4").is_file()

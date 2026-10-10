import array
import math

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from vlogii.api import create_app
from vlogii.media import Tools, inspect_clip
from vlogii.models import Appearance, Plan, Project, Review, Segment, Settings, Text
from vlogii.music import mix_music, speech_ranges
from vlogii.pipeline import edit, undo
from vlogii.presets import asset_path, library
from vlogii.render import font_path, render, text_layout
from vlogii.storage import VlogiiError, read_json, write_json


def test_bundled_fonts_cover_text_and_english_presets_fall_back(monkeypatch):
    monkeypatch.delenv("VLOGII_FONT", raising=False)
    assert len(library()["fonts"]) == 6 and len(library()["music"]) == 6
    for preset in (
        "noto-sans",
        "noto-serif",
        "ma-shan-zheng",
        "zcool-xiaowei",
        "caveat",
        "playfair-display",
    ):
        asset_path("fonts", preset)
        text = "今天记录美好时刻。Hello, world!"
        wrapped, _, _, stroke, padding, margin, bbox = text_layout(text, 1080, 1920, True, preset)
        assert "".join(wrapped.split()) == "".join(text.split())
        assert bbox[2] - bbox[0] + 2 * (stroke + padding + margin) <= 1080
    for preset in ("caveat", "playfair-display"):
        assert font_path("Hello", preset) == asset_path("fonts", preset)
        assert font_path("你好 Hello", preset) == asset_path("fonts", "noto-sans")
    with pytest.raises(ValidationError):
        Appearance(music="../../secret")
    for volume in (-1, 1.1, float("nan")):
        with pytest.raises(ValidationError):
            Appearance(music_volume=volume)


def test_preset_api_is_allowlisted_and_does_not_expose_local_paths(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/api/vlogii/presets")
        assert response.status_code == 200
        assert "file" not in response.json()["fonts"][0]
        assert "src/vlogii" not in response.text
        assert len(response.json()["music"]) == 6
        preview = client.get(
            "/api/vlogii/presets/music/holizna-day-jobs", headers={"Range": "bytes=0-100"}
        )
        assert preview.status_code == 206 and len(preview.content) == 101
        assert client.get("/api/vlogii/presets/fonts/caveat").headers["content-type"] == "font/ttf"
        assert client.get("/api/vlogii/presets/unknown/secret").status_code == 404
        assert client.get("/api/vlogii/presets/fonts/unknown").status_code == 404


def samples(tools, media, raw, log):
    tools.run(["-i", str(media), "-vn", "-ac", "1", "-ar", "48000", "-f", "f32le", str(raw)], log)
    data = array.array("f")
    data.frombytes(raw.read_bytes())
    return data


def rms(data, start, end):
    region = data[round(start * 48000) : round(end * 48000)]
    return math.sqrt(sum(value * value for value in region) / len(region))


@pytest.mark.media
def test_music_loops_ducks_and_fades_without_changing_video_duration(tmp_path):
    tools = Tools()
    video = tmp_path / "video.mp4"
    music = tmp_path / "music.wav"
    tools.run(
        [
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=96x64:r=30:d=4",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-t",
            "4",
            str(video),
        ],
        tmp_path / "video.log",
    )
    tools.run(
        ["-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=1", str(music)],
        tmp_path / "music.log",
    )
    results = []
    for index, ranges in enumerate(([], [[1.4, 2.6]])):
        output = tmp_path / f"mixed-{index}.mp4"
        mix_music(
            tools, video, music, output, 4, 0.4, ranges, tmp_path / f"mix-{index}.log", tmp_path
        )
        assert float(tools.probe(output)["format"]["duration"]) == pytest.approx(4, abs=0.1)
        data = samples(tools, output, tmp_path / f"{index}.raw", tmp_path / f"decode-{index}.log")
        results.append(data)
        assert rms(data, 3, 3.3) > 0.01  # Longer than the one-second music source.
        assert rms(data, 0, 0.1) < rms(data, 0.6, 0.9) * 0.4
        assert rms(data, 3.9, 4) < rms(data, 3, 3.3) * 0.4
    assert rms(results[1], 1.8, 2.2) < rms(results[0], 1.8, 2.2) * 0.4
    assert rms(results[1], 2.8, 3.2) == pytest.approx(rms(results[0], 2.8, 3.2), rel=0.1)


@pytest.mark.media
def test_preset_edit_reuses_segments_removes_music_undo_and_failed_mix(tmp_path, monkeypatch):
    tools = Tools()
    source = tmp_path / "source.mp4"
    tools.run(
        ["-f", "lavfi", "-i", "testsrc2=s=96x64:r=30:d=3", "-c:v", "libx264", str(source)],
        tmp_path / "source.log",
    )
    clip = inspect_clip(tools, source)
    project = Project(
        name="presets",
        clips=[clip],
        settings=Settings(width=96, height=128, color="sdr", encoder="software"),
    )
    plan = Plan(
        title="Day",
        reasoning="Synthetic fixture",
        mute_source_audio=True,
        captions=False,
        segments=[Segment(clip_id=clip.id, in_sec=0, out_sec=3)],
    )
    directory = tmp_path / "project"
    write_json(directory / "project.json", project)
    plain = render(directory, project, plan, [])
    assert read_json(plain / "assets.json")["music"] is None
    assert speech_ranges(project, plan, []) == []
    mixed = edit(directory, None, [], None, appearance=Appearance(music="auto", font="noto-serif"))
    assert not (
        mixed / "logs" / "segment-0000.log"
    ).exists()  # Font changes do not invalidate textless video.
    assert read_json(mixed / "assets.json")["music"]["id"] == "holizna-dancing"
    assert read_json(mixed / "plan.json")["mute_source_audio"] is True
    muted = edit(directory, None, [], None, appearance=Appearance(music="none", font="noto-serif"))
    data = samples(tools, muted / "film.mp4", tmp_path / "silent.raw", tmp_path / "silent.log")
    assert max(abs(value) for value in data) < 1e-6
    assert undo(directory) == mixed.name
    before = read_json(directory / "latest.json")
    original = Tools.run
    calls = []

    def fail_mix(self, args, log, **kwargs):
        calls.append(log.name)
        if log.name == "music.log":
            raise VlogiiError("Injected mix failure")
        return original(self, args, log, **kwargs)

    monkeypatch.setattr(Tools, "run", fail_mix)
    with pytest.raises(VlogiiError, match="Injected"):
        edit(directory, None, [], None, appearance=Appearance(music="holizna-dreams"))
    assert read_json(directory / "latest.json") == before
    assert (mixed / "film.mp4").is_file()
    monkeypatch.setattr(Tools, "run", original)
    recovered = edit(
        directory, None, [], None, resume=True, appearance=Appearance(music="holizna-dreams")
    )
    assert read_json(recovered / "assets.json")["music"]["id"] == "holizna-dreams"
    assert not (recovered / "logs" / "segment-0000.log").exists()


def test_duck_ranges_follow_speed_and_trimmed_speech():
    from vlogii.models import Clip

    clip = Clip(
        id="one",
        path="/unused",
        sha256="test",
        duration=10,
        width=96,
        height=64,
        fps=30,
        audio=True,
    )
    project = Project(name="timing", clips=[clip])
    plan = Plan(
        title="Day",
        reasoning="Fixture",
        segments=[Segment(clip_id="one", in_sec=2, out_sec=6, speed=2)],
    )
    review = Review(clip_id="one", summary="Fixture", speech=[Text(start=3, end=5, text="Hello")])
    assert speech_ranges(project, plan, [review])[0] == pytest.approx([0.4, 1.7])


def test_api_retry_preserves_appearance_and_old_clients_keep_music_off(tmp_path, monkeypatch):
    import time

    from vlogii.models import Clip

    directory = tmp_path / "day"
    project = Project(
        name="day",
        clips=[
            Clip(
                id="one",
                path="/unused",
                sha256="test",
                duration=1,
                width=96,
                height=64,
                fps=30,
                audio=False,
            )
        ],
    )
    write_json(directory / "project.json", project)
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    calls = []

    def generate(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise VlogiiError("Injected failure")

    monkeypatch.setattr("vlogii.api.generate", generate)

    def finish():
        for _ in range(200):
            job = read_json(directory / "job.json")
            if job["status"] in {"failed", "complete"}:
                return job
            time.sleep(0.01)
        raise AssertionError("Job did not finish")

    selected = Appearance(
        font="caveat", music="holizna-childhood", music_volume=0.24, duck_music=False
    )
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/vlogii/projects/day").json()["appearance"]["music"] == "none"
        assert (
            client.post(
                "/api/vlogii/projects/day/generate", json={"appearance": selected.model_dump()}
            ).status_code
            == 202
        )
        assert finish()["status"] == "failed"
        assert client.post("/api/vlogii/projects/day/retry").status_code == 202
        assert finish()["status"] == "complete"
        assert calls[0]["appearance"] == calls[1]["appearance"] == selected
        assert calls[1]["resume"] is True
        assert (
            client.post(
                "/api/vlogii/projects/day/generate", json={"appearance": {"font": "unknown"}}
            ).status_code
            == 422
        )

"""Cover layout, immutable publication and player-to-body edits on real exports."""

import copy

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from vlogii.api import create_app
from vlogii.chapters import version_chapters
from vlogii.cover import body_ranges, poster
from vlogii.media import Tools, inspect_clip
from vlogii.models import (
    ChapterEdit,
    Cover,
    Plan,
    Project,
    Review,
    Segment,
    Settings,
    Text,
    TimeRange,
)
from vlogii.pipeline import edit, undo
from vlogii.render import render
from vlogii.storage import VlogiiError, read_json, write_json


def fixture(tmp_path):
    tools = Tools()
    source = tmp_path / "source.mp4"
    tools.run(
        ["-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=3", "-c:v", "libx264", str(source)],
        tmp_path / "source.log",
    )
    clip = inspect_clip(tools, source)
    project = Project(
        name="day",
        clips=[clip],
        settings=Settings(width=320, height=568, color="sdr", encoder="software"),
    )
    plan = Plan(
        title="A day outside",
        reasoning="Fixture",
        captions=False,
        segments=[Segment(clip_id=clip.id, in_sec=0, out_sec=3)],
    )
    review = Review(
        clip_id=clip.id,
        summary="Colorful scene",
        highlights=[Text(start=0, end=3, text="Colorful scene")],
    )
    directory = tmp_path / "day"
    write_json(directory / "project.json", project)
    write_json(directory / "reviews" / f"{clip.id}.json", review)
    version = render(directory, project, plan, [review], lambda _: None)
    return tools, directory, project, version, review


def test_cover_validation_and_player_range_protection(tmp_path):
    with pytest.raises(ValidationError):
        Cover(title="   ")
    with pytest.raises(ValidationError):
        Cover(title="Day", frame_seconds=float("nan"))
    write_json(tmp_path / "cover.json", {"intro_seconds": 1})
    with pytest.raises(VlogiiError, match="cover editor"):
        body_ranges(tmp_path, [TimeRange(start=0.5, end=2)], [])
    removed, _ = body_ranges(tmp_path, [TimeRange(start=1, end=2)], [])
    assert removed == [TimeRange(start=0, end=1)]


@pytest.mark.media
def test_cover_versions_do_not_stack_and_refinement_uses_shifted_chapters(tmp_path, monkeypatch):
    tools, directory, project, original, review = fixture(tmp_path)
    first = edit(
        directory,
        None,
        [],
        None,
        cover=Cover(
            title="山间徒步",
            subtitle="A peaceful day",
            kicker="5:01 AM – 6:22 PM",
            style="playful",
            frame_seconds=1.4,
        ),
    )
    assert not (first / "logs" / "segment-0000.log").exists()
    assert Image.open(first / "cover.png").size == (320, 568)
    assert read_json(first / "verification.json")["duration"] == pytest.approx(4, abs=0.1)
    chapters = version_chapters(first, [review])
    assert [(c.start, c.end, c.kind) for c in chapters] == [(0, 1, "cover"), (1, 4, "scene")]
    second = edit(
        directory,
        None,
        [],
        None,
        cover=Cover(title="An ordinary day", font="playfair-display", frame_seconds=1.4),
    )
    assert read_json(second / "verification.json")["duration"] == pytest.approx(4, abs=0.1)
    assert len(version_chapters(second, [review])) == 2
    assert read_json(second / "timeline.json") == read_json(original / "timeline.json")
    shortened = edit(
        directory,
        None,
        [],
        None,
        chapter_edits=[ChapterEdit(chapter_index=1, action="remove_range", start=0, end=0.5)],
        base_cut=second.name,
    )
    assert read_json(shortened / "cover.json")["body_duration_seconds"] == pytest.approx(2.5)
    assert read_json(shortened / "plan.json")["segments"][0]["in_sec"] == pytest.approx(0.5)
    with pytest.raises(VlogiiError, match="cover editor"):
        edit(
            directory, None, [], None, chapter_edits=[ChapterEdit(chapter_index=0, action="remove")]
        )
    detached = edit(
        directory,
        None,
        [],
        None,
        cover=Cover(title="Still a cover", frame_seconds=99, show_intro=False),
    )
    assert (detached / "cover.png").exists()
    assert read_json(detached / "verification.json")["duration"] == pytest.approx(2.5, abs=0.1)
    assert read_json(detached / "cover.json")["frame_seconds"] < 2.5
    assert version_chapters(detached, [review])[0].start == 0
    assert undo(directory) == shortened.name
    before = read_json(directory / "latest.json")
    original_run = Tools.run

    def fail_intro(self, args, log, **kwargs):
        if log.name == "cover-intro.log":
            raise VlogiiError("Injected intro failure")
        return original_run(self, args, log, **kwargs)

    monkeypatch.setattr(Tools, "run", fail_intro)
    with pytest.raises(VlogiiError, match="Injected"):
        edit(directory, None, [], None, cover=Cover(title="Retry me"))
    assert read_json(directory / "latest.json") == before
    assert (shortened / "film.mp4").exists()
    monkeypatch.setattr(Tools, "run", original_run)
    retried = edit(directory, None, [], None, cover=Cover(title="Retry me"), resume=True)
    assert read_json(retried / "cover.json")["settings"]["title"] == "Retry me"
    assert read_json(retried / "verification.json")["duration"] == pytest.approx(3.5, abs=0.1)


@pytest.mark.media
@pytest.mark.parametrize("size", [(320, 568), (568, 320)])
def test_cover_layout_fits_long_bilingual_titles_without_clipping(tmp_path, size):
    tools, _, project, version, _ = fixture(tmp_path)
    project.settings.width, project.settings.height = size
    cover = Cover(
        title="山间漫步，记录平凡生活中值得珍藏的美好时刻 · A peaceful ordinary day worth keeping",
        subtitle="路过的风景与日常 / Slow down and remember the little things",
        kicker="5:01 AM – 6:22 PM",
        font="playfair-display",
        style="editorial",
        frame_seconds=0.4,
    )
    report = poster(
        tools,
        version / "film.mp4",
        tmp_path / "poster.png",
        cover,
        project,
        3,
        "sdr",
        tmp_path,
        tmp_path,
    )
    assert Image.open(tmp_path / "poster.png").size == size
    assert len(report["text"]) == 3
    assert report["text"][1]["lines"] >= 2
    for text in report["text"]:
        x, y, right, bottom = text["bounds"]
        assert x >= size[0] * 0.08 and right <= size[0] * 0.92
        assert y >= 0 and bottom <= size[1]
    assert report["text"][1]["font_file"].startswith("NotoSans")


@pytest.mark.media
def test_cover_api_preview_changes_no_version_and_downloads_completed_image(tmp_path):
    _, directory, _, version, _ = fixture(tmp_path)
    before = copy.deepcopy(read_json(directory / "latest.json"))
    app = create_app(tmp_path, tmp_path / "no-ui")
    with TestClient(app) as client:
        payload = {
            "base_cut": version.name,
            "cover": {"title": "Mountain hike", "style": "playful"},
        }
        response = client.post("/api/vlogii/projects/day/cover/preview", json=payload)
        assert response.status_code == 200 and response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")
        assert read_json(directory / "latest.json") == before
        cached = client.post("/api/vlogii/projects/day/cover/preview", json=payload)
        assert cached.content == response.content
        payload["base_cut"] = "cut_000"
        assert (
            client.post("/api/vlogii/projects/day/cover/preview", json=payload).status_code == 400
        )
        assert client.get("/api/vlogii/projects/day/cuts/cut_001/cover.png").status_code == 404
        edited = edit(directory, None, [], None, cover=Cover(title="Mountain hike"))
        view = client.get("/api/vlogii/projects/day").json()
        assert view["film_title"] == "A day outside"
        assert view["settings"]["cover"]["show_intro"] is True
        image = client.get(view["cover_url"] + "?download=true")
        assert image.status_code == 200 and "attachment" in image.headers["content-disposition"]
        assert edited.name in view["cover_url"]
        assert (
            client.post(
                "/api/vlogii/projects/day/edit",
                json={"chapter_edits": [{"chapter_index": 0, "action": "remove"}]},
            ).status_code
            == 400
        )


@pytest.mark.media
def test_cover_preserves_hlg_metadata_and_fixed_frame_count(tmp_path):
    tools = Tools()
    path = tmp_path / "hdr.mp4"
    tools.run(
        [
            "-f",
            "lavfi",
            "-i",
            "color=white:s=96x128:r=30:d=1",
            "-c:v",
            "libx265",
            "-pix_fmt",
            "yuv420p10le",
            "-x265-params",
            "colorprim=9:transfer=18:colormatrix=9:range=limited:pools=1",
            str(path),
        ],
        tmp_path / "hdr.log",
    )
    clip = inspect_clip(tools, path)
    project = Project(
        name="hdr",
        clips=[clip],
        settings=Settings(
            width=96,
            height=128,
            encoder="software",
            cover=Cover(title="HDR", font="playfair-display"),
        ),
    )
    plan = Plan(
        title="HDR",
        reasoning="Fixture",
        captions=False,
        segments=[Segment(clip_id=clip.id, in_sec=0, out_sec=0.5)],
    )
    directory = tmp_path / "hdr"
    write_json(directory / "project.json", project)
    version = render(directory, project, plan, [], lambda _: None)
    report = read_json(version / "verification.json")
    assert report["pixel_format"] == "yuv420p10le"
    assert report["color_transfer"] == "arib-std-b67"
    assert report["duration"] == pytest.approx(1.5, abs=0.1)
    video = next(
        s for s in tools.probe(version / "film.mp4")["streams"] if s["codec_type"] == "video"
    )
    assert video["nb_frames"] == "45" and video["r_frame_rate"] == "30/1"

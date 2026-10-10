import pytest

from vlogii.media import Tools, build_proxy, inspect_clip
from vlogii.models import Plan, Project, Review, Segment, Settings, Text
from vlogii.pipeline import edit, undo
from vlogii.render import render
from vlogii.storage import VlogiiError, read_json, write_json


@pytest.fixture
def tools():
    try:
        result = Tools()
    except VlogiiError:
        pytest.skip("FFmpeg must be installed to run media integration tests.")
    return result


@pytest.fixture
def source(tmp_path, tools):
    path = tmp_path / "footage ' one.mp4"
    tools.run(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=96x64:r=30:d=1.2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=1.2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        tmp_path / "source.log",
    )
    return path


@pytest.mark.media
@pytest.mark.parametrize("encoder", ["software", "auto"])
def test_real_text_captions_edits_undo_and_failed_export(
    tmp_path, tools, source, encoder, monkeypatch
):
    clip = inspect_clip(tools, source)
    project = Project(
        name="test",
        clips=[clip],
        settings=Settings(width=96, height=128, encoder=encoder, color="sdr"),
    )
    plan = Plan(
        title="Day",
        reasoning="Synthetic integration fixture",
        segments=[
            Segment(
                clip_id=clip.id,
                in_sec=0,
                out_sec=1,
                overlays=[Text(start=0, end=0.5, text="It's 100%: a [test] \\ day")],
            )
        ],
    )
    reviews = [
        Review(
            clip_id=clip.id,
            summary="Synthetic video",
            speech=[Text(start=0.1, end=0.8, text="你好，今天做早餐。Hello, world")],
        )
    ]
    directory = tmp_path / "project ' quoted"
    directory.mkdir()
    write_json(directory / "project.json", project)
    write_json(directory / "reviews" / f"{clip.id}.json", reviews[0])
    first = render(directory, project, plan, reviews)
    assert read_json(first / "verification.json")["pixel_format"] == "yuv420p"
    second = edit(directory, "Slow Sunday", [], 0.5)
    assert read_json(second / "project.json")["settings"]["warmth"] == 0.5
    assert read_json(second / "plan.json")["title"] == "Slow Sunday"
    assert undo(directory) == first.name
    before = read_json(directory / "latest.json")
    monkeypatch.setattr(
        Tools, "run", lambda *a, **k: (_ for _ in ()).throw(VlogiiError("Injected render failure"))
    )
    with pytest.raises(VlogiiError):
        render(directory, project, plan, reviews)
    assert read_json(directory / "latest.json") == before
    assert (first / "film.mp4").is_file()


@pytest.mark.media
def test_real_hlg_10bit_and_silent_clip(tmp_path, tools):
    path = tmp_path / "hdr.mp4"
    tools.run(
        [
            "-f",
            "lavfi",
            "-i",
            "color=white:s=64x64:r=30:d=1",
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
    assert clip.color == "hlg" and not clip.audio
    project = Project(
        name="hdr", clips=[clip], settings=Settings(width=64, height=64, encoder="software")
    )
    plan = Plan(
        title="HDR",
        reasoning="Synthetic",
        segments=[Segment(clip_id=clip.id, in_sec=0, out_sec=0.5)],
    )
    directory = tmp_path / "project"
    directory.mkdir()
    output = render(directory, project, plan, [])
    evidence = read_json(output / "verification.json")
    assert evidence["pixel_format"] == "yuv420p10le"
    assert evidence["color_transfer"] == "arib-std-b67"
    assert evidence["audio_codec"] == "aac"


@pytest.mark.media
def test_changed_source_is_rejected_before_render(tmp_path, tools, source):
    clip = inspect_clip(tools, source)
    project = Project(name="test", clips=[clip])
    plan = Plan(
        title="Test", reasoning="Test", segments=[Segment(clip_id=clip.id, in_sec=0, out_sec=1)]
    )
    source.write_bytes(b"changed")
    with pytest.raises(VlogiiError, match="changed"):
        render(tmp_path, project, plan, [])


def test_cjk_wrapping_and_missing_font_is_actionable(tmp_path, monkeypatch):
    from vlogii.render import draw_text, wrapped_text

    monkeypatch.delenv("VLOGII_FONT", raising=False)
    monkeypatch.setattr("vlogii.render.FONT_CANDIDATES", ())
    assert wrapped_text("早" * 20) == "早" * 16 + "\n" + "早" * 4
    with pytest.raises(VlogiiError, match="CJK captions"):
        draw_text(Text(start=0, end=1, text="你好"), tmp_path / "text.txt", 1920, True)


@pytest.mark.media
def test_retry_reuses_completed_segments_and_short_sources(tmp_path, tools, source, monkeypatch):
    clip = inspect_clip(tools, source)
    assert clip.duration < 5
    build_proxy(tools, clip, tmp_path / "short-proxy.mp4")
    assert float(tools.probe(tmp_path / "short-proxy.mp4")["format"]["duration"]) < 5
    project = Project(
        name="test",
        clips=[clip],
        settings=Settings(width=96, height=128, encoder="software", color="sdr"),
    )
    plan = Plan(
        title="Test",
        reasoning="Two segments",
        segments=[
            Segment(clip_id=clip.id, in_sec=0, out_sec=0.5),
            Segment(clip_id=clip.id, in_sec=0.5, out_sec=1),
        ],
    )
    directory = tmp_path / "project"
    directory.mkdir()
    original = Tools.run
    calls = []
    fail = True

    def run(self, args, log, **kwargs):
        calls.append(log.name)
        if fail and log.name == "segment-0001.log":
            raise VlogiiError("Injected second-segment failure")
        return original(self, args, log, **kwargs)

    monkeypatch.setattr(Tools, "run", run)
    with pytest.raises(VlogiiError):
        render(directory, project, plan, [])
    assert len(list((directory / "render-cache").glob("*.mp4"))) == 1
    fail = False
    output = render(directory, project, plan, [])
    assert calls.count("segment-0000.log") == 1
    assert calls.count("segment-0001.log") == 2
    assert read_json(output / "state.json")["status"] == "complete"


def test_auto_encoder_falls_back_when_hardware_session_is_unusable(monkeypatch):
    from types import SimpleNamespace

    tools = Tools.__new__(Tools)
    tools.ffmpeg = "/unused"
    monkeypatch.setattr(tools, "capability", lambda _: {"h264_videotoolbox", "libx264"})
    monkeypatch.setattr(
        "vlogii.media.subprocess.run", lambda *a, **k: SimpleNamespace(returncode=1)
    )
    assert tools.encoder("sdr", "auto") == "libx264"

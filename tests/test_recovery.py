import argparse
import json
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from vlogii import pipeline
from vlogii.api import create_app
from vlogii.cli import execute, run_with_retry
from vlogii.models import Clip, Plan, Project, Review, Segment
from vlogii.speech import caption_entries, transcription_request, transcription_words
from vlogii.storage import VlogiiError, project_path, read_json, write_json


def seed(root, audio=False):
    directory = root / "周末"
    project = Project(
        name="周末",
        clips=[
            Clip(
                id="one",
                path="/unused.mov",
                sha256="abc",
                duration=1.2,
                width=96,
                height=64,
                fps=30,
                audio=audio,
            )
        ],
    )
    write_json(directory / "project.json", project)
    return directory, project


def finished(directory):
    for _ in range(200):
        job = read_json(directory / "job.json")
        if job["status"] in {"failed", "complete"}:
            return job
        time.sleep(0.01)
    raise AssertionError("Worker did not finish")


@pytest.mark.parametrize("kind", ["generate", "edit"])
def test_retry_keeps_request_kind_and_old_success(tmp_path, monkeypatch, kind):
    directory, _ = seed(tmp_path)
    write_json(directory / "latest.json", {"cut": "cut_001", "history": ["cut_001"]})
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    calls = []

    def action(*args, **kwargs):
        calls.append((args[1:], kwargs["resume"]))
        if len(calls) == 1:
            raise VlogiiError("Injected failure")

    monkeypatch.setattr(f"vlogii.api.{kind}", action)
    request = (
        {"direction": "保留中文原声", "target_seconds": 30, "language": "zh"}
        if kind == "generate"
        else {"title": "我的周末", "exclude_clip_ids": ["one"], "warmth": 0.4, "language": "zh"}
    )
    with TestClient(create_app(tmp_path)) as client:
        first = client.post(f"/api/vlogii/projects/周末/{kind}", json=request)
        assert first.status_code == 202
        assert "request" not in first.json() and "resume" not in first.json()
        assert finished(directory)["retryable"]
        view = client.get("/api/vlogii/projects/周末").json()
        assert view["job"]["kind"] == kind
        assert "request" not in view["job"]
        assert client.post("/api/vlogii/projects/周末/retry").status_code == 202
        assert finished(directory)["status"] == "complete"
        assert calls[0][0] == calls[1][0] and calls[0][1] is False and calls[1][1] is True
        assert client.post("/api/vlogii/projects/周末/retry").status_code == 409
        assert read_json(directory / "latest.json")["cut"] == "cut_001"


def test_restart_restores_retry_payload(tmp_path, monkeypatch):
    directory, _ = seed(tmp_path)
    write_json(
        directory / "job.json",
        {
            "id": "old",
            "status": "running",
            "message": "Working",
            "kind": "generate",
            "request": {"direction": "中文", "target_seconds": 60},
        },
    )
    calls = []
    monkeypatch.setattr("vlogii.api.generate", lambda *a, **k: calls.append((a, k)))
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/vlogii/projects/周末").json()["job"]["retryable"]
        assert client.post("/api/vlogii/projects/周末/retry").status_code == 202
        assert finished(directory)["status"] == "complete"
    assert calls[0][0][1:] == ("中文", 60) and calls[0][1]["resume"]


def test_generation_retry_reuses_plan_but_new_direction_replans(tmp_path, monkeypatch):
    directory, project = seed(tmp_path)
    write_json(directory / "reviews/one.json", Review(clip_id="one", summary="Fixture"))
    calls = {"plan": 0, "render": 0}
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: None)

    def make_plan(*args, **kwargs):
        calls["plan"] += 1
        return Plan(
            title="周末",
            reasoning="Fixture",
            segments=[Segment(clip_id="one", in_sec=0, out_sec=1)],
        )

    def render(*args):
        calls["render"] += 1
        if calls["render"] == 1:
            raise VlogiiError("Injected render failure")
        path = directory / f"cuts/cut_{calls['render']:03}"
        path.mkdir(parents=True)
        (path / "film.mp4").write_bytes(b"fixture")
        return path

    monkeypatch.setattr(pipeline, "make_plan", make_plan)
    monkeypatch.setattr(pipeline, "render", render)
    with pytest.raises(VlogiiError):
        pipeline.generate(directory, "中文", 30)
    output = pipeline.generate(directory, "中文", 30, resume=True)
    assert calls == {"plan": 1, "render": 2}
    assert pipeline.generate(directory, "中文", 30, resume=True) == output
    assert calls == {"plan": 1, "render": 2}
    pipeline.generate(directory, "换个重点", 30, resume=True)
    assert calls == {"plan": 2, "render": 3}


def test_speech_failure_preserves_visual_cache(tmp_path, monkeypatch):
    directory, project = seed(tmp_path, audio=True)
    calls = {"visual": 0, "speech": 0}

    class Director:
        def __init__(self, *args):
            pass

        def close(self):
            pass

        def review(self, *a, **k):
            assert k["transcribe_speech"] is False
            calls["visual"] += 1
            return Review(clip_id="one", summary="Fixture")

    def speech(*args):
        calls["speech"] += 1
        if calls["speech"] == 1:
            raise VlogiiError("Injected speech failure")
        return []

    monkeypatch.setattr(pipeline, "Director", Director)
    monkeypatch.setattr(pipeline, "Tools", lambda: SimpleNamespace())
    monkeypatch.setattr(pipeline, "build_proxy", lambda *a: None)
    monkeypatch.setattr(pipeline, "transcribe", speech)
    with pytest.raises(VlogiiError):
        pipeline.analyze(directory, project)
    pipeline.analyze(directory, project)
    pipeline.analyze(directory, project)
    assert calls == {"visual": 1, "speech": 2}
    monkeypatch.setenv("VLOGII_SPEECH_LANGUAGE", "en-US")
    pipeline.analyze(directory, project)
    assert calls == {"visual": 1, "speech": 3}


def test_cli_retries_chinese_request_in_same_process(tmp_path, monkeypatch):
    calls = []

    def generate(*a, **k):
        calls.append((a[1:3], k["resume"]))
        if len(calls) == 1:
            raise VlogiiError("Injected failure")

    monkeypatch.setattr("vlogii.cli.generate", generate)
    monkeypatch.setattr("builtins.input", lambda _: "是")
    args = argparse.Namespace(
        command="run",
        projects=tmp_path,
        name="周末",
        language="zh",
        direction="保留早餐",
        seconds=30,
    )
    assert run_with_retry(lambda resume: execute(args, resume), "zh", True)
    assert calls == [(("保留早餐", 30), False), (("保留早餐", 30), True)]
    assert project_path(tmp_path, "周末") == tmp_path.resolve() / "周末"
    for name in ["../escape", "a/b", ".."]:
        with pytest.raises(VlogiiError):
            project_path(tmp_path, name)


def test_cli_retry_after_restart_repeats_edit_not_generate(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("vlogii.cli.edit", lambda *a, **k: calls.append((a, k)))
    args = argparse.Namespace(
        command="edit",
        projects=tmp_path,
        name="周末",
        language="zh",
        title="新的标题",
        exclude_clip_ids=["one"],
        warmth=0.4,
    )
    execute(args)
    execute(argparse.Namespace(command="retry", projects=tmp_path, name="周末", language="zh"))
    assert calls[0][0] == calls[1][0]
    assert calls[0][1]["resume"] is False and calls[1][1]["resume"] is True


def test_transcribe_rest_contract_retries_without_thinking(tmp_path, monkeypatch):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            429 if len(seen) == 1 else 200, json={"status": "completed", "steps": []}
        )

    factory = httpx.Client
    monkeypatch.setattr(
        "vlogii.speech.httpx.Client",
        lambda **k: factory(transport=httpx.MockTransport(handler), **k),
    )
    monkeypatch.setattr("vlogii.speech.time.sleep", lambda _: None)
    config = {"model": "gemini-3.5-transcribe", "language": "auto"}
    result = transcription_request("test-uri", config, "placeholder")
    assert result["status"] == "completed" and len(seen) == 2
    assert seen[0] == seen[1]
    assert seen[0]["generation_config"] == {
        "transcription_config": {"mode": {"type": "verbatim", "timestamp_granularities": ["word"]}}
    }
    assert seen[0]["store"] is False


def test_transcribe_auth_failure_is_not_retried(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": "private details"})

    factory = httpx.Client
    monkeypatch.setattr(
        "vlogii.speech.httpx.Client",
        lambda **k: factory(transport=httpx.MockTransport(handler), **k),
    )
    with pytest.raises(VlogiiError, match="HTTP 401") as exc:
        transcription_request(
            "test-uri", {"model": "gemini-3.5-transcribe", "language": "auto"}, "placeholder"
        )
    assert len(calls) == 1 and "private details" not in str(exc.value)


def test_word_annotations_keep_bilingual_text_and_validate_timings():
    annotations = [
        {
            "type": "word_info",
            "text": text,
            "start_offset": f"{i * 0.2}s",
            "end_offset": f"{(i + 1) * 0.2}s",
        }
        for i, text in enumerate(["Hello", "world", "你好", "。"])
    ]
    result = {
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"text": "Hello world你好。", "annotations": annotations}],
            }
        ],
    }
    entries = caption_entries(transcription_words(result), 1)
    assert entries[0].text == "Hello world你好。"
    assert entries[0].start == 0 and entries[0].end == 0.8
    annotations[0]["start_offset"] = "NaNs"
    with pytest.raises(VlogiiError):
        caption_entries(transcription_words(result), 1)
    with pytest.raises(VlogiiError, match="without timestamps"):
        transcription_words({"status": "completed", "output_text": "你好", "steps": []})
    with pytest.raises(VlogiiError):
        caption_entries([{"type": "word", "text": "bad", "start": 0, "end": 2}], 1)


def test_invalid_word_timings_retry_and_keep_raw_evidence(tmp_path, monkeypatch):
    from vlogii.speech import timed_transcription

    def response(start):
        return {
            "status": "completed",
            "steps": [
                {
                    "type": "model_output",
                    "content": [
                        {
                            "text": "Birthday",
                            "annotations": [
                                {
                                    "type": "word_info",
                                    "text": "Birthday",
                                    "start_offset": f"{start}s",
                                    "end_offset": "0.8s",
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    calls = []
    responses = iter([response(-0.2), response(0.1)])

    def request(*args):
        calls.append(args)
        return next(responses)

    monkeypatch.setattr("vlogii.speech.transcription_request", request)
    monkeypatch.setattr("vlogii.speech.time.sleep", lambda _: None)
    evidence = tmp_path / "clip.json"
    entries = timed_transcription("audio", {}, "placeholder", 1, evidence)
    assert len(calls) == 2
    assert [(entry.start, entry.end, entry.text) for entry in entries] == [(0.1, 0.8, "Birthday")]
    assert read_json(tmp_path / "clip-0.json") == response(-0.2)
    assert read_json(evidence) == response(0.1)

    calls.clear()
    monkeypatch.setattr(
        "vlogii.speech.transcription_request", lambda *args: calls.append(args) or response(-0.2)
    )
    with pytest.raises(VlogiiError, match="after three attempts"):
        timed_transcription("audio", {}, "placeholder", 1, evidence)
    assert len(calls) == 3


def test_one_tick_word_inversion_preserves_text_and_phrase_boundaries():
    words = [
        {"type": "word", "text": "A ", "start": 0.8, "end": 0.9},
        {"type": "word", "text": "birthday ", "start": 1.3, "end": 1.2},
        {"type": "word", "text": "wish.", "start": 1.2, "end": 1.3},
    ]
    entries = caption_entries(words, 2)
    assert [(entry.start, entry.end, entry.text) for entry in entries] == [
        (0.8, 1.3, "A birthday wish.")
    ]
    words[1]["start"] = 1.4
    with pytest.raises(VlogiiError, match="invalid timestamps"):
        caption_entries(words, 2)
    words[1].update(start=1.4, end=1.5)
    with pytest.raises(VlogiiError, match="out-of-order"):
        caption_entries(words, 2)


@pytest.mark.parametrize("size", [(1080, 1920), (1920, 1080), (96, 128)])
def test_caption_layout_keeps_all_characters_inside_video(size):
    from vlogii.render import text_layout

    text = (
        "今天我们一起出去走走，记录沿途风景。" * 6
        + "Hello world, every word should remain visible."
    )
    wrapped, _, _, stroke, padding, margin, bbox = text_layout(text, *size, True)
    assert "".join(wrapped.split()) == "".join(text.split())
    assert bbox[2] - bbox[0] + 2 * (stroke + padding + margin) <= size[0]
    assert bbox[3] - bbox[1] <= size[1] * 0.34 + 1

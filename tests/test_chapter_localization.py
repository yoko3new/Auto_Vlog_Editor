"""Display language is cached independently of immutable timing and source analysis."""

import pytest
from fastapi.testclient import TestClient

from vlogii.ai import ChapterTextTranslation, Director
from vlogii.api import create_app
from vlogii.chapters import version_chapters
from vlogii.localization import localize_chapters
from vlogii.models import Chapter, Clip, Plan, Project, Segment
from vlogii.storage import VlogiiError, locked, read_json, write_json
from vlogii.timeline import compile_timeline


def fake_director(monkeypatch):
    calls = []

    class Translator:
        def __init__(self, evidence):
            pass

        def translate_chapter_text(self, texts, language):
            calls.append((texts, language))
            return {key: "中文说明：" + text for key, text in texts.items()}

        def close(self):
            pass

    monkeypatch.setattr("vlogii.localization.Director", Translator)
    return calls


def scene(start=0):
    return Chapter(
        start=start,
        end=start + 1,
        title="Chicken in skillet",
        summary="Cooking chicken.",
        clip_ids=["a"],
    )


def test_display_translations_deduplicate_and_survive_time_changes_and_restart(
    tmp_path, monkeypatch
):
    calls = fake_director(monkeypatch)
    original = [scene(), scene(1)]
    before = [c.model_dump() for c in original]
    localized = localize_chapters(tmp_path, original, "zh")
    assert len(calls) == 1 and len(calls[0][0]) == 2
    assert all(c.title.startswith("中文说明") for c in localized)
    assert [c.model_dump() for c in original] == before
    assert [(c.start, c.end, c.clip_ids) for c in localized] == [(0, 1, ["a"]), (1, 2, ["a"])]
    # No provider is needed to reuse translations after an edit or server restart.
    monkeypatch.setattr(
        "vlogii.localization.Director", lambda *a: pytest.fail("Cached text must not call Gemini")
    )
    again = localize_chapters(tmp_path, [scene(5)], "zh")
    assert again[0].start == 5 and again[0].title == localized[0].title
    english = localize_chapters(tmp_path, original, "en")
    assert english == original


def test_chinese_analysis_is_translated_in_english_mode(tmp_path, monkeypatch):
    calls = []

    class Translator:
        def __init__(self, evidence):
            pass

        def translate_chapter_text(self, texts, language):
            calls.append(language)
            return {key: "Cooking chicken" for key in texts}

        def close(self):
            pass

    monkeypatch.setattr("vlogii.localization.Director", Translator)
    chapter = Chapter(start=0, end=1, title="炒鸡肉", summary="在锅里炒鸡肉")
    translated = localize_chapters(tmp_path, [chapter], "en")
    assert translated[0].title == "Cooking chicken" and calls == ["en"]
    assert chapter.title == "炒鸡肉"


@pytest.mark.parametrize("invalid", ["missing", "empty", "english"])
def test_incomplete_provider_response_never_becomes_a_cached_success(
    tmp_path, monkeypatch, invalid
):
    class Translator:
        def __init__(self, evidence):
            pass

        def translate_chapter_text(self, texts, language):
            if invalid == "missing":
                return {}
            return {key: "" if invalid == "empty" else text for key, text in texts.items()}

        def close(self):
            pass

    monkeypatch.setattr("vlogii.localization.Director", Translator)
    with pytest.raises(VlogiiError, match="incomplete"):
        localize_chapters(tmp_path, [scene()], "zh")
    assert not list((tmp_path / "chapter-locales").rglob("*.json"))


def test_director_rejects_duplicate_keys_even_if_the_set_matches():
    director = object.__new__(Director)
    director._generate = lambda *args: ChapterTextTranslation(
        items=[{"key": "a", "text": "标题"}, {"key": "a", "text": "重复"}]
    )
    with pytest.raises(VlogiiError, match="mismatched"):
        director.translate_chapter_text({"a": "Title"}, "zh")


def seed(root):
    directory = root / "day"
    project = Project(
        name="day",
        clips=[
            Clip(
                id="a",
                path="/private/clip.mp4",
                sha256="a",
                duration=1,
                width=96,
                height=64,
                fps=30,
                audio=False,
            )
        ],
    )
    plan = Plan(
        title="Day",
        reasoning="Fixture",
        captions=False,
        segments=[Segment(clip_id="a", in_sec=0, out_sec=1, purpose="Cooking chicken")],
    )
    version = directory / "cuts/cut_001"
    write_json(directory / "project.json", project)
    write_json(version / "project.json", project)
    write_json(version / "plan.json", plan)
    write_json(version / "timeline.json", compile_timeline(project, plan, []))
    write_json(directory / "latest.json", {"cut": "cut_001", "history": ["cut_001"]})
    return directory, version


def test_api_translation_is_additive_and_keeps_film_time_and_ids(tmp_path, monkeypatch):
    fake_director(monkeypatch)
    directory, version = seed(tmp_path)
    original = version_chapters(version, [])
    with TestClient(create_app(tmp_path)) as client:
        response = client.post(
            "/api/vlogii/projects/day/chapters/localize",
            json={"language": "zh", "base_cut": "cut_001"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["chapters"][0]["title"].startswith("中文说明")
        assert data["cut"] == "cut_001" and data["language"] == "zh"
        assert data["chapters"][0]["start"] == 0 and data["chapters"][0]["end"] == 1
        assert data["chapters"][0]["clip_ids"] == ["a"]
        assert str(tmp_path) not in response.text
        assert (
            client.post(
                "/api/vlogii/projects/day/chapters/localize",
                json={"language": "zh", "base_cut": "cut_000"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/vlogii/projects/day/chapters/localize",
                json={"language": "fr", "base_cut": "cut_001"},
            ).status_code
            == 422
        )
        # Existing project responses remain backward-compatible, with original chapter text.
        assert (
            client.get("/api/vlogii/projects/day").json()["chapters"][0]["title"]
            == "Cooking chicken"
        )
    assert version_chapters(version, []) == original
    assert not (directory / "job.json").exists()
    assert read_json(directory / "latest.json")["cut"] == "cut_001"


def test_concurrent_request_can_wait_for_translation_without_starting_a_render(tmp_path):
    directory, _ = seed(tmp_path)
    with locked(directory / "chapter-locales"), TestClient(create_app(tmp_path)) as client:
        response = client.post(
            "/api/vlogii/projects/day/chapters/localize",
            json={"language": "zh", "base_cut": "cut_001"},
        )
        assert response.status_code == 409 and "already running" in response.json()["detail"]
    assert not (directory / "job.json").exists()


def test_translation_failure_preserves_the_successful_film_and_can_retry(tmp_path, monkeypatch):
    directory, version = seed(tmp_path)
    latest = read_json(directory / "latest.json")
    plan = read_json(version / "plan.json")

    def fail(*args):
        raise VlogiiError("Could not translate chapter text. Retry translation.")

    monkeypatch.setattr("vlogii.api.localize_chapters", fail)
    with TestClient(create_app(tmp_path)) as client:
        body = {"language": "zh", "base_cut": "cut_001"}
        assert (
            client.post("/api/vlogii/projects/day/chapters/localize", json=body).status_code == 400
        )
        assert read_json(directory / "latest.json") == latest
        assert read_json(version / "plan.json") == plan
        monkeypatch.setattr(
            "vlogii.api.localize_chapters", lambda directory, chapters, language: chapters
        )
        assert (
            client.post("/api/vlogii/projects/day/chapters/localize", json=body).status_code == 200
        )
    assert not (directory / "job.json").exists()

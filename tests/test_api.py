import time

from fastapi.testclient import TestClient

from vlogii.api import create_app
from vlogii.models import Clip, Project
from vlogii.storage import read_json, write_json


def seed(root):
    directory = root / "day"
    project = Project(
        name="day",
        clips=[
            Clip(
                id="one",
                path="/private/secret.mov",
                sha256="abc",
                duration=1,
                width=64,
                height=64,
                fps=30,
                audio=False,
            )
        ],
    )
    write_json(directory / "project.json", project)
    return directory


def test_api_does_not_expose_source_paths_and_persists_restart_status(tmp_path):
    directory = seed(tmp_path)
    write_json(directory / "job.json", {"id": "old", "status": "running", "message": "Working"})
    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/api/vlogii/projects/day")
        assert response.status_code == 200
        assert "/private/secret.mov" not in response.text
        assert response.json()["job"]["status"] == "failed"
        assert client.get("/api/vlogii/projects/day/cuts/../film.mp4").status_code == 404
        assert client.get("/api/vlogii/projects/day/cuts/cut_001/film.mp4").status_code == 404


def test_no_key_is_explicit_and_generate_validation_is_enforced(tmp_path, monkeypatch):
    seed(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        assert client.post("/api/vlogii/projects/day/generate", json={}).status_code == 400
        assert (
            client.post(
                "/api/vlogii/projects/day/generate", json={"target_seconds": 1801}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/vlogii/projects",
                data={"name": "../escape"},
                files={"files": ("bad.mp4", b"invalid", "video/mp4")},
            ).status_code
            == 400
        )


def test_failed_job_keeps_old_success_and_can_be_retried(tmp_path, monkeypatch):
    directory = seed(tmp_path)
    write_json(directory / "latest.json", {"cut": "cut_001", "history": ["cut_001"]})
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")

    def fail(*args, **kwargs):
        raise RuntimeError("Injected provider failure")

    monkeypatch.setattr("vlogii.api.generate", fail)
    with TestClient(create_app(tmp_path)) as client:
        for _ in range(2):
            assert client.post("/api/vlogii/projects/day/generate", json={}).status_code == 202
            for _ in range(100):
                if read_json(directory / "job.json")["status"] == "failed":
                    break
                time.sleep(0.01)
            assert read_json(directory / "job.json")["status"] == "failed"
        assert read_json(directory / "latest.json")["cut"] == "cut_001"

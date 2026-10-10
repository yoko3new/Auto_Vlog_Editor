"""A local-only FastAPI application with persistent status and one render worker."""

import os
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from .models import Model, Settings
from .pipeline import EXTENSIONS, edit, generate, initialize, load_project, undo
from .storage import VlogiiError, locked, project_path, read_json, write_json


class GenerateRequest(Model):
    direction: str = Field(default="A calm chronological diary of my day.", max_length=2000)
    target_seconds: int = Field(default=30, ge=5, le=300)
    language: Literal["en", "zh"] = "en"


class EditRequest(Model):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    exclude_clip_ids: list[str] = Field(default_factory=list, max_length=50)
    warmth: float | None = Field(default=None, ge=0, le=1)
    language: Literal["en", "zh"] = "en"


class WebClip(Model):
    id: str
    name: str
    duration: float


class JobState(Model):
    id: str
    status: Literal["queued", "running", "complete", "failed"]
    message: str
    error: str | None = None
    retryable: bool = False
    kind: Literal["generate", "edit"] | None = None


class VersionHistory(Model):
    cut: str
    history: list[str]


class ProjectView(Model):
    name: str
    clips: list[WebClip]
    settings: Settings
    job: JobState | None
    latest: VersionHistory | None
    video_url: str | None
    duration_seconds: float | None


def public_job(job):
    return {key: value for key, value in job.items() if key in JobState.model_fields}


def create_app(root: Path | None = None, frontend: Path | None = None) -> FastAPI:
    root = (root or Path(os.environ.get("VLOGII_PROJECTS", "projects"))).resolve()
    frontend = frontend or Path(__file__).resolve().parents[2] / "frontend" / "dist"
    gate = threading.Lock()
    executor = None

    @asynccontextmanager
    async def lifespan(app):
        nonlocal executor
        root.mkdir(parents=True, exist_ok=True)
        with locked(root / ".server"):
            # A restart makes interrupted work explicit; old successful exports remain playable.
            for path in root.glob("*/job.json"):
                job = read_json(path)
                if job.get("status") in {"queued", "running"}:
                    write_json(
                        path,
                        {
                            **job,
                            "status": "failed",
                            "message": "Interrupted by server restart. Retry generation.",
                            "error": "Interrupted by server restart. Retry generation.",
                            "retryable": bool(job.get("request")),
                        },
                    )
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vlogii")
            try:
                yield
            finally:
                executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="Vlogii Local API", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(VlogiiError)
    async def friendly_error(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=400, content={"detail": str(exc)})

    def existing(name):
        directory = project_path(root, name)
        if not (directory / "project.json").is_file():
            raise HTTPException(404, "Project not found.")
        return directory

    def describe(directory):
        project = load_project(directory)
        latest = (
            read_json(directory / "latest.json") if (directory / "latest.json").exists() else None
        )
        job = read_json(directory / "job.json") if (directory / "job.json").exists() else None
        names = (
            read_json(directory / "upload-names.json")
            if (directory / "upload-names.json").exists()
            else {}
        )
        return {
            "name": project.name,
            "clips": [
                {
                    "id": c.id,
                    "name": names.get(Path(c.path).name, Path(c.path).name),
                    "duration": c.duration,
                }
                for c in project.clips
            ],
            "settings": project.settings.model_dump(),
            "job": public_job(job) if job else None,
            "latest": latest,
            "duration_seconds": (
                read_json(directory / "cuts" / latest["cut"] / "verification.json").get("duration")
                if latest and (directory / "cuts" / latest["cut"] / "verification.json").is_file()
                else None
            ),
            "video_url": f"/api/vlogii/projects/{project.name}/cuts/{latest['cut']}/film.mp4"
            if latest
            else None,
        }

    @app.get("/api/vlogii/health")
    def health():
        from .speech import speech_config

        return {
            "status": "ok",
            "api_version": "vlogii.local.v1",
            "ai_configured": bool(
                os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            ),
            "video_model": os.environ.get("VLOGII_MODEL", "gemini-3.8-flash"),
            "speech": speech_config(),
            "speech_configured": bool(
                os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            ),
        }

    @app.get("/api/vlogii/projects", response_model=list[ProjectView])
    def projects():
        return [describe(path.parent) for path in sorted(root.glob("*/project.json"))]

    @app.post("/api/vlogii/projects", status_code=201, response_model=ProjectView)
    def upload(
        name: Annotated[str, Form()],
        files: Annotated[list[UploadFile], File()],
        orientation: Annotated[str, Form()] = "portrait",
        color: Annotated[str, Form()] = "sdr",
    ):
        directory = project_path(root, name)
        if (directory / "project.json").exists():
            raise HTTPException(409, "Project name already exists.")
        if not 1 <= len(files) <= 50:
            raise HTTPException(400, "Choose 1-50 video clips.")
        if orientation not in {"portrait", "landscape"} or color not in {"sdr", "auto"}:
            raise HTTPException(400, "Unsupported output settings.")
        folder = directory / "uploads"
        with locked(directory):
            if (directory / "project.json").exists():
                raise HTTPException(409, "Project name already exists.")
            folder.mkdir(exist_ok=True)
            saved = []
            names = {}
            total = 0
            try:
                for index, file in enumerate(files):
                    suffix = Path(file.filename or "").suffix.lower()
                    if suffix not in EXTENSIONS:
                        raise HTTPException(400, "Upload MP4, MOV, M4V or MKV files.")
                    path = folder / (f"{index:03d}_" + uuid.uuid4().hex + suffix)
                    saved.append(path)
                    size = 0
                    with path.open("wb") as output:
                        while chunk := file.file.read(1024 * 1024):
                            size += len(chunk)
                            total += len(chunk)
                            if size > 512 * 1024**2 or total > 2 * 1024**3:
                                raise HTTPException(
                                    413, "Limit: 512 MB per clip and 2 GB per project."
                                )
                            output.write(chunk)
                    names[path.name] = Path(file.filename or path.name).name
                settings = Settings(
                    width=1080 if orientation == "portrait" else 1920,
                    height=1920 if orientation == "portrait" else 1080,
                    color=color,
                )
                initialize(directory, folder, settings, progress=lambda _: None)
                write_json(directory / "upload-names.json", names)
            except BaseException:
                for path in saved:
                    path.unlink(missing_ok=True)
                raise
            finally:
                for file in files:
                    file.file.close()
        return describe(directory)

    @app.get("/api/vlogii/projects/{name}", response_model=ProjectView)
    def project(name: str):
        return describe(existing(name))

    def worker(directory, request, job):
        def progress(message):
            write_json(
                directory / "job.json",
                {**job, "status": "running", "message": message, "error": None},
            )

        try:
            if isinstance(request, EditRequest):
                edit(
                    directory,
                    request.title,
                    request.exclude_clip_ids,
                    request.warmth,
                    progress=progress,
                    resume=job.get("resume", False),
                )
            else:
                generate(
                    directory,
                    request.direction,
                    request.target_seconds,
                    progress=progress,
                    resume=job.get("resume", False),
                )
            write_json(
                directory / "job.json",
                {
                    **job,
                    "status": "complete",
                    "message": "Your film is ready.",
                    "error": None,
                    "retryable": False,
                },
            )
        except Exception as exc:
            # Private logs hold diagnostics; the browser receives an actionable summary.
            write_json(
                directory / "last-error.json", {"type": type(exc).__name__, "message": str(exc)}
            )
            message = "Generation failed. Previous films are preserved. Check the server terminal or retry."
            if isinstance(exc, VlogiiError) and "GEMINI_API_KEY" in str(exc):
                message = "Set GEMINI_API_KEY in the server's .env file and restart."
            elif isinstance(exc, VlogiiError):
                if "Gemini" in str(exc) and "speech" in str(exc).lower():
                    message = "Speech recognition failed. Check the Gemini connection, key, quota and speech model, then retry."
                elif "Gemini" in str(exc):
                    message = "Video analysis or planning failed. Check the Gemini connection, key and quota, then retry."
                elif "font" in str(exc).lower():
                    message = (
                        "A caption font is missing. Set VLOGII_FONT to a suitable font, then retry."
                    )
                elif "Keep at least" in str(exc):
                    message = (
                        "Keep at least one selected clip. Change the selection and apply again."
                    )
            print(f"Vlogii job failed: {exc}", flush=True)
            write_json(
                directory / "job.json",
                {
                    **job,
                    "status": "failed",
                    "message": message,
                    "error": message,
                    "retryable": "Keep at least" not in str(exc),
                },
            )

    def enqueue(directory, request, retry_job_id=None):
        with gate:
            job_path = directory / "job.json"
            if retry_job_id is not None and (
                not job_path.exists()
                or read_json(job_path).get("id") != retry_job_id
                or read_json(job_path).get("status") != "failed"
            ):
                raise HTTPException(409, "The failed task changed. Refresh the project.")
            if job_path.exists() and read_json(job_path).get("status") in {"queued", "running"}:
                raise HTTPException(409, "This project is already generating.")
            if executor is None:
                raise HTTPException(503, "Worker is unavailable.")
            active = sum(
                read_json(path).get("status") in {"queued", "running"}
                for path in root.glob("*/job.json")
            )
            if active >= 8:
                raise HTTPException(429, "Queue is full. Wait for a film to finish.")
            job = {
                "id": uuid.uuid4().hex,
                "status": "queued",
                "message": "Waiting to start.",
                "error": None,
                "kind": "edit" if isinstance(request, EditRequest) else "generate",
                "retryable": False,
                "request": request.model_dump(mode="json"),
                "resume": retry_job_id is not None,
            }
            write_json(job_path, job)
            executor.submit(worker, directory, request, job)
        return public_job(job)

    @app.post("/api/vlogii/projects/{name}/generate", status_code=202, response_model=JobState)
    def start(name: str, request: GenerateRequest):
        directory = existing(name)
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise HTTPException(400, "Set GEMINI_API_KEY in .env and restart the server.")
        return enqueue(directory, request)

    @app.post("/api/vlogii/projects/{name}/retry", status_code=202, response_model=JobState)
    def retry_job(name: str):
        directory = existing(name)
        job_path = directory / "job.json"
        job = read_json(job_path) if job_path.exists() else {}
        if job.get("status") != "failed" or not job.get("retryable") or not job.get("request"):
            raise HTTPException(409, "No retryable task. Start generation or apply a new edit.")
        model = EditRequest if job.get("kind") == "edit" else GenerateRequest
        request = model.model_validate(job["request"])
        return enqueue(directory, request, retry_job_id=job["id"])

    @app.post("/api/vlogii/projects/{name}/edit", status_code=202, response_model=JobState)
    def edit_film(name: str, request: EditRequest):
        directory = existing(name)
        if not (directory / "latest.json").exists():
            raise HTTPException(400, "Generate a film before editing.")
        if request.title is None and request.warmth is None and not request.exclude_clip_ids:
            raise HTTPException(400, "Choose at least one change.")
        return enqueue(directory, request)

    @app.post("/api/vlogii/projects/{name}/undo", response_model=ProjectView)
    def undo_version(name: str):
        directory = existing(name)
        if (directory / "job.json").exists() and read_json(directory / "job.json").get(
            "status"
        ) in {"queued", "running"}:
            raise HTTPException(409, "Wait for generation to finish before undoing.")
        undo(directory)
        return describe(directory)

    @app.get("/api/vlogii/projects/{name}/cuts/{cut}/film.mp4")
    def film(name: str, cut: str, download: bool = False):
        if not re.fullmatch(r"cut_\d{3,}", cut):
            raise HTTPException(404, "Film not found.")
        directory = existing(name) / "cuts" / cut
        if (
            not (directory / "state.json").exists()
            or read_json(directory / "state.json").get("status") != "complete"
        ):
            raise HTTPException(404, "Film is not ready.")
        path = directory / "film.mp4"
        if not path.is_file():
            raise HTTPException(404, "Film file is missing.")
        return FileResponse(
            path, media_type="video/mp4", filename=f"{name}-{cut}.mp4" if download else None
        )

    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    else:

        @app.get("/")
        def missing_frontend():
            return {
                "message": "Build the frontend: cd frontend && npm ci && npm run build",
                "api_docs": "/docs",
            }

    return app

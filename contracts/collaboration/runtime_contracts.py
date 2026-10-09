"""A/B handoff types. Implementations belong to the application, not this kit.

Only RenderStub below is implemented. It is explicitly simulated and cannot
establish that FFmpeg, layout, persistence, or production deployment works.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
import shutil

JsonObject = dict[str, Any]


class ModuleError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


@dataclass(frozen=True)
class RenderProgress:
    completed_frames: int
    total_frames: int
    message: str


@dataclass(frozen=True)
class RenderRequest:
    timeline_document: JsonObject  # Entire timeline.json envelope, not just shots.
    asset_paths: Mapping[str, Path]  # Materialized video, audio, font and image IDs.
    work_dir: Path                 # Private to this job, owned/cleaned by A.
    output_path: Path              # Temporary MP4 path, never an existing version.
    timeout_seconds: float
    is_cancelled: Callable[[], bool]


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    width: int
    height: int
    fps: int
    duration_frames: int
    simulation: bool


class Renderer(Protocol):
    def render_timeline(self, request: RenderRequest,
                        on_progress: Callable[[RenderProgress], None]) -> RenderResult:
        """Blocking call from the worker thread. Raise ModuleError on failure.

        B must terminate FFmpeg on timeout/cancel, honor exact timeline timing,
        inspect real output metadata, and set simulation=False only for real work.
        The callback reports local progress; A writes jobs and versions.
        """
        ...


@dataclass(frozen=True)
class TitleLayoutRequest:
    title: Mapping[str, str]       # eyebrow/headline/tagline after user overrides.
    style_id: str
    style_revision: int
    output: JsonObject            # Schema Output object.
    display_frames: int           # min(90, final duration_frames).
    asset_paths: Mapping[str, Path]


class TitleLayouter(Protocol):
    def layout_title(self, request: TitleLayoutRequest) -> list[JsonObject]:
        """Return validated Overlay objects with measured text/rect/font sizes.

        Called by A before freezing timeline.json. B later rasterizes these
        overlays exactly, without selecting new text, fonts, line breaks or layout.
        No network, project writes, or version creation inside this operation.
        Missing font / unsupported glyph / overflow raises ModuleError.
        """
        ...


class RenderStub:
    """Copies an explicitly provided test file; performs NO video processing.

    Enable only in local isolated tests. Result dimensions are simulated from the
    request, not measured. Do not publish a stub result as a real generated film.
    """
    def __init__(self, fixture_media: Path | None = None, fail: bool = False):
        self.fixture_media, self.fail = fixture_media, fail

    def render_timeline(self, request: RenderRequest,
                        on_progress: Callable[[RenderProgress], None]) -> RenderResult:
        if request.is_cancelled():
            raise ModuleError('JOB_INTERRUPTED', '模拟：任务已取消', True)
        if self.fail:
            raise ModuleError('RENDER_FAILED', '模拟：用于检查队列释放的渲染失败', True)
        if self.fixture_media is None or not self.fixture_media.is_file():
            raise ModuleError('FIXTURE_MEDIA_MISSING', '请提供本地测试文件；契约包未包含媒体')
        if request.output_path.exists():
            raise ModuleError('OUTPUT_EXISTS', '模拟渲染也不覆盖已有输出')
        t = request.timeline_document['timeline']
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        on_progress(RenderProgress(0, t['duration_frames'], '模拟渲染开始'))
        shutil.copyfile(self.fixture_media, request.output_path)
        on_progress(RenderProgress(t['duration_frames'], t['duration_frames'], '模拟复制结束'))
        o=t['output']
        return RenderResult(request.output_path, o['width'], o['height'], o['fps'], t['duration_frames'], True)

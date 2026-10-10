"""Atomic local storage and a single-writer project lock."""

import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel


class VlogiiError(Exception):
    """An actionable failure that the CLI can report without a traceback."""


def project_path(root: Path, name: str) -> Path:
    if not re.fullmatch(r"[^\W_][\w-]{0,63}", name):
        raise VlogiiError(
            "Use a project name with 1-64 Chinese or English letters, numbers, '-' or '_'."
        )
    return root.resolve() / name


def write_json(path: Path, value: BaseModel | dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VlogiiError(f"Cannot read {path.name}: {exc}") from exc


@contextmanager
def locked(project: Path):
    """Use OS locks: a terminated process cannot leave a stale held lock."""
    import fcntl

    project.mkdir(parents=True, exist_ok=True)
    with (project / ".lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise VlogiiError("This project is already busy in another process.") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)

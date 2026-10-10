"""Bundled, licensed presets shared by browser previews and the renderer."""

from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont

from .media import sha256
from .models import Music
from .storage import VlogiiError, read_json

ASSETS = Path(__file__).parent / "assets"


def manifest():
    return read_json(ASSETS / "manifest.json")


def asset(kind: str, identifier: str):
    entry = next((item for item in manifest().get(kind, []) if item["id"] == identifier), None)
    if entry is None:
        raise VlogiiError("Unknown preset. Choose a bundled font or music track.")
    return entry


def asset_path(kind: str, identifier: str, verify_hash=True) -> Path:
    entry = asset(kind, identifier)
    path = ASSETS / entry["file"]
    if not path.is_file() or (verify_hash and sha256(path) != entry["sha256"]):
        raise VlogiiError("A bundled preset is missing or changed. Restore the application assets.")
    return path


def library():
    return {
        kind: [
            {
                **{
                    k: v
                    for k, v in entry.items()
                    if k
                    in {
                        "id",
                        "name",
                        "source",
                        "license",
                        "sha256",
                        "bytes",
                        "author",
                        "duration_seconds",
                    }
                },
                "url": f"/api/vlogii/presets/{kind}/{entry['id']}",
            }
            for entry in manifest()[kind]
        ]
        for kind in ("fonts", "music")
    }


def music_id(choice: str, muted: bool) -> str | None:
    if choice == "none":
        return None
    if choice == "auto":
        # A small deterministic default, not an AI mood or beat analysis.
        return "holizna-dancing" if muted else "holizna-day-jobs"
    asset("music", choice)
    return choice


@lru_cache(maxsize=16)
def glyphs(path: str, modified: int, size: int):
    with TTFont(path, lazy=True, fontNumber=0) as font:
        return frozenset(font.getBestCmap() or {})


def supports_text(path: Path, text: str) -> bool:
    stat = path.stat()
    supported = glyphs(str(path), stat.st_mtime_ns, stat.st_size)
    return all(char.isspace() or ord(char) in supported for char in text)


def music_source(project_dir: Path, choice: str, muted: bool):
    if choice == "uploaded":
        metadata = project_dir / "music.json"
        if not metadata.exists():
            raise VlogiiError("Add a music track before making a style film.")
        track = Music.model_validate(read_json(metadata))
        path = project_dir / "music" / track.file
        if not path.is_file() or sha256(path) != track.sha256:
            raise VlogiiError(
                "The music file for this version is missing or changed. Add the music again."
            )
        return choice, path, track
    identifier = music_id(choice, muted)
    if identifier is None:
        return None, None, None
    entry = asset("music", identifier)
    return (
        identifier,
        asset_path("music", identifier),
        Music(
            file=entry["sha256"][:32] + ".mp3",
            name=entry["name"],
            sha256=entry["sha256"],
            duration=entry["duration_seconds"],
        ),
    )

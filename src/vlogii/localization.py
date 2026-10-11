"""Cached display translations, separate from render plans and original speech."""

import hashlib
import re
from pathlib import Path
from typing import Literal

from pydantic import Field

from .ai import Director
from .models import Chapter, Model
from .storage import VlogiiError, locked, read_json, write_json


class LocalizeChaptersRequest(Model):
    language: Literal["en", "zh"]
    base_cut: str = Field(pattern=r"^cut_\d{3,}$")


class LocalizedChapters(Model):
    cut: str
    language: Literal["en", "zh"]
    chapters: list[Chapter]


def chinese(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def localize_chapters(directory: Path, chapters: list[Chapter], language: str):
    texts = {}
    for chapter in chapters:
        for text in (chapter.title, chapter.summary):
            # Existing English metadata needs no request in English mode.
            if text.strip() and (language == "zh" or chinese(text)):
                key = hashlib.sha256(("v1:" + language + ":" + text).encode()).hexdigest()
                texts[key] = text
    if not texts:
        return chapters
    cache = directory / "chapter-locales"
    translated = {}
    with locked(cache):
        missing = {}
        for key, text in texts.items():
            path = cache / language / f"{key}.json"
            saved = read_json(path) if path.exists() else {}
            if isinstance(saved.get("text"), str) and saved["text"].strip():
                translated[key] = saved["text"]
            else:
                missing[key] = text
        if missing:
            director = Director(directory / "ai-evidence")
            try:
                entries = list(missing.items())
                for offset in range(0, len(entries), 32):
                    batch = dict(entries[offset : offset + 32])
                    result = director.translate_chapter_text(batch, language)
                    if result.keys() != batch.keys() or any(
                        not text.strip()
                        or (
                            language == "zh"
                            and not chinese(text)
                            and re.search(r"[A-Za-z]", batch[key])
                        )
                        for key, text in result.items()
                    ):
                        raise VlogiiError(
                            "Chapter translation returned incomplete text. Retry translation."
                        )
                    for key, text in result.items():
                        write_json(cache / language / f"{key}.json", {"text": text})
                    translated.update(result)
            finally:
                director.close()

    def translated_text(text):
        key = hashlib.sha256(("v1:" + language + ":" + text).encode()).hexdigest()
        return translated.get(key, text)

    return [
        chapter.model_copy(
            update={
                "title": translated_text(chapter.title),
                "summary": translated_text(chapter.summary),
            }
        )
        for chapter in chapters
    ]

"""Dedicated speech recognition, independent of visual understanding."""

import math
import os
import time
from pathlib import Path

import httpx

from .media import Tools
from .models import Clip, Text
from .storage import VlogiiError, write_json


def speech_config():
    return {
        "provider": "gemini",
        "model": os.environ.get("VLOGII_SPEECH_MODEL", "gemini-3.5-transcribe"),
        "language": os.environ.get("VLOGII_SPEECH_LANGUAGE", "auto"),
        "revision": 2,
    }


def caption_entries(words: list[dict], duration: float) -> list[Text]:
    """Build short, timed captions without inventing sentence-wide timings."""
    entries, group = [], []

    def flush():
        if not group:
            return
        text = "".join(w["text"] for w in group).strip()
        start, end = group[0]["start"], group[-1]["end"]
        if text and end > start:
            entries.append(Text(start=start, end=end, text=text))
        group.clear()

    previous_end = 0.0
    for word in words:
        if word.get("type") not in {"word", "spacing"}:
            continue
        text = word.get("text", "")
        if not isinstance(text, str):
            raise VlogiiError("Speech provider returned invalid text.")
        start, end = word.get("start"), word.get("end")
        if start is None or end is None:
            if word.get("type") == "spacing" and group:
                group[-1]["text"] += text
                continue
            raise VlogiiError("Speech provider did not return word timestamps.")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise VlogiiError("Speech provider returned invalid timestamps.")
        if not math.isfinite(start) or not math.isfinite(end) or end < start or start < 0:
            raise VlogiiError("Speech provider returned invalid timestamps.")
        if end > duration + 0.25 or start < previous_end - 0.05:
            raise VlogiiError("Speech provider returned out-of-order or out-of-range timestamps.")
        start, end = min(start, duration), min(end, duration)
        if group and (
            start - previous_end > 0.6
            or end - group[0]["start"] > 3.5
            or sum(len(w["text"]) for w in group) + len(text) > 64
        ):
            flush()
        group.append({"text": text, "start": start, "end": end})
        previous_end = end
        if text.rstrip().endswith(("。", "！", "？", ".", "!", "?")):
            flush()
    flush()
    return entries


def offset_seconds(value):
    if isinstance(value, str) and value.endswith("s"):
        value = value[:-1]
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise VlogiiError("Gemini returned an invalid speech timestamp.") from exc


def transcription_words(result: dict) -> list[dict]:
    if result.get("status") != "completed":
        raise VlogiiError("Gemini speech transcription did not complete. Retry this step.")
    words = []
    for step in result.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for content in step.get("content", []):
            for annotation in content.get("annotations", []):
                if annotation.get("type") != "word_info":
                    continue
                text = annotation.get("text", "")
                if words and text and words[-1]["text"] and text[0].isascii() and text[0].isalnum():
                    if words[-1]["text"][-1].isascii() and words[-1]["text"][-1].isalnum():
                        words[-1]["text"] += " "
                words.append(
                    {
                        "type": "word",
                        "text": text,
                        "start": offset_seconds(annotation.get("start_offset")),
                        "end": offset_seconds(annotation.get("end_offset")),
                    }
                )
    # A non-empty untimed transcript must never silently produce blank captions.
    has_text = result.get("output_text") or any(
        content.get("text", "").strip()
        for step in result.get("steps", [])
        for content in step.get("content", [])
    )
    if has_text and not words:
        raise VlogiiError(
            "Gemini returned speech without timestamps. Retry or select another speech model."
        )
    return words


def transcription_request(uri: str, config: dict, key: str) -> dict:
    transcription = {"mode": {"type": "verbatim", "timestamp_granularities": ["word"]}}
    if config["language"] != "auto":
        transcription["language_codes"] = [config["language"]]
    body = {
        "model": config["model"],
        "input": [{"type": "audio", "uri": uri, "mime_type": "audio/wav"}],
        "generation_config": {"transcription_config": transcription},
        "store": False,
    }
    for attempt in range(3):
        try:
            with httpx.Client(timeout=180) as client:
                response = client.post(
                    "https://generativelanguage.googleapis.com/v1beta/interactions",
                    headers={"x-goog-api-key": key},
                    json=body,
                )
            if (response.status_code == 429 or response.status_code >= 500) and attempt < 2:
                time.sleep(2**attempt)
                continue
            if response.is_error:
                raise VlogiiError(
                    f"Gemini speech request failed (HTTP {response.status_code}). "
                    "Check the key, quota and speech model availability, then retry."
                )
            result = response.json()
            if not isinstance(result, dict):
                raise VlogiiError("Gemini returned an invalid speech response.")
            return result
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt == 2:
                raise VlogiiError("Gemini speech connection failed. Retry this step.") from exc
            time.sleep(2**attempt)
        except ValueError as exc:
            raise VlogiiError(
                "Gemini returned an invalid speech response. Retry this step."
            ) from exc
    raise VlogiiError("Gemini speech recognition failed.")


def transcribe(clip: Clip, directory: Path, config: dict) -> list[Text]:
    if not clip.audio:
        return []
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise VlogiiError("Set GEMINI_API_KEY in .env before speech recognition.")
    audio = directory / "audio" / f"{clip.id}.wav"
    audio.parent.mkdir(parents=True, exist_ok=True)
    if not audio.is_file():
        pending = audio.with_suffix(".pending.wav")
        Tools().run(
            [
                "-i",
                clip.path,
                "-vn",
                "-map",
                "0:a:0",
                "-ac",
                "1",
                "-ar",
                "48000",
                "-c:a",
                "pcm_s16le",
                str(pending),
            ],
            audio.with_suffix(".ffmpeg.log"),
        )
        pending.replace(audio)
    from google.genai import types

    from .ai import Director
    from .models import Review

    director = Director(directory / "speech-evidence")
    director.model = config["model"]
    uploaded = None
    try:
        uploaded = director.client.files.upload(
            file=str(audio), config=types.UploadFileConfig(mime_type="audio/wav")
        )
        deadline = time.monotonic() + 180
        while uploaded.state and uploaded.state.name == "PROCESSING":
            if time.monotonic() >= deadline:
                raise VlogiiError("Gemini speech audio processing timed out. Retry this step.")
            time.sleep(2)
            uploaded = director.client.files.get(name=uploaded.name)
        if uploaded.state and uploaded.state.name != "ACTIVE":
            raise VlogiiError("Gemini could not process the speech audio. Retry this step.")
        if config["model"].endswith("transcribe"):
            result = transcription_request(uploaded.uri, config, key)
            entries = caption_entries(transcription_words(result), clip.duration)
            write_json(directory / "speech-evidence" / f"{clip.id}.json", result)
            return entries
        # Explicit compatibility choice for accounts without the dedicated model.
        prompt = (
            f"Transcribe only the audible speech in this audio. clip_id={clip.id}, duration={clip.duration:.3f} seconds. "
            "Return a Review with an empty summary, empty highlights and short speech entries. "
            "Use source seconds for start/end. Keep original Chinese, English and code-switching verbatim. "
            "Do not translate, paraphrase, add explanations or invent words. Use [] for silence. "
            "When uncertain omit only the inaudible span. Keep each caption under 100 characters, "
            "aligned to spoken phrases; preserve all clearly audible words. "
            "Speech language hint: " + config["language"]
        )
        parts = [types.Part.from_uri(file_uri=uploaded.uri, mime_type="audio/wav"), prompt]
        for attempt in range(2):
            try:
                review = director._generate(parts, Review, f"speech-{clip.id}-{attempt}")
                if review.clip_id != clip.id or any(
                    t.end > clip.duration + 0.001 for t in review.speech
                ):
                    raise ValueError("Speech timestamps exceed the source audio.")
                return review.speech
            except ValueError as exc:
                if attempt == 1:
                    raise VlogiiError(
                        "Gemini speech timestamps failed validation. Retry this step."
                    ) from exc
                parts.append(f"Correct the timestamps: {exc}")
    finally:
        if uploaded:
            try:
                director.client.files.delete(name=uploaded.name)
            except Exception:
                pass
        director.close()

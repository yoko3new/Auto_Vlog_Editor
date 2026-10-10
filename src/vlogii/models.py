"""Local application models, separate from the team's web API contracts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Seconds = Annotated[FiniteFloat, Field(ge=0)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Clip(Model):
    id: str
    path: str
    sha256: str
    duration: Annotated[FiniteFloat, Field(gt=0)]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: Annotated[FiniteFloat, Field(gt=0)]
    audio: bool
    color: Literal["sdr", "hlg", "pq"] = "sdr"


class Settings(Model):
    width: int = Field(default=1080, ge=64, le=3840)
    height: int = Field(default=1920, ge=64, le=3840)
    fps: int = Field(default=30, ge=1, le=60)
    color: Literal["auto", "sdr", "hlg"] = "auto"
    encoder: Literal["auto", "software"] = "auto"
    warmth: Annotated[FiniteFloat, Field(ge=0, le=1)] = 0

    @model_validator(mode="after")
    def even_dimensions(self):
        if self.width % 2 or self.height % 2:
            raise ValueError("Output dimensions must be even for 4:2:0 video.")
        return self


class Project(Model):
    schema_version: Literal[1] = 1
    name: str
    clips: list[Clip] = Field(min_length=1)
    settings: Settings = Field(default_factory=Settings)


class Text(Model):
    start: Seconds
    end: Seconds
    text: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Text end must be greater than start.")
        return self


class Review(Model):
    clip_id: str
    summary: str
    highlights: list[Text] = Field(default_factory=list)
    speech: list[Text] = Field(default_factory=list)


class Segment(Model):
    clip_id: str
    in_sec: Seconds
    out_sec: Seconds
    purpose: str = "scene"
    overlays: list[Text] = Field(default_factory=list)

    @model_validator(mode="after")
    def ordered(self):
        if self.out_sec <= self.in_sec:
            raise ValueError("Segment end must be greater than start.")
        return self


class Plan(Model):
    schema_version: Literal[1] = 1
    title: str = Field(min_length=1, max_length=160)
    reasoning: str
    segments: list[Segment] = Field(min_length=1, max_length=200)


class TimelineSegment(Model):
    clip_id: str
    source_start: int
    start: int
    frames: int = Field(gt=0)
    purpose: str
    overlays: list[Text]
    captions: list[Text]


class Timeline(Model):
    title: str
    fps: int
    total_frames: int
    segments: list[TimelineSegment]

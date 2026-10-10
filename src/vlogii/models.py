"""Local application models, separate from the team's web API contracts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Seconds = Annotated[FiniteFloat, Field(ge=0)]
Speed = Annotated[FiniteFloat, Field(ge=0.25, le=8)]
EditMode = Literal["auto", "highlights", "keep_most", "keep_all"]
FontPreset = Literal[
    "default",
    "noto-sans",
    "noto-serif",
    "ma-shan-zheng",
    "zcool-xiaowei",
    "caveat",
    "playfair-display",
]
MusicPreset = Literal[
    "uploaded",
    "none",
    "auto",
    "holizna-dreams",
    "holizna-day-jobs",
    "holizna-dancing",
    "holizna-deja-vu",
    "holizna-childhood",
    "holizna-advertisements",
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Appearance(Model):
    font: FontPreset = "default"
    music: MusicPreset = "none"
    music_volume: Annotated[FiniteFloat, Field(ge=0, le=1)] = 0.16
    duck_music: bool = True


class Selection(Model):
    mode: EditMode = "auto"
    target_seconds: Annotated[FiniteFloat, Field(ge=1, le=1800)] | None = None
    remove_no_speech: bool = False
    speed: Speed = 1
    shot_seconds: Annotated[FiniteFloat, Field(ge=0.15, le=1)] = 0.5


class TimeRange(Model):
    start: Seconds
    end: Seconds

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Range end must be greater than start.")
        return self


class SpeedRange(TimeRange):
    speed: Speed


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
    appearance: Appearance = Field(default_factory=Appearance)
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
    speed: Speed = 1
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
    mute_source_audio: bool = False
    captions: bool = True
    schema_version: Literal[1] = 1
    title: str = Field(min_length=1, max_length=160)
    reasoning: str
    segments: list[Segment] = Field(min_length=1, max_length=200)


class TimelineSegment(Model):
    clip_id: str
    source_start: int
    source_frames: int = Field(gt=0)
    speed: Speed = 1
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


class Music(Model):
    file: str = Field(pattern=r"^[0-9a-f]{32}\.[a-z0-9]{2,5}$")
    name: str = Field(min_length=1, max_length=255)
    sha256: str
    duration: Annotated[FiniteFloat, Field(gt=0)]


class StyleMoment(Model):
    clip_id: str
    in_sec: Seconds
    out_sec: Seconds
    label: str | None = Field(default=None, min_length=1, max_length=40)

    @model_validator(mode="after")
    def ordered(self):
        if self.out_sec <= self.in_sec:
            raise ValueError("Moment end must be greater than start.")
        return self


class StyleText(Model):
    kicker: str | None = Field(default=None, min_length=1, max_length=40)
    title: str | None = Field(default=None, min_length=1, max_length=40)
    subtitle: str | None = Field(default=None, min_length=1, max_length=60)
    location: str | None = Field(default=None, min_length=1, max_length=30)
    end_card: str | None = Field(default=None, min_length=1, max_length=80)


class StyleSelection(Model):
    """What AI (or the no-AI fallback) chooses; code computes every cut from it."""

    schema_version: Literal[1] = 1
    reasoning: str = ""
    text: StyleText = Field(default_factory=StyleText)
    moments: list[StyleMoment] = Field(min_length=1, max_length=60)


class StyleRequest(Model):
    """Everything needed to re-render a style version without another AI call."""

    schema_version: Literal[1] = 1
    style_id: str
    revision: int
    music: Music
    selection: StyleSelection
    ai_selected: bool
    warmth: Annotated[FiniteFloat, Field(ge=0, le=1)] = 0
    excluded: list[str] = Field(default_factory=list)

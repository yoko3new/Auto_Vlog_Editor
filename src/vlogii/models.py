"""Local application models, separate from the team's web API contracts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Seconds = Annotated[FiniteFloat, Field(ge=0)]
Speed = Annotated[FiniteFloat, Field(ge=0.25, le=8)]
EditMode = Literal["auto", "highlights", "keep_most", "keep_all"]
VideoFilter = Literal["none", "bright", "warm", "cool_white"]
FontPreset = Literal[
    "default",
    "noto-sans",
    "noto-serif",
    "ma-shan-zheng",
    "zcool-xiaowei",
    "caveat",
    "playfair-display",
    "tinos",
    "eb-garamond",
    "libre-baskerville",
    "lora",
    "cinzel",
    "cormorant-garamond",
    "montserrat",
    "source-sans-3",
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
    opening_highlights: bool = False
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


class ChapterEdit(Model):
    chapter_index: int = Field(ge=0)
    action: Literal["remove", "remove_range", "speed", "instruction"]
    start: Seconds | None = None
    end: Seconds | None = None
    speed: Speed | None = None
    instruction: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def complete_action(self):
        if (self.start is None) != (self.end is None):
            raise ValueError("Choose both start and end.")
        if self.start is not None and self.end <= self.start:
            raise ValueError("Range end must be greater than start.")
        if self.action == "remove_range" and self.start is None:
            raise ValueError("Choose a removal range.")
        if self.action == "speed" and self.speed is None:
            raise ValueError("Choose a speed.")
        if self.action == "instruction" and not self.instruction.strip():
            raise ValueError("Enter a chapter instruction.")
        if self.action in {"remove", "instruction"} and self.start is not None:
            raise ValueError("This action does not use a structured time range.")
        if self.action != "speed" and self.speed is not None:
            raise ValueError("Only speed actions accept a speed.")
        if self.action != "instruction" and self.instruction:
            raise ValueError("Only instruction actions accept text.")
        return self


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


class Cover(Model):
    title: str = Field(min_length=1, max_length=100)
    subtitle: str = Field(default="", max_length=160)
    kicker: str = Field(default="", max_length=80)
    font: FontPreset = "noto-serif"
    style: Literal["clean", "editorial", "playful"] = "clean"
    frame_seconds: Seconds = 0
    show_intro: bool = True

    @model_validator(mode="after")
    def clean_text(self):
        self.title = self.title.strip()
        self.subtitle = self.subtitle.strip()
        self.kicker = self.kicker.strip()
        if not self.title:
            raise ValueError("Enter a cover title.")
        return self


class Settings(Model):
    cover: Cover | None = None
    video_filter: VideoFilter = "none"
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
    included_clip_ids: list[str] | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def valid_inclusion(self):
        if self.included_clip_ids is not None:
            if len(set(self.included_clip_ids)) != len(self.included_clip_ids) or set(
                self.included_clip_ids
            ) - {clip.id for clip in self.clips}:
                raise ValueError("Choose unique clips from this project.")
        return self


class Chapter(Model):
    start: Seconds
    end: Seconds
    title: str
    summary: str
    clip_ids: list[str] = Field(default_factory=list)
    kind: Literal["scene", "hook", "body", "end_card", "cover"] = "scene"


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
    mute_source_audio: bool = False
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
    mute_source_audio: bool = False
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

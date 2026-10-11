"""Additional SDR color presets shared by ordinary and style rendering."""

from .models import Project, VideoFilter
from .storage import VlogiiError


def filter_args(choice: VideoFilter) -> list[str]:
    return {
        "none": [],
        "bright": ["eq=brightness=0.04:contrast=1.03:saturation=1.06"],
        "warm": ["colorbalance=rs=0.04:bs=-0.03", "eq=brightness=0.01"],
        "cool_white": ["colorbalance=rs=-0.02:bs=0.025", "eq=brightness=0.03:saturation=0.96"],
    }[choice]


def apply_filter(project: Project, choice: VideoFilter | None, style=False):
    if choice is None:
        return
    if project.settings.color == "hlg" and choice != "none" and not style:
        raise VlogiiError("Video filters require SDR output. Create an SDR project.")
    project.settings.video_filter = choice
    project.settings.warmth = 0
    if choice != "none":
        project.settings.color = "sdr"

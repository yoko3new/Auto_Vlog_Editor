"""Mix continuous background music after joining, using output speech timings."""

import array
import math
import sys
import wave
from pathlib import Path

from .models import Plan, Project, Review
from .timeline import compile_timeline


def speech_ranges(project: Project, plan: Plan, reviews: list[Review]):
    if plan.mute_source_audio:
        return []
    timeline = compile_timeline(project, plan.model_copy(update={"captions": True}), reviews)
    duration = timeline.total_frames / timeline.fps
    ranges = sorted(
        (
            max(0, segment.start / timeline.fps + caption.start - 0.1),
            min(duration, segment.start / timeline.fps + caption.end + 0.2),
        )
        for segment in timeline.segments
        for caption in segment.captions
    )
    merged = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def mix_music(
    tools,
    video: Path,
    music: Path,
    output: Path,
    duration: float,
    volume: float,
    ranges: list,
    log: Path,
    work: Path,
):
    fade = min(0.5, duration / 2)
    filters = [
        "aresample=48000",
        "asetpts=PTS-STARTPTS",
        "aformat=sample_fmts=fltp:channel_layouts=stereo",
        f"atrim=duration={duration:.9f}",
        f"volume={volume:.9f}",
    ]
    filters += [
        f"afade=t=in:st=0:d={fade:.9f}",
        f"afade=t=out:st={duration - fade:.9f}:d={fade:.9f}",
    ]
    script = work / "music-filter.txt"
    inputs = []
    duck_filter = "[music]anull[ducked];"
    if ranges:
        # A compact envelope keeps the graph bounded even with many speech entries.
        rate = 1000
        gain = array.array("h", [32767]) * math.ceil(duration * rate)
        for start, end in ranges:
            for index in range(
                max(0, math.floor(start * rate)), min(len(gain), math.ceil(end * rate))
            ):
                t = index / rate
                ramp = min(1, max(0, (t - start) / 0.1), max(0, (end - t) / 0.2))
                gain[index] = min(gain[index], round(32767 * (1 - 0.7 * ramp)))
        if sys.byteorder != "little":
            gain.byteswap()
        envelope = work / "duck-envelope.wav"
        with wave.open(str(envelope), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(gain.tobytes())
        inputs = ["-i", str(envelope)]
        duck_filter = (
            "[2:a]aresample=48000,asetpts=PTS-STARTPTS,"
            "pan=stereo|c0=c0|c1=c0[envelope];[music][envelope]amultiply[ducked];"
        )
    script.write_text(
        "[1:a]"
        + ",".join(filters)
        + "[music];"
        + duck_filter
        + "[0:a]aresample=48000,asetpts=PTS-STARTPTS[original];"
        "[original][ducked]amix=inputs=2:duration=first:normalize=0,"
        f"alimiter=limit=0.95:level=0:latency=1,atrim=duration={duration:.9f}[mixed]"
    )
    tools.run(
        [
            "-i",
            str(video),
            "-stream_loop",
            "-1",
            "-i",
            str(music),
            *inputs,
            "-filter_complex",
            script.read_text(),
            "-map",
            "0:v:0",
            "-map",
            "[mixed]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-t",
            f"{duration:.9f}",
            "-movflags",
            "+faststart",
            str(output),
        ],
        log,
    )

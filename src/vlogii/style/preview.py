"""Render a style film from a folder or manifest without creating a project."""

import json
import tempfile
from pathlib import Path

from ..storage import VlogiiError
from . import media, planner, templates
from .render import render


def render_preview(args) -> dict:
    template = templates.load(args.style)
    if args.manifest:
        inputs, text = planner.load_manifest(args.manifest)
    else:
        inputs, text = planner.clips_from_folder(args.clips), {}
    transcript = None
    if args.transcript:
        if not args.voiceover:
            raise VlogiiError("--transcript captions a --voiceover.")
        transcript = json.loads(args.transcript.read_text(encoding="utf-8"))
    plan = planner.plan(
        template,
        args.music,
        inputs,
        text,
        voiceover=args.voiceover,
        transcript=transcript,
        duration=args.seconds,
    )
    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    plan_path = out.with_suffix(".plan.json")
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logs = out.parent / f"{out.stem}-logs"
    with tempfile.TemporaryDirectory(prefix="vlogii-style-") as temporary:
        report = render(plan, template, out, Path(temporary), logs, progress=lambda _: None)
    info = media.probe(out)
    expected = plan["total_frames"] / plan["output"]["fps"]
    if abs(info["duration_s"] - expected) > 2 / plan["output"]["fps"]:
        raise VlogiiError(f"Rendered {info['duration_s']:.3f}s, planned {expected:.3f}s.")
    report = {
        "output": str(out),
        "plan": str(plan_path),
        "duration_s": info["duration_s"],
        **report,
    }
    out.with_suffix(".report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report

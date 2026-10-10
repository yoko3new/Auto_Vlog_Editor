"""Small debugging CLI plus the web application's startup command."""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from .media import Tools
from .models import Plan, Settings
from .pipeline import analyze, generate, initialize, load_project, load_reviews, make_plan, undo
from .render import render
from .storage import VlogiiError, locked, project_path, read_json


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="vlogii", description="Turn your footage into a little film."
    )
    parser.add_argument("--projects", type=Path, default=Path("projects"))
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("doctor", help="Check FFmpeg and Gemini configuration")
    serve = subs.add_parser("serve", help="Start the local web application")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    for command in ("init", "analyze", "plan", "render", "run", "status", "undo"):
        sub = subs.add_parser(command)
        sub.add_argument("name")
        if command == "init":
            sub.add_argument("footage", type=Path)
            sub.add_argument("--landscape", action="store_true")
            sub.add_argument("--color", choices=["auto", "sdr", "hlg"], default="auto")
        if command in {"plan", "run"}:
            sub.add_argument("--direction", default="A calm chronological diary of my day.")
            sub.add_argument(
                "--seconds", type=int, default=30, choices=range(5, 301), metavar="5-300"
            )
        if command == "analyze":
            sub.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "serve":
            import uvicorn

            from .api import create_app

            uvicorn.run(create_app(args.projects), host="127.0.0.1", port=args.port)
            return 0
        if args.command == "doctor":
            tools = Tools()
            tools.require_filters({"drawtext", "zscale", "tonemap"})
            print(f"FFmpeg: {tools.ffmpeg}\nFFprobe: {tools.ffprobe}")
            print(
                f"SDR encoder: {tools.encoder('sdr', 'auto')}\nHLG encoder: {tools.encoder('hlg', 'auto')}"
            )
            print(
                "Gemini key: "
                + (
                    "configured"
                    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                    else "missing"
                )
            )
            return 0
        directory = project_path(args.projects, args.name)
        if args.command == "init":
            settings = Settings(
                width=1920 if args.landscape else 1080,
                height=1080 if args.landscape else 1920,
                color=args.color,
            )
            with locked(directory):
                project = initialize(directory, args.footage.resolve(), settings)
            print(f"Imported {len(project.clips)} clips. Next: vlogii run {args.name}")
        elif args.command == "run":
            generate(directory, args.direction, args.seconds)
        elif args.command == "undo":
            print(f"Restored {undo(directory)}")
        elif args.command == "status":
            project = load_project(directory)
            latest = (
                read_json(directory / "latest.json")
                if (directory / "latest.json").exists()
                else None
            )
            print(
                json.dumps(
                    {"name": project.name, "clips": len(project.clips), "latest": latest}, indent=2
                )
            )
        else:
            with locked(directory):
                project = load_project(directory)
                if args.command == "analyze":
                    analyze(directory, project, force=args.force)
                elif args.command == "plan":
                    make_plan(directory, project, args.direction, args.seconds)
                elif args.command == "render":
                    plan = Plan.model_validate(read_json(directory / "plan.json"))
                    render(directory, project, plan, load_reviews(directory))
        return 0
    except (VlogiiError, ValidationError, OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Earlier successful films are preserved.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

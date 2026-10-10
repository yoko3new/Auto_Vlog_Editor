"""Bilingual CLI with an interactive session and resumable failed commands."""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .i18n import translate
from .media import Tools
from .models import Appearance, Plan, Settings
from .pipeline import (
    analyze,
    edit,
    generate,
    initialize,
    load_project,
    load_reviews,
    make_plan,
    undo,
)
from .render import render
from .speech import speech_config
from .storage import VlogiiError, locked, project_path, read_json, write_json


def say(language, english, chinese):
    return chinese if language == "zh" else english


def choose_language(argv):
    for index, value in enumerate(argv):
        if value.startswith("--language="):
            return value.split("=", 1)[1]
        if value == "--language" and index + 1 < len(argv):
            return argv[index + 1]
    if sys.stdin.isatty():
        value = input("Language / 语言 [1 中文 / 2 English] (1): ").strip().lower()
        return "en" if value in {"2", "en", "english"} else "zh"
    return os.environ.get("VLOGII_LANGUAGE", "en")


def selected_appearance(args, directory):
    values = {key: getattr(args, key, None) for key in ("font", "music", "music_volume")}
    if all(value is None for value in values.values()):
        return None
    path = directory / "project.json"
    if args.command == "edit" and (directory / "latest.json").exists():
        latest = read_json(directory / "latest.json")
        path = directory / "cuts" / latest["cut"] / "project.json"
    current = Settings.model_validate(read_json(path)["settings"]).appearance.model_dump()
    return Appearance.model_validate(
        {**current, **{k: v for k, v in values.items() if v is not None}}
    )


def execute(args, resume=False):
    directory = project_path(args.projects, args.name)

    def progress(message):
        print(translate(message, args.language))

    command = args.command
    if command == "retry":
        saved = read_json(directory / "cli-request.json")
        saved.update(projects=args.projects, name=args.name, language=args.language)
        return execute(argparse.Namespace(**saved), resume=True)
    if command in {"init", "run", "analyze", "plan", "render", "edit"}:
        saved = {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        }
        write_json(directory / "cli-request.json", saved)
    if command == "init":
        settings = Settings(
            width=1920 if args.landscape else 1080,
            height=1080 if args.landscape else 1920,
            color=args.color,
        )
        with locked(directory):
            project = initialize(
                directory, Path(args.footage).expanduser().resolve(), settings, progress
            )
        print(
            say(
                args.language,
                f"Imported {len(project.clips)} clips.",
                f"已导入 {len(project.clips)} 段素材。",
            )
        )
    elif command == "run":
        generate(
            directory,
            args.direction,
            args.seconds,
            progress,
            resume=resume,
            mode=getattr(args, "mode", "auto"),
            remove_no_speech=getattr(args, "remove_no_speech", False),
            speed=getattr(args, "speed", 1),
            shot_seconds=getattr(args, "shot_seconds", 0.5),
            appearance=selected_appearance(args, directory),
        )
    elif command == "edit":
        edit(
            directory,
            args.title,
            args.exclude_clip_ids,
            args.warmth,
            progress=progress,
            resume=resume,
            instruction=getattr(args, "instruction", ""),
            speed=getattr(args, "speed", None),
            appearance=selected_appearance(args, directory),
        )
    elif command == "undo":
        cut = undo(directory)
        print(say(args.language, f"Restored {cut}", f"已恢复到 {cut}"))
    elif command == "status":
        project = load_project(directory)
        latest = (
            read_json(directory / "latest.json") if (directory / "latest.json").exists() else None
        )
        print(
            json.dumps(
                {"name": project.name, "clips": len(project.clips), "latest": latest},
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        with locked(directory):
            project = load_project(directory)
            if command == "analyze":
                analyze(directory, project, progress, force=args.force)
            elif command == "plan":
                make_plan(
                    directory,
                    project,
                    args.direction,
                    args.seconds,
                    progress,
                    mode=getattr(args, "mode", "auto"),
                    remove_no_speech=getattr(args, "remove_no_speech", False),
                    speed=getattr(args, "speed", 1),
                    shot_seconds=getattr(args, "shot_seconds", 0.5),
                )
            elif command == "render":
                plan = Plan.model_validate(read_json(directory / "plan.json"))
                render(directory, project, plan, load_reviews(directory), progress)


def report_error(exc, language):
    message = (
        str(exc) if isinstance(exc, (VlogiiError, OSError, ValueError)) else type(exc).__name__
    )
    print(say(language, f"Error: {message}", f"操作失败：{translate(message, language)}"))
    print(
        say(
            language,
            "Earlier successful films and completed steps are preserved.",
            "旧成片和已完成步骤已保留；修正配置后可以重试，无需重新导入。",
        )
    )


def run_with_retry(action, language, interactive):
    resume = False
    while True:
        try:
            action(resume)
            return True
        except KeyboardInterrupt:
            print(
                say(
                    language,
                    "Interrupted. Earlier films are preserved.",
                    "操作中断，旧成片已保留。",
                )
            )
            return False
        except Exception as exc:
            report_error(exc, language)
            if not interactive:
                return False
            try:
                answer = (
                    input(
                        say(
                            language,
                            "Retry this step? [y/N]: ",
                            "重试当前步骤？[y/是，其他键返回]：",
                        )
                    )
                    .strip()
                    .lower()
                )
            except (EOFError, KeyboardInterrupt):
                return False
            if answer not in {"y", "yes", "是", "重试"}:
                return False
            resume = True


def interactive_session(projects, language):
    print(
        say(
            language,
            "Vlogii — press Ctrl+C to leave. Direction is optional.",
            "Vlogii — 中英文描述均可，创作方向可留空。Ctrl+C 退出。",
        )
    )
    while True:
        name = input(
            say(language, "Project name (Chinese or English): ", "项目名（支持中文或英文）：")
        ).strip()
        try:
            directory = project_path(projects, name)
            break
        except VlogiiError as exc:
            report_error(exc, language)
    while not (directory / "project.json").exists():
        footage = input(say(language, "Footage folder: ", "素材目录：")).strip()
        args = argparse.Namespace(
            command="init",
            projects=projects,
            name=name,
            footage=footage,
            landscape=False,
            color="sdr",
            language=language,
        )
        if not run_with_retry(
            lambda resume, request=args: execute(request, resume), language, True
        ):
            choice = (
                input(
                    say(
                        language,
                        "Change footage folder? [y/N]: ",
                        "重新输入素材目录？[y/是，其他键退出]：",
                    )
                )
                .strip()
                .lower()
            )
            if choice not in {"y", "yes", "是"}:
                return 1
    last_action = None
    while True:
        choice = (
            input(
                say(
                    language,
                    "[g] generate  [r] retry  [e] edit  [u] undo  [q] quit: ",
                    "[g/生成] 生成  [r/重试] 重试  [e/修改] 修改  [u/撤销] 撤销  [q/退出] 退出：",
                )
            )
            .strip()
            .lower()
        )
        if choice in {"q", "退出"}:
            return 0
        if choice in {"g", "生成"}:
            choice_mode = (
                input(
                    say(
                        language,
                        "Mode [1 auto / 2 opening highlights / 3 keep most / 4 keep all] (1): ",
                        "模式 [1 AI自动 / 2 开头快剪 / 3 保留大部分 / 4 完整保留] (1)：",
                    )
                ).strip()
                or "1"
            )
            modes = {"1": "auto", "2": "highlights", "3": "keep_most", "4": "keep_all"}
            if choice_mode not in modes:
                print(say(language, "Choose 1–4.", "请选择 1–4。"))
                continue
            mode = modes[choice_mode]
            direction = input(
                say(language, "Direction (optional): ", "想保留什么/怎样表达（可留空）：")
            ).strip()
            seconds = (
                input(
                    say(
                        language,
                        "Target seconds (blank = mode decides): ",
                        "目标秒数（留空按模式决定）：",
                    )
                ).strip()
                if mode in {"auto", "highlights"}
                else ""
            )
            if seconds and (not seconds.isdigit() or not 1 <= int(seconds) <= 1800):
                print(
                    say(
                        language,
                        "Choose 1–1800 seconds, or leave blank.",
                        "请输入 1–1800 秒，或留空；保留模式不设目标时长。",
                    )
                )
                continue
            try:
                speed = float(
                    input(
                        say(language, "Video speed 0.25–8 (1): ", "视频速度 0.25–8 倍（1）：")
                    ).strip()
                    or "1"
                )
                shot_seconds = (
                    float(
                        input(
                            say(
                                language,
                                "Maximum shot seconds 0.15–1 (0.5): ",
                                "每镜头最多停留 0.15–1 秒（0.5）：",
                            )
                        ).strip()
                        or "0.5"
                    )
                    if mode == "highlights"
                    else 0.5
                )
                from .models import Selection

                Selection(speed=speed, shot_seconds=shot_seconds)
            except ValueError:
                print(
                    say(
                        language,
                        "Choose valid speed/shot values.",
                        "请填写范围内的速度和镜头秒数。",
                    )
                )
                continue
            args = argparse.Namespace(
                command="run",
                projects=projects,
                name=name,
                direction=direction,
                seconds=int(seconds) if seconds else None,
                mode=mode,
                speed=speed,
                shot_seconds=shot_seconds,
                font="default",
                music="auto",
                language=language,
            )

            def last_action(resume, args=args):
                execute(args, resume)
        elif choice in {"r", "重试"}:
            args = argparse.Namespace(
                command="retry", projects=projects, name=name, language=language
            )
            if last_action is not None:
                run_with_retry(lambda _, action=last_action: action(True), language, True)
            else:
                run_with_retry(lambda _, request=args: execute(request), language, True)
            continue
        elif choice in {"u", "撤销"}:
            run_with_retry(lambda _: print(undo(directory)), language, False)
            continue
        elif choice in {"e", "修改"}:
            project = load_project(directory)
            for index, clip in enumerate(project.clips):
                print(f"{index + 1}: {Path(clip.path).name}")
            title = (
                input(say(language, "New title (optional): ", "新标题（可留空）：")).strip() or None
            )
            selected = (
                input(
                    say(
                        language,
                        "Exclude clip numbers, comma-separated (optional): ",
                        "排除素材编号，用逗号分隔（可留空）：",
                    )
                )
                .strip()
                .replace("，", ",")
            )
            try:
                indices = [int(x.strip()) - 1 for x in selected.split(",") if x.strip()]
                if any(i < 0 or i >= len(project.clips) for i in indices):
                    raise ValueError("Unknown clip number")
                excluded = [project.clips[i].id for i in indices]
            except ValueError:
                print(say(language, "Invalid clip number.", "素材编号不正确。"))
                continue
            warmer = (
                input(say(language, "Warmer? [y/N]: ", "调暖一点？[y/是，其他键跳过]："))
                .strip()
                .lower()
            )
            warmth = 0.5 if warmer in {"y", "yes", "是"} else None
            instruction = input(
                say(
                    language,
                    "Time edits (delete 00:12-00:18 / speed up 00:12-00:18 to 2x): ",
                    "成片时间修改（可留空，例如 删掉00:12到00:18 / 00:12到00:18加速到2倍）：",
                )
            ).strip()
            if title is None and not excluded and warmth is None and not instruction:
                continue

            args = argparse.Namespace(
                command="edit",
                projects=projects,
                name=name,
                language=language,
                title=title,
                exclude_clip_ids=excluded,
                warmth=warmth,
                instruction=instruction,
            )

            def last_action(resume, args=args):
                execute(args, resume)
        else:
            continue
        run_with_retry(last_action, language, True)


def main(argv=None):
    load_dotenv()
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        language = choose_language(argv)
    except (EOFError, KeyboardInterrupt):
        return 130
    parser = argparse.ArgumentParser(
        prog="vlogii",
        description=say(
            language, "Turn your footage into a little film.", "把你的生活素材剪成短片。"
        ),
    )
    parser.add_argument("--projects", type=Path, default=Path("projects"))
    parser.add_argument("--language", choices=["en", "zh"], default=language)
    subs = parser.add_subparsers(dest="command")
    subs.add_parser("doctor", help=say(language, "Check configuration", "检查环境与模型配置"))
    serve = subs.add_parser("serve", help=say(language, "Start the web app", "启动网页应用"))
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    for command in ("init", "analyze", "plan", "render", "run", "edit", "retry", "status", "undo"):
        sub = subs.add_parser(command)
        sub.add_argument("name")
        sub.add_argument("--language", choices=["en", "zh"], default=argparse.SUPPRESS)
        if command == "init":
            sub.add_argument("footage", type=Path)
            sub.add_argument("--landscape", action="store_true")
            sub.add_argument("--color", choices=["auto", "sdr", "hlg"], default="auto")
        if command in {"plan", "run"}:
            sub.add_argument("--direction", default="")
            sub.add_argument(
                "--mode", choices=["auto", "highlights", "keep_most", "keep_all"], default="auto"
            )
            sub.add_argument("--remove-no-speech", action="store_true")
            sub.add_argument("--speed", type=float, default=1)
            sub.add_argument("--shot-seconds", type=float, default=0.5)
            sub.add_argument(
                "--seconds", type=int, default=None, choices=range(1, 1801), metavar="1-1800"
            )
        if command == "analyze":
            sub.add_argument("--force", action="store_true")
        if command in {"run", "edit"}:
            from typing import get_args

            from .models import FontPreset, MusicPreset

            sub.add_argument("--font", choices=get_args(FontPreset))
            sub.add_argument(
                "--music",
                choices=get_args(MusicPreset),
                default="auto" if command == "run" else None,
            )
            sub.add_argument("--music-volume", type=float)
        if command == "edit":
            sub.add_argument("--title")
            sub.add_argument("--exclude-clip-ids", nargs="*", default=[])
            sub.add_argument("--warmth", type=float)
            sub.add_argument("--speed", type=float)
            sub.add_argument("--remove-ranges", "--instruction", dest="instruction", default="")
    args = parser.parse_args(argv)
    if not args.command:
        if sys.stdin.isatty():
            try:
                return interactive_session(args.projects, args.language)
            except (EOFError, KeyboardInterrupt):
                return 130
        parser.print_help()
        return 0
    if args.command == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(args.projects), host="127.0.0.1", port=args.port)
        return 0
    if args.command == "doctor":

        def doctor(_):
            tools = Tools()
            tools.require_filters({"drawtext", "zscale", "tonemap"})
            print(f"FFmpeg: {tools.ffmpeg}\nFFprobe: {tools.ffprobe}")
            print(f"Gemini: {os.environ.get('VLOGII_MODEL', 'gemini-3.8-flash')}")
            print(
                say(args.language, "Speech recognition: ", "语音识别：")
                + json.dumps(speech_config(), ensure_ascii=False)
            )
            print(
                say(args.language, "Gemini key: ", "Gemini 密钥：")
                + (
                    say(args.language, "configured", "已配置")
                    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                    else say(args.language, "missing", "未配置")
                )
            )

        return 0 if run_with_retry(doctor, args.language, False) else 1
    success = run_with_retry(
        lambda resume: execute(args, resume), args.language, sys.stdin.isatty()
    )
    if not success and args.command in {"run", "render", "plan", "analyze", "edit", "retry"}:
        print(f"vlogii --language {args.language} retry {args.name}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

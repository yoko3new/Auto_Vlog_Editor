# Vlogii

[中文](vlogii-guide.zh.md) · **English**

A local web app for everyday Shorts, with editable exports.

**Upload → Gemini video analysis → validated edit plan → real FFmpeg export → preview, edit, undo and download.**

The current implementation is a local MVP. The next product direction is styled covers, opening highlights and a captioned body; covers and automatic opening/body assembly are pending. See [Shorts direction](shorts-direction.en.md).

## Run locally

Requirements: macOS or Linux, Python 3.11+, Node.js 20+, [uv](https://docs.astral.sh/uv/), and FFmpeg with `drawtext`, `zscale`, `tonemap`, AAC, H.264 and HEVC support.

On macOS:

```sh
brew install ffmpeg-full
```

On Ubuntu:

```sh
sudo apt-get update
sudo apt-get install ffmpeg fontconfig fonts-dejavu-core fonts-noto-cjk
```

Clone the implementation branch and install the locked dependencies:

```sh
git clone --branch codex/integrate-feng-ui https://github.com/yoko3new/Auto_Vlog_Editor.git vlogii
cd vlogii
uv sync --frozen --extra dev
cp .env.example .env
```

Add your Gemini API key to `.env`. Keep `.env` local. The defaults are `VLOGII_MODEL=gemini-3.8-flash` for visual analysis/planning and `VLOGII_SPEECH_MODEL=gemini-3.5-transcribe` for speech. Both use the same key. Models are configurable because account availability can change. Gemini receives low-resolution video copies and separately extracted original audio. Remote uploaded files are deleted after recognition when the provider accepts deletion. New model access passed a one-clip live run; accuracy is not yet benchmarked; see [current fixes and choices](mvp-fixes.en.md).

Build the frontend and start the server:

```sh
cd frontend
npm ci
npm run build
cd ..
uv run vlogii doctor
uv run vlogii serve
```

Open **http://127.0.0.1:8000**. The server is intentionally bound to localhost. Run one server process. Do not use multiple workers or expose this unauthenticated MVP as a public service.

On macOS the app automatically prefers Homebrew's `ffmpeg-full`, so no manual `brew link` or PATH modification is needed. Override executables with `VLOGII_FFMPEG` and `VLOGII_FFPROBE` when necessary.

## What works

- Upload MP4, MOV, M4V or MKV footage, inspect its actual metadata and deduplicate identical files.
- Creative direction and target duration are optional. Choose AI auto, opening highlights, keep most or keep all. Without a target, AI auto decides the length, highlights aims for 5 seconds and retention modes preserve content. Clickable examples populate the input and mode without submitting. See [editing modes and time changes](editing-modes.en.md).
- Gemini watches proxy videos and describes visible events. A separate Gemini speech request processes original audio extracted as PCM. Captions retain the source language. `VLOGII_SPEECH_LANGUAGE=auto` supports mixed languages; use a supported BCP-47 code for an explicit hint. The renderer measures complete text against output width and height and selects Arial Unicode on macOS or Noto CJK on Linux; set `VLOGII_FONT` to override the font. Speech transcription needs human review.
- The AI selects source intervals and occasional factual text. Python validates references, ranges and overlays, then computes all output timing in integer frames.
- FFmpeg preserves original audio in normal modes, adds silence to clips without audio, burns text and captions, normalizes segments and joins them. Highlights mute source audio and omit speech captions by default.
- Browser-friendly SDR/H.264 is the web default. All-HLG projects can preserve 10-bit HDR using HEVC; mixed HDR/SDR footage is tone-mapped to SDR. HEVC playback depends on the browser and display.
- Change the title, apply a controlled warmth adjustment or remove selected source clips. These edits render a new version without another AI call. Undo restores the previous successful version without rendering.
- Failed work keeps previous successful exports. Progress is based on actual stages, not a simulated percentage. A server restart marks interrupted jobs as retryable failures.
- Retry preserves the failed task's exact request and kind, including edits. It reuses valid visual/speech caches, the saved plan and completed rendered segments. New generation with different direction replans from the original imported clips.
- The browser offers Chinese/English switching, saved locally. Unicode project names and creative direction are supported. UI language does not force speech language.
- Local project records, analysis caches, plans, timelines, full FFmpeg logs and successful versions are stored under `projects/` and ignored by Git.

Limits: 50 clips, 512 MB per clip, 2 GB per upload, 30 minutes of source footage, and optional target durations of 1–1800 seconds for AI auto/highlights. Warmth edits use SDR output. Re-generating an AI plan uses the original imported clip set; removing a clip is a version edit, not a permanent deletion of source footage.

## Scope and compatibility

This branch implements a **local vlog web MVP** based on the tested VX workflow. It is not a claim that the original team's full competition MVP has been delivered. Background music, beat matching, magazine decorations, arbitrary natural-language editing, authentication, cloud storage, Replit deployment, scene-detection heuristics and NLE exports are outside this release.

The existing [team product plan](product.en.md), [architecture](architecture.en.md), [contracts](contracts.en.md), schemas, examples and development substitutes are preserved as planning material. Vlogii uses an explicit, separate `/api/vlogii` namespace and local models; it does not pretend to implement the older `/api` contract. The live API specification is at `/openapi.json`, with interactive docs at `/docs`; the checked-in snapshot is [vlogii.openapi.json](vlogii.openapi.json).

## Code layout

```text
src/vlogii/
  models.py       Strict local schemas
  storage.py      Atomic JSON writes and OS project locks
  media.py        FFmpeg discovery, probing, hashes and SDR proxies
  ai.py           Gemini video reviews and validated planning
  speech.py       Independent original-audio Gemini transcription
  i18n.py         Chinese CLI status messages
  editorial.py    Retention modes, black detection and time-range changes
  timeline.py     Deterministic frame timing and caption remapping
  render.py       Text, audio, HDR, encoding and output verification
  pipeline.py     Analysis caching, generation, edits and undo
  api.py          Uploads, persistent jobs, one worker and media delivery
  cli.py          Web startup and debugging commands
frontend/         React + TypeScript + Vite editor
tests/           Validation, failure recovery, API and real-media checks
```

## Verify

```sh
uv run pytest -q
uv run ruff check src/vlogii tests
uv run ruff format --check src/vlogii tests
cd frontend && npm run build
```

Real media tests generate short synthetic clips and require FFmpeg. Skipped media tests do not count as successful video validation. API provider test doubles check failure behavior only; they do not count as live AI verification. See the [validation record](vlogii-validation.md) for actual results and remaining limitations.

The preserved team scaffolding can still be checked separately:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 contracts/validate_examples.py
PYTHONDONTWRITEBYTECODE=1 python3 contracts/collaboration/validate_collaboration.py
python3 tools/check_docs.py
```

## CLI debugging

The web app and CLI use the same modules:

```sh
uv run vlogii init my-day /absolute/path/to/footage --color sdr
uv run vlogii run my-day --mode keep_all
uv run vlogii run my-day --mode highlights --seconds 5 --shot-seconds 0.5 --speed 1
uv run vlogii run my-day --seconds 120 --direction "A chronological diary"
uv run vlogii retry my-day  # Resume the saved failed generation or edit
uv run vlogii edit my-day --title "Slow Sunday" --warmth 0.5
uv run vlogii status my-day
uv run vlogii render my-day   # Reuse a saved plan; no new AI request
uv run vlogii undo my-day
```

Use `vlogii --projects /another/local/directory ...` to choose a different workspace. This release supports macOS and Linux; Windows project locking is not implemented.

Run `uv run vlogii` in a terminal to choose Chinese/English and stay in an interactive generate/retry/edit/undo session. Commands accept `--language zh` or `--language en`; descriptions can use either language regardless of the interface. For example: `uv run vlogii --language zh run 周末 --direction "保留早餐和散步"`. Failed interactive commands offer retry without exiting; non-interactive use prints an explicit retry command. The 1–1800 second constraint applies only to an explicit target in AI auto/highlights; retention modes do not set a target.

The retry API is `POST /api/vlogii/projects/{name}/retry`, with no body. `JobState` adds `retryable` and `kind`; generation/edit accept optional `language`. Existing requests remain valid. The saved request stays private in local job records. Current retry has no old-contract `request_id` idempotency guarantee; the backend prevents simultaneous work on one project. Frontend controls and [OpenAPI](vlogii.openapi.json) use the same fields.

Generate requests add `mode`, `remove_no_speech`, `speed` and `shot_seconds`; `target_seconds` is now optional (default null). Edit requests add `remove_ranges` and `speed_ranges` in current-film seconds, nullable `speed`, and `instruction` for supported deletion/speed phrases. `ProjectView.selection` describes the latest version’s resolved mode. This changes the omitted-target behavior; callers requiring the old default must send 30 explicitly. See [editing semantics](editing-modes.en.md) and the updated [OpenAPI](vlogii.openapi.json).

## Data and publishing

Only source code, dependency locks, bilingual documentation, API schema and non-sensitive verification summaries belong in Git. No API keys, footage, private prompts, transcripts, generated videos, analysis caches or local absolute paths are part of the published project.

This first release is suitable for local testing and iteration. Successful decoding is not proof of good editorial choices, correct transcription, performance on every input or production readiness.

### Flash cuts and playback speed

`run/plan --speed 1 --shot-seconds 0.5` changes export speed and the maximum output shot length for highlights. `edit --speed 1` restores source speed; `edit --instruction "00:12到00:18加速到2倍"` changes only that interval in the current film. Rates are absolute; subtitles and audio follow the frame timeline. The web UI offers separate radio groups for cadence and speed. See [editing rules](editing-modes.en.md) and the [Shorts direction](shorts-direction.en.md); cover styling and automatic opening/body assembly are still pending.

Highlights exports now mute source audio by default, preserving that choice through edits/retries. Normal body/retention modes keep source audio. A silent AAC track keeps the MP4 suitable for future opening/body concatenation; BGM is still pending.

<a id="web-design"></a>

## Integrated web editor

The `codex/integrate-feng-ui` branch combines the frontend from `feng-emergence` with current `kang` behavior. The page uses a thin white masthead with reading progress, one reading column, a wide film band, a round Play control and three numbered chapters. Chinese/English switching, retry, generation modes, examples, cadence, speed, time-range edits and undo remain available.

The fresh palette uses mint emphasis on a light background. Newsreader, Libre Franklin and Courier Prime are bundled through Fontsource under OFL; no external font requests are required. Chinese uses local system fallbacks. Browser typography changes the editor only; MP4 caption fonts and layouts retain their existing rendering rules. Brand assets are in `frontend/public/brand`.

For first-time macOS and Safari setup, see the [Mac guide](vlogii-mac-setup.en.md).

License notices are included in `frontend/public/fonts` and served with the frontend.

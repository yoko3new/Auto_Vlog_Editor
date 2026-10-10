# Vlogii

[中文](vlogii-guide.zh.md) · **English**

A local web app for everyday Shorts, with editable exports.

**Upload → Gemini video analysis → validated edit plan → real FFmpeg export → preview, edit, undo and download.**

The current implementation is a local MVP. The next product direction is styled covers, opening highlights and a captioned body; covers and automatic opening/body assembly are pending. See [Shorts direction](shorts-direction.en.md).

## Run locally

Requirements: macOS or Linux, Python 3.11+, Node.js 20+, [uv](https://docs.astral.sh/uv/), and FFmpeg with `drawtext`, `zscale`, `tonemap`, AAC, H.264 and HEVC support. Style films also need the `ass` filter (libass), which `ffmpeg-full` and Ubuntu's `ffmpeg` include.

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
- Gemini watches proxy videos and describes visible events. A separate Gemini speech request processes original audio extracted as PCM. Captions retain the source language. `VLOGII_SPEECH_LANGUAGE=auto` supports mixed languages; use a supported BCP-47 code for an explicit hint. The renderer measures complete text against output width and height and defaults to bundled Noto CJK; set `VLOGII_FONT` to override the font. Speech transcription needs human review.
- The AI selects source intervals and occasional factual text. Python validates references, ranges and overlays, then computes all output timing in integer frames.
- FFmpeg preserves original audio in normal modes, adds silence to clips without audio, burns text and captions, normalizes segments and joins them. Highlights mute source audio and omit speech captions by default.
- Browser-friendly SDR/H.264 is the web default. All-HLG projects can preserve 10-bit HDR using HEVC; mixed HDR/SDR footage is tone-mapped to SDR. HEVC playback depends on the browser and display.
- Change the title, apply a controlled warmth adjustment or remove selected source clips. These edits render a new version without another AI call. Undo restores the previous successful version without rendering.
- Failed work keeps previous successful exports. Progress is based on actual stages, not a simulated percentage. A server restart marks interrupted jobs as retryable failures.
- Retry preserves the failed task's exact request and kind, including edits. It reuses valid visual/speech caches, the saved plan and completed rendered segments. New generation with different direction replans from the original imported clips.
- The browser offers Chinese/English switching, saved locally. Unicode project names and creative direction are supported. UI language does not force speech language.
- Local project records, analysis caches, plans, timelines, full FFmpeg logs and successful versions are stored under `projects/` and ignored by Git.

Limits: 50 clips, 512 MB per clip, 2 GB per upload, 30 minutes of source footage, and optional target durations of 1–1800 seconds for AI auto/highlights. Warmth edits use SDR output. Re-generating an AI plan uses the original imported clip set; removing a clip is a version edit, not a permanent deletion of source footage.

<a id="styles"></a>

## Styles: background music, beat sync and reference looks

A style is a template learned from a reference reel: shot lengths and opening montage, grade targets, title and stamp layout, and mix rules. The measurements, the finding that the references themselves are not beat-locked, and how each template was derived are in [style templates](style-templates.en.md).

1. In the web app, choose a style and bundled or uploaded music in *No. 2*. On the command line, add music with `vlogii music` and generate with `vlogii run --style`.
2. With a Gemini key, cached visual reviews feed a style request: Gemini returns chronological moments, short activity labels and title text, which Python validates (clip IDs, ranges and total length) with one corrected retry. Clip speech is not transcribed because style films mute it. Without a key, every clip is used in import order with the style's default title, and the page says so. Retry reuses the saved choice.
3. `style/planner.py` detects the music's beats (librosa, corrected for onset latency), starts on a downbeat, rounds the film to whole bars, picks shot lengths near the reference's seconds as beat multiples and spreads them over the moments in order. Every cut is within half a frame of the beat grid. Footage is never repeated to fill time; too little footage or too short music is reported.
4. `style/render.py` trims each shot and grades it toward the reference (HDR is tone-mapped to SDR), sets titles, clocks and labels with ASS in bundled OFL fonts (Poppins, DM Serif Display, Share Tech Mono), mutes clip audio and masters the music to −14 LUFS with a −1 dBTP true-peak ceiling measured after AAC encoding. The narrated style can also duck music under a voiceover with captions from a transcript (command line only).
5. The result is a normal version with `style.json`, `style-plan.json`, logs and `verification.json`. Title, warmth and clip edits re-cut on the beat without another AI call; speed and time-range edits are refused because they would break the beat lock. Undo and download work as usual.

Music: MP3, M4A, AAC, WAV, FLAC or OGG, 10 seconds to 15 minutes and up to 200 MB, stored in the project. Use music you are allowed to publish. `GET /api/vlogii/styles` lists styles, `POST /api/vlogii/projects/{name}/music` adds a track and generation accepts `style_id`.

```sh
uv run vlogii styles
uv run vlogii music my-day ~/Music/song.mp3
uv run vlogii run my-day --style ig_city_day_in_life
uv run vlogii style-preview ig_cozy_night_study --music song.mp3 --clips ~/Movies/day --out work/day.mp4
```

Limits: style films are SDR/H.264 at the project's size and 30 fps; the three styles are portrait. Beat detection cannot hear: on music without a clear kick the downbeat may be wrong, and the page shows such warnings. Learning new styles uses `tools/style_lab/` after `uv sync --extra style-lab`.

## Scope and compatibility

This branch implements a **local vlog web MVP** based on the tested VX workflow. It is not a claim that the original team's full competition MVP has been delivered. Background music and beat matching are available through [styles](#styles). Magazine decorations, arbitrary natural-language editing, authentication, cloud storage, Replit deployment, scene-detection heuristics and NLE exports are outside this release.

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
  style/          Templates, beat detection, beat-locked planning, style rendering and fonts
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

Highlights exports now mute source audio by default, preserving that choice through edits/retries. Normal body/retention modes keep source audio. A silent AAC track keeps the MP4 suitable for future opening/body concatenation; Optional bundled BGM can now be mixed over the muted opening.

<a id="web-design"></a>

## Integrated web editor

The `codex/integrate-feng-ui` branch combines the frontend from `feng-emergence` with current `kang` behavior. The page uses a thin white masthead with reading progress, one reading column, a wide film band, a round Play control and numbered chapters. The page starts with project creation/import, followed by generation controls, editing an existing film and the final preview. Imported clip details are collapsible. Apply changes is available beside whole-film speed and at the end of the edit form; View film jumps to the final player. Chinese/English switching, retry, generation modes, examples, cadence, speed, time-range edits and undo remain available.

The fresh palette uses mint emphasis on a light background. Newsreader, Libre Franklin and Courier Prime are bundled through Fontsource under OFL; no external font requests are required. Chinese uses local system fallbacks. Browser typography changes the editor only; MP4 caption fonts and layouts retain their existing rendering rules. Brand assets are in `frontend/public/brand`.

For first-time macOS and Safari setup, see the [Mac guide](vlogii-mac-setup.en.md).

License notices are included in `frontend/public/fonts` and served with the frontend.

Duration input accepts seconds and common notation such as “about 2 minutes”, “约120秒” or “01:30”, resolves them to an approximate seconds target and rejects invalid/out-of-range entries. Example buttons sit between each question and its input. Generation speed takes effect after Make my film / Make a new version; Whole-film speed in the edit chapter reuses the current plan after Apply changes.

The masthead has no completion badge. An active-task progress panel shows parsing, speech recognition, scene analysis, edit planning and rendering with real job messages and clip counters. It follows the current batch rather than estimating a global percentage or remaining time; analysis stages can alternate by clip. Queueing, planning, joining and verification without counters use an indeterminate bar. The panel remains visible while scrolling and disappears after success.

Fonts and music: the generation chapter defaults to bundled Noto Sans and Automatic music. Preview fonts, listen to six instrumental tracks, choose No background music, or adjust volume and speech ducking. For an existing film, change presets in the edit chapter and Apply changes; the previous version remains available for undo. Assets load automatically with the app; see [bundled assets and licenses](free-resources.en.md). Style mode supports music uploads and automatic beat syncing; custom font uploads remain pending.

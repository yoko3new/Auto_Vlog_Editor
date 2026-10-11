# Vlogii

![Vlogii](frontend/public/brand/vlogii-logo.png)

**Turn everyday footage into an editable short film.** Vlogii is a local video editor with a React interface, a FastAPI backend, Gemini analysis and real FFmpeg exports. The web app and CLI support English and Chinese.

把日常素材剪成可预览、修改、撤销和导出的短片。当前是本地网页 MVP；本 README 集中说明启动、功能、代码入口和验证边界。

Upload clips → analyze pictures and speech → validate a frame-based timeline → render → refine, undo and download.

## Quick start

Requirements: **Python 3.11+, Node.js 20+, uv, FFmpeg and FFprobe** on macOS or Linux. FFmpeg needs `drawtext`, `zscale`, `tonemap`, `libx264`, AAC and `libass` for style titles; HLG export also needs `libx265`.

```sh
# macOS
brew install uv ffmpeg-full

# Ubuntu / Debian: install uv separately, then install media tools
# sudo apt-get update
# sudo apt-get install -y ffmpeg fontconfig fonts-dejavu-core fonts-noto-cjk

git clone https://github.com/yoko3new/Auto_Vlog_Editor.git
cd Auto_Vlog_Editor
uv sync --frozen --extra dev
npm --prefix frontend ci
cp .env.example .env
```

Set `GEMINI_API_KEY` in your local `.env`, and choose models available to your account. Then:

```sh
npm --prefix frontend run build
uv run vlogii --language en doctor
uv run vlogii --language en serve
```

Open **http://127.0.0.1:8000**. FastAPI serves the built frontend and the API. Interactive API documentation is at **http://127.0.0.1:8000/docs**.

The service binds to localhost. Run one process: rendering uses one worker, with up to eight pending jobs and one active job per project. This MVP has no authentication and is intended for local use.

For frontend development, keep the backend running and use `npm --prefix frontend run dev`; Vite proxies `/api` to port 8000. After changing frontend code, rebuild to update the page served by FastAPI.

## What you can do

1. Create a project and upload MP4, MOV, M4V or MKV clips. Imports inspect metadata and deduplicate files.
2. Choose portrait or landscape output, included clips, creative direction, font, music, filter and editing mode.
3. Generate a film; follow the actual analysis, planning and rendering stages, then preview and download the MP4.
4. Refine chapters, remove a chapter or time range, change speed, adjust titles or appearance, and apply edits as a batch.
5. Create a cover with a frame from the film, title, subtitle, label, font and decoration. Download the PNG or add/replace a one-second intro.
6. Undo to an earlier successful version, or retry failed work using the saved request and valid caches. A failed render preserves the previous successful film.

| Mode | Behavior |
| --- | --- |
| AI auto (`auto`) | Gemini selects and orders moments using your direction and optional target duration. |
| Opening montage (`highlights`) | A standalone, roughly five-second montage; default shots are at most about 0.5 seconds at normal speed, with source audio muted and no speech captions. |
| Keep most (`keep_most`) | Keeps import order, trims black frames and long speech pauses; optionally removes intervals with no recognized speech. |
| Keep all (`keep_all`) | Keeps all included source intervals in import order; playback speed changes output length. |

Retention modes can prepend an optional five-second highlight montage. The opening is muted; the body retains its configured audio and captions. Auto/montage targets accept 1–1800 seconds and are approximate; retention duration follows the footage. Footage is not repeated to fill a requested duration.

The renderer supports source-language captions, portrait/landscape layout, original/bright/warm/cool-white filters, **14 bundled fonts and six CC0 instrumental tracks**, music looping and speech ducking. Chapter titles and summaries can be localized separately from the original speech captions.

Three reference styles provide music-driven cuts, titles and clock labels: `ig_city_day_in_life`, `ig_cozy_night_study` and `ig_narrated_college_day`. Python computes their beat grid and cut timing. Style films mute clip audio; the music target at full volume is −14 LUFS with a −1 dBTP true-peak ceiling. With no Gemini key, style mode uses clips in import order and default text; this fallback does not perform AI selection.

## Configuration and data

Start from [.env.example](.env.example). Keys stay on the backend.

| Setting | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Gemini credential for picture analysis, planning, speech recognition and chapter localization. |
| `VLOGII_MODEL` | Picture/planning model; the example defaults to `gemini-3.8-flash`. |
| `VLOGII_SPEECH_MODEL` | Separate original-audio recognition model; the example defaults to `gemini-3.5-transcribe`. |
| `VLOGII_SPEECH_LANGUAGE` | Recognition language hint; `auto` by default. |
| `VLOGII_THINKING` | Thinking level for picture/planning requests. |
| `VLOGII_LANGUAGE` | Default CLI language; `--language en` or `--language zh` overrides it. |
| `VLOGII_FFMPEG`, `VLOGII_FFPROBE` | Optional absolute executable paths. macOS prefers Homebrew `ffmpeg-full` automatically. |
| `VLOGII_FONT` | Optional caption font override. |

Model access, API cost and recognition quality depend on your provider account. `doctor` checks local configuration and media capabilities; it does not prove model access or AI quality. Video proxies and original audio are sent to Gemini when their analysis is enabled.

Project files live under ignored `projects/`: imported footage, analysis/transcription caches, plans, job state, version history, logs and exported media. Use `uv run vlogii --projects /absolute/path/to/projects serve` to choose a different directory. Keep this directory when restarting or backing up your work.

Web uploads allow **50 clips, 512 MiB per clip, 2 GiB per upload and 30 minutes of source footage**. Uploaded style music accepts MP3/M4A/AAC/WAV/FLAC/OGG, up to 200 MiB and 10 seconds–15 minutes.

## CLI examples

```sh
uv run vlogii --language zh                           # Interactive session
uv run vlogii --language en init my-day /absolute/path/to/footage --color sdr
uv run vlogii --language en run my-day --mode keep_all
uv run vlogii --language en run my-day --mode highlights --shot-seconds 0.5 --speed 1
uv run vlogii --language en run my-day --style ig_city_day_in_life --music /absolute/path/to/song.mp3
uv run vlogii --language zh edit my-day --instruction "00:12到00:18加速到2倍"
uv run vlogii --language en retry my-day
uv run vlogii --language en undo my-day
uv run vlogii --language en styles
```

Time edits use the **currently successful film's timestamps**, including any cover intro. Supported instructions are explicit time-range removal/speed operations in English or Chinese. Arbitrary semantic editing is not implemented. Style films currently reject chapter time/speed refinement.

## Code review guide

The active HTTP interface is `/api/vlogii`. The [OpenAPI snapshot](api/openapi.json) is generated from the running application's models and routes. The repository contains the current implementation; historical competition plans and the unused alternative API contract have been removed.

| Area | Entry points |
| --- | --- |
| API, uploads, jobs and media responses | [api.py](src/vlogii/api.py) |
| Shared models and validation | [models.py](src/vlogii/models.py) |
| Generation, retry, editing and undo | [pipeline.py](src/vlogii/pipeline.py), [storage.py](src/vlogii/storage.py) |
| Gemini analysis and separate speech recognition | [ai.py](src/vlogii/ai.py), [speech.py](src/vlogii/speech.py) |
| Deterministic timeline, range edits and clip inclusion | [timeline.py](src/vlogii/timeline.py), [editorial.py](src/vlogii/editorial.py), [inclusion.py](src/vlogii/inclusion.py) |
| Chapter refinement and localization | [chapters.py](src/vlogii/chapters.py), [refinement.py](src/vlogii/refinement.py), [localization.py](src/vlogii/localization.py) |
| Rendering, audio, covers and filters | [render.py](src/vlogii/render.py), [music.py](src/vlogii/music.py), [cover.py](src/vlogii/cover.py), [grading.py](src/vlogii/grading.py) |
| Beat planning, style rendering and templates | [src/vlogii/style/](src/vlogii/style/) |
| React application and editors | [frontend/src/](frontend/src/) |
| Regression and real-media integration checks | [tests/](tests/) |
| Optional reference analysis tools and measured profiles | [tools/style_lab/](tools/style_lab/), [style/references/](style/references/) |

AI proposes content; Python validates source references and intervals and computes integer-frame timing; FFmpeg executes the timeline. Only verified successful renders become the latest version. Public request/response changes should update backend models, frontend calls, the snapshot and relevant tests together.

```sh
uv run ruff check src/vlogii tests tools/check_docs.py tools/export_openapi.py
uv run ruff format --check src/vlogii tests tools/check_docs.py tools/export_openapi.py
uv run pytest -q
npm --prefix frontend run build
python3 tools/check_docs.py
uv run python tools/export_openapi.py --check
```

To refresh the API snapshot: `uv run python tools/export_openapi.py`. [GitHub Actions](.github/workflows/vlogii.yml) runs these checks on `main`, the integration branch and pull requests using Python 3.12, Node.js 22 and Ubuntu FFmpeg. Local validation on 2026-10-11: **164 Python tests passed**, Ruff checks and the frontend build passed. The test suite includes synthetic media rendered and decoded with real FFmpeg; provider substitutes validate program behavior, not live Gemini quality. `uv run pytest -q -m "not media"` selects the tests outside the explicit media marker; FFmpeg is still required by some API/import checks.

Optional style research dependencies: `uv sync --frozen --extra dev --extra style-lab`. Reference profiles contain measurements and source URLs; reference videos are not distributed.

## Current limits

- Local filesystem storage only; authentication, cloud storage, public deployment and multi-worker execution are not implemented.
- Default web output is 1080×1920, 30 fps, SDR/H.264/AAC. All-HLG inputs can use 10-bit HEVC; mixed inputs use SDR, and HEVC playback depends on the browser/device. Filters that require SDR reject incompatible HLG settings.
- No automatic person cutout, custom sticker/font upload, arbitrary semantic editing or exact-duration guarantee.
- Automated checks do not establish real-footage aesthetics, transcription accuracy, native Safari/mobile compatibility or production load capacity. Live Gemini and manual browser acceptance need separate review with your own footage.

## Bundled assets

Runtime font/music provenance, hashes and license identifiers are recorded in [assets/manifest.json](src/vlogii/assets/manifest.json). Full notices remain in [assets/licenses/](src/vlogii/assets/licenses/), [style/fonts/](src/vlogii/style/fonts/), [frontend/public/fonts/](frontend/public/fonts/) and [frontend/public/font-licenses/](frontend/public/font-licenses/). Preserve these notices when distributing bundled assets. The repository does not currently declare a project-wide code license.

Credentials, uploaded media, generated films, caches and private validation records are excluded from Git.

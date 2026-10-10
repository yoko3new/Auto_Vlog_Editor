# Vlogii

![Vlogii logo](resources/branding/vlogii-logo.png)

The selected brand identity is a mint-green frame/play icon with a chunky lowercase `vlogii` wordmark. See [logo and usage guidelines](docs/visual-design.md#brand-logo).

A local web app that turns real footage into a small, editable vlog.

**Upload → Gemini video analysis → validated plan → FFmpeg export → preview, edit, undo and download.**

This is an independent implementation informed by a working VX workflow and its failure cases. It does not copy or import VX. New code, comments and documentation are in English.

## Start locally

Requirements: macOS or Linux, Python 3.11+, Node.js 20+, [uv](https://docs.astral.sh/uv/), and FFmpeg with text, H.264 and HEVC support.

```sh
# macOS; Ubuntu setup is in the guide below.
brew install ffmpeg-full

git clone --branch kang https://github.com/yoko3new/Auto_Vlog_Editor.git vlogii
cd vlogii
uv sync --frozen --extra dev
cp .env.example .env
```

Add your Gemini API key to `.env`, then build and start:

```sh
cd frontend
npm ci
npm run build
cd ..
uv run vlogii doctor
uv run vlogii serve
```

Open **http://127.0.0.1:8000**. The app automatically prefers Homebrew's `ffmpeg-full`; no manual linking is needed. Gemini receives low-resolution video copies for visual analysis and separately extracted audio for speech recognition. Credentials, exports and private AI records remain local and are ignored by Git.

Run one server process. This unauthenticated release is bound to localhost and is not ready to expose as a public service.

## Included

- Upload real footage, inspect metadata and deduplicate identical files.
- Gemini video understanding, source-language speech transcription and structured planning.
- Strict validation and deterministic frame-based timing before rendering.
- Original audio, speech captions, occasional text, portrait or landscape exports.
- Browser-friendly SDR/H.264 by default; optional all-HLG 10-bit HEVC preservation.
- Title changes, controlled warmth and clip exclusion without another AI call.
- Successful versions, undo, persistent actual progress, restart recovery and download.
- Full FFmpeg logs and output verification; failures preserve previous successful films.
- Retry failed generation or edits with their saved request, plan and completed segments.
- Chinese/English interface switching and a bilingual interactive CLI; creative direction is optional.
- AI auto, opening highlights, keep most or keep all; optional duration and clickable input examples.
- Delete precise ranges from the current film with timestamps or supported Chinese/English phrases.

Default models: `gemini-3.8-flash` for video/planning and `gemini-3.5-transcribe` for speech. Both use the same Gemini API key and are configurable. New model access passed a one-clip live run; accuracy still needs human-ground-truth evaluation; see [MVP fixes and model choices](docs/mvp-fixes.md).

Limits: 50 clips, 512 MB per clip, 2 GB per upload, 30 minutes of source footage. Target duration guides the AI; it is not guaranteed or padded with repeated footage. Warmth edits use SDR. HEVC playback depends on the browser and display. AI captions and editorial choices require human review.

## Verify

```sh
uv run pytest -q
uv run ruff check src/vlogii tests
uv run ruff format --check src/vlogii tests
cd frontend && npm run build
```

Tests include real FFmpeg exports. Provider test doubles verify failure handling, not live AI performance. Actual results and limitations are recorded in [local validation](docs/vlogii-validation.md).

## Documentation and scope

- [MVP feature coverage and remaining competition gaps](docs/mvp-coverage.md)
- [Editing modes, longer films and time-range changes](docs/editing-modes.md)
- [Free font/BGM candidates and default/upload design](docs/free-resources.md)
- [Team ownership and handoff](docs/collaboration.md): Yang Kang owns the video pipeline, AI, backend, renderer and integration; the teammate owns the frontend.
- [Setup, modules, CLI, supported formats and limitations](docs/vlogii-guide.md)
- [Local API specification](docs/vlogii.openapi.json); interactive docs at `/docs`
- [Implementation and validation status](docs/status.md)
- [Existing team product plan](docs/product.md) and [contracts](docs/contracts.md)

This branch implements the local vlog web MVP requested after VX validation. Existing team documents, schemas and substitutes are preserved as planning material. The application uses a separate `/api/vlogii` namespace; it does not claim compatibility with the older `/api` contract.

BGM, beat matching, magazine decorations, arbitrary natural-language editing, authentication, cloud storage, Replit deployment and NLE exports are outside this release. The original competition MVP is not presented as fully delivered.

Only source, dependency locks, English documentation and non-sensitive verification summaries are published. Footage, transcripts, AI caches, generated videos and keys are excluded.

当前产品方向：[生活记录 Shorts](docs/shorts-direction.md)（封面、闪切、正文）；已实现的速度与剪辑选项见[规则](docs/editing-modes.md)。

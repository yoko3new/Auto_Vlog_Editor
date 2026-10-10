# Vlogii

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

Open **http://127.0.0.1:8000**. The app automatically prefers Homebrew's `ffmpeg-full`; no manual linking is needed. Gemini receives low-resolution proxy videos for analysis. Source footage, credentials and private AI records remain local and are ignored by Git.

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

- [Setup, modules, CLI, supported formats and limitations](docs/vlogii-guide.md)
- [Local API specification](docs/vlogii.openapi.json); interactive docs at `/docs`
- [Implementation and validation status](docs/status.md)
- [Existing team product plan](docs/product.md) and [contracts](docs/contracts.md)

This branch implements the local vlog web MVP requested after VX validation. Existing team documents, schemas and substitutes are preserved as planning material. The application uses a separate `/api/vlogii` namespace; it does not claim compatibility with the older `/api` contract.

BGM, beat matching, magazine decorations, arbitrary natural-language editing, authentication, cloud storage, Replit deployment and NLE exports are outside this release. The original competition MVP is not presented as fully delivered.

Only source, dependency locks, English documentation and non-sensitive verification summaries are published. Footage, transcripts, AI caches, generated videos and keys are excluded.

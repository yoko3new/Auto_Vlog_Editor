# Two-Person Division of Work and Handoff

[中文](collaboration.md) · **English**

[Back to Overview](../README.en.md) · [Current Progress](status.en.md) · [MVP Feature Comparison](mvp-coverage.en.md)

The division of work on this page takes effect starting 2026-10-10; the arrangement from older documents where "B is responsible for rendering/title layout" is superseded by this page. The current baseline is the Vlogii local web MVP at `kang`, no longer building the skeleton from an empty repository repeatedly.

<a id="s13"></a>

## Two-Person Division of Work and Collaboration

<a id="s13-1"></a>

### Single Owner and File Scopes

**A = Yang Kang: Responsible for video generation logic, all video modules, backend, and integration. B = Teammate: Responsible for frontend.** The visual style of the finished video is implemented by A, and page visuals are implemented by B; both parties jointly watch the finished video, confirm requirements, and accept the closed-loop delivery. Coding assistants modify files only after taking on a specific file scope.

| Current File / Scope | Primary Owner | Handoff Boundary |
| --- | --- | --- |
| `src/vlogii/ai.py`, `speech.py` | A | Gemini video understanding, standalone audio transcription, clip selection, sorting, prompts, and plan validation |
| `src/vlogii/media.py`, `timeline.py`, `editorial.py` | A | Metadata, proxies, encoding/color, retain/fast-cut modes, time-range deletion/speed adjustment, frame timeline, subtitle mapping; B does not recalculate cut results in the browser |
| `src/vlogii/render.py` | A | FFmpeg, original audio/subtitles, title layout, warmth, output verification; newly added BGM/beat alignment/finished video styles also belong to A |
| `src/vlogii/pipeline.py`, `storage.py` | A | Analysis cache, generation/editing/undo, versions, locks, saving and restoration |
| `src/vlogii/api.py`, `models.py`, `cli.py` | A | HTTP, task queues, uploads, media routing, data models, debug entrypoints |
| `tests/**`, `pyproject.toml`, `uv.lock`, `.env.example` | A | Backend/media checks, Python dependencies, and server configuration; future deployment configurations also belong to A |
| `frontend/**` (including package.json, lockfile, Vite/TS configuration) | B | Page layout/styles, file selection/drag-and-drop, requests and polling, player, editing controls, undo/download, responsiveness, and accessibility |
| `docs/vlogii.openapi.json`, `contracts/**` | A | A maintains the structure, B submits fields required by the page; calling code on both sides stays synchronized with changes |
| Fonts, music, decorations, style presets for video, and rendered sample clips | A | B can propose design suggestions, but does not directly modify rendering implementations; frontend images and CSS belong to B |
| README, status, decisions, integration and deployment documentation | A | B provides frontend startup/build/joint-debugging evidence; for [Visual Specifications](visual-design.en.md), A manages the finished video section and B manages the page section |

Except for the first row, abbreviations for `src/vlogii/` paths in the table refer to files within that directory. Originally planned `api/`, `core/`, `style/`, and `tools/render_fixture.py`, if implemented later, will likewise be owned by A and will not belong to B simply because of old document paths. Directory migration requires a separate task, and existing code will not be moved this time.

<a id="s13-2"></a>

### Common Baseline and Current APIs

Both people first synchronize to the same commit of `kang` and reproduce the startup following the [Vlogii Guide](vlogii-guide.md). The teammate works on the frontend in their own directory/branch; Yang Kang maintains the video and backend logic on `kang`. Merging into `main` and formal release are still handled by A; current MVP uploads do not equal being merged or deployed.

- Current endpoint is `/api/vlogii`; see the [Current OpenAPI](vlogii.openapi.json) for fields, and check `/openapi.json` and `/docs` at runtime.
- Generation POST returns task status, frontend polls project GET to retrieve `job`, `latest`, `video_url`; the current task status is `queued/running/complete/failed`.
- Edits submit `title`, `warmth`, `exclude_clip_ids`; undo goes through `/undo`. Frontend consumes media URLs from the response and does not construct disk paths.
- This round of UX fixes adds `/retry` (no request body), `job.retryable/kind`, and optional `language`; see [Fix Records](mvp-fixes.en.md) for model defaults and real acceptance constraints. Frontend Chinese/English switching and retry buttons have been synchronized and will be maintained by B going forward.
- Added generation `mode`, nullable `target_seconds`, `remove_no_speech`, editing `remove_ranges/instruction`, and version `selection`; the page has synchronized modes and clickable examples. Omitting duration is changed from default 30 seconds to AI-decided; old callers can explicitly pass 30; see [Editing Modes](editing-modes.en.md).
- Generation added `speed/shot_seconds`, editing added nullable `speed` and `speed_ranges`; temporal commands support deletion/speed adjustment, and time coordinates are referenced to the same current finished video. The page single-select bar is synchronized with current OpenAPI; [Shorts Output Structure](shorts-direction.en.md) is the direction for the next batch, with covers/stickers/intro-body splicing still pending implementation.
- Bundled assets use `GET /api/vlogii/presets`. Generation/editing accept optional `appearance` containing `font/music/music_volume/duck_music`; project responses return the current successful version’s appearance. Older requests that omit it retain no music. A maintains the asset registry, versions/undo and rendering; page callers are synchronized. See [assets](free-resources.en.md).

- The legacy `/api` OpenAPI, `simulation`, `request_id`, `base_version_id`, and mocks were the original competition design; current Vlogii provides no such compatibility guarantees. You cannot replace the legacy mock with the Vlogii backend and assume frontend fields remain unchanged.

<a id="s13-3"></a>

### Next Handoff Steps Based on the Existing MVP

| Milestone | A: Video & Backend | B: Frontend | Shared Evidence |
| --- | --- | --- | --- |
| Reproduce Current Version | Verify environment/keys/FFmpeg, provide startup instructions, current APIs, and requirements for real test media | Build existing frontend, verify upload, generation status, preview, editing, and undo/download | Local closed loop on the same commit; clearly state unverified controls/environments |
| Define Next Batch of Requirements | Assess BGM, beats, magazine style, duration, natural language editing, and deployment against competition gaps | Organize page states and design requirements based on actual capabilities | Scope for each item, file owners, acceptance criteria; do not treat the gap list as an automatic authorization to start work |
| Authorized Development | Implement video/backend modules, deliver request/response examples, playable outputs, and constraints | Implement corresponding controls, states, and error feedback; maintain API consistency | Joint verification of the entire flow from upload to playback and each edit effect |
| Integration & Release Acceptance | Merging, dependencies, cloud saving/restoration, production runtime configuration, finished video/asset testing | Real API joint debugging, browser operations, display and download acceptance | Synchronized commits, build/test summaries, real MP4, and restoration results |

<a id="s13-4"></a>

### How to Proceed When Dependencies Are Not Ready

| Gap | Work That Can Continue | What Cannot Be Claimed as Passed |
| --- | --- | --- |
| Current backend temporarily unavailable | B develops pages using frontend fixtures matching `/api/vlogii` fields; existing legacy mocks are used only for old contract pages | Real upload/generation/restoration |
| Rendering or fonts not finished | A pinpoints video issues using fixed plans; B verifies player and layout using clearly labeled sample clips | Real style video export or title modification |
| AI call failure | A reuses existing plans to check real rendering; B refines failure and retry states | This run's AI understanding/clip selection |
| Deployment not finished | A handles deployment; B continues local real API joint debugging | Replit formal verification |

When blocked, save reproducible inputs, errors, and minimal commands, and pass them to the owner of the corresponding files. If cross-scope modifications are needed, hand off files first; concurrent editing by both parties is prohibited; there is no need to have the teammate maintain rendering implementations.

<a id="s13-5"></a>

### Merging and Contract Discipline

- Use independent working directories/branches; do not switch branches or edit the same file concurrently in a shared directory. New branches can use `codex/video-pipeline`, `codex/frontend`; existing `kang` can continue to be used.
- A is responsible for integrating `main`; B delivers frontend changes along with build/operation evidence; merge in small steps per feature.
- Current API changes synchronize models, OpenAPI snapshots, tests, and frontend call sites. Legacy contracts update schemas, samples, and doubles only when actual changes occur; do not silently claim that the two sets of APIs are compatible.
- Frontend lockfiles are updated by B; Python lockfiles are updated by A. Conflicts are resolved and validated by owners, avoiding whole-file overwriting.
- After modifications to the main flow, run from upload to playback with the same set of real media; provider doubles and real Gemini results are logged separately.
- Record commits and configurations upon release, keeping stable versions first; do not promote local success to online success without cloud acceptance.

<a id="s13-6"></a>

### Startup, Configuration, and Definition of Done

Currently using `src/vlogii/`, `frontend/`, `tests/`; local projects are saved by default in `projects/`. Actual installation requirements, commands, and limitations are subject to the [Guide](vlogii-guide.md):

```sh
uv sync --frozen --extra dev
npm --prefix frontend ci
npm --prefix frontend run build
uv run vlogii doctor
uv run vlogii serve
```

The service defaults to `127.0.0.1:8000`, with production builds served by FastAPI; frontend development uses a proxy configured in Vite, calling relative `/api/vlogii`. A manages server-side configurations in `.env.example`, and secret keys do not enter the frontend or `VITE_` variables.

Provide for each handoff: commit/file scope, API basis, startup or invocation commands, reproducible inputs, actual results, and limitations. Frontend build passing does not mean the full flow in video or browser passes; local JSON restoration does not mean App Storage/formal deployment restoration. Private media, transcriptions, raw AI logs, caches, secret keys, and generated videos are not committed to Git.

<a id="s14"></a>

## Scope of Application for Competition Stages

The original 36-hour plan represents competition acceptance targets and is no longer a schedule for "current development from scratch." The current implementation already possesses original audio subtitles, vertical video, and other capabilities, but still lacks beat syncing, magazine style, natural language editing, fixed duration, and Replit verification; see [Coverage Comparison](mvp-coverage.en.md) for details.

The original competition scope was not changed in this adjustment; if continuing to participate under that scope, verify in sequence:

1. [Replit Environment, Formal Closed Loop, and Actual Workload](deployment.en.md#s18-2). Local success cannot replace the production environment.
2. [AI Clip Selection Quality](ai-selection.en.md#s20-4): Key moments, repetitions, scopes, and final output; existing Gemini integration does not need to be redone from scratch, but quality evidence is still required.
3. [Entire MVP Acceptance](acceptance.en.md#s15-1): Competition finished video, three types of edits, failure protection/undo, second set of media, save/restore/download.
4. Decide on newly added scopes only after passing, freeze stable versions, rehearse, and prepare backups; specific new work must be explicitly authorized.

## How Coding Assistants Participate

A/B is a human division of responsibilities; coding assistants adhere to the same file ownership and interfaces. Each person may choose their own tools; there is no requirement to unify individual agent configurations, nor will video rendering be assigned to the frontend owner based on legacy role templates. Status and decisions are consolidated and maintained by A.

# HTTP and Module Handover

[中文](api.md) · **English**

[Return to Project Overview](../../README.en.md)

When to read: Read when modifying original competition interfaces/states or video module designs. Currently, `/api/vlogii` is based on the [Current OpenAPI](../vlogii.openapi.json) and the [Vlogii Guide](../vlogii-guide.md); this page is the legacy `/api` plan and cannot be directly connected to the current frontend. In the new division of labor, A (Yang Kang) is simultaneously responsible for scheduling, layout, and rendering, while B (teammate) is solely responsible for the frontend.

<a id="s10"></a>

## How Frontend and Backend Interact: Starting from a Single Click

<a id="s10-1"></a>

### Understanding a Single Generation

User clicks "Generate" → React sends project ID, request ID, and modifiable settings via `fetch()` → FastAPI returns `202 Accepted` and `job_id` → Background worker processes the task → React polls status every 1–2 seconds → Obtains `video_url` upon completion, passing it to `<video>` for playback.

`job_id` is like a meal pickup number: grab the number first, query progress during processing, and retrieve results when done. Generation and modifications must not make the browser hang on a prolonged HTTP response.

<a id="s10-2"></a>

### HTTP Interface Conventions: Frontend and Backend Develop Against the Same Samples

Attached are the [OpenAPI 3.1 Interface Definitions](../../contracts/collaboration/api.openapi.json) and [31 Request/Response and State Samples](../../contracts/collaboration/api.examples.json). These definitions complete the HTTP handover, while the original `contracts.schema.json` continues to handle the six project and clip data categories. **Existing samples and mocks are development materials and do not indicate that real APIs are implemented.** The full package is placed in this repository at `contracts/`, with both collaborators using the same commit version.

All JSON responses consistently include `api_version: "1.0.0"` and `simulation: boolean`. Samples and stubs return `true`; the actual backend returns `false` only when using a real implementation. Successful responses are named by resource as `project`, `clip`, `job`, or `versions`, without an extra `data` wrapper. Fields defined as nullable must still be present, using `null` to indicate that there is no value yet; empty collections return `[]`.

| Endpoint | Request | Success Response |
| --- | --- | --- |
| `GET /api/health` | None | 200; `status`, `execution_mode`, upload limits, and mock flags |
| `POST /api/projects` | JSON: `request_id` | 201; `project`, containing `project_id`, complete default settings, and empty asset list |
| `POST /api/projects/{project_id}/clips` | multipart: `request_id` + **one** `file` | 201; `project_id`, `clip`, containing asset ID, duration, orientation, filename, and nullable thumbnail URL |
| `GET /api/projects/{project_id}` | None | 200; `project`, restoring settings, assets, `current_version`, `active_job_id`, `pending_selection` |
| `POST /api/projects/{project_id}/generate` | JSON: `request_id`, `settings`; default `settings: {}` | 202; `project_id`, `job_id`, without waiting for rendering |
| `POST /api/projects/{project_id}/edits` | JSON: `request_id`, `base_version_id`, `input` | 202; `project_id`, `job_id` |
| `GET /api/jobs/{job_id}` | None | 200; `job`, fixed fields detailed below; this query can still return 200 successfully even if the task fails |
| `GET /api/projects/{project_id}/versions` | None | 200; `project_id`, `current_version_id`, `versions`, ordered with the latest created version first |
| `POST /api/projects/{project_id}/current-version` | JSON: `request_id`, current `base_version_id`, target `version_id` | 200; updated `project`; restores target version settings without creating a new version |
| `GET /api/projects/{project_id}/versions/{version_id}/video` | Optional `Range` header; download uses `?download=true` | MP4 bytes, 200 or 206 for single-range Range; returns 416 for invalid range |
| `GET /api/projects/{project_id}/clips/{clip_id}/thumbnail` | None | Actual JPEG bytes; when thumbnail is not yet available, asset contains `thumbnail_url=null`, and frontend displays placeholder image |

Uploads are executed by the frontend file by file, one file at a time, keeping retry access points for failed files. Uploads may continue before the initial version is generated; uploads, modifications, and version switching are prohibited during generation; once a successful version exists, the asset set is fixed, and additional assets are handled via a new project. `generate` is used for the initial generation or retrying after an initial failure, whereas `edits` is used once an edited video exists, avoiding differing understandings between both parties regarding "whether re-generating clears history".

HTTP `settings` is a whitelist of initial settings; MVP accepts only optional `title_overrides` and `warmth_override`, not the entire `config.settings`. Fixed styles, BGM, output specifications, and exclusion lists are populated by the backend. When the frontend needs complete settings, it reads `project.settings` or `version.settings` instead of maintaining another set of default values on its own.

`input` takes only one form: natural language uses `{"kind":"instruction","text":"暖一点"}`; fixed buttons or ambiguity confirmations use `{"kind":"operations","operations":[{"type":"set_warmth","value":0.25}]}`. When confirming deletion, submit explicit `remove_clip` and new `request_id`, while still checking the original `base_version_id`. Canceling a selection merely collapses the UI without submitting an edit request. When reopening a project, the backend restores unconfirmed candidates via `pending_selection`; this does not occupy the executor.

**Task query fields are fixed:** `job_id`, `project_id`, `request_id`, `kind`, `base_version_id`, `status`, `message`, `progress`, `version_id`, `video_url`, `summary`, `resolution`, `error`, `created_at`, `updated_at`. Times are UTC ISO 8601 strings. `progress` is `null` or `{completed,total,unit}`, used only for stages with a genuine total, not as a fake total progress.

- Active tasks: `version_id/video_url/summary/resolution/error` are all `null`.
- `done`: Fill in the successful version, media URLs, and actual modification summary; `resolution/error=null`. Frontend then re-reads the project, updating the current version and settings.
- `needs_selection`: Only fill in the selection structure of [`edit_request.json`: Modification is a controlled operation, not an arbitrary JSON patch](timeline.en.md#s6-8), candidate thumbnails are looked up from the project asset list by `clip_id`; no successful version is generated.
- `failed/interrupted`: Fill in `error: {code,message,retryable}`; retain the project's old successful version. `retryable` indicates that the user can initiate a new request to retry, without requiring the frontend to automatically retry generation.

**API request failures uniformly return:** `{"api_version":"1.0.0","simulation":false,"error":{"code":"STALE_VERSION","message":"请刷新项目后重试","retryable":false}}`. Fixed handling for 400 bad request format, 404 missing resource, 409 project busy / version conflict / idempotency conflict, 413 payload too large, 415 unsupported format, 422 data validation error, 429 queue full, 500 internal error; FastAPI default validation errors are also converted into the same wrapper. Rendering failures for accepted tasks are written to `job.error`, preventing the frontend from conflating the two types of errors.

`request_id` is generated by the frontend, reusing the original value for the same network retry; a new value is generated when the user amends content or actively retries a failed task. The backend uses project, operation, and `request_id` as the idempotency key, checking first for existing requests, then busy status and version conditions; identical requests return original results without re-queuing, while identical IDs with different content return 409. Uploads compare file content and valid form fields, rather than determining different files based on multipart random boundaries.

Media URLs use relative same-origin addresses, which the frontend consumes directly as opaque values without constructing disk paths or object storage keys on its own. HTTP 200/206 playback returns bytes, not wrapped in JSON; version downloads set attachment filenames. Media and version routing as well as the renderer are all implemented by A; the render module maintains an independent boundary from media services.

<a id="s10-3"></a>

### Separate Page and Task States

Page main flow: `empty → ready → processing → done`; additionally `awaiting_selection` and error prompts. Background main flow: `queued → analyzing → planning → rendering → done`; exceptions/unsupported are `failed`, interruptions are `interrupted`, and ambiguity results in `needs_selection` which terminates the current task. The latter does not occupy the executor, nor does it create a successful video version; after confirmation, a new request is created to re-verify the baseline version.

Analysis, planning, and rendering are actual stages, without pretending to know what exact percentage of the entire process is completed. Only steps with an explicit total display numbers like "Analyzed 8/15 segments".

Re-generation and modification are disabled during processing, but the previous version player is preserved. Task failure retains the old edited video and original assets, displaying a retry entry point. Polling stops upon completion, failure, interruption, awaiting selection, or component unmount, and resumes querying the same task once a temporary network disconnection recovers.

<a id="s10-4"></a>

### A Single Shared Queue to Ensure Stability First

The prototype employs a single FastAPI service process (Uvicorn `workers=1`), a single shared queue, and a background execution thread. Both generation and modification enter the same queue; the worker thread invokes the synchronous pipeline and spawns an FFmpeg child process. Set a relatively small upper limit for the queue; prompt to retry later when full, preventing unbounded backlogs.

The API atomically inspects project busy status, duplicate requests, and baseline versions before enqueueing; after processing completes, it confirms the version relationship of the submitted result once again. Do not rely solely on the frontend disabling buttons; the backend must still reject outdated `base_version_id`.

Do not run blocking transcoding directly inside `async` routes, nor mistakenly assume that FastAPI's `BackgroundTasks` automatically provides a reliable queue. Official recommendations suggest considering an independent task system for heavy background computation; this single-instance approach is a tradeoff for a controlled demo, with independent workers and persistent queues added later. [FastAPI Documentation](https://fastapi.tiangolo.com/tutorial/background-tasks/)

Task progress is written to project records, read by pages via the API. Each task is configured with a timeout; upon exception or timeout, child processes are cleaned up and the busy state is released, while legacy tasks are marked as interrupted upon startup.

<a id="s10-5"></a>

### Independent Development and Stub Switching for Both Sides

When B develops the frontend, run the accompanying [Local mock API](../../contracts/collaboration/mock_api.py) and implement pages according to OpenAPI and the same samples without waiting for A's API. The mock listens on `127.0.0.1:8000` by default; Vite proxies `/api` to this address. When switching to the real backend, only the service changes, while page components and fields remain identical. Both JSON and media responses are tagged as mocked, and the frontend continuously displays "Mock Data / Development Mode" after reading the health check.

When A develops queues, versions, and error recovery, use [Rendering Stubs and Module Types](../../contracts/collaboration/runtime_contracts.py) to inject `RenderStub`; success mode copies explicitly provided test files, and failure mode throws agreed errors, without relying on full FFmpeg implementation. Replace with the same interface once the real renderer is ready. Results involving any stubs remain `simulation=true`, use independent test directories, and cannot be committed as real successful versions or used to pass Replit acceptance.

When A develops the render module independently, read the [Nine-Second Timeline](../../contracts/collaboration/smoke9.timeline.json) and [Asset Path Mapping Example](../../contracts/collaboration/asset-paths.example.json), outputting MP4 directly from local files without waiting for API, storage, or AI. The mapping example does not include real media; prepare real files during the first hour and update mappings and asset manifests according to actual metadata.

The mock is a single-project, in-memory state service supporting success, failure, interruption, awaiting selection, and continuous in-progress scenarios; uploads only perform form validation and return mock metadata, natural language does not call models, and data resets upon restart. Test video playback is available only when `--media` is provided; returns `FIXTURE_MEDIA_MISSING` when not provided, without fabricating files. It supports frontend interaction development and does not substitute for real uploads, persistent recovery, AI, video quality, and resource testing.

API keys exist only in backend environment variables / Replit Secrets, and are not written to the frontend or `VITE_` environment variables. In the early stages, manual plan mode can be configured with real rendering for environment verification, during which the health check is `execution_mode=manual_plan`; marked as `ai` only after the full model pipeline is operational. When using mock API, it is `mock`.

<a id="s10-6"></a>

### Python Video Module Boundary: A Maintains Scheduling, Layout, and Rendering

Below are the module signatures from the original competition plan, with accompanying `runtime_contracts.py` providing types/stubs; the legacy A/B role descriptions no longer serve as personnel task allocations. Vlogii currently uses its own `pipeline.py`, `timeline.py`, and `render.py`, and has not yet adapted to these signatures. Personnel assignments are unified per the [Collaboration Handbook](../collaboration.en.md#s13-1), while module boundaries remain preserved.

| Call | Implemented by / Called by | Fixed Boundary |
| --- | --- | --- |
| `render_timeline(request, on_progress) -> RenderResult` | Implemented by A's render module, called by background worker thread | Receives complete `timeline.json`, asset ID to local path mappings, independent working directory, output path, timeout, and cancellation check; executes synchronously, returning local output along with measured width, height, fps, and frame count |
| `layout_title(request) -> list[Overlay]` | Implemented by A's layout module, called before timeline compilation | Receives final three-tier titles, style ID/version, output specifications, display frame count, and font path; returns typesetting compliant with existing Overlay schema after measurement, without inventing another coordinate format |
| `on_progress(RenderProgress)` | Implemented by A's pipeline, callback from render module | Render module reports processed frames, total frames, and text; pipeline uniformly persists task status to disk, render module does not write to `jobs/` |
| `ModuleError(code,message,retryable)` | Thrown by render module, caught by pipeline | Explicitly reports errors for missing assets, missing fonts, text overflow, rendering failure, timeout, or cancellation; render module terminates child processes, pipeline releases queue and preserves old versions |

Asset IDs are registered by A, storage keys are resolved by A, and necessary files are prepared locally by A. The render module only accesses passed paths, without constructing cloud addresses, creating projects or versions, or altering shot durations on its own. A verifies returned files against the timeline after rendering, saves App Storage, and commits version pointers; success must not be claimed merely because the render function returned normally.

Title layout adopts two steps: A's layout function determines line wrapping, font size, and position before compilation; A writes the result to the timeline; the render module draws transparent layers based on the same result without re-typesetting. When the layout function is not yet complete, A tests the pipeline using the attached fixed timeline, keeping the title editing feature as pending integration testing, without faking real font measurements.

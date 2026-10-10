# Two-Person Collaboration Package: Start Without Waiting for Each Other

[中文](README.md) · **English**

This directory contains interface contracts and test doubles for development. **It is not the finished Auto Vlog application, nor does it include videos, music, fonts, or keys.** The [Interface Documentation](../../docs/reference/api.en.md) defines handoffs, and the [Collaboration Manual](../../docs/collaboration.en.md) organizes divisions of labor; real video production and Replit acceptance testing will still proceed according to the original checkpoints.

This package is already located at `contracts/` in the application repository. Both developers start from the same Git commit, without maintaining separate copies of the contract.

This package was planned for the original competition `/api`; the current Vlogii uses an independent `/api/vlogii` and the [current OpenAPI](../../docs/vlogii.openapi.json), and is not directly compatible with the mocks in this package. Under the new division of labor, A (Yang Kang) maintains the backend and all video modules, while B (teammate) maintains the frontend; the A/B comments in the original type files are historical notes, and ownership follows the [Collaboration Manual](../../docs/collaboration.en.md#s13-1).

## Which Files to Check First

| File | Purpose | Primary User |
| --- | --- | --- |
| `api.openapi.json` | Field definitions for HTTP requests, responses, statuses, and errors | A implements API, B connects pages |
| `api.examples.json` | 31 directly viewable request/response and status samples | A, B |
| `mock_api.py` | Runnable local mock API | B, without waiting for the real backend |
| `runtime_contracts.py` | Renderer, title layout, progress, and error types; includes RenderStub | A's video modules |
| `smoke9.timeline.json` | Fixed timeline with three 3-second segments | A's rendering module, without waiting for AI or API |
| `asset-paths.example.json` | Example mapping from asset IDs to local files | A prepares and renders |
| `validate_collaboration.py` | Sample consistency and development double checks | Run before merging |
| `contract_utils.py` | Limited schema checker used by doubles and check scripts | Internal tool usage |

## B: Mock API Ready to Connect Now

Run in this directory, using Python 3.10 or newer, without installing third-party packages:

```sh
python3 mock_api.py --port 8000 --scenario success
```

Visit `http://127.0.0.1:8000/api/health` to check the service. The service only listens locally; Vite configures `/api` to forward to `http://127.0.0.1:8000`, and React always calls relative paths. When switching to A's real service, stop the mock and start the real service, without changing fields in components.

By default, there is a `project_demo` containing ten virtual asset records, which can directly call the generation endpoint. `POST /api/projects` resets this single sandbox project when creating an empty project; this limitation only applies to the mock. Uploading passes `request_id` and a `file` via multipart; file contents are discarded, returning simulated metadata such as an eight-second duration.

Simulated video playback requires an additional local MP4; stop the old service before running:

```sh
python3 mock_api.py --port 8000 --scenario success --media /absolute/path/sample.mp4
```

All versions play the same file; the mock does not check whether it matches the timeline or declared duration. When `--media` is not passed, the video endpoint explicitly returns `FIXTURE_MEDIA_MISSING`, while other states remain available for development. Thumbnails return `null`, and the page uses a placeholder image. The media route supports single-range requests, byte responses needed for scrubbing, and download parameters; actual browser playback and real output videos still require separate acceptance testing.

Start different scenarios with the following parameters; stop the old service occupying port 8000 each time:

| `--scenario` | What Can Be Checked |
| --- | --- |
| `success` | Generation, completion, version list, undo, explicit operation modifications |
| `failed` | Prompts after task failure, retry entry points, and clearing busy status |
| `interrupted` | Prompts after interruption and retry entry points; this is a simulated state, not a restart-recovery test |
| `needs_selection` | Generate the initial version first, then submit natural language edits; when candidates appear, submit explicit `remove_clip` to complete |
| `rendering` | Stays in processing continuously, checking duplicate submission prevention and preservation of old previews |

Task status advances with polling count, typically entering the final state on the third query. Static states such as analysis/planning can fetch fixtures from `api.examples.json`. Natural language in the mock will not actually understand or modify the video; only explicit operations update mock settings. Re-read the project after the task completes; when ambiguity occurs, read `pending_selection`, and confirm the choice using a new request ID and the original baseline version.

Every JSON response includes `simulation: true`, and all responses contain `X-Auto-Vlog-Simulation: true`. The frontend continuously displays "Simulated Data / Development Mode". The scope of the mock is forms, interactions, and statuses; it does not verify real media, cumulative upload volume, AI performance, persistent storage, restart recovery, or online assets. Do not record formal acceptance based on its successful outcomes.

## A: Test Your Queue with the Rendering Double

`runtime_contracts` can be imported from this directory. When used in the application, A confirms the sole import path, avoiding separate type definitions created by each developer.

```python
import json
from pathlib import Path
from runtime_contracts import RenderRequest, RenderStub

request = RenderRequest(
    timeline_document=json.loads(Path("smoke9.timeline.json").read_text()),
    asset_paths={},  # 替身不读取资源；真实渲染必须提供完整映射。
    work_dir=Path("/tmp/auto-vlog-stub/job-001"),
    output_path=Path("/tmp/auto-vlog-stub/job-001/preview.mp4"),
    timeout_seconds=120,
    is_cancelled=lambda: False,
)
result = RenderStub(Path("/absolute/path/sample.mp4")).render_timeline(
    request, lambda progress: print(progress)
)
assert result.simulation is True
```

Success mode only copies the specified file; dimensions and frame counts come from the request and are not actually measured. Switch to a new task directory when running repeatedly, as existing outputs will be rejected from being overwritten. Use `RenderStub(fail=True)` to check whether failures release the queue and retain old successful versions; `is_cancelled` returning `True` can simulate pre-invocation cancellation. It does not implement real subprocess timeouts or in-flight cancellation.

The real Renderer must adopt the same function signature, measure actual output, return `simulation=False`, and terminate FFmpeg on timeout/cancellation. A maintains all video modules; the pipeline validates results, writes storage, and commits versions, while the rendering module does not write project records. Doubles and real tasks use different test directories; stub mode is prohibited in formal releases.

## A: Independently Develop the Real Rendering Module (Original Contract Plan)

1. Read `smoke9.timeline.json`: all three shots start from their respective second zero, totaling 270 frames at 30 fps.
2. Copy the path mapping example into your own `fixtures/local-paths.json`, providing three segments of real footage of at least three seconds, along with BGM, font, and decoration files referenced by the timeline. Paths resolve relative to the application repository root; A and B share asset IDs.
3. Update metadata such as duration and orientation in the asset list based on actual videos; do not treat assumed values from samples as probe results.
4. Implement the rendering CLI agreed upon in `Renderer.render_timeline()` and the [Collaboration Manual](../../docs/collaboration.en.md#s13-6). This CLI is **not included in this package** and will be created by A in tasks that explicitly require adapting the old contract; the current Vlogii uses its own CLI.
5. Title layout is independently implemented via `TitleLayouter.layout_title()`; A's timeline module calls it, and the rendering module renders strictly according to the returned Overlay.

This planned path does not require a full API or AI. The current Vlogii already has its own real rendering module and will not be redeveloped simply to retain the to-do items here; B can advance the frontend using clearly labeled sample videos.

## Pre-Merge Checks

Enter `contracts/` from the repository root, then run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 validate_examples.py
PYTHONDONTWRITEBYTECODE=1 python3 collaboration/validate_collaboration.py
```

The second check verifies HTTP samples, data definitions copied inside OpenAPI, the nine-second timeline, as well as mock request deduplication, expired versions, failures, pending choices, version switching, and media byte-range responses. By default, HTTP request bytes are passed to the same handler, reading and writing responses via memory without opening ports; media tests use temporary byte files and **do not prove that these bytes constitute valid video**.

The current delivery environment does not permit listening on local ports, so real HTTP service connectivity has not been verified. On a development machine, you can run the following additional command; it temporarily starts a random local port and shuts it down automatically, without accessing the external network:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 collaboration/validate_collaboration.py --http
```

The two checkers only cover the rules used in this package and are not complete, standard OpenAPI / JSON Schema validators. Real applications still require standard field validation and semantic checks from the [Timeline Documentation](../../docs/reference/timeline.en.md); after connecting to real implementations, use the same set of requests to verify the response contract before performing real upload-to-playback, persistent recovery, and Replit load testing.

Current delivery checks: the original 13 data samples passed, and 19 negative cases were rejected as expected; 11 new sets of collaboration checks passed, covering all 31 HTTP samples, copied definition consistency, the nine-second timeline, and in-memory request processing. Real port connections, browser playback, FFmpeg, or Replit tests have not yet been executed.

## Four Items to Fill In Before Starting Work

- Names and branch names of A and B.
- Mutually verified versions of Python, Node, and package manager, as well as backend configuration owner A.
- Acquisition location and file hashes for real assets; media, keys, and caches are not stored in Git.
- First real integration time: target 4th hour; continue with doubles if blocked, and both parties still perform real acceptance testing.

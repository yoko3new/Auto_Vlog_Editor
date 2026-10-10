# Local Development and Replit Verification

[中文](deployment.md) · **English**

[Return to Project Overview](../README.en.md)

When to read: Read when dealing with Replit deployment or production environment failures; all real Replit stages are currently unverified. For the current Vlogii local startup, see the [Practical Guide](vlogii-guide.md), using `src/vlogii/` and `/api/vlogii`; the legacy `api/core` directory and interfaces below represent the original competition plan and must be explicitly adapted during deployment. A (Yang Kang) is responsible for the backend, video, and deployment; B (teammate) is responsible for frontend joint debugging.

<a id="s18"></a>

## How Codex and Replit Collaborate and Deploy

<a id="s18-1"></a>

### Recommended Development Approach

**Continue prioritizing local development: Edit and debug locally → Save code to GitHub → Pull, run, and formally publish on Replit.** Using Replit does not require migrating all daily coding to the browser; in this project, Replit first handles cloud verification and launching, deploying both the frontend and backend as a single application.

Use a single GitHub repository as the code handover point: Codex modifies code locally, verifies, and commits; Replit imports the same repository, pulls updates, runs, and previews. Changes made in Replit are also committed and pushed, then pulled locally. Git synchronization requires explicit operations; files are not automatically synchronized in real time between both sides. [Replit Import Instructions](https://docs.replit.com/build/import-from-providers), [Version Control Instructions](https://docs.replit.com/learn/projects-and-artifacts/version-control)

It is recommended to have Codex focus on interfaces, timeline, rendering, and troubleshooting, while letting Replit Agent assist with building pages and checking the runtime environment; this is a division of labor recommendation, and both can participate in frontend and backend work. For each task, clearly define the file scope, branch, and acceptance criteria in the [Kickoff Agreement and Single Owner](collaboration.en.md#s13-1) to avoid two Agents rewriting the same files simultaneously. Official deployment is executed by A using the merged main branch.

This solution does not rely on a dedicated Codex–Replit connector. API keys are configured separately in Replit Secrets and will not automatically be fully set up just by importing the GitHub repository.

<a id="s18-2"></a>

### Kickoff Verification: Confirm Replit Works Before Integrating AI

**Goal: Prove that real footage can complete "upload → background editing → save → play and download" in the Replit production environment.** First, use a fixed editing plan to isolate platform issues; after passing, integrate AI, refine the magazine style, and implement the three types of edits. These are kickoff steps for the same MVP; do not build a separate verification application, nor add additional work stages beyond the 36 hours.

Current status: All stages below are **unverified**. Existing JSON checks do not represent successful FFmpeg or Replit actual testing.

**Prepare Minimum Samples and Pages**

- Three 1080p SDR video clips, each at least 3 seconds long, plus an available BGM track of sufficient length and actual font files. Footage paths in the accompanying JSON are only examples and do not contain real media.
- In the first round, take 3 seconds from each clip in a fixed order, mute original audio, add fixed titles, a subtle warm tint, and BGM; hard cut to output a 9-second, 1280×720, 30 fps, H.264/AAC MP4.
- The page only requires upload, generate, real processing status, player, and download; project links include `project_id` for easy restoration upon reopening.
- The backend registers real footage IDs, and the program compiles manual `edit_plan.json` into `timeline.json` conforming to [JSON Data Contract: Usable for MVP, Extensible for V2/V3](reference/timeline.en.md#s6); do not directly use placeholder asset references. The 9-second sample uses `duration_policy.mode=natural`, `target_seconds=null`, and `tolerance_frames=0`, totaling 270 frames; this is a development verification sample. The official MVP initial generation still defaults to 30 seconds, and no 9-second option is added for users.

**Stage A: Environment is Operational (0–2 Hours)**

| Check Item | Specific Operation | Passing Criteria |
| --- | --- | --- |
| Local-to-cloud code handover | Create `frontend/`, `api/`, `core/`, and `/api/health`; push to GitHub, import to Replit, and sync a page text change once | The same codebase starts; verified that the pulled commit is the latest |
| Video processing dependencies | Check Node, Python, FFmpeg, ffprobe, fonts; run a small video composition command using real footage | Actually outputs a valid MP4 with titles, color grading, and music; successful installation or printing version numbers cannot replace final video output |
| Deployment configuration | Review available deployment types, CPU, memory, and costs; build frontend, serve web pages, `/api`, and media endpoints via FastAPI, then publish the minimal skeleton | `/api/health` at the production URL is accessible; record build/start commands, ports, and machine specifications |

A beautiful interface or AI is not required at this point. Subtitles and cross-dissolve dependencies remain to be verified separately during the corresponding V2/V3 stages.

**Stage B: Production URL Completes Minimal Closed Loop (2–6 Hours, Do First)**

After passing the development preview, retest the following items on the officially published URL. Preview and production deployment are two separate environments, and page changes require redeployment; do not use Preview test results to fill in production environment acceptance records. [Replit Publishing Instructions](https://docs.replit.com/build/publish-your-app)

| Check Item | Specific Operation | Passing Criteria |
| --- | --- | --- |
| Upload and background processing | Upload three clips from the production web page and click generate using a manual plan | Endpoint promptly returns `job_id`; backend actually renders, polling displays real stages, web page remains responsive |
| Continue after leaving page | Close page after confirming task entered rendering, then reopen the same project link | While service is still running, task continues processing; reopening retrieves status and results |
| Playback and download | Play on web page, scrub progress bar, then download to computer and play | Video, title, warm tint, and music are correct; media endpoints support scrubbing playback, downloaded file is usable |
| Persistent storage and recovery | Confirm original footage, project/version JSON, and final video are written to App Storage; restart production service or redeploy after success, return to the same project link | Can restore footage records and successful versions, re-play, and download; confirm recovery reads App Storage files rather than relying solely on old process memory or local cache |
| Error and queue recovery | Submit invalid files; also, in test mode, cause a queued rendering task to fail, then submit a normal task | Invalid files show prompts; background failure is recorded and releases queue, subsequent normal tasks complete, old final video remains playable |

App Storage is used to persistently store files, while local directories only serve as temporary workspaces during processing. For the specific storage sequence, see [Do We Need a Database: Not for Single-Instance Demo, but Persistent Storage Is Required](architecture.en.md#s11). [App Storage Documentation](https://docs.replit.com/features/data-and-storage/object-storage)

**Closing the page and restarting the service are two different scenarios.** When closing the page, the service is still running, and background tasks should continue; a restart terminates running tasks. The MVP only requires marking them as `interrupted` and allowing retries, while retaining previously successful versions, without promising breakpoint resumption. Refreshing the page cannot replace a restart test; restart once during rendering to confirm it does not show "processing" forever.

**Stage C: Realistic Footage Volume Can Be Processed Stably (2–6 Hours, Do After B Passes)**

Input 10–15 compliant clips with a total duration not exceeding 3 minutes, containing sufficient usable intervals; generate a ~30-second, 720p video according to the manual plan, including titles, warm tint, and BGM. Execute three complete serial renderings consecutively without reusing old final videos to fake re-generation. Record differences between initial processing and cache reuse.

Record the time consumed for upload, reading/normalization, timeline calculation, rendering, and saving to playable state respectively, along with CPU/memory status, total footage bytes, and machine specifications. All three runs should actually complete, with normal audio and video, without out-of-memory errors, process exits, or hung tasks; determine the acceptable upload size ceiling for current deployment accordingly. If a metric cannot be read, mark it as "Not collected"; do not fill in estimated values.

Passing the 9-second sample only proves that the basic pipeline is viable. Stage C tests processing loads close to the MVP; AI is not involved at this point, so duration cannot be regarded as complete AI generation speed. 90 seconds remains an optimization goal, and stable completion is the primary criterion for this stage.

**Records and Failure Handling**

Record each item as "Pass / Fail / Unverified", accompanied by test time, code commit, production environment configuration, `project_id` / `job_id`, elapsed time, and final video or log location. After changes to environment, rendering configuration, or storage implementation, retest affected stages; after integrating AI, re-verify the full MVP according to [Staged Acceptance, Performance, and Risks](acceptance.en.md#s15).

| Symptom | Primary Troubleshooting | Impact on Subsequent Work |
| --- | --- | --- |
| Runs locally, fails to start on Replit | Dependencies, font paths, build and start commands, ports | Fix environment first; do not proceed with layering AI |
| Preview succeeds, production link fails | Deployed version, dependencies, environment variables, App Storage access configuration | Production environment is still considered failed |
| Tasks lost after closing page, or one failure blocks all tasks | Whether tasks run independently of requests, whether status is written, whether exceptions release queue | Fix background lifecycle before proceeding |
| Old final video cannot be found after restart | Whether files are truly persistently saved, whether project pointers and reading logic are correct | Fix saving and recovery; do not substitute with browser cache |
| Sample succeeds, realistic footage volume fails | Memory, temporary disk, input normalization, FFmpeg thread count, and machine specifications | Retest after optimization; if reducing promised scope, synchronize [Phased Delivery: MVP Mandatory, V2 Expressive Enhancements, V3 Capability Expansion](product.en.md#s2) and record clearly, cannot continue claiming MVP compliance |

Only when stages A, B, and C all pass by Hour 6 should the team proceed to the first round of AI footage selection testing in [AI Footage Understanding and Clip Selection Testing: First Test at Hours 6–7, Final Video Verified Before Hour 14](ai-selection.en.md#s20-4), and then advance the main pipeline to AI automated orchestration. If not passed, pause AI integration and extra effects, troubleshoot specific blockers first; for fallback plans, see [Selection of Deployment Types](deployment.en.md#s18-3).

<a id="s18-3"></a>

### Selection of Deployment Types

For single-instance prototypes where "FFmpeg must continue running after HTTP returns", **prioritize evaluating Replit Reserved VM**, which is suitable for long-running APIs and background tasks. Autoscale can scale to zero and add instances, requiring extra handling for task lifecycle, shared queues, and cross-instance state; Static cannot execute this Python backend. This choice is based on project architecture fit, not platform performance testing. [Replit Deployment Types](https://docs.replit.com/features/publishing/deployment-types)

Confirm available deployment types, CPU/memory, and costs for the account within the first 2 hours. If resources are insufficient, check serial execution, FFmpeg thread counts, and footage normalization first, evaluating affordable machine specifications if necessary. Reducing footage volume or output dimensions can help isolate bottlenecks; if used as the final delivery scope, promised commitments in [Phased Delivery: MVP Mandatory, V2 Expressive Enhancements, V3 Capability Expansion](product.en.md#s2) must be synchronized. If still unable to go live, use the full local application as a demo fallback, retaining Replit development and preview results, and truthfully report that online verification failed; local success cannot be counted as passing the "Replit Online Demo" acceptance.

Development preview and production deployment are two different environments. Verify upload, generation, playback, download, and persistent storage on the production link; code modifications require redeployment to take effect on the live version. [Deployment Notes](https://docs.replit.com/build/publish-your-app)

<a id="s18-4"></a>

### First Task for the Coding Assistant

> Please establish a minimal environment verification skeleton for Auto Vlog Editor according to [Kickoff Verification: Confirm Replit Works Before Integrating AI](deployment.en.md#s18-2), continuing to support local development and GitHub syncing to Replit. frontend uses React + TypeScript + Vite + Tailwind + shadcn/ui; api uses FastAPI; implement according to [How Frontend and Backend Interact: Starting from a Single Click](reference/api.en.md#s10) interfaces and [JSON Data Contract: Usable for MVP, Extensible for V2/V3](reference/timeline.en.md#s6) JSON contracts, using only a single service process and a serial task executor. First, take three seconds each from three real videos, compile manual plan into a natural-duration nine-second timeline, add titles, subtle warm tint, and fixed BGM, mute original audio, hard cut, and output 720p MP4. Verify upload, job_id return, real status polling, continuing processing after closing page, playback scrubbing, and download. Backend encapsulates storage, using local directories locally and App Storage online to save originals, project/version JSON, and final videos; restore successful versions after restart, allow retry for interrupted tasks, and release queue on failure. After sample passes, execute the three realistic load tests in Stage C of [Kickoff Verification: Confirm Replit Works Before Integrating AI](deployment.en.md#s18-2). Development uses Vite to proxy /api, and FastAPI serves built web pages and API upon deployment. Do not integrate AI, database, auth, or V2/V3 features yet; do not automatically enable paid deployments. Provide startup and deployment configurations, required resources, and costs, along with empirical evidence for each test; mark unexecuted items as "Unverified", and do not substitute with pre-made final videos or simulated progress.

This is the overall task description. When both start work, split into respective file scopes according to [Two-Person Division of Labor and Collaboration](collaboration.en.md#s13) using existing collaboration packages, rather than giving the entire prompt simultaneously to two Agents to build separate applications. Application repository creation, installation, secret configuration, or deployment have not been executed yet.

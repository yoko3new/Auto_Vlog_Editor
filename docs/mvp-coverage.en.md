# Uploaded MVP Feature Coverage

[中文](mvp-coverage.md) · **English**

[Back to Overview](../README.en.md) · [Editing Modes and Speed Adjustment](editing-modes.en.md) · [Current Progress](status.en.md) · [Division of Work](collaboration.en.md)

Current code release: `2e5ff31` of `kang` (2026-10-10, America/New_York). Original upload baseline `ec21851`, UX fixes `6799bda`; the table below reflects the current local web page implementation. Added [Retry, Chinese/English, standalone voiceover and subtitle adaptation](mvp-fixes.en.md), as well as [editing modes, selectable duration, examples, and speed adjustment](editing-modes.en.md). Each verification batch is recorded separately; private raw materials are not uploaded, and small samples are not generalized as all inputs being verified.

## Currently Covered

| Feature | Actual Behavior and Boundaries | Implementation / Existing Verification Records |
| --- | --- | --- |
| Real Footage Import | MP4/MOV/M4V/MKV; batch upload, reading duration/dimensions/frame rate/audio tracks/color, hash deduplication; page lists filenames and durations, no thumbnails | [API](../src/vlogii/api.py), [Media](../src/vlogii/media.py); real HTTP uploads recorded, browser file picker control not automated for acceptance |
| Gemini Video Understanding | Low-resolution proxy videos used for event/highlight analysis, original audio independently transcribed preserving source language; both analysis types cached separately | [AI](../src/vlogii/ai.py), [Pipeline](../src/vlogii/pipeline.py); two sets of three real phone clips recorded, no footage selection quality benchmark tests performed |
| AI Editing Plan | Receives creative direction and target duration, selects segments, sequences, generates titles and minimal text; validates and attempts repair if plan is invalid | [AI](../src/vlogii/ai.py); direction description optional before generation; supports common mode/duration and rendered time deletion/speed adjustment expressions; arbitrary semantic editing not implemented |
| Deterministic Timeline | Python validates footage references, segments, and text, calculates duration by integer frames and remaps subtitles | [Timeline](../src/vlogii/timeline.py), [Tests](../tests/test_core.py) |
| Real MP4 Rendering | FFmpeg hard cuts, aspect ratio scaling with letterboxing, normal mode preserves original audio, missing audio track filled with silence; fast cut muted by default without overlaying spoken subtitles; burns text/subtitles, checks output specs and decodes full video | [Rendering](../src/vlogii/render.py), [Media Tests](../tests/test_media.py) |
| Landscape/Portrait and Color | Web page selectable 9:16 / 16:9, default portrait 1080×1920, 30 fps, SDR/H.264/AAC; all-HLG footage can optionally retain 10-bit HEVC, mixed footage converted to SDR | [Models](../src/vlogii/models.py), [API](../src/vlogii/api.py); portrait/SDR/all-HLG recorded, HEVC browser playback depends on environment |
| Title, Warmth, Exclude Footage | Enter new title, check warm tone, select footage to exclude by file; re-render, reuse existing plan without re-invoking AI | [Editing Logic](../src/vlogii/pipeline.py), [Frontend](../frontend/src/main.tsx); three operations have browser verification records |
| Versions and Undo | Successful output saved as independent version; failure preserves old rendered video; undo returns to previous successful version without AI or re-rendering | [Pipeline](../src/vlogii/pipeline.py), [Rendering](../src/vlogii/render.py); no arbitrary history version selection UI or redo entry point |
| Closed-Loop Page | Drag-and-drop/select files, project list, direction input, generate, polling actual stages, player, error prompts, edit, undo, download | [Frontend](../frontend/src/main.tsx); build and major browser operations recorded, mobile/full end-to-end tests not recorded |
| Local Tasks and Recovery | Single worker, queue cap of 8, duplicate run prevention for same project, JSON persistent records; restart marks unfinished tasks as failed, click Retry to reuse original request and valid outputs; old successful videos remain readable | [API](../src/vlogii/api.py), [Storage](../src/vlogii/storage.py), [API Tests](../tests/test_api.py); lacks request_id idempotency and base_version_id check from old contract |
| Playback, Download, and Diagnostics | MP4 playback / byte-range response / attachment download; records full FFmpeg log and verification.json; CLI and web share core | [API](../src/vlogii/api.py), [CLI](../src/vlogii/cli.py); post-restart playback and HTTP 206 download recorded |

Input constraints: at most 50 clips, single file 512 MiB, single upload 2 GiB, total footage 30 minutes. Target for AI Auto/Fast Cut can be left blank or specified as 1–1800 seconds; Preserve mode determines duration by content and does not accept a target. Duration is a planning preference, not guaranteed to be exact, nor is footage repeated to pad time. Fast Cut defaults to ~5s target, ~0.5s per shot, 1x speed, muted, and exported separately. Supports whole-video speed adjustment, deletion/speed adjustment within current rendered range, and input examples; see [Editing Modes](editing-modes.en.md) for complete rules. The real full preserve sample is 195.5s/21 clips, and the approved rhythm sample is 7s/14 shots; 7s is that sample's target, not the default total length.

## Comparison with Original Competition MVP: What Is Still Missing

| Original Competition Goal | Current Coverage | Remaining Work |
| --- | --- | --- |
| Upload and Footage Display | Partially covered | Thumbnails, orientation display, and acceptance on competition footage set |
| AI Understanding/Selection/Sequencing | Main pipeline available | Human-annotated key moments, duplicate shots, and content quality evaluation |
| Fixed Magazine-Style Output | Not yet covered | Designing and rendering fixed title hierarchy, decorations, and unified visual styling; web aesthetics do not equal MP4 style |
| Fixed BGM and Beat Editing | Partially covered | Six CC0 tracks, continuous mixing and speech ducking are bundled; [style films](style-templates.en.md) support uploaded music, beat detection and syncing; see [asset notes](free-resources.en.md) |
| First Cut 30±1 Seconds, 720p/16:9/30 fps | Partially covered | Current specs configurable, web defaults to 1080p portrait; 30 seconds is only a target, needs verification to meet competition duration and specs |
| Three Types of Natural Language Edits | Available via controls | Parsing, ambiguity confirmation, and summarization of arbitrary semantic operations; currently supports field/file ID operations and controlled time deletion/speed adjustment expressions |
| Versioning/Undo/Failure Protection | Main behaviors available | Re-testing full scenarios such as continuing edits after undo; do not claim full support for old API versions and idempotency semantics |
| Complete Single-Page Interaction | Basic page available | Teammates handle frontend polish and real API integration; do not display entry points that are not yet implemented |
| Official Replit Deployment/Persistent Recovery | Not yet covered | Cloud storage, official deployment, real load, and reboot recovery acceptance; currently local file storage only |

The original [Product Definition](product.en.md) continues to serve as the competition goal. Having capabilities like original audio subtitles, portrait orientation, and HDR now does not mean the entire original V2/V3 stage is complete: for example, subtitles and BGM ducking are present, and beat syncing is covered in style mode. Whether to change the competition scope requires separate clarification; this page only records actual coverage and does not treat subsequent proposals as implemented.

## How to Read Verification Conclusions

The record accompanying `ec21851` shows 29 Python tests passed, 0 skipped, along with real Gemini, FFmpeg, browser, and recovery samples. This round of UX fixes includes another 44 tests, real landscape/portrait subtitle output, and web edit Retry verification, plus real closed-loop verification of two new Gemini models on single clips after local API key configuration; recognition accuracy still lacks human comparison. The latest editing mode/speed release has 95 passed tests, real full preserve and muted fast-cut samples, as well as web speed adjustment/reset/undo records. Linux CI, official deployment, editing quality benchmarks, and performance targets are all unconfirmed. See [Fix Records](mvp-fixes.en.md) and [Verification](vlogii-validation.md) for details.

# Confirmed Decisions and Change Log

[中文](decisions.md) · **English**

[Return to Project Overview](../README.en.md)

When to read: Records decisions affecting product scope, architecture, and public contracts; maintained and summarized by A. Specific implementations still link to their respective technical documents.

<a id="s19"></a>

## Confirmed Directions and Kickoff Defaults

| Item | Current Decision |
| --- | --- |
| Primary Track | Adobe Creative; showcasing life feelings, aesthetics, and creative control |
| Development Environment | Primarily local development, synced via GitHub to Replit for verification and official release |
| Frontend | React + Vite + Tailwind + shadcn/ui, single-page editing console |
| Backend & Rendering | FastAPI + single task executor + FFmpeg; AI provides the plan, code calculates the timeline |
| Storage | Single-instance JSON manages projects; online persistent media and JSON use App Storage |
| AI (Original Competition Evaluation Schedule) | Test with 10 footage clips at hours 6–7 according to [AI Footage Understanding and Clip Selection Test: First Test at Hours 6–7, Final Video Verified Before Hour 14](ai-selection.en.md#s20-4); test one provider first, compare at most one other, lock in only one primary provider; current Vlogii already uses Gemini, competition quality evaluation remains to be completed |
| Voice (Original Competition Goal) | Original plan MVP did not transcribe, original audio muted; voiceover subtitles added only in V2-3. Current Vlogii preserves original audio/subtitles, scope differences between the two see feature comparison; competition goals were not modified this time |
| Optional Sponsors | Neither Gemini nor ElevenLabs is mandatory, do not add useless features just for dual-submitting |
| Phase Scope | MVP must be reached; V2 added in order of emotional expression, shortening, and voiceover; V3 primarily post-competition |
| Delivery Checkpoints | Hour 2 environment pre-check, Hour 6 Replit verification passed, Hour 7 AI first-round clip selection test completed, Hour 14 automatic quick cut and key moments review, Hour 24 MVP acceptance, final 6 hours freeze |

First complete the Replit environment, formal closed loop, and actual load verification in [Kickoff Verification: Confirm Replit Works Before Connecting AI](deployment.en.md#s18-2), then complete AI, fixed styles, and three types of modifications; voiceover belongs to V2-3 after MVP release. The choice of platform and model serves this closed loop.

## How Subsequent Decisions Are Recorded

A saves decisions affecting scope, architecture, or public contracts, and may delegate to a coding assistant; retain date, decision, rationale, affected documents, and status. Lapsed decisions note which item replaced them, preventing historical conclusions from continuing to act as current specifications.

| Date | Decision | Rationale / Impact | Status |
| --- | --- | --- | --- |
| 2026-10-10 | Merge the reference-reel styles from feng-style: style films with uploaded music, beat-locked cuts and −14 LUFS mixing join the web app and CLI; where they overlap existing modes, this implementation prevails | The user made `codex/integrate-feng-ui` the deployment base and asked to add this session's BGM mixing, beat-locked cuts and style films; new style and music endpoints on `/api/vlogii`, team `contracts/` unchanged; style films refuse speed and time-range edits to keep the beat lock | Implemented; [style templates](style-templates.en.md#evidence) |
| 2026-10-10 | Support AI Automatic, Intro Quick Cut, Keep Most, and Keep Full; target duration omission no longer defaults to 30 seconds; add clickable examples and final video time deletion | User wants free choice of retention volume and highlight intro, with subsequent precise deletion; mode/default compatibility rules see [Editing Modes](editing-modes.en.md) | Delivered with this batch commit; 95 tests as well as real long video/quick cut/web edit undo passed |
| 2026-10-10 | Brand adopts vlogii's light mint green, bold rounded lowercase wordmark, and overlapping frame icon (v8) | User confirmed final design; formal PNG and usage conventions see [Visual Specifications](visual-design.en.md#brand-logo) | Assets and documentation saved; web integration pending implementation by B |
| 2026-10-09 | Split long documents into short overviews, independent collaboration guides, and on-demand references | Reduce repeated reading; old full text archived, technical conventions preserved | Accepted and implemented |
| 2026-10-09 | Share project documentation, contracts, and generic AGENTS.md; personal roles and dispatch settings kept locally | Two people can use different development tools; jointly abide by file ownership, interfaces, and acceptance | Accepted; shared content is subject to the current GitHub commit |
| 2026-10-10 | A (Yang Kang) responsible for end-to-end video generation pipeline, backend/AI/rendering/titles/footage/storage/contracts/integration; B (teammate) responsible for frontend | Replaced old "B rendering + frontend" per user's explicit adjustment; does not change module behavior or APIs | Implemented in shared division of labor documentation |
| 2026-10-10 | Current baseline adopts kang's Vlogii local web MVP, recording current implementation and original competition goals separately | Uploaded ec21851; uses /api/vlogii, independent models, and local file storage; does not mark BGM/magazine style/Replit gaps as completed | Verified code and existing validation records; did not rerun application in this round |

Vlogii already uses Gemini, with model configured by `VLOGII_MODEL`, and existing environment records can be found in [Local Verification](vlogii-validation.md); specific competition model quality, formal runtime environment, and deployment configurations remain to be verified, without treating small samples as complete overall.


## Vlogii local web implementation — 2026-10-10

At the user's request, branch `kang` adds an independent local web MVP based on the
successfully exercised VX workflow. The core renderer is shared by FastAPI and a
small debugging CLI. New source and notes are English. No VX source is copied.
The user clarified that the product should be a website, so this release includes
React upload, real job status, playback, version edits, undo and download.

The existing competition product and public API contracts are preserved.
Vlogii's separately versioned `/api/vlogii` interface is documented by its own
OpenAPI snapshot. Replit, App Storage, BGM and magazine styling remain outside
this local release and are not marked accepted.

## 2026-10-10: Lifestyle Shorts and Speed

User confirmed the product focuses on lifestyle Shorts: artistic typography/sticker cover, a few quick jump-cut shots at the beginning, and body footage with simple subtitles/minimal words, timestamps, and light special effects. Saved [Design Directions](shorts-direction.en.md); full cover and intro-to-body stitching have not yet been implemented.

Local quick cut defaults changed to approximately 5 seconds, with a maximum of approximately 0.5 seconds per shot; shot duration and video speed are configured separately. Full video and current final video time ranges support absolute speed adjustments, with subtitles/original audio following the timeline, and old edits can be undone. New API fields see [Editing Rules](editing-modes.en.md), verification evidence see [Records](vlogii-validation.md). This batch commit includes implementation, callers, and acceptance records.

Quick cut defaults to mute: user pointed out that fast cut points truncate original audio. Planned to persist the mute strategy, replace rendering with a silent audio track, and maintain this strategy across speed adjustment/deletion/retry; body mode continues to preserve original audio.

User approved the comparison version of 0.5 seconds per shot, 1x speed, and muted as the current default quick cut rhythm; target duration remains optional, while shot hold duration and speed are independently adjustable.

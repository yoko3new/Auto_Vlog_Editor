# Vlogii local validation

Implementation branch: `kang`. Validation date: 2026-10-10 (America/New_York).

This record describes the new application. No old VX export is counted as Vlogii evidence.

## Scope

React/TypeScript, FastAPI, Gemini video understanding, a validated Python timeline and real FFmpeg rendering run together locally. Vlogii uses `/api/vlogii`; the preserved team competition requirements are not claimed as fully implemented.

## Uploaded baseline checks (`ec21851`)

- Python: **29 passed, 0 skipped**, with one upstream Starlette/httpx deprecation warning. Tests cover timeline bounds, frame timing, caption remapping, storage locks, path safety, persistent jobs, failure recovery and provider schema compatibility.
- Real FFmpeg tests: SDR software and automatic encoding, text/captions, portrait geometry, missing-audio silence, all-HLG 10-bit HEVC, edits, undo and preservation of successful output after an injected failure.
- Ruff lint and formatting: passed. TypeScript checking and production frontend build: passed.
- Preserved contract fixtures: 13 fixtures and 19 negative checks passed. Collaboration contracts: 11 tests passed. Documentation links: passed.
- First live dataset: three private phone clips, real multipart upload to the local web API, real Gemini reviews and planning, then a 1080 × 1920 SDR/H.264/AAC film of approximately 18 seconds. Browser playback metadata reported no media error.
- Browser controls: generation, title change, warmth edit, clip exclusion and undo completed. The title/warmth edit created version 002; exclusion created version 003 with two source clips; undo restored version 002.
- Second live dataset: three different private phone clips, real Gemini analysis and planning through the shared CLI core, then a 720 × 1280 SDR/H.264/AAC film of 16.288 seconds. Full output decoding passed.
- Visual inspection found missing Chinese glyphs in the default font. Explicit Unicode/CJK font selection and full-width text wrapping were added, regression tests passed, and version 004 was rendered from the saved plan without another AI call. Browser inspection confirmed readable Chinese captions.
- After restarting the server, both successful films remained accessible. MP4 byte-range downloads returned HTTP 206 and attachment headers.
- Publication checks examine exact local credentials and common key patterns against eligible files and then staged Git blobs. Media and private project directories are excluded. The local server binds only to `127.0.0.1`.

Private footage, transcripts, raw AI responses, prompts, screenshots, exports and full diagnostic logs remain ignored locally. Local evidence is stored under `local-evidence/`, and each export has `verification.json`, its plan, timeline and FFmpeg logs under `projects/<project>/cuts/<version>/`.

## Published experience fixes (`6799bda`, 2026-10-10)

See [MVP fixes](mvp-fixes.md) for behavior, model choices, request compatibility and iteration rules. The baseline live Gemini results above do not validate the new model configuration.

- Python: **44 passed, 0 skipped**, with the same upstream Starlette/httpx warning. Added checks cover original-request generate/edit retry, restart recovery, plan reuse after render failure, visual-cache preservation after speech failure, Chinese CLI and saved edit retry, HTTP transcription request shape, transient/auth failures, timestamp bounds, complete text layout and hardware fallback.
- Real FFmpeg: a failed second segment preserves the first rendered segment; retry encodes only the unfinished segment. A 1.2-second source builds a proxy and renders, disproving a five-second input gate.
- Private user dataset: 21 phone clips, six shorter than five seconds, shortest 2.4 seconds. A fixed two-second cut rendered at 720×1280 and 1280×720, 30 fps, SDR/H.264/AAC; complete decoding and visual inspection of long Chinese/English captions passed. Caption content is a synthetic fixture, not a recognition result.
- Browser: Chinese/English switching, actionable failed-job Retry, original edit request replay, version 002 creation and version 001 preservation passed against the local real API and renderer. The failed job was seeded for the test; no AI call occurred.
- Ruff and production frontend build passed. OpenAPI regenerated from the app; existing requests remain valid, and request bodies are not exposed in job responses. Documentation: 25 Markdown files, 249 local links passed. Preserved contracts: 13 fixtures and 19 negative cases; collaboration: 11 tests passed. Git diff whitespace check passed.
- After the user configured the local Gemini key, one 2.4-second source completed real `gemini-3.8-flash` visual analysis, `gemini-3.5-transcribe` speech recognition, planning and export in 23.55 seconds. Two speech captions were produced. The 720×1280/30 fps SDR H.264/AAC output decoded completely. This verifies access for this account and a small integration path; human-ground-truth accuracy, billing costs and load performance remain unverified.

Full logs, source metadata, exports, caption frames and browser screenshots are ignored under `local-evidence/mvp-fixes-2026-10-10/`. Preserved contract and documentation checks are run separately; those do not validate new live AI.

## Local editing modes and examples (2026-10-10)

See [editing semantics](editing-modes.md) for changed duration defaults, modes, controlled natural language and current-film time coordinates.

- Python: **71 passed, 0 skipped**. New checks cover retention/duration precedence, full retention, silent scenery versus explicit no-speech removal, highlights shot bounds, cross-cut range mapping, overlapping/out-of-bounds removal, unsupported instruction rejection and retry preservation. Real FFmpeg integration checks full retention, black detection, frame-accurate removal and undo.
- Ruff, formatting and TypeScript/Vite build passed. OpenAPI is regenerated from the same API used by the frontend; original competition contracts remain separate.
- Browser using a synthetic 24-second clip and the real local API/renderer: Chinese/English examples, preserving manually entered direction, replacing conflicting presets, automatic mode/checkbox changes and no submission on an example click passed. Keep-all generation produced 24 seconds. Clicking the time example and applying removal of 12–18 seconds produced an 18-second new version; Undo restored the original 24-second version. No AI was called in this browser fixture.
- All 21 private user clips (195.5 seconds in total) completed real visual/speech analysis and a 28.8-second five-segment cut at an explicit 30-second target, with 11 captions, 1080×1920 SDR/H.264/AAC and full decoding. Three caption frames showed no text clipping. The user reported improved recognition/display; this is subjective feedback, not a measured accuracy benchmark.

Private evidence is under `local-evidence/示例回归20261010/`; media and transcripts stay excluded from Git. The full-retention output is 195.521333 seconds (195.5 seconds on the frame timeline), 21 segments and 69 captions. All imported source intervals are preserved. The independent real-Gemini opening montage is 12.021333 seconds (12.0 timeline seconds), eight shots of 1.4–1.6 seconds each. Both 1080×1920/30 fps SDR H.264/AAC films passed complete decoding; sampled full-film captions were visible without clipping. The short montage is not automatically attached to the full film.

## Limitations

- Live AI runs are small-sample integration checks, not an editorial-quality benchmark. AI transcription and creative choices require human review.
- Browser-extension file access blocked automated file-picker injection. Real HTTP uploads and browser generation were tested separately; the picker is not claimed as automatically verified.
- Target duration is a planning preference, not a guarantee.
- No public deployment, Replit storage, authentication, BGM or magazine rendering was validated.
- Linux CI is configured but its result must be read separately after publication. Local verification used macOS and FFmpeg-full 9.0.2.
- Windows project locks are not implemented.
- Gemini receives proxy videos for visual analysis and separately extracted original audio for speech recognition. The application calls remote deletion after recognition; provider-side retention is outside local verification.

## Flash montage and speed (local, 2026-10-10)

- Python: **94 passed, 0 skipped**, one upstream Starlette/httpx deprecation warning. Checks include bilingual rate instructions, bounds/non-finite/reversed ranges, refusal of unsupported mixed instructions, absolute rates, deletion after speed changes, overlay/caption mapping, exact retry/base preservation and speed-only API requests.
- Real FFmpeg renders: 0.25/0.5/1.5/2/8x with audio, 4x silent footage; expected frame counts, audio stream and duration verified. Decoded synthetic 440 Hz audio retains its fundamental rather than shifting to 220/880 Hz. Silent footage stays silent; a discovered u8 silent-input tempo artifact was fixed by bypassing unnecessary tempo processing. No subjective audio-quality benchmark.
- Browser: real local API with 24-second synthetic footage. Whole-film 2x → 12 seconds; undo → 24 seconds. Clicked “00:12到00:18加速到2倍”, reviewed, applied → 21 seconds. Set absolute 1x → 24 seconds, undo → 21 seconds. Chinese/English labels, cadence and speed radio selection passed. Evidence: private `local-evidence/示例回归20261010/speed-controls-full.png`.
- Real user footage: reused the 21-clip analysis cache; Gemini selected 14 varied shots for a 5-second target at 2x. Final export `projects/示例快剪20261010/cuts/cut_003/film.mp4`: **4.667-second frame timeline / 4.688-second container**, 14 shots each **0.333 seconds**, 1080×1920, 30 fps, SDR H.264/AAC; full video/audio decode verified. Final code disabled flash-montage captions/overlays and re-rendered the validated AI plan without another AI request. Source content intervals and old successful versions remain preserved.
- Updated TypeScript/Vite build, Ruff, current OpenAPI snapshot, documentation links and both original contract checks pass. Logs stay private under `local-evidence/示例回归20261010/` (`speed-tests.log`, `speed-frontend.log`, `flash-run.log`, `flash-final-render.log`, `flash-summary.json`).
- Product direction documented as [life Shorts](shorts-direction.md). Cover art/stickers, automatic opening/body assembly, time/keyword controls, effects and BGM/beat alignment are pending. YouTube reference page opened and played; no frame-by-frame reference timing was measured. Code, current API snapshot, caller and evidence summary ship together in this batch; private media stays local.

### Default mute for opening highlights

User reported chopped source speech in the flash opening. `Plan.mute_source_audio` now defaults false for compatibility and is set true for highlights; real rendering maps silent audio rather than source audio. The flag persists through time/speed edits and retry; editing a historical highlights cut also applies the policy using its saved selection. Body modes keep natural audio. Muting participates in the render-cache fingerprint, so an audible cached segment cannot be reused as a muted output.

**95 Python tests passed**, including a real audible-versus-muted export, cache separation, a partial speed edit staying muted and undo. TypeScript/Vite, Ruff and documentation checks passed. The user's same 14-shot montage was re-rendered as `projects/示例快剪20261010/cuts/cut_004/film.mp4` (4.667-second timeline, 4.688-second container). Decoding its audio into PCM verified **peak amplitude 0**, and full video/audio decode passed; older exports remain. Logs and summary: private `local-evidence/示例回归20261010/mute-tests.log`, `flash-muted-render.log`, `flash-muted-audio.log`, `flash-muted-summary.json`. No new Gemini request was needed.

User found the 0.333-second/2x flash too fast. A second comparison uses the same 14 selected moments, centred 0.5-second source intervals at 1x: `projects/示例快剪20261010/cuts/cut_005/film.mp4`, **7-second timeline**, muted. Full decoding and decoded audio peak 0 verified; source files and earlier cuts remain. Private evidence: `local-evidence/示例回归20261010/flash-balanced-summary.json`, `flash-balanced-render.log`, `flash-balanced-audio.log`. The user approved this cadence; current defaults are 0.5 seconds per shot, 1x, source audio muted, with editable controls.

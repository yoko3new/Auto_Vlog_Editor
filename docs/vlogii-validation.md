# Vlogii local validation

Implementation branch: `kang`. Validation date: 2026-10-10 (America/New_York).

This record describes the new application. No old VX export is counted as Vlogii evidence.

## Scope

React/TypeScript, FastAPI, Gemini video understanding, a validated Python timeline and real FFmpeg rendering run together locally. Vlogii uses `/api/vlogii`; the preserved team competition requirements are not claimed as fully implemented.

## Actual checks

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

## Limitations

- Live AI runs are small-sample integration checks, not an editorial-quality benchmark. AI transcription and creative choices require human review.
- Browser-extension file access blocked automated file-picker injection. Real HTTP uploads and browser generation were tested separately; the picker is not claimed as automatically verified.
- Target duration is a planning preference, not a guarantee.
- No public deployment, Replit storage, authentication, BGM or magazine rendering was validated.
- Linux CI is configured but its result must be read separately after publication. Local verification used macOS and FFmpeg-full 9.0.2.
- Windows project locks are not implemented.
- Gemini receives proxy videos for analysis. The application calls remote deletion after review; provider-side retention is outside local verification.

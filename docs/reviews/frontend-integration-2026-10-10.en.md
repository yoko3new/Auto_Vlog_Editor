# Frontend integration verification: 2026-10-10

[中文](frontend-integration-2026-10-10.md) · **English**

[Current status](../status.en.md) · [Web editor](../vlogii-guide.md#web-design)

Baseline: create `codex/integrate-feng-ui` from `kang` at `46acdf4`, then merge `feng-emergence` at `4db8163`. Both histories are retained. Integration changes only the frontend, brand assets and relevant bilingual documents; generation, model calls, rendering and API implementation are unchanged.

## Completed work

Merge the teammate’s mint editorial page, white masthead and reading progress, three chapters, wide film area, round Play control and Safari first-frame media request. Restore Chinese/English, Chinese project names, Retry, four generation modes, optional targets, clickable examples, highlight cadence, whole-film and time-range speed/deletion, and undo. Web fonts are bundled with all three OFL notices in `frontend/public/fonts`. The Mac tutorial is updated with a matching English version.

## Actual verification

- 95 Python tests passed, including real FFmpeg; Ruff lint and formatting passed. Tests emitted one Starlette/httpx deprecation warning.
- Frontend TypeScript checking and Vite production build passed; original data contracts passed 13 fixtures/19 negative cases, and collaboration contracts passed 11 tests.
- In the in-app browser, using an isolated real-footage project: playback, language switching, highlight example/mode linkage, cadence controls, whole-film 2x export and undo passed. The 7.0-second sample produced approximately 3.8 seconds at 2x; frame alignment affects actual length.
- Injected a retryable interrupted edit record only in the isolated project. The page preserved the old film; Retry reused the request, set the resume flag and completed a real export. This verifies interrupted-state handling and resumption, not a Gemini service outage.
- Uploaded a real MOV through the web file chooser, created a Chinese-named project and displayed its 2.4-second metadata.
- At 390 pixels wide, language controls, examples and speed radio groups displayed and wrapped correctly, with no horizontal page overflow found.

Private films, footage, screenshots and full logs remain in ignored `local-evidence/integration-feng-ui-20261010/` and are not pushed to GitHub.

## Unverified scope

Native Safari and physical phones were not retested. Gemini transcription/selection quality, a fresh-machine installation and formal deployment were not rerun. The new UI does not implement artistic covers, BGM, beat cuts or automatic opening/body assembly. The integration branch is for joint review before deciding to merge into the main branch.

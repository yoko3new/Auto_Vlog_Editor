# MVP Experience Fixes and Model Selection

[中文](mvp-fixes.md) · **English**

[Back to Overview](../README.en.md) · [Feature Coverage](mvp-coverage.en.md) · [User Guide](vlogii-guide.md)

Local modifications based on `kang/ec21851`, 2026-10-10. Yang Kang is responsible for backend and video modules; this time, frontend Retry and Chinese/English switching were synchronized per authorized requirements. The frontend will continue to be maintained by teammates. The experience fixes were pushed to `kang` as `6799bda`; editing modes and speed controls were published as `2e5ff31`. For font/BGM asset research, see [Resource Candidates](free-resources.en.md).

## Changes in This Round

| Issue | Current Handling |
| --- | --- |
| Re-entering CLI / regenerating after an intermediate error | CLI interactions can be retried directly after failure; continuous session when started without arguments. Web failed tasks display Retry. Server saves original request and task type; retrying an edit will not turn into regeneration |
| Repeated invocation of successful steps | Visuals and speech are cached separately by source file hash, model, and configuration; rendering failures retain the editing plan and completed segments. Retries reuse the same request, keeping the old version playable before success |
| Chinese interaction | Choose Chinese or English when starting CLI, supporting Chinese project names and creative directions; `--language zh/en` can also be specified. Web page provides Chinese/English switching and remembers selection |
| Poor speech accuracy | Separated visual analysis and speech recognition. Speech extracts PCM audio separately from original footage, using Gemini dedicated transcription endpoint; no longer relies on speech results from lossy proxy video |
| Subtitle left/right clipping / trailing sentence loss | Wraps lines based on actual video dimensions and font measurements; reduces font size when too long, preserving all lines; checked for both landscape and portrait. Explicitly reports errors when fonts are missing or text genuinely cannot fit |
| Mid-process errors in automatic hardware encoding | Checks whether an encoding session can actually be created before selecting VideoToolbox; falls back to software encoding when unavailable |
| Cannot analyze under 5 seconds? | No such input threshold. Explicit output target is now 1–1800 seconds (duration/mode updates see [Editing Modes](editing-modes.en.md)); 6 out of 21 segments in real directory are under 5 seconds, shortest being 2.4 seconds. This short footage has completed real Gemini analysis, transcription, and export |

Existing `reviews/` cannot directly serve as a valid recognition cache for the new workflow: the first run with the new workflow will re-analyze and re-transcribe, while the original successful video is retained. Changes to model, speech language, or thinking configuration will invalidate relevant caches. AI failures will not silently switch models, drop subtitles, or pretend to succeed with mocks.

## Gemini Models and Accuracy

Checked official documentation on 2026-10-10; the latest general stable model is [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), model ID `gemini-3.8-flash`. It supports video, images, audio, and structured output, serving as the default choice for visual understanding and editing planning in this round; thinking is explicitly set to `medium`, adjustable via `VLOGII_THINKING`.

Selected [Gemini 3.5 Transcribe](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-transcribe) for speech, model ID `gemini-3.5-transcribe`. It supports Chinese, English, and mixed languages, automatic language detection, and word timestamps, and **does not support thinking**. This project requires subtitle timing, adopting verbatim faithful transcription and word timestamps; the official documentation also notes that enabling timestamps may reduce text accuracy, so it cannot be claimed in advance that it is definitely more accurate on this footage.

The old default `gemini-3-flash-preview` handled both visuals and lossy proxy audio simultaneously, without explicitly setting thinking. Therefore, accuracy issues cannot be attributed solely to effort or model capability. Comparisons must also be made against original audio, noise/accent, mixed Chinese and English, prompts, and subtitle time mapping. In the next round, actual gains can only be determined by measuring Chinese character error rate, English word error rate, missed sentences, and time offsets with manual sentence-by-sentence annotation.

For configuration, see [.env.example](../.env.example): `VLOGII_MODEL` controls visuals/planning, `VLOGII_SPEECH_MODEL` controls speech, and `VLOGII_SPEECH_LANGUAGE=auto` maintains mixed language detection. When the language is clearly known, official BCP-47 codes can be filled in, such as `cmn-Hans-CN` or `en-US`. Interface language and footage speech language are independent options.

Dedicated transcription uses the [Interactions REST API](https://ai.google.dev/gemini-api/docs/transcribe), continuing to use the same `GEMINI_API_KEY`. The currently locked SDK does not yet have a dedicated transcription_config type, so httpx is used to request this endpoint; account availability requires real verification. If an account does not currently support it, `VLOGII_SPEECH_MODEL` can be explicitly set to an available general Gemini model to run standalone audio transcription, without automatic downgrading.

Visual understanding is also affected by sampling: [official video documentation](https://ai.google.dev/gemini-api/docs/video-understanding) defaults to approximately one frame per second in static mode. A proxy file being 12 fps does not mean the model saw 12 frames per second; missed recognition of fast motion requires first verifying input sampling before comparing thinking or models.

## What Users Need to Input and How to Iterate

For first-time generation, selecting footage is the only requirement; project name has a default value, target duration can be left blank to be determined by mode (new rules see [Editing Modes](editing-modes.en.md)), and aspect ratio/color also have defaults. Creative direction can be left blank, without requiring users to write a full editing script, segment-by-segment descriptions, subtitles, or titles on the first run. The optional description only expresses preferences, such as "keep breakfast and walking, original Chinese audio, in chronological order".

Two types of subsequent operations are handled separately:

- **Failure Retry**: Click Retry to follow the original request and reuse successful work, without requiring text to be refilled. `vlogii retry 项目名` can also be executed after the CLI exits; generation and edit requests are saved separately.
- **Dissatisfied with Finished Video**: Fill only the fields to be changed. Currently supports title, warmth, and exclusion by footage ID; generates a new version and can be undone. After modifying creative direction, "Generate New Version" replans while reusing unchanged footage analysis; it still uses the original imported set and does not automatically inherit exclusions from the previous version.

Common expressions in Chinese and English for time range deletion/speed adjustment and generation mode/duration have been implemented; an arbitrary natural language modification parser is not yet implemented, see [Editing Modes](editing-modes.en.md) for details. In this round, "automatic editing direction input" is not represented as "existing natural language modification". Subsequent designs should accept short incremental instructions, such as "delete the cooking segment, change title to Weekend"; the backend converts them into controlled operations by combining the current successful version, original preferences, and footage descriptions, prompting users to choose candidates only when references are ambiguous. Preserves modification summaries and versions, eliminating the need for users to restate all requirements, while keeping the old video on failure. Polishing features such as BGM, beat sync, and finished video styling are left for the next step.

## Empirical Evidence from This Round

- Python: 44 tests passed, 0 skipped; including real FFmpeg, segmented resumption, visual/speech caching, generation/edit Retry, restart recovery, Chinese CLI, transcription HTTP structure, and edge cases. One upstream Starlette/httpx deprecation notice.
- Private real footage: a 2-second excerpt from the same 2.4-second clip, outputting 720×1280 and 1280×720, both at 30 fps, SDR/H.264/AAC, passing full decoding; full display of long Chinese and English subtitles visually confirmed.
- Browser: Chinese/English switching, failed edit Retry, successful new version, and old version retention verified. This task was an artificially configured failed edit with no AI calls; not counted as real Gemini acceptance.
- Gemini transcription endpoint verified requests/timestamps/retries using HTTP doubles. The user subsequently configured local keys, and a 2.4-second clip truly completed Gemini 3.8 Flash visual analysis, 3.5 Transcribe transcription, planning, and export, yielding 2 subtitles and taking approximately 23.55 seconds. Only a single sample integration result, without testing manual benchmark accuracy, billing costs, or load performance.

Private logs, footage, exports, subtitles, and screenshots are kept in ignored `local-evidence/mvp-fixes-2026-10-10/` and not committed to Git. For the final automated check summary, see [Verification Records](vlogii-validation.md).

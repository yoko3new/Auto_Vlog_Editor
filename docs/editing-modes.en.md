# Retention Ratio, Intro Fast Cut, and Modification by Time

[中文](editing-modes.md) · **English**

[Back to Overview](../README.en.md) · [Current API](vlogii.openapi.json) · [Vlogii Guide](vlogii-guide.md)

## Four Generation Modes

| Page Option / API `mode` | Behavior | Target Duration Left Blank |
| --- | --- | --- |
| AI Auto / `auto` | Selects content and order based on footage, voiceover, and user description | Decided by AI, no longer defaults to 30 seconds |
| Intro Fast Cut / `highlights` | Standalone collection of highlight intro visuals, hard cuts between short shots; single shot defaults to at most about 0.5 seconds, adjustable | About 5 seconds; does not repeat footage to make up duration if insufficient |
| Retain Most / `keep_most` | Retained in import order; removes black screens, trims non-speech gaps of at least 3 seconds in footage with voiceover; leaves about 0.35 seconds before and after each sentence | Determined by retained content; does not accept target duration |
| Retain All / `keep_all` | Retains all imported footage in import order, without AI shot selection | Close to total footage length, affected only by segment-by-segment frame rounding; does not accept target duration |

Retain All and Retain Most do not invoke AI to make editing decisions; they still reuse or run original audio transcription to generate subtitles. Duplicate files are deduplicated upon import, and "all" refers to the set of imported footage. The CLI sorts by filename, while the web page imports in upload order without inferring shooting time; subsequent deletions only modify the new version and do not modify the original files.

Retain Most by default keeps scenery shots without voiceover. Checking "Delete all intervals where no speech was recognized at the same time", or entering "Delete everything without speech", will remove these shots; "no speech" is based on recognition timestamps rather than silence detection, and missed recognition may cause content to be deleted, requiring verification via the final cut. Black screen detection checks for black frames that last continuously for at least 0.3 seconds with approximately 98% of pixels below the threshold; proxies are reused when available, and time precision is limited by proxy sampling.

AI Auto / Fast Cut accepts optional `target_seconds`, ranging from 1 to 1800 seconds; one can also enter "keep about 2 minutes". Duration is an approximate target, not guaranteed to be exact, and does not repeat footage to make up duration. Retain All cannot simultaneously specify "30 seconds"; a conflict will prompt switching modes or clearing the duration.

## Input Examples and Priority

Examples next to the generation description can be clicked, preserving self-written text and synchronizing the corresponding mode; switching replaces the previous mode example to avoid conflicts and does not submit automatically. Chinese and English examples include:

- "Keep all, in footage order" → Retain All.
- "Keep most of the content" → Retain Most.
- "Delete everything without speech" → Retain Most, and enable removing non-speech intervals.
- "Generate a 5-second intro highlight fast cut" → Fast Cut.
- "Keep about 2 minutes, keep voiceover as complete as possible" → AI Auto, target about 120 seconds.

An explicitly selected non-auto mode and filled-in target seconds take priority over text; under AI Auto, common retain/fast cut expressions and numeric durations are recognized. The remaining creative descriptions are passed to the AI Auto / Fast Cut plan for use. Retention modes follow fixed retention rules and do not support arbitrary semantic shot selection; to change shot selection order or select by event, use AI Auto. Fast cut is currently exported separately and is not automatically appended to the full version; BGM and beat-matching are not integrated.

After comparing real sample clips, users approved **0.5 seconds per shot, 1x speed, muted**, which is now used as the default fast cut rhythm; it can still be adjusted faster or slower.

## Video Speed and Flash Cut Rhythm

Generation adds `speed` (0.25–8x relative to original footage, default 1) and `shot_seconds` (fast cut single-shot playback cap 0.15–1 seconds, default 0.5). The web page provides a speed radio bar for 0.5 / 1 / 1.5 / 2 / 4 / 8x; fast cut provides 0.25 / 0.35 / 0.5 / 0.8-second rhythm options. Both target seconds and shot dwell are calculated based on **final playback time**. The fast cut intro is muted by default, without overlaying voiceover subtitles/text, to avoid short shots chopping up vocals; the main body retains original audio and subtitles. The mute state is saved in `mute_source_audio` of the plan, remaining muted after speed adjustments, deletions, and Retry, while legacy successful files are preserved. Currently, BGM is not added. Retain All still keeps all intervals under speed multipliers, with duration changing according to speed.

Editing `speed` is nullable: null maintains the existing speed of each segment; passing 1 restores the original speed. `speed_ranges: [{"start": 12, "end": 18, "speed": 2}]` sets the absolute speed multiplier for the corresponding range; intervals override any whole-video speed specified at the same time, without cumulative multiplication. Time range commands include, for example, "speed up 00:12 to 00:18 to 2x" or `speed up 00:12 to 00:18 to 2x`; semicolons can concatenate deletions and speed adjustments. Speed intervals cannot overlap; out-of-bounds, shorter than one output frame, or mapping to less than one footage frame will all be rejected.

The code calculates playback duration and footage mapping on a frame-by-frame basis, scaling subtitles and text with speed; FFmpeg uses video timestamps and audio tempo adjustments, preserving pitch (without guaranteeing perceptual auditory quality at extreme speed multipliers). Footage without original audio is padded with silence, and speed changes are not performed on silence. Slow speeds duplicate frames rather than using AI frame interpolation. Implementation reference: [FFmpeg Filters](https://ffmpeg.org/ffmpeg-filters.html#atempo).

## Deleting from Current Final Cut by Time

Editing fields add `remove_ranges: [{"start": 12, "end": 18}]` (seconds) and optional `instruction`; the web page has an input box and clickable examples, and the CLI can use `--remove-ranges`. For example, "delete 00:12 to 00:18, don't use 1 min to 1 min 8 sec" or `delete 00:12 to 00:18`.

Time refers to the playback position of the **current successful final cut**. Supports `mm:ss`, `hh:mm:ss`, decimal seconds, `1分8秒`, and multiple intervals; also supports the explicit speed multiplier commands mentioned above, but does not support arbitrary natural language operations. When containing unsupported operations such as "add BGM", the entire instruction is rejected without silently executing partial modifications. Out-of-bounds, reversed, less than one frame, or deleting the entire video are all rejected; overlapping intervals are merged and mapped back to the original footage frame by frame. When deletions, speed adjustments, and footage exclusions are submitted simultaneously, all time coordinates are first taken against the same current final cut, after which deletions/speed adjustments are completed and footage is excluded.

Each modification saves a new plan and timeline, re-mapping subtitles/text and exporting a new version; failures retain the old cut, Retry retains the original intervals and original version, and Undo restores the old version. Dialogue may be truncated at deletion points, requiring selection of appropriate sentence boundaries.

```sh
uv run vlogii run my-day --mode keep_all
uv run vlogii run my-day --mode keep_most --remove-no-speech
uv run vlogii run my-day --mode highlights --seconds 5 --shot-seconds 0.5 --speed 1
uv run vlogii run my-day --direction "保留约2分钟，口播尽量完整"
uv run vlogii edit my-day --remove-ranges "删掉00:12到00:18"
uv run vlogii edit my-day --instruction "00:12到00:18加速到2倍"
uv run vlogii edit my-day --speed 1
```

## Compatibility and Verification

Legacy requests can still explicitly submit `target_seconds: 30`, and legacy successful versions continue to play and undo. Legacy plans lacking `speed/captions` default to original speed and display subtitles; existing successful files are not rewritten. New plans save speed by footage interval, and the timeline adds `source_frames/speed`. **Omitting the target duration has been changed from defaulting to 30 seconds to being decided by AI**; callers relying on the legacy default should explicitly pass 30; the 30 saved by legacy Retries remains unchanged. Generation checkpoints add mode and rule versions; mode changes will recreate the plan while still reusing the recognition cache. Each new final cut retains `selection.json`, and project responses add nullable `selection`; returns null when legacy versions lack this file.

Automated checks cover mode/duration priority, Retain All, black screen and pause removal, fast cut shot constraints, cross-segment deletion and subtitle/text time mapping, rejection of out-of-bounds/unsupported instructions, failure retries, and legacy version retention. Real FFmpeg tests verify Retain All, black screen deletion, frame-accurate deletion, and undo; web operations and real footage results can be found in [Local Verification](vlogii-validation.md).

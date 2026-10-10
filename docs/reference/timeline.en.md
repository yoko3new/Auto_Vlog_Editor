# Project JSON and Timeline Semantics

[中文](timeline.md) · **English**

[Return to Project Overview](../../README.en.md)

When to read: Read relevant subsections when modifying JSON, compiling timelines, or rendering; machine structures are governed by contracts/contracts.schema.json.

<a id="s6"></a>

## JSON Data Contract: Available in MVP, Extensible in V2/V3

<a id="s6-1"></a>

### Who Generates What: Distinguish Plans, Settings, and Execution Results First

**AI generates editing suggestions, the backend compiles them into the final timeline, and the renderer only executes the timeline.** User settings and modification constraints are stored by the backend; AI cannot overwrite them.

```text
原素材 → assets.json + 内容分析
                    ↓
             AI → edit_plan.json
                    ↓
config.json → 后端编译与校验 → timeline.json → FFmpeg → MP4
                    ↑
用户修改 → edit_request.json → 更新设置/计划，形成新版本
```

| File | Written By | Purpose | Stage |
| --- | --- | --- | --- |
| `assets.json` | Backend asset registration module | Maps stable IDs to corresponding videos, music, fonts, and images; only resolves real files on the backend | MVP |
| `config.json` | Backend, updated based on UI input or confirmed modifications | What the user wants; stores settings and excluded assets for each version | MVP |
| `edit_plan.json` | AI outputs `plan`, backend fills outer identifiers | Clip selection, order, suggested ranges, titles; not responsible for the position of the final frame | MVP |
| `timeline.json` | Backend compiler | Confirmed visuals, audio tracks, layers, subtitles, and exact durations | MVP |
| `edit_request.json` | AI or fixed button parsing, backend validates and fills identifiers | Permitted modification operations; can also express requests for user selection or lack of support | MVP |
| `transcript.json` | ASR + backend sentence segmentation | Sentence and word timing in source assets; subtitles are generated from this | V2-3 |

`analysis.json` continues to serve as an analysis cache and is not passed directly to the renderer; the machine-verifiable contracts in this section focus on the six document types above. Frontend HTTP requests can be smaller, with the backend filling in default values before saving them as these files.

Provided: [Machine-readable JSON Schema](../../contracts/contracts.schema.json), [MVP Full Timeline](../../contracts/examples/mvp.timeline.json), [MVP Plan](../../contracts/examples/mvp.edit_plan.json), and [Validation Script](../../contracts/validate_examples.py). Media, font, and image IDs and paths in the examples are placeholder references for design purposes; corresponding assets do not yet exist, and successful rendering cannot be claimed based on them.

<a id="s6-2"></a>

### Unified Conventions: Fields, Time, Versions, and Capabilities

| Convention | Fixed Meaning |
| --- | --- |
| `schema_version` | This contract is `"1.0.0"`; unrelated to product stages MVP/V2/V3 |
| `document_type` | Distinguishes `assets`, `project_config`, `edit_plan`, `timeline`, `edit_request`, `transcript` |
| `project_id` | Project identifier; originates from backend, not guessed by model |
| `version_id` / `parent_version_id` | Retains independent version on each generation/modification; parent version of the first version is `null`; branches after undo also use new IDs |
| Source Asset Time | `*_seconds`, in seconds, relative to the zero starting point of decoded media |
| Final Cut Time | `*_frame` / `*_frames`, in output frames; fixed at 30 fps across all three stages for now |
| Time Interval | Left-closed right-open, e.g., `[0, 90)` represents frames 0–89, totaling 3 seconds |
| Coordinates | Layer `rect` is in final canvas pixels, with the top-left corner as the origin; not percentages or native video dimensions |
| Null Values | Unused collections use `[]`; identifiers with explicitly nullable types use `null`; do not mix with empty strings |
| File References | Timeline only stores `asset_id` / `clip_id`, not local absolute paths or expiring access URLs |
| Unknown Fields | Reject misspelled or undeclared fields; do not silently ignore unknown fields and proceed with rendering |

The schema uses JSON Schema Draft 2020-12. Both structural validation and business validation are required: the former checks fields and types, while the latter verifies whether assets exist and durations match. [Objects and Required Fields](https://json-schema.org/understanding-json-schema/reference/object), [Compositions of Different Object Structures](https://json-schema.org/understanding-json-schema/reference/combining)

Structural versioning strategy: publish a new schema alongside new fields; backward-compatible additions bump the minor version, while breaking changes such as altering time semantics bump the major version. The reading end first selects the installed schema based on the exact version, then validates; unknown versions are explicitly rejected or written to a new file after explicit migration. Legacy files and old MP4s are not overwritten in place.

`timeline.required_capabilities` is used to determine whether the current renderer can execute:

| Capability | Meaning | Earliest Stage |
| --- | --- | --- |
| `core_v1` | Hard cuts, fixed color grading, text/image overlays, audio tracks, and head/tail fade in/out | MVP |
| `audio_envelopes_v1` | Time-segmented music ducking | V2-3 |
| `subtitles_v1` | Positioned and timed subtitles | V2-3 |
| `portrait_v1` | 720×1280 canvas and corresponding framing | V3-1 |
| `dissolve_v1` | Shot overlap cross-dissolve | V3-3 |
| `overlay_fade_v1` | Layer fade in/out animation | V3-3 |

The MVP renderer only declares `core_v1`. When receiving a file that requires additional capabilities, it must report "not supported in current version" and must not pretend export succeeded. Mood, duration, and style are compiler/product capabilities, so separate rendering types need not be invented for each; stickers reuse image layers, and narration reuses audio tracks. **Having fields to express a feature does not mean product functionality for that stage is already implemented.**

<a id="s6-3"></a>

### `assets.json`: Separating Stable IDs from Real Files

Common fields are `asset_id`, `kind`, `origin`, `storage_key`. `origin` is `upload`, `bundled`, or `generated`; `storage_key` is a relative key within object storage/workspace and cannot contain absolute paths or `..` path segments.

| `kind` | Additional Required Fields | Example Use Cases |
| --- | --- | --- |
| `video` | `duration_seconds`, `display_width`, `display_height`, `rotation_degrees`, `has_audio` | User assets; `clip_id` references these resources |
| `audio` | `duration_seconds` | BGM, V3-generated narration |
| `image` | `width`, `height` | Fixed decorations, cutout stickers, reference images |
| `font` | None | Installed and verified font files |

`display_width/height` represents viewing dimensions after applying rotation metadata; `rotation_degrees` records rotation that needs to be applied when decoding the original file. Normalized proxies should record that rotation has been applied and must not rotate twice. Asset seconds still correspond to the original content; proxy files must not secretly alter the timebase.

The same asset ID points to immutable content; assign a new ID when replacing music, fonts, or generating stickers. The analysis cache is still built based on actual file content hashes and analysis versions, not just filenames. The backend downloads/resolves `storage_key` to temporary paths; the renderer does not depend on pre-deployment disk paths. The [assets examples](../../contracts/examples/assets.json) in the directory simultaneously provide references for MVP, V2, and V3 examples.

<a id="s6-4"></a>

### `config.json`: Storing User Intent and Version Settings

The outer layer includes project/version identifiers, while actual settings reside in `settings`. The backend stores full snapshots in each new version rather than overwriting old configurations.

| `settings` Field | Type / MVP Default | Meaning and Subsequent Purpose |
| --- | --- | --- |
| `output` | Object: 1280×720, 30 fps, `mp4_h264_aac` | V3-1 optional 720×1280; encoding specifications remain consistent |
| `duration_policy` | `target`, 30 seconds, 30 frames tolerance | Clarifies when target duration fitting is required; see below |
| `style_id` / `style_revision` | `magazine_scrapbook` / `1` | Selects which validated style version to use |
| `mood_id` | `null` | V2-1 uses `cozy_memory` / `bright_diary` |
| `title_overrides` | `{}`, can contain any modified layer among the three title tiers | Non-overridden parts use existing AI titles; does not mean AI rewrites user titles every time |
| `warmth_override` | `null`; explicit range −1…1 | `null` uses presets; 0 is neutral, positive is warmer, negative is cooler |
| `music_asset_id` | `bgm_lofi_01` | Fixed in MVP; V2-1 selects prepared tracks based on mood |
| `voice_enabled` / `subtitles_enabled` | `false` / `false` | Only opened in V2-3; turning off source audio also turns off spoken subtitles |
| `excluded_clip_ids` | `[]` | Persistently records source assets excluded by the user; subsequent re-selection cannot add them back |
| `creation_brief` | `text: null`, `reference_image_asset_ids: []` | V3-5 accepts a single sentence or reference image; ultimately still compiled into supported style parameters |

Output configuration only accepts 1280×720 or 720×1280, rejecting arbitrary combinations of width and height values. The encoding profile `mp4_h264_aac` is fixed to MP4, H.264, yuv420p, AAC 48 kHz; encoding performance parameters are managed by validated renderer configurations, not generated by AI.

**Duration conflicts are resolved using two modes:**

- Initial generation or V2 explicit duration specification: `{"mode":"target","target_seconds":30,"tolerance_frames":30}`. When assets are insufficient, return inability to meet target without duplicating footage to pad; 20 seconds is available starting in V2-2, 60 seconds starting in V3-2.
- Pure asset deletion: switches to `{"mode":"natural","target_seconds":null,"tolerance_frames":0}`. A 27-second result is a valid 27 seconds and will not continue to be judged a failure against the old 30-second target. Only explicitly requesting 20/30 seconds switches back to target mode.

Only changing titles or warmth preserves the original duration mode and shot arrangements. Deleting all available shots will reject the modification and retain the old version, avoiding generating an empty video.

<a id="s6-5"></a>

### `edit_plan.json`: What AI Outputs

Outer `schema_version`, project/version IDs, and `origin` are written by the backend; `origin` marks `ai`, `rules`, or design sample `fixture`. **AI actually only returns the `plan` object**, without undertaking version allocation, path concatenation, or final timing calculations.

| `plan` Field | Type | Function |
| --- | --- | --- |
| `title` | Three strings: `eyebrow`, `headline`, `tagline` | Three-tier titles, character limits 40, 60, 80 respectively; actual layout still requires measurement |
| `shots` | Ordered array | Array order represents suggested final cut sequence |
| `sections` | `{section_id,label}` array, `[]` in MVP | Source of chapter labels in V3-3 |

Each `plan.shots[]`:

| Field | Meaning |
| --- | --- |
| `shot_id` | Unique shot ID in this plan, retained after compilation; the same source asset can be referenced by multiple shots |
| `clip_id` | References `video` in `assets.json` |
| `source_window.in_seconds/out_seconds` | Permissible candidate extraction range, must be within source asset |
| `preferred_duration_seconds` | Suggested shot duration, not exceeding candidate range; actual duration determined by backend |
| `importance` | 1–5, higher values should be retained; used for stable sorting during shortening, not a quality guarantee |
| `section_id` | `null` in MVP; subsequently references `sections` |
| `speech_sentence_ids` | `[]` in MVP; V2-3 references real transcribed sentences |

The complete [MVP Plan Example](../../contracts/examples/mvp.edit_plan.json) contains 10 shots, suggesting 3 seconds each. Candidate ranges do not require the model to guess frame-accurate action boundaries; it can only base them on provided keyframes, timing information, and subsequent transcriptions.

The schema provided to model services only extracts `PlanPayload` or `EditPayload` and needed definitions, adapted to the schema subset supported by that service; do not submit the entire backend root schema as-is to all vendors.

<a id="s6-6"></a>

### `timeline.json`: Final Execution Instructions

The outer layer is fixed to `schema_version`, `document_type`, `project_id`, `version_id`, `parent_version_id`, `timeline`.

| `timeline` Field | Function |
| --- | --- |
| `compiler_version` | Compiler algorithm version; current contract sample is `1.0.0` |
| `required_capabilities` | Capability checklist inspected before rendering |
| `output` | Final dimensions, frame rate, and encoding profile |
| `duration_frames` | Actual total frame count of final cut; 900 frames is 30 seconds |
| `duration_policy` | Validation policy copied from config; renderer does not readjust targets |
| `excluded_clip_ids` | Copied from config; re-checks exclusion constraints in the end |
| `style_snapshot` | Style ID, version, mood, and actual `grade` parameters |
| `shots` | Final video track, containing at least one shot |
| `audio_tracks` | Explicit audio tracks; MVP contains only one BGM track |
| `overlays` | Typeset titles and image decorations; V3 extends chapters and stickers |
| `subtitles` | Positioned and timed subtitles; `[]` in MVP |

The renderer uses actual parameters here and no longer loads "current latest version presets" to overwrite snapshots. `grade` includes `warmth` (−1…1), `saturation` (0…2, 1 being original value), `contrast` (0.5…1.5, 1 being original value), `brightness` (−0.2…0.2, 0 being original value). Concrete pixel mapping is fixed and verified with renderer implementation and cannot be delegated to the model to pick filters ad hoc.

**The complete structure of a shot is as follows:**

```json
{
  "shot_id": "shot_01",
  "clip_id": "clip_01",
  "source_in_seconds": 1.0,
  "start_frame": 0,
  "duration_frames": 90,
  "framing": {
    "mode": "contain",
    "background_color": "#F6F3EE",
    "focus_x": 0.5,
    "focus_y": 0.5
  },
  "transition_in": {"type": "cut", "duration_frames": 0}
}
```

It indicates: seconds 1–4 of the source asset are placed at frames 0–90 of the final cut, displayed as a complete frame; unused areas use a warm white background.

Only one duration field is stored to prevent mutual contradiction among `source_out_seconds`, `end_frame`, and duration. Derived relationships are:

- `end_frame = start_frame + duration_frames`.
- `source_out_seconds = source_in_seconds + duration_frames / fps`; speed ramping is not supported from MVP through V3.
- The first shot must start from frame 0, and `transition_in` is a hard cut.
- Subsequent `start_frame = 前一镜头 end_frame − 当前 transition_in.duration_frames`.
- Across the entire video, `duration_frames = 最后镜头 end_frame`; there must be no unexpected gaps.

The compiler first quantizes candidate ranges inward to the 30 fps grid, and the final video extraction start point also falls on this grid; keep at least 6 significant digits when storing decimal seconds, allowing for minor floating-point serialization differences during validation. After asset normalization, it must output the agreed number of frames without correcting via silent speed changes.

`framing.mode=contain` is the MVP default, retaining the full image without automatically cropping out subjects; `focus_x/y` does not participate in calculation in this mode. `cover` scales proportionally and crops to fill the canvas, picking the crop center via 0…1 focus coordinates, with the crop frame always constrained within asset bounds; only used in V3-1 after verifying subject visibility.

`transition_in` represents the transition entering the current shot. MVP fixes `cut/0`; V3-3 allows `dissolve`, 1–30 frames, default 15 frames. The sum of incoming and outgoing transition lengths must be less than current shot length to prevent three shots overlapping simultaneously; spoken shots still use hard cuts on both sides.

<a id="s6-7"></a>

### How Audio Tracks, Subtitles, and Layers Are Extended

**`audio_tracks[]`: All audible sound originates here.** Source audio cannot be automatically mixed in just because the video file comes with an audio track, nor is another set of `keep_audio` switches used concurrently.

| Field | Meaning |
| --- | --- |
| `track_id` / `kind` / `asset_id` | Audio track ID, `bgm/source_audio/narration`, asset ID |
| `shot_id` | Only `source_audio` binds visual shots; BGM and narration use `null` |
| `source_in_seconds` | Where to start extracting from audio or video native audio tracks |
| `start_frame` / `duration_frames` | Position and duration in the final cut |
| `gain_db` | Fixed gain, 0 represents original volume; example BGM is −12 dB, merely an initial value pending audition |
| `fade_in_frames` / `fade_out_frames` | Frame counts for track head/tail fade in/out, their sum not exceeding track duration |
| `envelope` | `[]` in MVP; V2-3 `{offset_frame,delta_db}` volume change points |

`envelope.offset_frame` is relative to the start of this audio track, strictly increasing in time, and contains two endpoints (0 and track duration) when non-empty; `delta_db` stacks onto base `gain_db`, performing linear interpolation across dB values between adjacent points. Head/tail fades are superimposed separately via linear amplitude. The compiler calculates ducking curves in advance based on spoken segments, avoiding speech detection during rendering.

Exactly one BGM track must cover the entire video; when asset length is insufficient, reject early or select a sufficiently long prepared track without implicit looping. The asset ID of source audio must match `clip_id` of the bound shot, maintaining the same time mapping between start point and visual. Source audio and narration must not overlap each other; fixed limiting policies are applied after full-video mixing to prevent clipping.

In V3, narration generates audio first, registers as an `audio` asset, and measures actual duration before arranging tracks. Copy, timbre, and generation settings belong to generation requests/asset provenance records; timeline only references generated audio without letting the renderer invoke TTS ad hoc.

**`overlays[]`: Both text and image layers are supported starting in MVP.**

| Field | Meaning |
| --- | --- |
| `overlay_id` / `kind` / `role` | Unique ID; `text/image`; distinguishes three-tier titles, decorations, and subsequent chapters/stickers |
| `start_frame` / `end_frame` | Global start/end frames in final cut, must not exceed entire video |
| `rect` | `x/y/width/height`, final canvas pixels; entirely inside canvas |
| `z_index` / `opacity` | Higher values on top; same layer rendered in array order, later ones on top; opacity 0…1 |
| `animation` | `none/0/0` in MVP; V3-3 supports in/out frame counts for `fade` |
| Text-Specific Fields | `text`, `text_style`: font ID, pixel font size, color, alignment, stroke width/color |
| Image-Specific Fields | `asset_id`, `fit=contain`; transparent PNGs directly preserve alpha |

Layer rectangles are positioned from the top-left corner. Text wrapping, casing, and font size are resolved before the final timeline is produced; `text` can carry explicit line breaks. The compilation/titling module measures with actual fonts; when overflowing, it first shrinks font size to the verified lower bound, returning title too long if still overflowing; do not silently rewrite user-specified text. MVP titles are displayed from frame 0 to `min(90, duration_frames)`, remaining within bounds even if the final cut is under 3 seconds after deletions. The renderer generates PNG overlays from final fonts and layouts without redesigning layout. Recompute these pixel coordinates in vertical video without simply stretching horizontal final cuts.

**`subtitles[]`: Only populated in V2-3.** Each item contains `subtitle_id`, `source_audio_track_id`, `source_sentence_id`, `start_frame/end_frame`, `text`, `rect`, `text_style`. Sentences originate from `transcript.json` and cannot be fabricated by the director model; start/end frames must lie within corresponding source audio/narration ranges. Long sentences may be split into multiple subtitle blocks, but their content and bounds must remain traceable to original transcripts without averaging or guessing timings.

`transcript.sentences[]` defines `sentence_id`, `asset_id`, source asset `in_seconds/out_seconds`, `text`, and `words[]`. Each word also has text and source asset timing in seconds. When only sentence timings exist, `words=[]`; in this case only sentence-level subtitles are generated without claiming word-by-word highlighting. Lacking reliable sentence timing fails acceptance.

<a id="s6-8"></a>

### `edit_request.json`: Modifications Are Controlled Operations, Not Arbitrary JSON Patches

Outer fields are `request_id`, `project_id`, `base_version_id`, original `instruction`, and `resolution`, along with general schema/type. Version IDs and request IDs are provided by the caller/backend and cannot be modified by the model.

| Operation | Parameters | Stage |
| --- | --- | --- |
| `set_title` | `field: eyebrow/headline/tagline`, `value: string` | MVP; "change title" defaults to headline |
| `set_warmth` | Absolute value of `value: -1…1` | MVP; "a bit warmer" clamps after current value +0.1 |
| `remove_clip` | `clip_id` | MVP; deletes all final cut references to that source asset and records into exclusion list |
| `set_mood` | `mood_id: cozy_memory/bright_diary` | V2-1 |
| `set_target_length` | `seconds: 20/30/60` | 20/30 in V2-2, 60 in V3-2 |
| `set_voice` / `set_subtitles` | `enabled: boolean` | V2-3 |
| `set_aspect_ratio` | `value: 16:9/9:16` | V3-1 |
| `set_style` | Registered `style_id` | V3-3 |

Multiple operations in a single request undergo overall validation first, applied to a copy in array order, creating a visible successful version only when all succeed; none are executed partially if one is unsupported. `set_title` must also be validated against the 40/60/80 character limits of corresponding tiers. `set_mood` clears old warmth overrides while preserving user titles and exclusion constraints; place `set_warmth` after if the same command explicitly sets warmth again. Switching full styles clears old mood/warmth overrides, retaining user titles, exclusion constraints, aspect ratio, and duration intent.

Stage validation is executed by the backend: MVP only accepts the first three operations and cannot open all capabilities just because the root schema includes V2/V3 operations. Sticker/narration generation and reference image inputs in V3 produce assets or settings via corresponding pipelines before utilizing existing timeline structures; this does not let the model generate arbitrary shell commands or arbitrary layer types.

`resolution` has the following three mutually exclusive structures:

- `ready`: Contains non-empty `operations`, permitting continuing validation and rendering.
- `needs_selection`: Contains `prompt` and at least two `{clip_id,label}` candidates; no executable operations at this point. The task returns this result and releases executors, while the frontend displays thumbnails resolved by the backend; after user confirmation, submit explicit `remove_clip` with a new `request_id`, re-checking `base_version_id`.
- `unsupported`: Contains `reason`, leaving versions unmodified. For instance, when MVP requests "only delete half a second of dog footage in this video", it cannot secretly delete the entire source clip.

Candidates can only come from assets actually utilized in the current successful version; return explicit unsupported/cannot locate reasons when there is no match. Model parsing results do not use "modification succeeded" summaries; only after successful rendering and storage does the backend generate `result.summary` based on actual operations.

<a id="s6-9"></a>

### Which Fields Will V2/V3 Modify

| Feature | Fields Used or Modified | Requires Overhauling Shot Structure? |
| --- | --- | --- |
| V2-1 Two moods | config mood/music; actual grade, shots duration, and BGM | No, recompiles existing structure |
| V2-2 Shortening | duration_policy, shots, affected audio track/layer spans | No, recalculates without letting renderer delete shots ad hoc |
| V2-3 Spoken subtitles | plan sentence references; adds source_audio, envelope, and subtitles | No |
| V3-1 Vertical video | output dimensions, per-shot framing, layer/subtitle rect and font size | No |
| V3-2 60 seconds | target_seconds, more shots, sufficiently long BGM | No, re-executes asset and performance acceptance |
| V3-3 Styles/Animations | style_snapshot, sections, overlays, transition_in | No |
| V3-4 Cutout/Narration | new image/audio in assets; image layers or narration audio tracks | No |
| V3-5 Text/Reference image | creation_brief, maps to existing style, mood, plan | No, does not treat reference image content directly as rendering commands |

<a id="s6-10"></a>

### Rules That Compilation and Validation Must Follow

1. **Validate references and stages first.** Assets, fonts, sentences, and style IDs exist with matching types; excluded assets cannot be reselected; supported by both current stage and renderer capabilities.
2. **Valid asset bounds take precedence.** Quantized candidate intervals remain within assets; actual duration must not exceed available range. MVP defaults to 45–90 frames per shot. Full spoken passages retained in V2-3 can exceed this regular shot cap while still satisfying source and overall duration.
3. **Separate target duration from natural duration.** Target mode checks ±30 frames; natural mode adopts actual total shot length. Deletions do not automatically replenish clips, and subsequent title edits cannot reactivate old targets.
4. **Beat matching is a preference.** Pick available beats close to suggested duration within valid bounds; yield in case of conflict with overall duration or complete speech. Never cut off a sentence for beat matching. The beat array is relative to original music; subtract music extraction start point and add final cut start point before converting to frames.
5. **Stable shortening order.** V2-2 shortens non-spoken shots from lowest to highest importance, starting from later shots within the same priority; each shot is shortened at most to allowed minimum, halting once target is met. If still too long, attempt removing shots in the same order and re-check target tolerance. Explicitly fail and retain old version when remaining assets cannot satisfy target, avoiding endless AI reinvocations.
6. **Inspect all tracks.** No visual holes, transitions overlap correctly; BGM covers full video; source audio matches visual source timing; subtitles and layers do not exceed boundaries; source audio and narration do not overlap.
7. **Inspect actual visuals and sound.** Fonts exist and text can be typeset, original audio tracks are not mixed in by default, and final encoding/resolution/frame count meet expectations. Structural validity does not imply passing aesthetic or playback quality.
8. **Publish version upon success.** Validation or rendering failures do not advance the current version pointer; undo merely switches among successful versions. Config, plan, and timeline should maintain consistent project/version identity.

A single compilation path is sufficient: validate input → apply exclusion and override settings → determine valid extraction length → calculate hard cut/subsequent transition positions → arrange music/speech → arrange titles/subtitles → full validation. Plan repair calls are capped at 2 times, with total timeout bounded by task config; return reason when unsatisfied.

<a id="s6-11"></a>

### Complete Examples and Explicit Expectations

| Example | Expected Time Relationships | Purpose |
| --- | --- | --- |
| [MVP config](../../contracts/examples/mvp.config.json) + [Plan](../../contracts/examples/mvp.edit_plan.json) + [Timeline](../../contracts/examples/mvp.timeline.json) | 10 shots, 90 frames each, totaling 900 frames; titles first 3 seconds; BGM only | Two-person integration baseline |
| [Delete Request](../../contracts/examples/mvp.edit_request.json) + [Post-deletion Config](../../contracts/examples/mvp.after-delete.config.json) + [Post-deletion Timeline](../../contracts/examples/mvp.after-delete.timeline.json) | 9 shots after deleting clip_07, totaling 810 frames/27 seconds; natural duration mode, old version retained | Verifies separation of deletion from target duration conflicts |
| [Modification Requiring Selection](../../contracts/examples/selection.edit_request.json) | Generates no new video, returns two candidates | Prevents erroneous deletion |
| [V2 Timeline](../../contracts/examples/v2.timeline.json) + [Transcript](../../contracts/examples/v2.transcript.json) | Still 900 frames; seconds 6.1–8.7 play source audio with margin, seconds 6.2–8.6 display sentence subtitles, BGM ducks synchronously | Verifies audio-visual time mapping |
| [V3 Timeline](../../contracts/examples/v3.timeline.json) | 720×1280; totaling 885 frames/29.5 seconds after a single 15-frame dissolve; also includes stickers, fades, and narration | Verifies structural extensibility; does not imply V3 features are implemented |

V2/V3 examples demonstrate field capacity, reusing the same set of placeholder references for shot assets; they are not results of aesthetic comparison. The 3-second cut points in the MVP example can be verified with a 100 BPM music clip changing every 5 beats, though actual music or beat files are not attached to the examples.

<a id="s6-12"></a>

### Verification Methods and Delivery Boundaries

Enter `contracts/` from repo root and run `python3 validate_examples.py` to check JSON structure, references, shot durations, audio tracks, subtitle mappings, and error cases. Run `python3 collaboration/validate_collaboration.py` separately for collaboration interfaces and development doubles; see [Collaboration Package Notes](../../contracts/collaboration/README.en.md) for complete usage.

Scripts do not rely on additional installations; structural checks only cover keywords used by this schema, not being a general JSON Schema standard implementation. Use standard JSON Schema validators or Pydantic during actual application development, preserving cross-field business validation. Current checks do not read real assets or fonts, invoke models, or execute FFmpeg/Replit; actual rendering and UI remain subject to project milestone acceptance.

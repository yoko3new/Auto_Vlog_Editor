# Styles, Editing, and Revision Rules

[中文](editing.md) · **English**

[Return to Project Overview](../../README.en.md)

When to read: Read when modifying styles, titles, warmth, deletions, caching, or undoing. For web visuals, see visual-design.md.

<a id="s7"></a>

## Style Configuration and Project Settings

<a id="s7-1"></a>

### Differences Between the Two Types of Data

Style answers "what it looks like": fonts, colors, color grading, transitions, shot pacing.

Project settings answer "what to do this time": frame size, duration, title copy, whether to keep original audio and subtitles.

Read versioned style presets → Apply mood presets → Apply user title/warmth overrides → Calculate layout according to output specifications → Save `config.settings` and `timeline.style_snapshot`. For how to clean up old overrides when switching moods/styles, see [`edit_request.json`: Modifications are Controlled Operations, Not Arbitrary JSON Patches](timeline.en.md#s6-8); rendering only reads the final timeline and does not reload default presets.

<a id="s7-2"></a>

### Style Schema

| Field | Content | MVP Actual Support and Subsequent Phases |
| --- | --- | --- |
| `id`, `display_name`, `description` | Style identifier and description | Retained |
| `grade` | LUT, saturation, contrast, brightness, warmth | First implement a small number of parameters that map clearly to filters |
| `title_card` | Text, background, duration, decorations, animation | MVP fixed typography + static decorations; add animation in V3-3 |
| `chapter_labels` | Activity tags, position, animation | Implement in V3-3; not displayed in MVP |
| `transitions` | Intra-segment and inter-segment transitions and durations | MVP only has hard cuts; implement dissolves in V3-3 |
| `pacing` | Allowed shot durations, beat selection, music genre | Select beat cut points within allowed durations |

Options from the original draft such as collage, typewriter, zoom, and push-in will only appear in the usable schema once implemented and tested by the renderer. There must not be valid configurations where "the AI can select it, but the renderer cannot draw it."

The original `cut_on=beat` should be explicitly interpreted as "cut points land on beats", not "cut on every beat". `downbeat` requires the track to provide corresponding markers; if there are no markers, do not open it.

`TextStyle` can retain font, font size ratio, case, letter spacing, color, and opacity. Letter spacing is not equally easy to implement across all text rendering approaches; the first version should verify the selected solution first; use a fixed value when not implemented.

<a id="s7-3"></a>

### Design Constraints

- The main title is the largest, with three layers of typography having a clear hierarchy.
- Script fonts do not use all-caps; script fonts are only used for short subtitles.
- Fonts, LUTs, and decorations can only come from local verified assets.
- Accent colors can come from the footage, but titles must remain legible; add background color or drop shadows if necessary.
- `three_tier` requires content in all three layers; when decorations are turned off, the quantity is zero.
- Constrain copy length, line count, and minimum font size to handle overly long titles.

The schema is responsible for the structure, but whether the title is actually clear still needs to be visually verified at video resolution.

<a id="s7-4"></a>

### Formal Fields for Project Settings

`config.settings` from [`config.json`: Preserving User Intent and Version Settings](timeline.en.md#s6-4) is referenced here, rather than building another set of synonymous fields.

| Field | MVP Default | Subsequent Phases |
| --- | --- | --- |
| `output` | 1280×720, 30 fps, fixed MP4 encoding profile | Switch to 720×1280 in V3-1 |
| `duration_policy` | target, 30 seconds, tolerance 30 frames | natural upon deletion; add 20 seconds in V2-2; add 60 seconds in V3-2 |
| `style_id` / `style_revision` | magazine_scrapbook / 1 | Only select registered and implemented preset versions |
| `title_overrides` | `{}` | User-specified titles are saved in the corresponding layer, not overwritten by re-selecting footage |
| `warmth_override` | null | Save absolute value −1…1 when explicitly set by the user |
| `mood_id` / `music_asset_id` | null / fixed music ID | Open mood-corresponding tracks in V2-1 |
| `voice_enabled` / `subtitles_enabled` | false / false | Open in V2-3 |
| `excluded_clip_ids` | `[]` | Continuously retained after footage deletion; restoring an older version recovers its list |
| `creation_brief` | No text/reference image | Input in V3-5, eventually mapped to existing parameters |

<a id="s8"></a>

## Preset Styles

MVP uses the `magazine_scrapbook` base version by default. V2-1 provides two mood parameters on the same layout; the second complete layout `clean_magazine` belongs to V3-3.

| | `magazine_scrapbook` | `clean_magazine` |
| --- | --- | --- |
| Status | MVP base version; extended animations in V3-3 | V3-3 complete second style |
| Mood | Warm, magazine typography, minimal scrapbook decorations | Restrained, whitespace, pure typography |
| Color Grading | Slightly warm, soft, LUT intensity verified with real footage | Neutral, slightly desaturated |
| Eyebrow | DM Sans or Inter, short phrases, all-caps | Same as left |
| Main Title | Playfair Display | Cormorant Garamond |
| Subtitle | Pinyon Script, content kept brief | Can first reuse existing subtitle implementation |
| Background | First segment main frame | First reuse single frame; dual-frame collage deferred |
| Decorations | 0–2 fixed paper, tape, or line elements | None |
| Chapter Tags (V3-3) | Activity phrase, e.g., `slow mornings` | Activity or reliable time information |
| Transitions | MVP only hard cuts; 0.5-second dissolves added in V3-3 | Reuse verified capabilities |
| Shot Pacing | Cuts on beat within 1.5–3 second range | Cuts on beat within 2–3.5 second range |
| Music | MVP fixed to one lofi or acoustic track; mood-corresponding tracks added in V2-1 | Reuse prepared tracks |

When reliable time or location cannot be read, do not generate seemingly precise `08:30 am · home`. Use activity descriptions that can be supported from the footage.

After adding a new preset, it must pass configuration validation and actually render a segment. Passing JSON self-check alone does not mean fonts, colors, and transitions will end up normal.

<a id="s9"></a>

## Natural Language Modifications, Caching, and Undo

<a id="s9-1"></a>

### Using Explicit Operations

The formal structure is governed by [`edit_request.json`: Modifications are Controlled Operations, Not Arbitrary JSON Patches](timeline.en.md#s6-8) and the machine schema. MVP only enables `set_title`, `set_warmth`, and `remove_clip`; the backend simultaneously validates field legality and current phase capabilities. The following example is a parsed deletion request; it is not yet the "render succeeded" result.

```json
{
  "schema_version": "1.0.0",
  "document_type": "edit_request",
  "project_id": "project_demo",
  "request_id": "request_remove_01",
  "base_version_id": "version_mvp_01",
  "instruction": "删掉有狗的那段",
  "resolution": {
    "decision": "ready",
    "operations": [
      {
        "type": "remove_clip",
        "clip_id": "clip_07"
      }
    ]
  }
}
```

The frontend can accept modification requests in Chinese and English; the finished video title defaults to English. The generation success summary is produced by the backend based on actual changes completed, rather than using model self-reported success during the parsing stage.

<a id="s9-2"></a>

### Which Steps Require Rerunning

| Modification | Handling Method |
| --- | --- |
| MVP: Title text, warmth | Retain selected footage; update configuration and overlay layers, then re-render |
| V2-3: Turn off subtitles | Retain selected footage and audio; update subtitle switch, then re-render |
| V2: Shorten duration, change pacing | Modify or regenerate plan, recalculate complete timeline, then re-render |
| MVP: Delete specified footage | Delete corresponding shot, record exclusion constraints, recalculate subsequent positions, then re-render; verify subtitles and transitions separately in corresponding phases |
| V2-1: Change music atmosphere | Reselect track, load corresponding beats, recalculate timeline, then re-render |
| V3-1: Change frame size | Recalculate cropping and layout, then re-render; re-selecting footage is needed only if assets do not fit the new frame size |
| V3-3: Switch complete style | Re-render only for pure visual parameters; recalculate timeline if music or pacing changes |

A simple deletion switches configuration to `duration_policy.mode=natural`, clears target duration, and records excluded footage. Explicitly specifying a target duration belongs to V2-2; re-arranging also cannot bring back excluded footage. When there are multiple candidates, return `needs_selection` from [`edit_request.json`: Modifications are Controlled Operations, Not Arbitrary JSON Patches](timeline.en.md#s6-8), release the executor, and submit an explicit deletion with a new request ID once the user confirms.

<a id="s9-3"></a>

### Buttons Do Not Need to Route Through AI

MVP's fixed `Warmer` buttons directly generate operation objects; freeform input is handed off to `intent`; both subsequently follow the same validation and rendering pipeline. The `20 sec` button is added in V2-2, and `No subtitles` is added in V2-3; do not display unimplemented controls on the MVP page.

<a id="s9-4"></a>

### Caching and Versioning

Caches are distinguished by "original file content identifier + analysis configuration/version"; music caches are distinguished by "track + analysis configuration". Identical filenames do not mean identical content.

Each generation creates a new version, saving the plan, final timeline, configuration snapshot, modification request, summary, and finished video. A new version becomes the current version only after passing checks; the old video continues to be retained upon failure.

Undo directly switches back to the previous successful version without calling AI or re-rendering. Subsequent modifications after an undo create a new unique version and record the parent version; do not overwrite an already existing `v002`.

AI output validation failures can be retried with repairs up to 2 times, with an overall timeout configured. When initial generation fails persistently, use a chronological, deduplicated rule-based fallback and flag the degraded result. When modification requests fail persistently, retain the old version and explain that it was not completed, rather than displaying a false success summary.

<a id="s9-5"></a>

### V2-1: Expressing the Desired Feeling

After MVP acceptance, prioritize supporting two explicit, tested mood presets, such as `cozy_memory` and `bright_diary`. When a user says "Make it feel like a cozy memory", `intent` selects a predefined preset and then expands it into allowed parameter modifications.

Each preset only combines existing capabilities. For example, warm memory can use slightly warm colors, longer shots, and soft preselected music; brisk diary can use bright visuals, shorter shots, and upbeat music. These are design solutions that require visual verification and do not mean changing a parameter will inevitably produce the corresponding feeling.

If a preset alters music or shot pacing, the timeline must be recalculated. Generate a summary describing actual changes, such as "Warmer colors, gentler music, longer shots", to help the user understand the result. When this layer is not implemented, continue using precise operations like "Warmer" and do not show over-promising mood buttons.

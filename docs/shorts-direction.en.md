# Vlogii: Life Record Shorts

[中文](shorts-direction.md) · **English**

[Back to Overview](../README.en.md) · [Product Scope](product.en.md) · [Editing and Speed](editing-modes.en.md) · [Visual Specifications](visual-design.en.md)

2026-10-10 Product direction confirmed by the user: Focus on lifestyle short vlogs such as campus, studying abroad, commuting, and cooking. Refer to the structure and user description of [Day In My Life Shorts](https://www.youtube.com/shorts/um2oBpliDbk); page opened and played, cut points of the reference video not measured frame by frame. The seconds below are adjustable design parameters of this project and do not claim to match the reference frame by frame.

## Default Work Structure

1. **Attractive Cover**: Select clear, authentic footage with a sense of daily life; the title must include visual design with stickers or artistic typography to ensure legibility on mobile phones. The cover is not just an overlay of plain subtitles; the theme is determined by footage and the user, without fabricating dates, locations, or experiences.
2. **Opening Flash Cuts**: A few representative shots flash by to preview the day's content. Currently defaults to about 5 seconds, with each shot at most about 0.5 seconds, with 0.25 / 0.35 / 0.5 / 0.8 seconds selectable. Shot duration and footage playback speed are two independent settings; short shots are muted by default to avoid clipping voiceovers, nor do they overlay voiceover subtitles that are hard to finish reading; original audio is retained upon returning to the main body.
3. **Main Body**: Return to an understandable narrative pacing, preserving voiceovers or important ambient sounds, based on simple subtitles and supplemented with a few timestamp callouts, keywords, and light special effects. Do not edit the entire main body into flash cuts as well; meaningful segments can maintain original speed, while walking, commuting, and preparation processes can be sped up by interval.
4. **Natural Ending**: Retain authentic footage suitable for winding down, avoiding looping footage to meet a fixed duration.

Shorts is the default creation format, without forcing all footage to be compressed to 30 seconds; existing duration, retention ratio, and full retention options remain available. The opening and the main body can use different pacings and speeds.

## Status and Next Batch Scope

| Capability | Current Status |
| --- | --- |
| Original audio recognition, basic subtitles, text, color, vertical export | Implemented; real footage evidence available |
| Independent flash cut opening, shot duration, full-video/interval speed adjustment | Implemented locally; see [Records](vlogii-validation.md) for verification |
| Cover generation and artistic typography/sticker presets | Pending implementation; free font candidates [prepared](free-resources.en.md) |
| Generating a complete work of "cover + flash cuts + main body" in one pass | Pending implementation; currently quick cuts and main body are exported separately |
| Time/short word callout widgets, light special effects, BGM, beat syncing | Pending implementation; not claimed as completed due to current basic text capabilities |
| Style documents from natural-language iterations, saving and importing personal styles | Future plan; not implemented |

The next batch takes a complete work of unified style as the delivery unit: first design authentic cover and main body layouts, then connect opening/main body stitching and a few callouts; BGM and beats will be implemented separately when authorized. Timestamp callouts must be provided by reliable footage metadata or the user, not letting AI guess the time of day. Default style and music can spare users lengthy inputs; users only need to provide footage, with optional theme/title/retention preferences, and modify by timestamp after viewing.

A is responsible for planning, cover and video rendering, speed, subtitles, and versions; B is responsible for the corresponding pages and previewable style selections. Unimplemented presets must not appear on the page as executable features.

<a id="personal-style-library"></a>

## Future Improvement: Personal Style Library

The user wants natural-language editing to produce a readable, reusable style document that they can choose to save to their personal library when satisfied, then import next time to avoid repeated setup. This is a future requirement; this round records the design without implementing saving, importing, or reference-video extraction.

### Workflow

1. **Create a draft**: Compile a style document from the user's description, applied editing settings, and reference style. Mark unknown or inferred values from reference videos for the user to review and edit.
2. **Iterate alongside the edit**: Requests such as "slow down the opening," "mute the flash cuts," or "simplify the subtitles" update the style draft and produce a corresponding preview. Failed, undone, or unapplied changes do not automatically become saved preferences.
3. **Choose to save**: Once satisfied, name and save the style, linking it to the corresponding successful film version. The user explicitly chooses to create a new style or update an existing one; attempts are not automatically added to the personal library.
4. **Import next time**: Select a personal style, provide new footage, and optionally add a theme and adjustments for this project. Imported settings remain editable. Overrides affect only the current project; updating the library requires an explicit save.

### What the Style Document Records

| Category | Reusable Information |
| --- | --- |
| Cover | Artistic fonts, stickers, title layout, and colors; the actual title comes from the current footage |
| Opening | Flash cut duration, shot duration, playback speed, and muting |
| Main body | Retention preferences, narrative ordering principles, and types of footage suitable for speeding up |
| Subtitles and callouts | Fonts, sizes, safe areas, keyword emphasis, and timestamp presentation |
| Picture and sound | Color, light effects, BGM mood and volume, and the balance between speech and background music |
| Duration and ending | Default target duration or retention ratio, and ending approach |

Each style provides a readable description, with structured settings planned for application by the system. Saving records the style format version, resource identifiers for fonts/music, and the corresponding film version to support future compatibility checks. Only supported settings are applied; capabilities such as covers and BGM that are not yet implemented remain marked as pending support.

**Separate reusable style from instructions for a specific edit**: "Opening shots last about 0.5 seconds and are muted" is reusable; "delete 01:20–01:35," source filenames, specific dialogue, locations, and dates belong to the current project and are excluded from reusable style documents by default. New footage requires fresh selection and timeline calculation following the style, rather than copying timestamps from old footage. Reference Shorts inform an editable style draft, without promising frame-by-frame reproduction.

A owns style extraction, settings merging and application, storage, and rendering compatibility checks. B owns style document previews, save/import controls, and the personal style library page. Implementation should first enable saving and reusing existing settings, then gradually include new cover, music, and effects capabilities.

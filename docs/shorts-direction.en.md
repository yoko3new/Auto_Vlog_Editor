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

The next batch takes a complete work of unified style as the delivery unit: first design authentic cover and main body layouts, then connect opening/main body stitching and a few callouts; BGM and beats will be implemented separately per licensing. Timestamp callouts must be provided by reliable footage metadata or the user, not letting AI guess the time of day. Default style and music can spare users lengthy inputs; users only need to provide footage, with optional theme/title/retention preferences, and modify by timestamp after viewing.

A is responsible for planning, cover and video rendering, speed, subtitles, and versions; B is responsible for the corresponding pages and previewable style selections. Unimplemented presets must not appear on the page as executable features.

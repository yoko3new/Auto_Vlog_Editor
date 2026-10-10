# Page and Video Visuals

[中文](visual-design.md) · **English**

[Return to Project Overview](../README.en.md)

When to read: Used for frontend and video typesetting tasks. B (teammate) is responsible for page layout, CSS, and interactions; A (Yangkang) is responsible for in-video titles, subtitles, color grading, music, and decorations. Currently Vlogii has basic text/subtitle rendering, and the magazine-style final video described below remains the goal; CSS effects and exported MP4s are accepted separately.

<a id="brand-logo"></a>

## Confirmed Vlogii Logo

On 2026-10-10, confirmed adoption of the version with light mint green, bold rounded lowercase wordmark, and stacked frame icon (design draft v8). The brand wordmark is unified as `vlogii`, six lowercase letters; on the left is stacked frames and a play symbol within a rounded square, on the right is a thick, slightly irregular rounded letterform.

![Vlogii Final Confirmed Logo](../resources/branding/vlogii-logo.png)

[Download confirmed transparent PNG](../resources/branding/vlogii-logo.png). The shared file is `resources/branding/vlogii-logo.png`, fully consistent with the confirmed design draft; early candidate drafts remain local and are not official assets.

- Color scheme direction: Light mint green wordmark and graphics, milky mint icon background. Design reference colors are `#8CCDB8` and `#E1F5EC`; actual colors and transparency in the PNG are subject to the original image.
- Maintain the relative position and overall proportion of the icon and wordmark, scale proportionally and preserve white space; do not stretch, do not rearrange letters, and do not replace the wordmark with regular fonts.
- B is responsible for subsequent web page integration and readability verification under different backgrounds and sizes; if A uses it for exported videos, implement and accept separately. This time only brand assets and documentation are saved, not yet integrated into web pages or added as video watermarks.
- Current assets are PNGs with alpha, with a small amount of white residue remaining on transparent edges. When cleaning up edges or creating SVGs subsequently, maintain the shape and color scheme of this version and verify visual consistency; do not claim the current PNG as a vector file or font file.

The current integration branch `codex/integrate-feng-ui` uses the teammate’s editorial column: a light background, mint emphasis, chapter navigation and a wide player. The logo appears in the masthead and empty state; Fontsource web fonts are bundled, with system fallbacks for Chinese. See the [web editor](vlogii-guide.md#web-design). This leaves MP4 caption layout unchanged; covers, stickers and BGM remain pending.

The layouts and palette below are historical suggestions from the competition proposal. The integrated implementation defines the current web editor; editorial styling of exported films remains pending.

<a id="s12"></a>

## How to Make the Interface More Appealing with Minimal Time

<a id="s12-1"></a>

### Visual Direction: Small Magazine Editorial Desk

The interface uses a warm white background, dark text, sparse terracotta accents, paired with a video preview occupying the primary area. Let users see the video and style examples first.

For the Creative track, a feeling description line can be added next to the cover, such as “Warm, playful, a little nostalgic”. The mood description must align with actual results. Work previews and before-and-after comparisons are more suitable for the primary area than technical parameters.

It is recommended to set the UI polishing time budget to about 3–4 hours, as a scope control target, not a work-hour guarantee. Finish layout and states first, then add decorations.

<a id="s12-2"></a>

### Single-Page Two-Column Layout

Desktop main content width is about 1120–1200px, left side about one-third, right side about two-thirds. Narrow screens stack vertically automatically. Check effects on the presentation computer and projector with priority.

```text
AUTO VLOG                         A little film of your day.
Your day, beautifully cut.
Turn everyday clips into a film worth keeping.

┌──────────────────────┐  ┌────────────────────────────────────┐
│ 01  Your moments     │  │                                    │
│ 拖入素材 / 使用示例   │  │           大视频预览              │
│ [缩略图][缩略图]      │  │      开始前：标明示例的封面       │
│ 素材段数 · 总时长     │  │      完成后：真实成片播放器       │
│                      │  │                                    │
│ 02  Your style       │  └────────────────────────────────────┘
│ [杂志手账风封面] ✓   │  v1 · Magazine Scrapbook · 实际时长
│ [第二风格封面]*      │  [Download] [Undo] [Version ▾]
│                      │
│ Output  30s · 720p   │  Make it yours
│ [ Create my film ]  │  [Warmer]
└──────────────────────┘  [Remove the clip with the dog…] [Apply]
                          Changed: …

* MVP 仅显示固定风格；V2-1 增加情绪卡，V3-3 才增加第二套完整风格卡。
```

The first version does not need navigation bars, dashboards, sidebar menus, or complex project landing pages. Actions revolve around this current video.

<a id="s12-3"></a>

### A Set of Directly Usable Design Parameters

| Item | Recommendation |
| --- | --- |
| Page background | `#F6F3EE` warm white |
| Content card | `#FFFEFA`, thin border `#DED8CF` |
| Primary text | `#252522` |
| Secondary text | `#68645E`, maintain readability |
| Primary button | `#8F422D`, white text |
| Body font | Inter or DM Sans, choose one |
| Large heading font | Playfair Display, use sparingly |
| Control height | About 44px, easy to click |
| Border radius | Card about 16px, button about 10px |
| Spacing | In 8px units: 8, 16, 24, 32 |
| Animations | Subtle hover, selected border, and fade-in only |

Centralize colors, fonts, border radii, and spacing into CSS variables, then lay them out with Tailwind. shadcn/ui provides buttons, cards, input boxes, and other components, with an official Vite installation route; add only components needed by the page and lock dependencies. [Official Vite Guide](https://ui.shadcn.com/docs/installation/vite)

This set of colors and spacing represents design recommendations for this project, and can be fine-tuned based on actual covers. Do not use all colors as accent colors.

<a id="s12-4"></a>

### Six Things Most Worth Spending Time On

1. **Real covers.** Each style uses covers from actually rendered videos, reflecting fonts, composition, and colors; covers illustrate effects better than abstract icons.
2. **Large preview.** The final video always occupies the visual center. Titles and subtitles must be legible at normal playback size.
3. **Pleasing initial state.** Show a clearly labeled sample and “Try sample clips” before upload, letting users know what they can ultimately get.
4. **Collapse infrequently used settings.** The MVP only displays fixed styles and output specifications; V2 displays implemented mood and duration selections. Advanced options are collapsed to avoid a screen full of parameters.
5. **Proper waiting and results states.** Include stage copy, viewable old versions, downloads, and summaries; recoverable upon failure.
6. **Unified alignment.** Consistent font sizes, button heights, card padding, and cover aspect ratios; delete redundant explanatory text and duplicate borders.

Sample clip buttons reuse the real workflow. If pre-generated videos are played directly, they must be marked as samples; do not mislead users into thinking it is a newly generated result. Browsers may restrict automatic playback with sound; keep manual click-to-play in demo scripts.

<a id="s12-5"></a>

### How to Choose Frontend Components

| Page Section | Implementation Recommendation |
| --- | --- |
| Two-column layout | CSS Grid; switch to vertical stacking on narrow screens |
| Upload area | Native file input + drag and drop; backend still checks real format and size |
| Media clip bar | Thumbnail grid + duration Badge, no draggable complex timeline |
| Style card | Actual finished video cover + single-select state; display only truly exportable styles |
| Main preview | Native `<video controls>`, fixed ratio, sufficiently large |
| Modification panel | Textarea, Apply, Warmer; titles and deletions can provide text examples, no unimplemented action buttons |
| Versions and settings | Select, Tabs, or accordion; advanced options collapsed by default |
| Waiting and errors | Stage list, Skeleton, retryable prompts, retain old videos |

Use React's text rendering to display user and model text, without concatenating this content directly into HTML.

<a id="s12-6"></a>

### Spending Two Hours for a Noticeable Visual Boost

First give Replit Agent a set of specific visual constraints: “Warm white paper background, black editorial large headings, a single terracotta accent color, media and styles on the left, large video preview on the right, one-sentence modification at the bottom; use real sample video covers. Only build the empty, processing, completed, and failed states for this single screen.”

Recommended time investment: 30 minutes to unify layout and fonts, 30 minutes to create real covers, 30 minutes to complete the four states, 30 minutes to check playback, alignment, and small screens. Animations should only feature short fade-ins and button feedback; do not crowd out the video preview with numerous floating cards, decorative gradients, and particle backgrounds.

**CSS effects on the web page will not automatically transfer into exported MP4s.** Web design is completed by React; titles, fixed decorations, and color grading in videos are completed by `titlecard` + FFmpeg; subtitles are only added in V2-3. Both sides share color and font specifications, accepted separately.

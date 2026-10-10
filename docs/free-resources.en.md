# Bundled Fonts and Free Instrumental Music

[中文](free-resources.md) · **English**

[Back to Overview](../README.en.md) · [User Guide](vlogii-guide.md) · [Runtime Asset Manifest](../src/vlogii/assets/manifest.json)

2026-10-10: The integration branch now includes 6 fonts and 6 instrumental tracks, browser selection/preview, real MP4 font rendering, and BGM mixing. Assets load with the application without requiring font installation, preset uploads, or runtime third-party requests. Presets also integrate with [style films](style-templates.en.md), which support music uploads, BPM/beat measurement and automatic beat syncing. Custom font uploads remain pending.

## Fonts

| Font | Suggested Use | Coverage and Source |
| --- | --- | --- |
| Noto Sans CJK SC | Default subtitles and clear titles | Chinese and English; [Official Noto](https://github.com/notofonts/noto-cjk/tree/main/Sans) |
| Noto Serif CJK SC | Book and magazine lettering | Chinese and English; [Official Noto](https://github.com/notofonts/noto-cjk/tree/main/Serif) |
| Ma Shan Zheng | Brush handwriting and short titles | Chinese/English samples passed; [Google Fonts](https://github.com/google/fonts/tree/main/ofl/mashanzheng) |
| ZCOOL XiaoWei | Literary titles | Chinese/English samples passed; [Google Fonts](https://github.com/google/fonts/tree/main/ofl/zcoolxiaowei) |
| Caveat | English handwriting | English; Chinese falls back; [Google Fonts](https://github.com/google/fonts/tree/main/ofl/caveat) |
| Playfair Display | English editorial titles | English; Chinese falls back; [Google Fonts](https://github.com/google/fonts/tree/main/ofl/playfairdisplay) |

Fonts are distributed unchanged under SIL OFL 1.1, with complete copyright and licenses in the [asset license directory](../src/vlogii/assets/licenses). Fonts are neither modified nor sold separately. Titles and subtitles share the selected font, using measured glyph widths, wrapping, and size adjustment. Missing glyphs cause the entire text entry to fall back to Noto Sans. If that also lacks a glyph, rendering reports an error instead of silently displaying boxes. English-only fonts never become the sole font for Chinese captions. Browser samples are not final video layouts; Default previews use Noto Sans, while an existing local override may change the actual export.

## Free Instrumental Music

All six tracks come from [Holizna's Chillout Instrumentals collection](https://opengameart.org/content/chillout-instrumentals-collection), published by the author under CC0. Users should listen to decide suitability and pacing; titles do not establish BPM.

| Track | Duration (seconds) | Format |
| --- | --- | --- |
| Dreams | 306.636 | MP3 / 48 kHz / stereo |
| Day Jobs | 138.540 | MP3 / 48 kHz / stereo |
| Dancing | 135.708 | MP3 / 48 kHz / stereo |
| Deja Vu | 124.764 | MP3 / 48 kHz / stereo |
| Childhood | 133.284 | MP3 / 48 kHz / stereo |
| Advertisements | 183.204 | MP3 / 48 kHz / stereo |

The [official CC0 description](https://creativecommons.org/publicdomain/zero/1.0/) and [author/source notice](../src/vlogii/assets/licenses/Holizna-CC0.txt) are retained with the manifest. Original tracks are unchanged. Sources, license verification date, sizes, and SHA-256 hashes are recorded. Platform Content ID has not been verified.

## Defaults and Editing

- Ordinary browser generations default to Noto Sans and Automatic music. Automatic uses a fixed rule: Dancing for opening highlights and Day Jobs for other modes; it is not AI mood matching or beat syncing. Users can select No background music or any of the six tracks.
- Ordinary-mode previews play the original track. Export music defaults to 16% volume, adjustable from 0–100%. Music is trimmed or looped to fit the final film, with fades up to 0.5 seconds at each end. Loop boundaries are not beat-aligned.
- Speech ducking is enabled by default. Recognized speech intervals are mapped after cuts and speed changes, reducing music to about 30% of the selected volume during speech with short ramps. Missed speech does not trigger ducking. Highlights keep source audio muted; BGM is neither sped up nor restarted per shot.
- Existing films can change fonts, tracks, volume, or ducking in the edit chapter, then Apply changes. Plans and analysis are reused. Music-only edits reuse video segment caches and mix continuously after joining. Undo restores the previous settings and soundtrack.
- Compatibility: Omitting the new appearance field does not add music to older requests. Old versions without settings load as Default font and No background music.

Style cuts retain template fonts by default (Chinese falls back to Noto Sans) and also accept the six presets. Automatic music chooses Dancing; bundled tracks or uploaded music can be selected. Initial volume is 100%, corresponding to the template’s −14 LUFS; reducing volume lowers target loudness. Source sound stays muted, so speech ducking controls are hidden. Track changes re-detect beats and re-cut rather than reusing ordinary-mode segment caches. Older style calls omitting appearance retain uploaded music and full template volume; older style versions are read the same way.

## Storage and API

Assets reside in `src/vlogii/assets/` and ship with the Python package, totaling about 94.8 MB. The browser reads the catalog from `GET /api/vlogii/presets`, with registered IDs in resource URLs and no arbitrary disk paths. Music supports range-based previews and fonts load on demand. Generation and editing accept optional `appearance`, containing `font`, `music`, `music_volume`, and `duck_music`. See the current [OpenAPI](vlogii.openapi.json).

Successful ordinary versions retain settings in `project.json` and actual IDs, hashes, fallback markers, and ducking intervals in `assets.json`. Retry preserves the request. Mixing or glyph-check failures do not replace prior successful films. Public bundled assets can be committed with Git; private footage, caches, keys, and uploaded custom assets are excluded.

```sh
uv run vlogii run my-day --music auto --font noto-sans
uv run vlogii edit my-day --music holizna-dreams --music-volume 0.2 --font caveat
uv run vlogii edit my-day --music none
```

Style versions save the actual music hash in the style request and record fonts, loudness and beats in render verification. Music files remain with project versions.

The existing local override remains available via `VLOGII_FONT`; explicit font presets take precedence over that override.

## Checks and Next Steps

All six tracks passed complete decoding. English samples passed for all six fonts, and Chinese samples passed for four. [Regression tests](../tests/test_presets.py) cover duration, short-track looping, fades, speech ducking, font fallback, allowlisted resource endpoints/HTTP 206, changing/removing tracks, undo, failure recovery, request setting persistence, and segment cache reuse. The merged suite passes 124 tests, including CLI preset/upload compatibility, Chinese style font fallback and style track/volume changes with old-film protection. Private logs are in `local-evidence/presets-20261010/`. Automated checks do not replace user listening for music suitability and speech intelligibility.

Future work includes project-local TTF/OTF uploads, a music upload control for ordinary modes, separate title/subtitle fonts and more music genres. A (Yang Kang) owns assets, rendering, mixing, storage, and APIs; B (the teammate) maintains selection/preview pages. The corresponding controls are synchronized in this round.

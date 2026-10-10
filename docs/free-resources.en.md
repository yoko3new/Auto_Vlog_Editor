# Font and BGM Free Resource Candidates

[中文](free-resources.md) · **English**

[Back to Overview](../README.en.md) · [This Round of Fixes](mvp-fixes.en.md) · [Candidate Files and Checksums](../resources/candidates.json)

Researched and pre-downloaded on 2026-10-10. Currently, candidate resources, licensing sources, and basic file validations are completed. Custom music upload, mixing and beat-locked cuts now ship with [style films](style-templates.en.md); a bundled library and resource selection are not implemented, and the candidates’ style effect, BPM and beat behaviour are pending auditioning/measurement. This round does not modify the existing API contract.

## Resources Recommended to be Built-in First

| Resource | Suggested Use | License and Basis | Local Check |
| --- | --- | --- | --- |
| Noto Sans CJK SC Regular | Chinese-English subtitles and default titles; use a stable font set first to reduce missing glyphs | [Official Font](https://github.com/notofonts/noto-cjk/blob/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf), SIL OFL 1.1 | Approx. 16.4 MB; Pillow successfully read it, contains Chinese and English glyphs; SHA-256 recorded |
| Noto Serif CJK SC Regular | Subsequent book page/magazine-style titles, as an optional preset | [Official Font](https://github.com/notofonts/noto-cjk/blob/main/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Regular.otf), SIL OFL 1.1 | Approx. 24.5 MB; Pillow successfully read Chinese and English; SHA-256 recorded |
| Dreams — Holizna | Light music candidate, 306.636 seconds | [Author release collection](https://opengameart.org/content/chillout-instrumentals-collection) marked as CC0 | MP3, 48 kHz, dual-channel, full decoding passed |
| Day Jobs — Holizna | Daily vlog candidate, 138.540 seconds | Same author collection, CC0 | MP3, 48 kHz, dual-channel, full decoding passed |
| Dancing — Holizna | Rhythmic candidate, 135.708 seconds; actual beat to be measured | Same author collection, CC0 | MP3, 48 kHz, dual-channel, full decoding passed |

Suggested uses are preliminary selections pending auditioning; tempo or beat cannot be determined solely by song titles. The collection contains six tracks in total, each available in MP3/OGG formats; extract the above three MP3s first to avoid introducing a large number of presets immediately.

OFL permits fonts to be bundled, embedded, and distributed with software, requiring copyright and license files to be retained; fonts cannot be sold individually, and font modifications must comply with Reserved Font Name requirements. [Noto Sans License](https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE), [Noto Serif License](https://github.com/notofonts/noto-cjk/blob/main/Serif/LICENSE). Original licenses have been saved in [Sans OFL](../resources/licenses/NotoSans-OFL.txt) and [Serif OFL](../resources/licenses/NotoSerif-OFL.txt).

The author marked the music collection as CC0; [CC0 official description](https://creativecommons.org/publicdomain/zero/1.0/) allows copying, adapting, distributing, and commercial use. Retain author, work title, source, license verification date, and downloaded file hashes to facilitate future audits. Platform Content ID has not been tested; do not treat license labels as platform automated review results.

## How to Use Other Resource Libraries

- [Kenney Music Jingles](https://kenney.nl/assets/music-jingles): Marked as CC0 by the author, 85 short music clips, more suitable for intros/outros, not yet downloaded, cannot be used as long BGMs.
- Google Fonts / Noto Official Repository: Prioritize fetching published font files and licenses in the same directory; the current static Regular fonts can be used directly by FFmpeg/Pillow without global installation.
- [Pixabay](https://pixabay.com/service/license-summary/) allows free use and adaptation, but restricts standalone distribution of raw assets. It can be evaluated for single finished video usage; do not publicly distribute downloaded raw music as a default resource pack for now.

## Next Design Steps for Default Resources and User Uploads

Initial generation does not require users to enter font names or upload music. Fonts default to built-in sans-serif; BGM adopts four modes: "Auto-select / Do not add / Specify built-in track / Upload own". Auto-select only picks tracks from a limited library that has undergone auditioning, license registration, and preprocessing; BGM is automatically ducked during voiceovers. Keep "Do not add" for finished videos using purely original audio.

Fonts provide "Default / Preset / Upload font", supporting TTF/OTF first, and then confirming TTC font indices based on the renderer. Music supports MP3/WAV/OGG first, probing audio tracks, duration, sample rate, and verifying decodability upon import; the server retains a copy, not relying on the user to keep the original file afterward. Uploaded fonts check Chinese and English glyphs first; when incomplete, fallback to built-in fonts and provide an explanation.

Resources are associated with projects and successful versions via `asset_id`, without exposing local file paths to the browser or AI. Generation records save the actual used resource IDs, hashes, volumes, and selected segments; font or music changes only invalidate the relevant rendering cache, reusing unchanged material comprehension and transcription. User-uploaded resources are saved only in that project and do not automatically become part of the global default library; UI prompts users to only upload files they have the rights to use.

A (Yang Kang) is responsible for resource registration, storage/versioning, font rendering, mixing, and beats; B (Teammate) is responsible for selection, auditioning, uploading, and failure feedback. When implementing, uniformly modify models, OpenAPI, callers, and relevant tests, then verify voiceover intelligibility, subtitles without missing glyphs, BGMs of different lengths, Retry, and undo.

## Scope of Downloads and Deliverables

Full downloads are located in the ignored `local-evidence/free-resources-2026-10-10/`: two fonts, original licenses, a 79.6 MB collection ZIP, snapshots of author/CC0 pages, three selected MP3s, full decoding logs, and download hashes. Candidate metadata and font licenses can be committed; binary resources have not yet been placed into the application release package and need to be integrated according to the determined default library and packaging method.

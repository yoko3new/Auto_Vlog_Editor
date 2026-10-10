# Reference Reel Styles: Music Mixing and Beat-Locked Cuts

[中文](style-templates.md) · **English**

[Back to the overview](../README.en.md)

When to read: to see what the three styles learned from their reference reels, how cuts are locked to the beat and how music is mixed, or before learning a new reference.

**Status:** integrated into the Vlogii web app on `codex/integrate-feng-ui`: pick a style and music in *No. 2*, or use `vlogii run --style` on the command line. Verified on synthetic media, two real music tracks and a real HTTP flow (see the [validation record](#evidence)); not yet reviewed on real user footage with live Gemini. The team `contracts/` are unchanged; Vlogii uses its own `/api/vlogii` interface. The scope decision is in the [decision log](decisions.en.md).

## What the three reference reels taught

| Template | Reference | Pacing (measured) | Sound (measured) | Picture and text |
| --- | --- | --- | --- | --- |
| `ig_cozy_night_study` | [DNvYfcx5EBk](https://www.instagram.com/reel/DNvYfcx5EBk/), 15.3 s | 24 shots, median 0.67 s, even throughout, no fast opening | Music only, −14.0 LUFS, LRA 1.7, true peak −1.2 dBTP, no fades, no voice | Warm desk lamp (warmth 0.22, saturation 0.46); three-tier title “cozy night / study / with me” with a typed kicker; small activity labels |
| `ig_city_day_in_life` | [DYui5l2x141](https://www.instagram.com/reel/DYui5l2x141/), 37.9 s | 13 shots in the first 3.77 s (median 0.30 s), then median 0.70 s | Music only, −15.6 LUFS, true peak +3.0 dBTP (clipped), no voice | Natural daylight (saturation 0.30); white bold “day in my life”, time range and location tag; digital clock with a small caption in the body |
| `ig_narrated_college_day` | [DWxtN9tCoc2](https://www.instagram.com/reel/DWxtN9tCoc2/), 64.9 s | 21 shots in the first 2.87 s (median 0.13 s), body median 0.67 s with a wide range, 3.55 s black end card | Voice in 99% of the runtime with word-by-word captions, so narrated; −14.1 LUFS, 0.6 s fade out | Overcast cool grade (warmth 0.06); heavy crimson title with white stars; mid-height digital clock and captions at 62% height |

Measurements come from `style/references/*.profile.json`; the picture and text column comes from reviewing frames. Each `reference.learned` entry in a template says whether it was measured or observed.

### Key finding: the references are not beat-locked

In all three reels the cuts meet the music's beats at about chance level (beat hit rate 0.13/0.31/0.29 against chance 0.29/0.25/0.27). A second test that does not depend on tempo estimation, comparing onset strength near the cuts with random positions, is not significant for any of them. Their rhythm comes from **steady shot lengths**, not from cutting on the beat; the music may have been added inside Instagram, which is only a guess.

So a template learns **shot lengths in seconds and the section structure**, and applying it snaps every cut onto **your own music's** beat grid: the reference's pacing, cut truly on the beat. Previews made with two real music tracks put 100% of the cuts on half-beats, and their onset test is significant (the references' is not).

## How it works

```text
参考 reel ─ tools/style_lab/analyze_reference.py → profile.json（只有测量值）＋ 人工看帧
                                                 → src/vlogii/style/templates/<id>.json（模板）
网页/CLI：素材 + 音乐 + 风格 ─ Gemini 选片段、标签、标题（无 key 时按导入顺序）
         ─ style/planner.py → style-plan.json（每一刀的帧位置、调色、文字、混音参数）
         ─ style/render.py → film.mp4（Vlogii 的一个新版本，可撤销、可下载）
```

The diagram reads: a reference reel is measured into a profile and, with a review of its frames, written up as a template; in the app, footage, music and a style go through Gemini's choice of moments, labels and title (import order without a key), then the planner fixes every cut and the renderer exports a normal Vlogii version that can be undone and downloaded. The project rule holds: AI only chooses moments, order, labels and title text; code computes beats, frame positions and the mix; the renderer only executes the plan.

Steps in `style/planner.py`:

1. Detect the music's beats, correct the tracker's roughly 30 ms latency and smooth its jitter; estimate the downbeat and warn when it is uncertain.
2. Choose the start from the template: `first_downbeat` starts on the first downbeat, `most_energetic` picks the loudest stretch. The total length is rounded to whole bars, the opening and end card to two beats.
3. For each section, pick beat multiples (such as 0.5/1/1.5/2 beats) close to the reference's shot seconds so that the section is filled exactly; then share the shots among the moments in proportion to their length, in order, spreading several shots across one moment. The opening takes previews from late in each moment, as the references reuse moments of the day.
4. Move each clip part of the way toward the reference's measured brightness, saturation and warmth, by the template's correction strength.
5. Clocks only come from a QuickTime capture time with a time zone or a clock written in a manifest; without a reliable time no clock is shown, never an invented one.

With too little footage the film is shortened, and below the template's minimum it fails instead of repeating frames; too short music is handled the same way.

## Template fields

The structure is in [style_template.schema.json](../src/vlogii/style/templates/style_template.schema.json); the validator `src/vlogii/style/templates.py` uses only the standard library, and `tests/test_style.py` checks every template and invalid variants. Every field is implemented by the planner and renderer, so there is no valid setting that cannot be drawn.

| Field | Purpose |
| --- | --- |
| `sections` | `hook` (optional) and `body`: length, shot-length range, variation, allowed beat multiples |
| `duration`, `end_card` | Target, shortest and longest length; black end card and its text |
| `music` | Start policy, fades, target loudness, true-peak ceiling |
| `source_audio`, `voiceover` | Clip sound is always muted; voice loudness and music ducking for the narrated style |
| `grade` | The reference's measured brightness, saturation and warmth, and correction strength |
| `text` | Text roles (font candidates, size, colour, shadow, box), title lines and decorations, clock or label stamps, voiceover captions |

## Mixing rules

- Clip sound is muted, as in all three references.
- Overall loudness is −14 LUFS with true peak at most −1 dBTP. The renderer limits, measures again after AAC encoding and re-encodes with a lower ceiling if needed, so the final MP4 meets the target.
- Narrated style: voice at −14 LUFS, music 12 dB lower while someone speaks (80 ms attack, 300 ms release). The references' music level under the voice could not be separated, so −12 dB is a common default, not a measurement.
- Fades follow the reference (0 or 0.6 s), plus a 30 ms de-click.

## How to use

Font presets and volume can also be changed. At 100% volume the template loudness is preserved; Chinese falls back to bundled Noto Sans.

Web app: import portrait footage, choose a style and bundled or uploaded music in *No. 2*, and generate. Style films accept title, warmth and clip changes and re-cut them on the beat; speed and time-range edits are not available. Steps and troubleshooting are in [Mac setup](vlogii-mac-setup.en.md).

Command line:

```sh
uv run vlogii --language zh styles
uv run vlogii --language zh music my-day ~/Music/song.mp3
uv run vlogii --language zh run my-day --style ig_city_day_in_life
uv run vlogii --language zh style-preview ig_cozy_night_study --music song.mp3 --manifest work/me/manifest.json --out work/me/preview.mp4
```

The manifest format is described at the top of `src/vlogii/style/planner.py`; `--clips` takes a folder instead, ordered by capture time and without labels. The narrated style also accepts `--voiceover` and `--transcript`, the latter in the contracts' `transcript.json` format; the web app does not upload voiceovers yet.

To learn a new reference: run `uv sync --extra dev --extra style-lab`, download it with `yt-dlp` into `work/references/`, then analyse it with `uv run python tools/style_lab/analyze_reference.py` (arguments: the video, `--url` and `--out-dir`). Review `contact_sheet.jpg`, write the template JSON and copy the measurements to `style/references/`. The full self-test is `uv run python tools/style_lab/selftest.py --work work/style_lab/selftest`.

## Media and licences

- References are downloaded only into the Git-ignored `work/`, never committed and never used in films. The repository keeps measurements and public links only; templates copy no music, footage or fonts from the references.
- Film text uses bundled OFL fonts: Poppins, DM Serif Display and Share Tech Mono, with their licences in `src/vlogii/style/fonts/`. Output looks the same on macOS and Linux; the fonts actually used are recorded in each version's `verification.json`.
- Music you upload must be cleared for publishing; record its licence as described in [Preparation and demo](demo.en.md).

<a id="evidence"></a>

## Validation record

2026-10-10, Linux container, FFmpeg 6.1.1, Python 3.13, librosa 1.0.0.

| Check | Result |
| --- | --- |
| Beat detection (synthetic 100 BPM drums, known truth) | Recall 0.994, precision 1.0, 99.83 BPM, mean error about −3 ms |
| Full self-test, all three templates end to end | All passed; largest planned-cut offset from the true beat 2/2/18.7 ms; rendered cuts match the plan and every clip change is detected; the clips' test tone is absent; loudness −14.3/−14.1/−14.1 LUFS, true peak −1.5 to −1.8 dBTP; the narrated style ducks music 11.6 dB under the voice and makes 12 captions |
| Real music (two reference soundtracks, local only) | 100% of cuts on half-beats, onset test significant; −14.1 LUFS, true peak −1.3/−1.5 dBTP |
| Application tests | All 21 new style tests pass: templates and invalid variants, a known beat grid, sections filled exactly, shots kept within their moments, AI output validation, the AI choice saved and reused on retry, API checks and a real film (on half-beats, −14 LUFS ±1, true peak ≤ −1 dBTP, re-cut after title/clip/warmth edits, speed edit rejected, undo) |
| Real HTTP flow (no Gemini key) | 14 clips and one MP3 uploaded; the city style made a 38.4 s 1080×1920 H.264/AAC film at −14.1 LUFS and 99 BPM; a title and clip edit made version 2; download as an attachment; undo returned to version 1 |
| Web page and text | Browser screenshots of the style and music controls and the film caption; frame checks of titles, typing effect, labels, clock, captions, stars and end card |

The synthetic clips are solid colours, so jump cuts inside one clip are invisible and only cuts between clips are counted.

Not verified: the look on real user footage, live Gemini style selection, real voiceover and transcription, HEVC/HDR footage, timing on large 1080p projects, macOS hardware with Safari, Replit, and grading beyond synthetic media.

## Relation to team contracts and next steps

Styles use Vlogii's `/api/vlogii` interface (`GET /styles`, `POST /projects/{name}/music` and `style_id` on `generate`) and do not change the team `contracts/`, so there is no compatibility impact. If they move to the team contracts later, `config.settings.style_id` would name the template and the frame positions in `style-plan.json` compile directly into `timeline.json`, which needs `portrait_v1`, plus `audio_envelopes_v1` and `subtitles_v1` for the narrated style.

Suggested next step: make one film in each style with your own 10–15 clips, a licensed song and a Gemini key, then say where it does not feel like the reference.

# Use Vlogii on a Mac

[中文](vlogii-mac-setup.md) · **English**

[Overview](../README.en.md) · [Usage guide](vlogii-guide.md)

This tutorial installs integration branch `codex/integrate-feng-ui` in Terminal and runs the local editor in Safari.

## 1. Install prerequisites

```sh
# Install developer tools if needed.
xcode-select --install
# Install Homebrew if needed.
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install ffmpeg-full uv node
```

Node.js 20+ is required; check with `node -v`. uv prepares Python 3.11+. Full FFmpeg provides captions, color conversion and encoding; the application automatically prefers the full Homebrew installation.

## 2. Download and build

```sh
cd ~/Desktop
git clone --branch codex/integrate-feng-ui https://github.com/yoko3new/Auto_Vlog_Editor.git vlogii
cd vlogii
uv sync --frozen --extra dev
cp .env.example .env
npm --prefix frontend ci
npm --prefix frontend run build
```

An existing checkout can be reused: switch to the integration branch and update, preserving any local work first. Private repositories require GitHub access.

## 3. Configure Gemini

Get a key from [Google AI Studio](https://aistudio.google.com/apikey), open the configuration with `open -e .env`, and save it. Replace the placeholder with your local key:

```text
GEMINI_API_KEY=YOUR_LOCAL_KEY
VLOGII_MODEL=gemini-3.8-flash
VLOGII_SPEECH_MODEL=gemini-3.5-transcribe
```

Visual/planning and speech models are configured separately and share a key; use compatible models your account can access if necessary. `.env` is ignored by Git; never commit keys. Restart the server after configuration changes. Without a key, you can browse the editor, play and edit existing successful films, and make style films in import order (step 6); new footage analysis, transcription and AI selection need a key. See the [guide](vlogii-guide.md) for the handwritten-plan CLI path.

## 4. Start the server

```sh
uv run vlogii doctor
uv run vlogii serve
```

Open **http://127.0.0.1:8000** and keep Terminal running; press `Ctrl+C` to stop. Next time, enter the project directory and run `uv run vlogii serve`. If the port is occupied, use `uv run vlogii serve --port 8010` and open http://127.0.0.1:8010. The server listens locally; run one process.

## 5. Make a film

1. Switch Chinese/English in the masthead. Name a project in the moments chapter using Chinese/English letters, digits, underscores and hyphens, starting with a letter or digit; for example `my-sunday`. Drop or choose MP4/MOV/M4V/MKV files, select an orientation and import.
2. Choose AI auto, opening highlights, keep most or keep all in the direction chapter. A description is optional; clicking an example fills it and selects the matching mode, then you confirm submission.
3. Auto/highlights accept an approximate target of 1–1800 seconds; retention modes have no duration target. Highlights default to at most 0.5 seconds per shot, 1x and muted audio, exporting separately; automatic body assembly is pending. Cadence and speed are selectable.
4. Progress is shown during generation. After a failure, click Retry to reuse the request and caches without re-importing. Previous successful films stay playable.
5. Click the round Play control, then download MP4. Default SDR/H.264 offers broad compatibility; HLG-preserving HEVC playback depends on the device.
6. The edit chapter supports titles, warmth, clip exclusions, whole-film speed and current-film time-range deletion/speed. Review example timestamps before applying. Undo restores the previous successful version.

Time edits use the current film as their coordinate system; see [editing rules](editing-modes.en.md) for constraints. Check captions manually before publishing.

## 6. Style films: music mixing and beat-locked cuts

A style is a template learned from an Instagram reference reel: pacing, opening montage, grade, title and clock layout, and mix rules. All three styles are portrait, so import as portrait.

1. In the direction chapter, pick a reference style: cozy night study (about 15 seconds), city day in my life (fast opening, about 38 seconds) or narrated college day (strobe opening and black end card, about 60 seconds). Mode, target and speed controls are then hidden because the style decides them.
2. Click Choose music and pick a song you have the rights to use (MP3, M4A, AAC, WAV, FLAC or OGG, 10 seconds to 15 minutes). It is uploaded when you generate.
3. Every cut lands on the music's beat, the music is mixed to −14 LUFS and clip sound is muted. With a key, AI picks moments, labels and title; without one, every clip is used in import order with the style's default title, as the caption under the film says.
4. Style films accept title, warmth and clip changes and re-cut them on the beat; speed and time-range edits are not available. Undo and download work as usual.

The first music analysis takes about ten extra seconds. Clocks only use iPhone capture times with a time zone; without a reliable time no clock is shown. `uv run vlogii doctor` should report libass as available; if it is missing, reinstall `ffmpeg-full`. How the styles were learned and measured is in [style templates](style-templates.en.md).

## 7. Update and local data

Stop the server first, then run:

```sh
cd ~/Desktop/vlogii
git pull --ff-only
uv sync --frozen --extra dev
npm --prefix frontend ci
npm --prefix frontend run build
uv run vlogii serve
```

Footage, music, caches, plans and films are stored in `projects/` and excluded from Git. Analysis sends visual proxies and original audio to Google Gemini; originals and exports remain local. Web fonts are bundled and need no remote font requests. If Safari shows old styling, press Option+Command+R to refresh its cache.

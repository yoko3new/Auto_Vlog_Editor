# Product and Delivery Scope

[中文](product.md) · **English**

[Return to Project Overview](../README.en.md)

When to read: Read this when referring to the original competition positioning, MVP/V2/V3 boundaries, or requirements changes. The current local web MVP for Vlogii in `kang` has an independent implementation scope, see [Coverage and Gaps](mvp-coverage.en.md); this page contains competition targets, not a completion checklist. Current capabilities such as original audio subtitles, vertical video, and larger input limits do not automatically change the competition scope. For division of responsibilities, see [Collaboration Handbook](collaboration.en.md).

## Current Product Direction (2026-10-10)

The user decided to focus Vlogii on lifestyle Shorts: a cover with stickers or artistic text → several shots flashing past quickly → body content featuring basic subtitles, a few short words/time stamps, and light special effects. Full compositions are the next batch of design directions; the current standalone quick cut and subtitles cannot be considered as completion of the full style suite. See [Structure and Implementation Boundaries](shorts-direction.en.md) for details. Existing retention ratios, optional durations, and playback speeds remain available, without enforcing a fixed 30-second duration.

The phased plan and acceptance criteria of the original competition are preserved below, where descriptions like "only generates a 30-second opening, no voiceover needed, landscape mode" reflect the historical competition scope; the current product's default direction is governed by the user decision above, and formal competition acceptance has not yet been reformulated or finalized.

<a id="s1"></a>

## Product Positioning: Exactly Whose Problems Are We Solving, and How

<a id="s1-1"></a>

### First Cohort of Users

First serve university students, international students, and daily life vloggers who like magazine-style and journal-style life journaling, already have shooting habits, but are unwilling to spend time learning video editing. Validate this group first before considering expanding to "everyone".

A typical user scenario: Their phones contain fragments of breakfast, commutes, classes, cafes, and evenings, but they have never organized them into a video.

<a id="s1-2"></a>

### Product Promises

- Automatically select representative moments, reduce duplicate shots, and organize clips suitable for a fast opening montage based on activities and identifiable information.
- Unify typography, color grading, and pacing using human-designed styles.
- Keep the default result as close to publish-ready status as possible.
- MVP users can say "delete the segment with the dog", "change title to Slow Sunday", or "make it warmer", seeing changes and an undo entry point; shortening to a specified duration is deferred to V2.

"Having good taste" covers both attractive titles and appropriately selected shots, sensible sequencing, and ensuring key moments are not lost. Development time must be invested into both visual design and content organization.

<a id="s1-3"></a>

### Relationship with Existing Products

CapCut already provides automatic footage merging, music synchronization, and stylized effects. Therefore, the pitch will no longer use claims like "CapCut only provides tools and templates". [Official Introduction](https://www.capcut.com/resource/capcut-autocut)

What this project needs to prove is: **For this category of lifestyle footage, we can automatically organize more suitable content and allow users to effortlessly express specific revisions.** This is an advantage waiting to be validated; it cannot be proven solely by architecture diagrams or parameter counts.

<a id="s1-4"></a>

### Measuring Value

Prioritize recording three questions: Is the user willing to publish, how many revisions are needed, and why are they dissatisfied. After the competition, using the identical footage, compare the outputs of this project, chronological concatenation, and CapCut AutoCut, having target users perform a blind test.

The proportion of "published without modifications" can serve as a long-term metric; during the competition phase, feedback on "willing to publish without modifications" can be logged first, while distinguishing editing issues, footage issues, and reasons why users are reluctant to share publicly.

<a id="s1-5"></a>

### Adjustments for Adobe Creative Track

The key phrasing in the screenshot is "make something people feel", explicitly including design tools. This project can compete as a creative tool that helps ordinary people express their feelings about life.

Below are presentation suggestions formulated based on the track description, not official scoring criteria published by the organizers:

| Presentation Focus | How the Project Reflects It | Evidence Provided on Site |
| --- | --- | --- |
| Emotional Feeling | Music, shot dwell time, color grading, and titles collectively express the atmosphere of a slice of life | Play a short video with a complete intro and outro |
| Creative Participation | The user decides what to keep and how they wish to express it | Make revisions with one sentence and display the result |
| Personal Expression | Clip selection and narrative originate from the user's own footage | Showcase the transition from raw footage to finished video, preserving meaningful moments |
| Design Quality | Typographic hierarchy, framing, pacing, and UI establish a cohesive style | Use real finished video covers and large previews |

After passing MVP acceptance, V2 will prioritize adding "two emotional expressions for the same footage", prioritized higher than V3's additional export aspect ratios. The identical layout and rendering code can be reused, changing only a few already implemented color grading, music, and pacing parameters; there is no need to develop a brand new style engine.

Do not equate "warm tones" directly with "having emotion". A genuine smile, a line of original audio, or a breathing pause can all be more impactful than adding stickers. During testing, beyond asking if they are willing to publish, also ask: "Does this video express the day you wanted to remember?"

The screenshot does not state that calling Adobe APIs is mandatory, nor does it provide scoring weights or eligibility details. Whether Adobe product integration is required should be determined by the full track rules; the current technical solution does not add this prerequisite on its own.

<a id="s2"></a>

## Phased Delivery: MVP Must Deliver, V2 Enhances Expression, V3 Expands Capabilities

<a id="s2-1"></a>

### Phase Overview and Entry Criteria

| Phase | Objective | Belongs to 36-Hour Must-Deliver | Entry Criteria |
| --- | --- | --- | --- |
| MVP | A set of lifestyle clips can truly turn into a piece of work and be revised with one sentence | Yes; completing this phase alone is sufficient for Demo | Start here, complete all core capabilities first |
| V2 | Enhance emotional expression and editing value | No; add items in table sequence if capacity allows | MVP passes full acceptance on Replit, and stable version is preserved |
| V3 | Expand publishing scenarios, styles, and creation methods | No; primarily for post-competition | Advance in order after V2 is complete and stable |

**Features in V2 and V3 must not become implicit dependencies for MVP.** For instance, even without a speech service key, it must still be possible to generate MVP videos. Subtitle, transition, and other designs preserved later in the text are all labeled by phase; if conflicts arise, this section's delivery scope prevails.

<a id="s2-2"></a>

### MVP: Must Finish in Competition, Can Run Demo Independently

Target: **Upload campus daily life footage → Automatically generate ~30-second magazine-style opening quick cut → Revise with one sentence → Undo → Download.**

The reference point is the opening quick-cut montage of campus vlogs; the longer segments that follow only serve as daily life context, and the MVP is not required to produce a full-length vlog. Footage selection acceptance evaluates representative moments, redundancy, and music rhythm, without requiring the entire day's progression to be narrated within 30 seconds.

| Required Capability | Explicit Boundaries | Acceptance Result |
| --- | --- | --- |
| Upload & Footage Display | Save original files, read duration and orientation, generate thumbnails; prioritize verified 1080p SDR footage first | Uploaded footage is visible; invalid files display prompts |
| AI Understanding, Selection & Ordering | One primary AI provider; keyframe description, redundancy reduction, activity sequence, short titles | Genuinely uses uploaded footage to generate plan, and can also produce videos on a second footage set |
| One Fixed Magazine Style | `magazine_scrapbook` Base Edition: fixed title typography, subtle warm grading, minimal fixed decorations; no chapter animations | Exported video inherently possesses a unified style, page cover comes from actual finished video |
| BGM & Basic Beat Editing | One fixed track with pre-marked beats; hard cuts, reasonable cut points prioritize landing on beats; raw footage audio muted | Audio is audible, video is coherent, no ASR, subtitles, or dubbing services required |
| Fixed Output | First generation targets 30 seconds, 720p, 30 fps, 16:9, MP4 | Browser can play and download; initial target 30±1 seconds; natural shortening allowed after pure deletion, see [JSON Data Contract: MVP Usable, V2/V3 Extensible](reference/timeline.en.md#s6) |
| Three Types of Natural Language Revisions | Change title, adjust warmth, delete specified footage; no promise of arbitrary editing instructions | Revisions take effect in practice with accurate summaries shown; unsupported requests show clear prompts |
| Versioning & Undo | Keep one version per successful edit; undo reverts to previous successful version | Failure does not overwrite old finished video, undo does not call AI or trigger re-rendering |
| Complete Single-Page Interaction | Upload, fixed style preview, large player, real processing stages, revision box, undo, download | No fake progress on page, no unimplemented options |
| Replit Online Demo | Single instance, serial tasks; persistently save necessary files and JSON | Official link can process, play, and download; can read existing successful versions after restart |

The MVP does not run speech transcription, does not retain talking head audio, and does not do subtitles or music ducking. User footage can contain human voices, but the page clearly clarifies that only visuals and BGM are used in this phase.

**MVP Release Checklist:**

- Complete end-to-end flow verified for a set of real footage from upload to generation, playback, and download.
- Changing title, adjusting warmth, and deleting footage each succeed once without unintended modifications to other content.
- When a revision fails, the previous version can still be played; after undo, edits can continue without overwriting history versions.
- Re-test using a second set of footage; existing successful versions can be found and played after page refresh and service restart.
- Rehearse in the official Replit environment, keeping clearly labeled fallback finished videos and demo screen recordings.

If any item above fails, keep fixing the MVP; do not proceed to V2.

<a id="s2-3"></a>

### V2: Sequentially Add Creative Expression and Editing Value

Add only one item at a time; connect, verify acceptance, and retain a stable version before starting the next item. During the competition, finishing only up to V2-1 is acceptable; completing the entire phase is not required.

| Order | Feature | Why Placed Here | Minimum Implementation and Acceptance |
| --- | --- | --- | --- |
| V2-1 | Second emotional expression for same footage | Most direct demonstration for Adobe Creative, reuses existing title and grading capabilities | Provide two sets of fixed emotion parameters on the same layout, paired with two pre-selected tracks and different shot pacing; recalculate beats, differences can be felt in actual playback |
| V2-2 | Shorten to specified duration | Complements common editing needs, demonstrates user control over content | Demonstrate "shorten to 20 seconds" on a 30-second video; only open 20/30 seconds at first, do not expand to 60 seconds; maintain exclusion constraints and valid footage range |
| V2-3 | Short voiceover segment, subtitles, and BGM ducking | Preserving personal voice has value, but introduces transcription and audio-video synchronization work | Integrate only one ASR, support one clear short voiceover segment, preserve complete sentences, align subtitles, smoothly duck music; open only when all three pass acceptance together |

V2-1 is a combination of a small number of existing parameters and does not build a second complex typography engine. V2-3 is an integrated feature package: connecting only the transcription API without subtitles or audio mixing implemented properly does not count as complete. Gemini / ElevenLabs are selected only when they actually address requirements.

<a id="s2-4"></a>

### V3: Sequentially Expand Publishing and Creative Capabilities

| Order | Feature | Added Value and Boundaries |
| --- | --- | --- |
| V3-1 | 9:16 Vertical Video Export | Adapt for mobile viewing and sharing; re-handle framing and text layout, cannot merely stretch horizontal video |
| V3-2 | 60-Second Output and Larger Footage Sets | Support a more complete day; re-verify story structure, processing duration, and resource limits |
| V3-3 | Second Complete Style and Limited Animations | Add `clean_magazine`, chapter tags, simple title animations, and one dissolve; verify item by item, avoid adding all effects at once |
| V3-4 | Auto Cutout Stickers, Optional Single Narration Line | Prioritize personalized decorations, then consider a single narration line with user-confirmed text; must not disrupt primary content and authentic original audio |
| V3-5 | One-Sentence Start, Reference Image-Assisted Style Matching | Select combinations within mature presets and parameter ranges; no guarantee of perfectly replicating arbitrary reference images |

User accounts, multi-user collaboration, mobile apps, complex drag-and-drop timelines, filler-word removal in long voiceovers, and large-scale production deployments still do not enter these three phases. Increasing the count of services or sponsors does not itself constitute a feature goal.

<a id="s2-5"></a>

### Input Boundaries and Speed Targets

The MVP first validates using 10–15 clips with a total duration not exceeding 3 minutes of verified footage, targeting a 30-second output; three short shots are used only during early integration testing. Footage must have sufficient usable intervals, without relying on extensive duplication to pad duration. Larger-scale testing with 15–30 clips and 60-second output belongs to V3-2.

The MVP first validates 1080p SDR, mixed horizontal/vertical, and rotation metadata; HEVC and HDR are claimed as supported only after separate verification. The MVP displays footage completely by default, filling blank areas with a background; when footage is insufficient, fail explicitly without duplicating to pad duration, see [JSON Data Contract: MVP Usable, V2/V3 Extensible](reference/timeline.en.md#s6) for details. Upload size limits and actual visual quality of sample clips still need to be determined in the runtime environment.

"Producing video in 90 seconds" is an optimization challenge, **not an MVP release gate**. The measurement window spans from upload completion to finished video playability; upload and cold-start times are recorded separately. Cached results must not be passed off as initial generation speed. Achieve stability, acceptable visual quality, and correct revisions first before optimizing.

Phase scopes and the JSON data contract have been documented in [Phased Delivery: MVP Must Deliver, V2 Enhances Expression, V3 Expands Capabilities](product.en.md#s2) and [JSON Data Contract: MVP Usable, V2/V3 Extensible](reference/timeline.en.md#s6) respectively; data states for ambiguous choices have also been defined. These are original competition designs; Vlogii uses an independent model and has not adapted them fully. Deployment verification, competition duration/style, and other gaps are implemented item by item against the feature comparison.

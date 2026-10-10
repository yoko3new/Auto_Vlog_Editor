# Pre-Competition Preparation and Live Demo

[中文](demo.md) · **English**

[Return to Project Overview](../README.en.md)

When to read: Read when preparing assets, licensing, screen recordings, and competition submissions; not a mandatory document for every development task.

<a id="s16"></a>

## Pre-Competition Preparation

First confirm the competition rules regarding existing code and pre-made assets, and prepare according to the rules. The following is a recommended checklist and does not indicate completion.

- [ ] Confirm the 36-hour schedule, live presentation duration, and code and asset rules.
- [ ] MVP primary footage of 10–15 clips, plus a backup set of footage with different content; both within input boundaries.
- [ ] Select 10 clips from the primary footage as an AI footage curation test set, and prepare manual annotations for [AI Footage Understanding and Curation Testing: Initial Test at Hours 6–7, Final Video Verification Before Hour 14](ai-selection.en.md#s20-4); cover similar shots, brief actions, meaningful but poorly angled frames, and obvious accidental shots. Reserve backup footage for a second review set, not for the first round of parameter tuning.
- [ ] Add a clear short talking-head test clip only when preparing to enter V2-3.
- [ ] One licensed fixed BGM suitable for demonstration in the MVP, save licensing records, and mark beats; add a second track in V2-1.
- [ ] Download the 2–4 fonts actually used in advance, and save the corresponding license files.
- [ ] One color grading profile tested with real footage; use simple color grading first when a suitable LUT is not available.
- [ ] Prepare Replit account, available deployment resources, and budget; execute Stage A of [Kickoff Verification: Confirm Replit Works Before Integrating AI](deployment.en.md#s18-2) at the time permitted by competition rules, locking Node, Python, FFmpeg, and font versions.
- [ ] Place Stages B and C of [Kickoff Verification: Confirm Replit Works Before Integrating AI](deployment.en.md#s18-2) into the first 6 hours task list, and prepare to record actual results; parts not permitted before the competition should be completed after the competition starts.
- [ ] Schedule the first round of testing for [AI Footage Understanding and Curation Testing: Initial Test at Hours 6–7, Final Video Verification Before Hour 14](ai-selection.en.md#s20-4) for hours 6–7 after Replit verification; prepare one usable AI API in advance, backend key configuration methods, and call usage tracking, without listing models as selected before actual testing.
- [ ] Verify title layer, font, hard cut, and color grading for the MVP; verify subtitles and dissolves separately before their corresponding phases start.
- [ ] The selected primary AI API is available on the demo network, with timeout and limited retry configured.
- [ ] Adopt Gemini / ElevenLabs only when few-shot performance or integration convenience is appropriate; if cross-applying for awards, verify actual API usage and submission requirements again.
- [ ] Generate style cover images using the actual final video, and prepare initial UI examples.
- [ ] Prepare a small joint debugging sample consisting of a manual plan, final timeline, and three shots.
- [ ] Save a complete demo screen recording and backup MP4s for each step, clearly marking cached or pre-generated content.

<a id="s17"></a>

## Three-Minute Demo and Pitch

Opening can use: "Your camera roll remembers what happened. We help you express how it felt." Then prove this promise through the final video. Let the audience see and feel the difference first, then explain how it is achieved with brief descriptions.

| Duration | Content | Focus |
| --- | --- | --- |
| 0:00–0:20 | Show a screen of unedited life footage | "These are clips I took in a day, and I wanted to preserve how that day felt." |
| 0:20–0:40 | Upload, showcase fixed style, start generation | Let judges see how simple the operation is |
| 0:40–1:10 | Explain the story and feeling intended to express during processing | Combine a small amount of raw footage to explain why a certain moment was kept; show real stages |
| 1:10–1:35 | Play 15–25 seconds of the finished video | Leave full playback time for visuals and music, avoid talking continuously over the work |
| 1:35–2:15 | Single-sentence modification, showcase before-and-after comparison | MVP demonstrates changing titles or deleting clips, and undoing; show emotion switching only after V2-1 acceptance |
| 2:15–2:35 | Explain personal creative space | How users control their own stories; explain that style comes from human design and content adaptation comes from footage analysis |
| 2:35–2:50 | One architecture diagram and a set of measured numbers | AI planning, deterministic timeline, render execution, explaining timing criteria |
| 2:50–3:00 | Wrap-up | "Turn everyday clips into a film that feels like you." |

The live script must be rearranged based on actual measurements. If the initial generation takes close to 90 seconds, adding modification rendering will make it difficult to fit into three minutes; you can play a clearly marked pre-generated primary sample first, then demonstrate one modification live, or showcase the full generation process in a screen recording.

Do not write "Vertical" into the official script unless it has been implemented and verified on demo footage.

If V2-1 is completed and demonstrates two emotions, use the same raw footage and play comparable segments of about 8–10 seconds each. Let the audience see clearly how music, pacing, or framing change the expression; if the modification is only color, truthfully describe it as a color change. Prepare a set of genuinely differentiated results before deciding whether to highlight it as a major feature.

Potential Questions:

- **Difference from CapCut?** Existing tools can also edit automatically; this project focuses on content organization, controllable style, and single-sentence modifications for this type of life footage, verifying results through comparisons using identical footage.
- **Does everyone's output look the same?** Style provides a consistent visual language, while clip curation, activity sequencing, copy, and accent colors come from user footage; actual testing is still required to determine whether it is personalized enough.
- **What happens if AI makes an error?** Format validation, business checks, limited retries, and rule-based fallbacks; older versions are preserved, and users can undo.
- **Why is there no database?** The MVP is a single-instance controlled demo, managing records with project JSON and storing media in object storage; migrate when multi-user requirements arise.
- **Why does this belong in the Creative track?** It allows users to express the feelings they want to preserve using their own life footage; users can participate in content and style decisions, demonstrating real creative changes on the spot.

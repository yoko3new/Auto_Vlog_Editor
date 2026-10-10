# Model Selection and Footage Selection Evaluation

[中文](ai-selection.md) · **English**

[Back to Project Overview](../README.en.md)

When to read: Read during the original competition model selection or footage selection quality acceptance. Currently, Vlogii has integrated Gemini proxy video analysis, original language transcription, and plan generation; see [Guide](vlogii-guide.md) and [Existing Demo Verification](vlogii-validation.md). The keyframe plan and phase timeline below are the original planning; they do not indicate that AI is still not integrated, nor do they replace the footage selection quality evaluation. The AI/video module is handled by A (Yang Kang).

This round continues using Gemini, with visual/planning defaulting to `gemini-3.8-flash`, and standalone original audio transcription defaulting to `gemini-3.5-transcribe`. For the latest model rationale, thinking/sampling limits, and actual verification boundaries, see [Fixes and Model Selection](mvp-fixes.en.md); the new model single-asset real closed-loop has passed, there are still no manually labeled accuracy scores, and ElevenLabs integration has been cancelled per user request.

<a id="s20"></a>

## Comparison and Selection Method of Current Mature Solutions

The following is proposed based on official documentation consulted on 2026-10-09 and the constraints of this project. **No horizontal actual testing was run using your footage, so this is a suitability assessment, not a model performance leaderboard.** When used in the competition, lock the specific model IDs and dependency versions that have already been verified.

<a id="s20-1"></a>

### Overall Architecture: First Option Recommended

| Solution | Primary Value | Cost to This Project | Conclusion |
| --- | --- | --- | --- |
| React + FastAPI + FFmpeg | Customizable pages; continues using Python analysis libraries; clear control over editing and audio | Requires aligning HTTP interfaces; video animation must be implemented independently | Primary solution for this time |
| React + Remotion + Node Backend | Uses React components to describe video layout and animation, suitable for templated motion graphics | Adds video composition learning curve, browser rendering environment, and performance verification; existing Python analysis still needs to be connected | Consider when dynamic layout becomes a core differentiator |
| Gradio + Python + FFmpeg | Fast connection between pages and processing functions | Custom interactions and visual details need to accommodate components | Consider as an emergency workaround only if the interface itself is blocking; do not use to mask rendering issues |

Remotion's server-side `renderMedia()` can export compositions as videos, and the official interface includes browser runtime configurations. It is worth noting, but React web pages cannot be directly used as finished video templates; frame-by-frame animation, footage, and audio arrangements still need to be defined. If adopted in the future, a 10-second sample should first be run on the target machine and resources measured, rather than rewriting the entire renderer halfway through the competition. [Remotion Rendering Documentation](https://www.remotion.dev/docs/renderer/render-media)

MVP's FFmpeg only does hard cuts, static titles, color grading, and fixed BGM. Subtitles belong to V2-3, and cross-dissolves belong to V3-3. Use real cover images and precise typography to improve visual quality; complex sticker animations can be left for later.

<a id="s20-2"></a>

### AI Understanding and Orchestration: Comparison by Input Method

| Candidate | How This Project Can Use It | Must-Verify Parts |
| --- | --- | --- |
| Claude Image Capabilities + Structured Outputs | Keyframes with timestamps, transcriptions, and metadata → content descriptions, story plans, modification operations | Static frames may miss actions; inspect shot selection, repetition, and elapsed time |
| OpenAI Image Capabilities + Structured Outputs | Same set of keyframes and text inputs, maintaining consistent output contract | Image/schema support, quota, and response time of the specific model chosen |
| Gemini Video/Image Understanding + Structured Outputs | Can continue using keyframes, or test compressed video inputs to understand continuous events | File upload processing time, sampling frame drops, time boundaries, and stability |

Capability references: [Claude Vision](https://platform.claude.com/docs/en/build-with-claude/vision) and [Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs); [OpenAI Vision](https://developers.openai.com/api/docs/guides/images-vision) and [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs); [Gemini Video Understanding](https://ai.google.dev/gemini-api/docs/video-understanding) and [Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output).

The project does not yet have an integrated API, with no migration cost premise. First get one provider working that is already activated and has available quota on hand; then select at most one other for comparison. The mention of Claude in the original draft does not mean its editing aesthetics have been proven superior. When continuous action indeed affects footage selection, Gemini's native video input is worth testing; it also does not guarantee frame-accurate positioning.

Retaining three functions is enough: `analyze_clips()`, `make_edit_plan()`, `parse_edit_request()`. By default, completed by the same provider; do not stack multi-agents, LangChain, vector databases, or model routing systems just to show off architecture. The key is stable asset IDs, timestamps, and business validation.

What is discussed here is runtime AI orchestration for the application. Multiple coding assistants can be used during development, but personal tools and scheduling methods do not constitute runtime dependencies of the product.

<a id="s20-3"></a>

### V2-3 Voice Selection: Accurate Recognition and Subtitle Alignment Are Two Requirements

| Candidate | Applicable Scenarios | Notes for This Project |
| --- | --- | --- |
| OpenAI Whisper API (`whisper-1`) | Want cloud to return word or segment timestamps | Timestamp capabilities must be selected per interface; do not assume all newer transcription models return word-by-word timestamps |
| ElevenLabs Scribe | Want cloud transcription and provision of word-level timing information | Validate accuracy, boundaries, elapsed time, and cost using actual mixed Chinese-English spoken audio |
| faster-whisper | Already have a usable local environment, or wish not to depend on a transcription API | CPU speed and model size require actual testing; Replit environments do not have CUDA GPUs by default |

References: [OpenAI Timestamp Notes](https://developers.openai.com/api/docs/guides/speech-to-text#timestamps), [ElevenLabs Transcription Documentation](https://elevenlabs.io/docs/overview/capabilities/speech-to-text), [faster-whisper Repository](https://github.com/SYSTRAN/faster-whisper).

MVP skips this section and does not require voice service keys. After entering V2-3, first try cloud transcription on Replit to prevent transcription and rendering from competing for limited CPU; if the local solution is already stable and fast enough, keep it. Implement only one transcription adapter. Skip ASR for footage without spoken audio; if transcription fails, fall back to visuals only + BGM, with clear notifications.

ElevenLabs voiceover belongs to V3-4 and is not a required dependency for V2-3 transcription. MVP only has BGM, and V2-3 prioritizes retaining real short spoken audio; later, if voiceover is indeed beneficial, add a single sentence of voiceover with user-confirmed text, and place it on the timeline after measuring the actual audio duration.

<a id="s20-4"></a>

### AI Footage Understanding and Selection Testing: First Test at Hours 6–7, Final Video Verification Before Hour 14

**Objective: Verify whether "the extracted frames are sufficient to find highlight moments, and whether AI can select clips suitable for a campus vlog opening quick-cut."** This is an MVP small-sample engineering screening, not a model leaderboard. Current status is **not executed**; no verified specific model has been selected, and there are no actual performance scores or cost records.

Schedule: [Kickoff Verification: First confirm Replit runs successfully before connecting AI](deployment.en.md#s18-2) After Replit A, B, and C pass, complete the first round of testing at hours 6–7, keeping it within one hour; connect compilation and rendering at hours 7–14, confirming that the final video still retains key moments; review with a second set of footage at hours 14–24. It falls within the original AI development budget without adding extra phases. Modification instruction testing is still completed during the hours 14–24 MVP acceptance, leaving spoken audio and transcription to V2-3.

**Step 1: Prepare 10 footage clips, and write down human judgments first**

Select 10 clips from the 10–15 footage clips used in Replit actual load testing, covering campus scenes such as attending class, walking, eating, self-study, or interacting with friends. These should include a set of shots with similar content, a brief action, a meaningful clip with suboptimal angle or slight shakiness, and an obviously accidental shot interval. These situations can appear in the same footage clip.

You review and annotate the footage first, and a teammate re-checks it. Write this down before looking at model outputs to avoid accommodating model answers after the fact. During development, it can be saved as an independent evaluation sheet without altering the product JSON contract in [JSON Data Contract: Usable for MVP, Extensible for V2/V3](reference/timeline.en.md#s6):

| Manual Annotation Field | What to Write |
| --- | --- |
| `clip_id` | Consistent with actual asset registration |
| Content Facts | What actually happened in the frames, without guessing character identities, locations, or moods |
| Key Moments | Select 3 moments from the entire test set that should be retained and can be clearly seen within the MVP shot duration; record start and end seconds in the original footage along with the rationale |
| Duplicate Groups | Which clips express the same content, where keeping one is sufficient; different contents of the same file cannot be judged as duplicates merely because IDs are identical |
| Unusable Intervals | Obviously accidental shots, severely obstructed, or unrecognizable intervals |
| Trade-off Between Video Quality and Content | Which clips are still worth keeping despite slight shakiness or angle issues |

Manual annotations are only used for evaluation and are not sent to the model as answers. The initial 10 clips can be used first to test understanding and footage selection; if after eliminating duplicates and accidental shots there is not enough to constitute 30 seconds, the correct result is to report insufficient footage. During rendering acceptance, replenish with other valid footage from the main footage set, keeping the total count controlled at 10–15 clips without relying on duplicate clips to pad length.

**Step 2: Fix inputs, run one model provider first**

First extract about 3 low-resolution representative frames per clip, accompanied by `clip_id`, original footage timestamps, duration, and orientation; record actual frame counts, dimensions, and sampling rules. The model first provides content analysis, then returns an editing plan according to [`edit_plan.json`: What AI Outputs](reference/timeline.en.md#s6-5), with the backend responsible for adding outer identifiers, validation, and compilation. Explicitly define the task as an approximately 30-second opening quick-cut, prioritizing representative moments, activity diversity, and a natural feel.

First run through using one provider that is already activated and has available quota. Call at least twice with the same configuration to observe stability; do not reuse the previous model response as the second test. In the first round, compare at most one other provider; keep footage, frame extraction, prompt objectives, and output contracts identical during comparison. Changing sampling or switching to video inputs belongs to a different input scheme and should be recorded separately; do not attribute all differences in results to the model.

**Step 3: Compare against annotations, and inspect the actually cropped frames**

| Check Item | How to Evaluate | Recommended Pass Criteria for This Time |
| --- | --- | --- |
| Content Understanding | Manually check subjects and activities item by item, recording number of correct items / total items and specific misjudgments | No major factual errors affecting footage selection; do not fabricate specific identities, dates, locations, or personal feelings |
| Key Moments | Compare against the 3 pre-selected moments; record hit count / 3 | Both plans retain these 3 moments; the core action or visual can also be clearly seen in the final MP4 before hour 14 |
| Duplicate and Unusable Content | Check whether duplicate groups crowd multiple shots and whether accidental shot intervals are selected | Do not pad duration with clearly duplicate content; do not select labeled unusable intervals |
| Preserving Raw Authenticity | Check footage labeled as valuable but with imperfect quality | Do not exclude all meaningful content solely due to slight shakiness, ordinary angles, or dim lighting |
| Time and Contract | Validate actual asset IDs, candidate ranges, suggested durations, and final timeline | Plans entering rendering have no out-of-bounds or invalid references; original failures and repair counts are recorded separately, and cannot be silently written as first-time model success |
| Quick-Cut Effect | Actually watch the opening, clip transitions, titles, and BGM of the finished video | Able to convey campus daily life themes, titles have rationale, main visuals are clear; specific issues pointed out by both individuals are recorded |
| Elapsed Time and Cost | Separately record frame extraction, analysis, planning, validation retries, rendering, and saving | Has actual records; mark as uncollected when usage or bills are not obtained, do not fabricate costs; 90 seconds is still not the pass threshold |

The criteria here are small-sample acceptance recommendations for this project, not an accuracy commitment for all user footage. Do not only check whether the broad `source_window` covers key moments: the compiler might extract other positions from it, so the final selected intervals and the actual MP4 must be inspected. Items not yet rendered at hours 6–7 are marked as "pending finished video review" and cannot be judged as all passed in advance.

**Fix by Cause upon Failure, Then Retest**

- Key moments did not appear in input frames: Prioritize increasing sampling in that type of clip, recording the new sampling strategy; do not rely solely on switching models expecting it to guess correctly. After revising the strategy, verify on the second set of footage as well.
- Frames already contain the moment, but the model misunderstood or ignored it: First adjust the task description and footage selection priorities; only compare another provider if it remains unsatisfactory. When continuous action still cannot be determined, test a short video input scheme separately within the same budget; keep independent result records.
- Content understanding is correct, but final cropping misses the moment: Check candidate ranges and compiler cropping logic; do not treat backend time calculation errors as model aesthetic problems.
- Output format or interface failure: Check schemas supported by the service, input limits, and timeouts; retain raw errors and limited retry records. Rule fallbacks can be used for emergencies, but cannot be counted as passing AI testing.

After the first round of one hour ends, stop expanding the candidate list and select one already usable provider to continue integration; if none pass, record specific blockers and fix the main link during hours 7–14, rather than filling in "selected". If the hour 14 milestone is not passed, shrink work according to [36-Hour Schedule and Phase Milestones](collaboration.en.md#s14).

During development, centrally store the footage inventory, manual annotations, frame extraction configurations, prompt versions, specific model IDs, raw responses, validation results, usage and elapsed time per run, and final video references into `fixtures/ai-selection/`; this is a record directory to be developed, and test results have not yet been generated. During hours 14–24, use the second set of footage not involved in the first round of parameter tuning for re-acceptance, locking the primary model and configuration upon completion.

<a id="s20-5"></a>

### Separate Sponsor Selection from Product Selection

Integration with Replit is already confirmed; Gemini and ElevenLabs will only be integrated if they improve results or lower implementation costs. Consider corresponding side tracks only after actual adoption. Screenshots only show names, which cannot guarantee award eligibility on that basis; event rules for this hackathon need to be verified.

Auth0, Tiger Data, and Solana are not being added for now, and Vultr will not open a separate deployment route; domain names can be handled along the way once the primary closed loop is stable. The main showcase for Adobe Creative remains: a set of everyday fragments → an emotionally resonant finished video → the user alters the expression with a single sentence.

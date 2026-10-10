# Acceptance and Risks

[中文](acceptance.md) · **English**

[Return to Project Overview](../README.en.md)

When to read: Read relevant cases during original competition delivery, review, debugging, and stage sign-off. This page retains the original competition thresholds; for existing verifications of the current Vlogii local implementation, see [Verification Records](vlogii-validation.md), and for gaps with this page, see [Feature Comparison](mvp-coverage.en.md). For example, the current implementation retains original audio/subtitles, which differs from the muted/BGM scheme below; passing locally cannot be treated as passing the competition overall. Evidence is written to status.md.

<a id="s15"></a>

## Stage-by-Stage Acceptance, Performance, and Risks

<a id="s15-1"></a>

### Minimum Acceptance Cases

| Stage | Case | Passing Criteria |
| --- | --- | --- |
| MVP Kickoff | Two-person interface and module handoff | HTTP samples, mocks, and real responses have consistent structures; the same timeline can be directly handed over to the real renderer; simulation flags do not enter formal success results |
| MVP Kickoff | Replit technical verification | [Kickoff Verification: First confirm Replit runs successfully before connecting AI](deployment.en.md#s18-2) A, B, and C all have actual results; the nine-second sample only verifies the environment, the thirty-second actual load is verified separately |
| MVP Kickoff | AI understanding and footage selection | [AI Footage Understanding and Selection Test: First test at hours 6–7, verify final video before hour 14](ai-selection.en.md#s20-4) has comparison records between manual annotations and model results; final clips preserve key moments without obvious repetition, accidental shots, or fabricated facts; contract and footage boundary checks pass |
| MVP | Routine daily footage | Generates an opening quick montage of about 30 seconds, with representative moments and reasonable transitions, without extensive repetition, and with continuous video and BGM |
| MVP | Change title, adjust warmth | Specified changes actually take effect; other shot arrangements remain consistent |
| MVP | Delete footage | Deleted content does not return, remaining footage is continuous; validated according to the natural duration strategy in [`config.json`: Save User Intent and Version Settings](reference/timeline.en.md#s6-4), and must not be rejected by old targets |
| MVP | Modification failure, re-modifying after undo | Old final video is playable, failure does not falsely report success, and historical versions are not overwritten |
| MVP | Second footage set | Re-examine footage selection and final video at hours 14–24 using footage not involved in the first round of parameter tuning, continuing comparison against manual annotations; must not only work for fixed Demo samples |
| MVP | Formal environment and recovery | Uploading, processing, playback, and downloading on the formal link are usable; closing the page does not cancel the task; old successful versions can be opened after reboot, interrupted tasks can be retried, and failure does not block the next task |
| MVP | Limited format combinations | Rotation metadata, mixed landscape/portrait, no audio track; all original audio muted; do not promote unverified HDR/HEVC |
| V2-1 | Same footage, two emotions | Video style, pacing, and music have perceptible differences, cut points are recomputed correctly |
| V2-2 | 30s shortened to 20s | Target duration satisfies the agreement, clips are valid, deleted footage is not patched back |
| V2-3 | One clear short talking-head clip | Complete sentences preserved, subtitles synchronized, BGM ducked; does not conflict with old features |
| V3 | Feature-by-feature verification | Portrait subjects visible, 60s resources are tolerable, second style can indeed be exported; special effects and reference image capabilities are not exaggerated |

MVP performs a small number of essential automated tests on the timeline: footage out-of-bounds, hard cut cumulative duration, reordering after deletion; and tests state for retaining the old version upon failure as well as undo. Subtitle mapping is additionally tested in V2-3, and transition overlap is additionally tested in V3-3. UI colors and spacing are inspected manually.

Final video inspection includes FFmpeg exiting successfully, ffprobe reading valid video streams, resolution and duration complying with stage contracts; followed by manual watching and listening. Being decodable does not equal being well-edited.

<a id="s15-2"></a>

### Example Budget for the 90-Second Challenge

The following is used to discover bottlenecks, not tested results. Timing starts after footage upload completes; runs with models already loaded and cold starts are reported separately.

| Stage | Initial Budget |
| --- | --- |
| Reading, frame extraction, audio extraction | 15 seconds |
| Content analysis (MVP does not call ASR) | 25 seconds |
| Director planning and timeline calculation | 15 seconds |
| Normalizing selected clips, rendering | 30 seconds |
| Output inspection and return | 5 seconds |
| Total | 90 seconds |

Record actual elapsed time for each stage. A single API retry may break the budget; know where the slowdown is before reducing images or adjusting encoding; ASR only needs additional evaluation in V2-3, do not blindly increase concurrency. Run complete tests on the same input at least several times, and report differences among cold start, initial processing, and cached modifications.

<a id="s15-3"></a>

### Key Risks and Countermeasures

| Risk | Approach |
| --- | --- |
| Modules run individually but fail to integrate overall | Early on, use the same manual dataset and perform real joint debugging stage by stage |
| Local or Preview succeeds, but formal deployment fails | Perform [Kickoff Verification: First confirm Replit runs successfully before connecting AI](deployment.en.md#s18-2) verification in the first 6 hours; inspect release configuration, background tasks, storage recovery, and actual load separately, recording at which step failure occurs |
| AI data is valid but the story is poor | Limit repetition, organize by activity, watch in real life and conduct blind evaluations |
| Cannot read shooting time | Metadata → Parseable filenames → Upload order; indicate source |
| Static keyframes miss critical actions | Add timestamps to frames, increase sampling when necessary, do not let AI guess exact action boundaries |
| Font or title overflow | Local fonts, short titles, text measurement, and minimum font size; render actual preview |
| Misaligned transitions and audio | Compute unified final timeline; prioritize hard cuts; place audio according to final start point |
| Anomalies caused by HDR, rotation, variable frame rate | Preserve originals, normalize selected ranges, save conversion logs |
| Simultaneous rendering freezes the machine | Generation and modification share a serial queue; limit resource consumption of FFmpeg and ASR |
| Network or API unavailable | Clearly marked cache, backup final video, and full screen recording |
| File leaks or API keys appearing on the page | API keys only in backend environment variables; only return output files that need to be displayed |

Invoke FFmpeg using argument lists and `shell=False`; do not concatenate user text into shell commands. Text in formats such as ASS also requires corresponding escaping.

Media endpoints only accept internal project/version IDs, mapped to files after inspection; do not accept arbitrary disk paths. The frontend static directory only holds page assets; API keys, original footage, and logs must not be exposed together.

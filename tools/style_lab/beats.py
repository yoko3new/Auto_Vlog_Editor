"""Beat, accent and level analysis for a music track or a finished reel's soundtrack."""

from __future__ import annotations

import numpy as np
import librosa

HOP = 512
BEATS_PER_BAR = 4


def analyze_music(y: np.ndarray, sr: int, start_bpm: float = 120.0) -> dict:
    """Estimate tempo, beat grid, downbeat phase, strong accents and level envelope.

    Downbeats are an estimate: the bar phase whose beats carry the most low-band
    (kick/bass) onset energy. ``downbeat_confidence`` near 0 means the phase is a guess.
    """
    if y.size < sr:
        raise ValueError("audio shorter than one second")
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sr, hop_length=HOP, start_bpm=start_bpm, units="frames"
    )
    tempo = float(np.atleast_1d(tempo)[0])
    raw_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP)
    beat_times, attack_offset = refine_beats(raw_times, y, sr)
    intervals = np.diff(beat_times)
    beat_period = float(np.median(intervals)) if intervals.size else 60.0 / max(tempo, 1.0)

    mel = librosa.feature.melspectrogram(y=y, sr=sr, hop_length=HOP, n_mels=64, fmax=8000)
    low_env = librosa.onset.onset_strength(S=librosa.power_to_db(mel[:6]), sr=sr, hop_length=HOP)
    phase_scores = []
    for phase in range(BEATS_PER_BAR):
        frames = beat_frames[phase::BEATS_PER_BAR]
        phase_scores.append(float(low_env[frames].mean()) if frames.size else 0.0)
    best = int(np.argmax(phase_scores))
    mean_score = float(np.mean(phase_scores)) or 1.0
    downbeat_confidence = (phase_scores[best] - mean_score) / mean_score

    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=HOP)
    strengths = onset_env[onset_frames]
    strong_cut = np.percentile(strengths, 75) if strengths.size else 0.0
    accents = librosa.frames_to_time(onset_frames[strengths >= strong_cut], sr=sr, hop_length=HOP)

    return {
        "tempo_bpm": round(tempo, 2),
        "attack_offset_s": round(attack_offset, 4),
        "beat_period_s": round(beat_period, 4),
        "beat_interval_cv": round(float(np.std(intervals) / np.mean(intervals)), 4) if intervals.size else None,
        "beats_s": [round(float(t), 3) for t in beat_times],
        "downbeat_phase": best,
        "downbeat_confidence": round(float(downbeat_confidence), 3),
        "downbeats_s": [round(float(t), 3) for t in beat_times[best::BEATS_PER_BAR]],
        "strong_accents_s": [round(float(t), 3) for t in accents],
        "onsets_s": [round(float(t), 3) for t in librosa.frames_to_time(onset_frames, sr=sr, hop_length=HOP)],
    }


def refine_beats(beat_times: np.ndarray, y: np.ndarray, sr: int, half_window: int = 4) -> tuple[np.ndarray, float]:
    """Move beats onto the audible attack and smooth tracker jitter.

    The onset envelope peaks roughly one analysis hop after the attack, so cuts would land
    late. The median distance to the steepest energy rise near each beat (5 ms resolution)
    corrects that bias; a local linear fit over +-4 beats then removes per-beat jitter
    while still following gradual tempo changes.
    """
    if beat_times.size < 2 * half_window + 1:
        return beat_times, 0.0
    hop = 64
    rms = librosa.feature.rms(y=y, frame_length=256, hop_length=hop)[0]
    log_energy = np.log(rms + 1e-6)
    rise = np.maximum(0.0, np.diff(log_energy, prepend=log_energy[0]))
    times = librosa.frames_to_time(np.arange(rise.size), sr=sr, hop_length=hop)
    floor = np.median(rise) + 1e-9
    shifts = []
    for beat in beat_times:
        window = (times >= beat - 0.06) & (times <= beat + 0.03)
        if window.any() and rise[window].max() > 3 * floor:
            shifts.append(times[window][rise[window].argmax()] - beat)
    offset = float(np.median(shifts)) if len(shifts) >= 8 else 0.0
    shifted = beat_times + offset
    index = np.arange(shifted.size)
    smoothed = np.empty_like(shifted)
    for i in index:
        a, b = max(0, i - half_window), min(shifted.size, i + half_window + 1)
        slope, intercept = np.polyfit(index[a:b], shifted[a:b], 1)
        smoothed[i] = slope * i + intercept
    return smoothed, offset


def level_envelope(y: np.ndarray, sr: int, window_s: float = 0.1) -> tuple[np.ndarray, np.ndarray]:
    """Short-term RMS level in dBFS and the window start times."""
    win = max(1, int(sr * window_s))
    usable = y[: (y.size // win) * win].reshape(-1, win)
    rms = np.sqrt(np.mean(usable.astype(np.float64) ** 2, axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-6))
    return np.arange(db.size) * window_s, db


def mix_shape(y: np.ndarray, sr: int) -> dict:
    """Describe how the soundtrack starts, ends and where it dips (possible ducking or breaks)."""
    times, db = level_envelope(y, sr)
    if db.size == 0:
        return {}
    body = np.median(db)
    audible = np.nonzero(db > body - 20)[0]
    start = float(times[audible[0]]) if audible.size else 0.0
    reach = np.nonzero(db >= body - 3)[0]
    fade_in = max(0.0, float(times[reach[0]]) - start) if reach.size else 0.0
    end_idx = audible[-1] if audible.size else db.size - 1
    last_full = reach[-1] if reach.size else end_idx
    fade_out = max(0.0, float(times[end_idx] - times[last_full]))

    rolling = np.array([np.median(db[max(0, i - 20): i + 21]) for i in range(db.size)])
    low = db < rolling - 6
    dips, i = [], 0
    while i < low.size:
        if low[i]:
            j = i
            while j < low.size and low[j]:
                j += 1
            if (j - i) * 0.1 >= 0.3 and times[i] > start + 0.5 and times[min(j, low.size - 1)] < times[end_idx] - 0.5:
                dips.append({"start_s": round(float(times[i]), 2), "end_s": round(float(times[j - 1] + 0.1), 2),
                             "depth_db": round(float(np.mean(rolling[i:j] - db[i:j])), 1)})
            i = j
        else:
            i += 1
    return {
        "body_level_dbfs": round(float(body), 1),
        "level_p10_p90_dbfs": [round(float(np.percentile(db, 10)), 1), round(float(np.percentile(db, 90)), 1)],
        "audio_starts_at_s": round(start, 2),
        "fade_in_s": round(fade_in, 2),
        "fade_out_s": round(fade_out, 2),
        "dips": dips,
    }

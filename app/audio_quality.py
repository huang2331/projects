import math
import re
from pathlib import Path

import numpy as np

from .analysis import count_words

FILLERS = {"um", "uh", "erm", "hmm", "like", "basically", "actually"}


def _decode_mono(path: Path, target_rate: int = 16_000) -> tuple[np.ndarray, int]:
    try:
        import av
        chunks = []
        with av.open(str(path)) as container:
            stream = container.streams.audio[0]
            resampler = av.audio.resampler.AudioResampler(format="fltp", layout="mono", rate=target_rate)
            for frame in container.decode(stream):
                for converted in resampler.resample(frame):
                    chunks.append(converted.to_ndarray().reshape(-1).astype(np.float32))
            for converted in resampler.resample(None):
                chunks.append(converted.to_ndarray().reshape(-1).astype(np.float32))
        if not chunks:
            raise ValueError("No decodable audio samples")
        samples = np.concatenate(chunks)
        peak = float(np.max(np.abs(samples)))
        if peak > 1.5:
            samples /= peak
        return samples, target_rate
    except Exception as exc:
        raise ValueError("Audio quality metrics could not be calculated from this recording.") from exc


def _pitch_values(samples: np.ndarray, sample_rate: int) -> list[float]:
    frame_size, hop = int(sample_rate * 0.04), int(sample_rate * 0.02)
    min_lag, max_lag = int(sample_rate / 350), int(sample_rate / 70)
    values = []
    for start in range(0, max(0, len(samples) - frame_size), hop * 3):
        frame = samples[start:start + frame_size]
        rms = float(np.sqrt(np.mean(frame * frame) + 1e-12))
        if rms < 0.008:
            continue
        frame = (frame - np.mean(frame)) * np.hanning(len(frame))
        corr = np.correlate(frame, frame, mode="full")[len(frame) - 1:]
        if corr[0] <= 0:
            continue
        search = corr[min_lag:max_lag]
        if not len(search):
            continue
        lag = int(np.argmax(search)) + min_lag
        confidence = corr[lag] / corr[0]
        if confidence >= 0.3:
            values.append(sample_rate / lag)
    return values


def _round_or_none(value, digits=1):
    return round(float(value), digits) if value is not None and math.isfinite(float(value)) else None


def analyze_speech_quality(path: Path, transcript: str, segments: list[dict], duration: float) -> dict:
    words = count_words(transcript)
    speech_seconds = sum(max(0.0, float(s["end"]) - float(s["start"])) for s in segments)
    speech_seconds = min(speech_seconds, duration) if duration else speech_seconds
    gaps = [max(0.0, float(b["start"]) - float(a["end"])) for a, b in zip(segments, segments[1:])]
    pauses = [gap for gap in gaps if gap >= 0.25]
    long_pauses = [gap for gap in gaps if gap >= 2.0]
    tokens = [w.lower() for w in re.findall(r"\b[A-Za-z]+\b", transcript)]
    filler_count = sum(token in FILLERS for token in tokens)

    samples, sample_rate = _decode_mono(path)
    frame_size, hop = int(sample_rate * 0.025), int(sample_rate * 0.01)
    rms_values = []
    clarity_values = []
    window = np.hanning(frame_size)
    freqs = np.fft.rfftfreq(frame_size, 1 / sample_rate)
    speech_band = (freqs >= 300) & (freqs <= 3400)
    for start in range(0, max(0, len(samples) - frame_size), hop):
        frame = samples[start:start + frame_size]
        rms = float(np.sqrt(np.mean(frame * frame) + 1e-12))
        if rms < 0.005:
            continue
        rms_values.append(20 * math.log10(rms + 1e-12))
        power = np.abs(np.fft.rfft(frame * window)) ** 2
        total = float(np.sum(power)) + 1e-12
        clarity_values.append(float(np.sum(power[speech_band])) / total * 100)

    pitches = _pitch_values(samples, sample_rate)
    pitch_median = float(np.median(pitches)) if pitches else None
    pitch_range_st = None
    if len(pitches) >= 5:
        low, high = np.percentile(pitches, [10, 90])
        if low > 0:
            pitch_range_st = 12 * math.log2(high / low)
    dynamics = None
    if len(rms_values) >= 5:
        low_db, high_db = np.percentile(rms_values, [10, 90])
        dynamics = high_db - low_db

    return {
        "speech_rate_wpm": round(words / (duration / 60)) if duration > 0 else None,
        "articulation_rate_wpm": round(words / (speech_seconds / 60)) if speech_seconds > 0 else None,
        "speaking_ratio_percent": _round_or_none(speech_seconds / duration * 100 if duration > 0 else None),
        "pause_ratio_percent": _round_or_none((duration - speech_seconds) / duration * 100 if duration > 0 else None),
        "average_pause_seconds": _round_or_none(np.mean(pauses) if pauses else 0, 2),
        "long_pause_count": len(long_pauses),
        "pitch_median_hz": _round_or_none(pitch_median),
        "pitch_range_semitones": _round_or_none(pitch_range_st),
        "dynamic_range_db": _round_or_none(dynamics),
        "clarity_proxy_percent": _round_or_none(np.median(clarity_values) if clarity_values else None),
        "filler_count": filler_count,
        "fillers_per_100_words": _round_or_none(filler_count / words * 100 if words else 0),
    }

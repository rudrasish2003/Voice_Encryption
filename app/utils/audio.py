"""Audio I/O and quality-check helpers.

SNR estimation here is a rough energy-percentile approximation, not a
calibrated measurement -- good enough for a Phase 1 quality gate. Replace
with a measured approach once Phase 3 evaluation data exists.
"""
import os
import subprocess
import tempfile

import numpy as np
import soundfile as sf


def normalize_to_wav(input_path: str, target_sr: int = 16000) -> str:
    """Convert any input audio to mono 16kHz WAV via ffmpeg. Returns a new temp file path."""
    fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ac", "1", "-ar", str(target_sr), out_path]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        if os.path.exists(out_path):
            os.unlink(out_path)
        raise ValueError(f"ffmpeg normalization failed: {proc.stderr.decode(errors='ignore')}")
    return out_path


def read_audio(path: str):
    data, sr = sf.read(path, dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data, sr


def duration_sec(samples: np.ndarray, sr: int) -> float:
    return len(samples) / float(sr) if sr else 0.0


def detect_clipping(samples: np.ndarray, threshold: float = 0.99, max_fraction: float = 0.001) -> bool:
    if len(samples) == 0:
        return False
    clipped = np.sum(np.abs(samples) >= threshold)
    return bool((clipped / len(samples)) > max_fraction)  # numpy.bool_ isn't JSON-serializable


def extract_segments(samples: np.ndarray, sr: int, segments: list, cap_sec: float = None) -> np.ndarray:
    """Concatenate the given [{"start", "end"}, ...] regions of samples, optionally capped to cap_sec total."""
    chunks = []
    total = 0.0
    for s in segments:
        start_idx, end_idx = int(s["start"] * sr), int(s["end"] * sr)
        chunk = samples[start_idx:end_idx]
        if cap_sec is not None:
            remaining = cap_sec - total
            if remaining <= 0:
                break
            max_len = int(remaining * sr)
            if len(chunk) > max_len:
                chunk = chunk[:max_len]
        chunks.append(chunk)
        total += len(chunk) / sr
    return np.concatenate(chunks) if chunks else np.array([], dtype=np.float32)


def estimate_snr_db(samples: np.ndarray, sr: int, frame_ms: float = 25.0) -> float:
    """Approximate SNR: loudest 10% of frames as signal, quietest 10% as noise floor."""
    frame_len = max(int(sr * frame_ms / 1000), 1)
    n_frames = len(samples) // frame_len
    if n_frames < 4:
        return 0.0
    frames = samples[: n_frames * frame_len].reshape(n_frames, frame_len)
    energies = np.mean(frames**2, axis=1)
    energies_sorted = np.sort(energies)
    k = max(n_frames // 10, 1)
    noise_floor = np.mean(energies_sorted[:k]) + 1e-12
    signal_power = np.mean(energies_sorted[-k:]) + 1e-12
    return float(10 * np.log10(signal_power / noise_floor))

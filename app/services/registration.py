"""Registration pipeline: quality gate -> dominant-speaker extraction -> voiceprint build -> duplicate check.

Diarization on a single-person clip often still emits more than one speaker
label (breathing, background noise, a brief echo) even though only one
person is actually talking. Rather than hard-rejecting any clip with >1
label, we take the speaker with the most total speech ("dominant speaker")
and build the voiceprint from only their audio -- and reject only when no
speaker clearly dominates, which is the real signature of a genuine
multi-person recording.
"""
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.config import get_settings
from app.repos.people_repo import PeopleRepo
from app.services.diarization import diarize
from app.services.embedding import embed_waveform
from app.utils.audio import detect_clipping, duration_sec, estimate_snr_db, extract_segments, normalize_to_wav, read_audio


class RegistrationError(Exception):
    def __init__(self, reason_code: str, message: str):
        self.reason_code = reason_code
        super().__init__(message)


@dataclass
class ClipAnalysis:
    wav_path: str
    dominant_samples: np.ndarray
    sr: int
    speech_duration_sec: float  # dominant speaker's speech only -- this is what gets embedded
    total_speech_duration_sec: float  # all detected speech, for diagnostics
    dominant_ratio: float
    snr_db: float
    clipping_detected: bool
    speaker_count: int
    embedding: Optional[np.ndarray] = None

    def quality_checks(self) -> dict:
        return {
            "speech_duration_sec": self.speech_duration_sec,
            "total_speech_duration_sec": self.total_speech_duration_sec,
            "dominant_speaker_ratio": self.dominant_ratio,
            "snr_db": self.snr_db,
            "clipping_detected": self.clipping_detected,
            "single_speaker_confirmed": self.speaker_count <= 1,
            "format_ok": True,
        }


def analyze_clip(raw_path: str, settings) -> ClipAnalysis:
    wav_path = normalize_to_wav(raw_path)
    try:
        samples, sr = read_audio(wav_path)
        total_dur = duration_sec(samples, sr)
        snr_db = estimate_snr_db(samples, sr)
        clipping = detect_clipping(samples)

        segments = diarize(wav_path, settings.diarization_model, settings.hf_token)
        if segments:
            by_speaker: dict[str, list[dict]] = {}
            for seg in segments:
                by_speaker.setdefault(seg["speaker"], []).append(seg)
            durations = {spk: sum(s["end"] - s["start"] for s in segs) for spk, segs in by_speaker.items()}
            total_speech = sum(durations.values())
            dominant_speaker = max(durations, key=durations.get)
            dominant_duration = durations[dominant_speaker]
            dominant_ratio = dominant_duration / total_speech if total_speech > 0 else 0.0
            dominant_samples = extract_segments(samples, sr, by_speaker[dominant_speaker])
            speaker_count = len(durations)
        else:
            # No distinct speaker segments found (e.g. very quiet clip) -- treat as a single speaker.
            dominant_samples = samples
            total_speech = total_dur
            dominant_duration = total_dur
            dominant_ratio = 1.0
            speaker_count = 1

        return ClipAnalysis(
            wav_path=wav_path,
            dominant_samples=dominant_samples,
            sr=sr,
            speech_duration_sec=dominant_duration,
            total_speech_duration_sec=total_speech,
            dominant_ratio=dominant_ratio,
            snr_db=snr_db,
            clipping_detected=clipping,
            speaker_count=speaker_count,
        )
    except Exception:
        if os.path.exists(wav_path):
            os.unlink(wav_path)
        raise


def validate_clip(analysis: ClipAnalysis, settings) -> None:
    if analysis.clipping_detected:
        raise RegistrationError("clipping", "audio clip has excessive clipping")
    if analysis.dominant_ratio < settings.dominant_speaker_min_ratio:
        raise RegistrationError(
            "multi_speaker_detected",
            f"no single dominant speaker (top speaker is only {analysis.dominant_ratio:.0%} of "
            f"detected speech, need >= {settings.dominant_speaker_min_ratio:.0%})",
        )


def build_voiceprint(clip_paths: list[str]) -> tuple[np.ndarray, float, list[ClipAnalysis]]:
    """Returns (centroid_vector, quality_score, per_clip_analyses). Caller owns cleanup of clip_paths."""
    settings = get_settings()
    analyses: list[ClipAnalysis] = []
    try:
        for p in clip_paths:
            analysis = analyze_clip(p, settings)
            validate_clip(analysis, settings)
            analysis.embedding = embed_waveform(analysis.dominant_samples, analysis.sr, settings.embedding_model)
            analyses.append(analysis)

        total_speech = sum(a.speech_duration_sec for a in analyses)
        if total_speech < settings.min_registration_speech_sec:
            raise RegistrationError(
                "insufficient_speech",
                f"only {total_speech:.1f}s clean speech across clips, need "
                f"{settings.min_registration_speech_sec}s",
            )

        vectors = [a.embedding for a in analyses]
        centroid = np.mean(vectors, axis=0)
        norm = np.linalg.norm(centroid)
        centroid = (centroid / norm if norm > 0 else centroid).astype(np.float32)

        if len(vectors) > 1:
            sims = [
                float(np.dot(vectors[i], vectors[j]))
                for i in range(len(vectors))
                for j in range(i + 1, len(vectors))
            ]
            quality_score = float(np.mean(sims))
        else:
            quality_score = 1.0

        return centroid, quality_score, analyses
    finally:
        for a in analyses:
            if os.path.exists(a.wav_path):
                os.unlink(a.wav_path)


def check_duplicate(people_repo: PeopleRepo, vector: np.ndarray) -> Optional[dict]:
    settings = get_settings()
    for doc in people_repo.list_active():
        existing_vec = people_repo.get_vector(doc)
        sim = float(np.dot(vector, existing_vec))
        if sim >= settings.match_threshold:
            return {"person_id": doc["_id"], "name": doc["name"], "score": sim}
    return None



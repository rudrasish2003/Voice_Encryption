"""Identification pipeline: diarize -> per-speaker embedding -> match -> decision rules
-> spoken self-introduction labeling (suggestion only, never auto-enrolled) -> generic
"Speaker N" fallback labels.
"""
import logging
import os
import time

import numpy as np

from app.config import get_settings
from app.repos.audio_snippets_repo import AudioSnippetsRepo
from app.repos.pending_embeddings_repo import PendingEmbeddingsRepo
from app.services.diarization import diarize
from app.services.embedding import embed_waveform
from app.services.matching import Matcher
from app.services.name_extraction import group_transcript_by_speaker, resolve_claimed_speakers
from app.services.registration import check_duplicate
from app.services.transcription import transcribe
from app.utils.audio import extract_segments, normalize_to_wav, read_audio

logger = logging.getLogger("identify_worker")

UNRESOLVED_DECISIONS = {"unknown", "ambiguous", "insufficient_speech"}
# Decisions where we have a usable embedding but didn't enroll it ourselves --
# these are the ones a human can confirm via "Add to Library".
ENROLLABLE_DECISIONS = {"unknown", "ambiguous", "claimed_unverified"}


def identify_file(raw_path: str, matcher: Matcher, job_id: str) -> list[dict]:
    settings = get_settings()
    pending_repo = PendingEmbeddingsRepo()
    snippets_repo = AudioSnippetsRepo()

    t0 = time.monotonic()
    logger.info("job %s: converting audio...", job_id)
    wav_path = normalize_to_wav(raw_path)
    try:
        samples, sr = read_audio(wav_path)
        duration_sec = len(samples) / sr if sr else 0.0
        logger.info("job %s: %.1fs of audio, running diarization (this is the slow part on CPU)...", job_id, duration_sec)

        t_stage = time.monotonic()
        segments = diarize(wav_path, settings.diarization_model, settings.hf_token)
        logger.info(
            "job %s: diarization found %d speaker(s) in %.1fs",
            job_id, len({s["speaker"] for s in segments}), time.monotonic() - t_stage,
        )

        by_speaker: dict[str, list[dict]] = {}
        for seg in segments:
            by_speaker.setdefault(seg["speaker"], []).append(seg)

        claims: dict[str, dict] = {}
        transcript_by_speaker: dict[str, list[dict]] = {}
        if settings.enable_spoken_name_labeling and segments:
            logger.info("job %s: transcribing (whisper '%s', also CPU-bound)...", job_id, settings.whisper_model)
            t_stage = time.monotonic()
            transcript_segments = transcribe(wav_path, settings.whisper_model)
            logger.info("job %s: transcription done in %.1fs", job_id, time.monotonic() - t_stage)
            claims = resolve_claimed_speakers(transcript_segments, segments)
            transcript_by_speaker = group_transcript_by_speaker(transcript_segments, segments)

        logger.info("job %s: embedding + matching %d speaker(s)...", job_id, len(by_speaker))
        results = []
        first_seen: dict[str, float] = {}
        for label, segs in by_speaker.items():
            first_seen[label] = min(s["start"] for s in segs)
            total_speech = sum(s["end"] - s["start"] for s in segs)
            result = {
                "speaker_label": label,
                "segments": [{"start": s["start"], "end": s["end"]} for s in segs],
                "total_speech_sec": total_speech,
                "transcript": transcript_by_speaker.get(label, []),
            }

            if total_speech < settings.min_identify_speech_sec:
                # No embedding is computed at all below this bar -- nothing to offer
                # "Add to Library" or playback on, by design (per the plan's quality gate).
                result["match"] = _no_match("insufficient_speech")
                result["embeddable"] = False
                result["playable"] = False
                results.append(result)
                continue

            speaker_samples = extract_segments(samples, sr, segs, cap_sec=settings.max_identify_speech_sec)
            vec = embed_waveform(speaker_samples, sr, settings.embedding_model)
            match = _decide(matcher, vec, settings)

            claim = claims.get(label)
            if claim and match["decision"] != "matched":
                match = _apply_claim(matcher, vec, claim, total_speech, settings, match)

            result["match"] = match
            result["embeddable"] = match["decision"] in ENROLLABLE_DECISIONS
            if result["embeddable"]:
                pending_repo.save(job_id, label, vec, total_speech, match.get("claimed_name"))

            snippets_repo.save(job_id, label, speaker_samples, sr)
            result["playable"] = True

            results.append(result)

        _assign_display_names(results, first_seen)
        logger.info("job %s: done in %.1fs total", job_id, time.monotonic() - t0)
        return results
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)


def _apply_claim(matcher: Matcher, vec: np.ndarray, claim: dict, total_speech: float, settings, match: dict) -> dict:
    """A speaker named themself (or was named by another speaker) and didn't already
    match a registered voiceprint via normal matching. Never auto-enrolls -- a spoken
    name is a transcript claim, not a verified identity, so it's always surfaced as a
    suggestion (decision "claimed_unverified", "Add to Library" prefilled with the
    name) for a human to confirm or reject. The one exception: if this voice already
    matches someone in the library (just not confidently enough via normal matching,
    or discovered only now via this more targeted check), report the existing match
    instead of a fresh claim -- an existing registration always wins.
    """
    dup = check_duplicate(matcher.people_repo, vec)
    if dup:
        person = matcher.people_repo.get(dup["person_id"])
        return {
            "person_id": dup["person_id"],
            "name": person["name"] if person else None,
            "score": dup["score"],
            "runner_up_score": match.get("runner_up_score", 0.0),
            "decision": "matched",
            "claimed_name": claim["name"],
            "claim_type": claim["claim_type"],
        }

    return {**match, "claimed_name": claim["name"], "claim_type": claim["claim_type"], "decision": "claimed_unverified"}


def _assign_display_names(results: list[dict], first_seen: dict[str, float]) -> None:
    """Named speakers (matched / claimed_unverified) show their name -- for a claim,
    this is a suggestion only, not yet a saved identity. Everyone else gets a generic
    "Speaker N" in order of first appearance in the file.
    """
    unresolved_labels = [
        r["speaker_label"] for r in results if r["match"]["decision"] in UNRESOLVED_DECISIONS
    ]
    unresolved_labels.sort(key=lambda label: first_seen[label])
    speaker_number = {label: i for i, label in enumerate(unresolved_labels)}

    for r in results:
        match = r["match"]
        if match["decision"] == "matched":
            r["display_name"] = match["name"]
        elif match["decision"] == "claimed_unverified":
            r["display_name"] = match["claimed_name"]
        else:
            r["display_name"] = f"Speaker {speaker_number[r['speaker_label']]}"


def _decide(matcher: Matcher, vec: np.ndarray, settings) -> dict:
    ranked = matcher.rank(vec)
    if not ranked:
        return _no_match("unknown")

    best_id, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0

    if best_score >= settings.match_threshold and (best_score - runner_up) >= settings.runner_up_margin:
        person = matcher.people_repo.get(best_id)
        return {
            "person_id": best_id,
            "name": person["name"] if person else None,
            "score": best_score,
            "runner_up_score": runner_up,
            "decision": "matched",
            "claimed_name": None,
            "claim_type": None,
        }
    if best_score >= settings.match_threshold:
        return {
            "person_id": None,
            "name": None,
            "score": best_score,
            "runner_up_score": runner_up,
            "decision": "ambiguous",
            "claimed_name": None,
            "claim_type": None,
        }
    return {
        "person_id": None,
        "name": None,
        "score": best_score,
        "runner_up_score": runner_up,
        "decision": "unknown",
        "claimed_name": None,
        "claim_type": None,
    }


def _no_match(decision: str) -> dict:
    return {
        "person_id": None,
        "name": None,
        "score": 0.0,
        "runner_up_score": 0.0,
        "decision": decision,
        "claimed_name": None,
        "claim_type": None,
    }

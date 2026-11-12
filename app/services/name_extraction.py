"""Regex-based detection of spoken name claims in a transcript segment.

Two kinds of claim:
  - self: the speaker names themself ("I am Sanjana", "my name is Sanjana",
    "this is Sanjana speaking", "myself Sanjana").
  - other: someone names the NEXT speaker ("Mr. X, please speak", "X, go
    ahead") -- the claimed name belongs to whoever starts talking next, not
    to whoever said the phrase.

This is deliberately simple pattern matching, not NLP/NER -- good enough to
catch clearly-spoken introductions, not a robust extractor for arbitrary
phrasing.
"""
import re
from typing import Optional

_STOPWORDS = [
    "and", "but", "who", "that", "so", "today", "now", "from", "please", "here",
    "speaking", "sir", "madam", "is", "the", "a", "an", "very", "just", "going",
    "gonna", "not", "really", "also", "too", "i", "you", "we", "they", "he", "she",
    "it", "this", "will", "be", "presenting", "about", "for", "with", "my", "your",
    "our", "their", "working", "trying", "looking", "thinking", "doing", "running",
    "sitting", "talking", "walking", "calling", "waiting", "checking", "testing",
    "writing", "coding", "sharing", "reviewing", "sure", "still", "actually",
    "basically", "probably", "maybe", "okay", "alright", "fine", "good", "great",
    "happy", "sorry", "busy", "available", "free", "ready", "done", "finished",
]
_STOPWORD_ALT = "|".join(_STOPWORDS)
# Negative lookahead stops the regex itself from capturing a filler word as part of
# the name, rather than capturing it and trying to strip it out afterwards.
_NAME_TOKEN = rf"(?!(?:{_STOPWORD_ALT})\b)[A-Za-z][A-Za-z'-]*"
_NAME_GROUP = rf"({_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,1}})"

_SELF_INTRO_PATTERNS = [
    re.compile(rf"\bi\s*(?:'?m|am)\s+{_NAME_GROUP}", re.IGNORECASE),
    re.compile(rf"\bmy name is\s+{_NAME_GROUP}", re.IGNORECASE),
    re.compile(rf"\bthis is\s+{_NAME_GROUP}\s+(?:speaking|here)\b", re.IGNORECASE),
    re.compile(rf"\bmyself\s+{_NAME_GROUP}", re.IGNORECASE),
]

_OTHER_INTRO_PATTERNS = [
    re.compile(
        rf"\b(?:mr|mrs|ms|dr|miss)\.?\s+{_NAME_GROUP}\b[^.?!]{{0,25}}\b"
        rf"(?:please\s+)?(?:speak|go ahead|your turn|continue|proceed)\b",
        re.IGNORECASE,
    ),
]

def _clean_name(raw: str) -> Optional[str]:
    words = raw.strip().split()
    if not words:
        return None
    # Require every captured word to already be capitalized in the transcript, as
    # Whisper produced it. Whisper capitalizes proper nouns but not ordinary words,
    # so this is what actually distinguishes a name from a verb/adjective phrase
    # that slipped past the stopword list -- e.g. "I am currently working" matches
    # the same regex shape as "I am Sanjana" and must be rejected here, since the
    # stopword list can never be exhaustive. This trades some missed real
    # introductions (an uncommon name Whisper doesn't capitalize) for far fewer
    # garbage names getting permanently enrolled -- the right tradeoff for a
    # biometric identity store.
    if not all(w[:1].isupper() for w in words):
        return None
    return " ".join(w.capitalize() for w in words[:2])


def extract_self_claim(text: str) -> Optional[str]:
    for pattern in _SELF_INTRO_PATTERNS:
        match = pattern.search(text)
        if match:
            name = _clean_name(match.group(1))
            if name:
                return name
    return None


def extract_other_intro(text: str) -> Optional[str]:
    for pattern in _OTHER_INTRO_PATTERNS:
        match = pattern.search(text)
        if match:
            name = _clean_name(match.group(1))
            if name:
                return name
    return None


def _overlapping_speaker(flat_segments: list[dict], t_start: float, t_end: float) -> Optional[str]:
    """Whichever diarized speaker has the most overlap with [t_start, t_end]."""
    best_speaker, best_overlap = None, 0.0
    for seg in flat_segments:
        overlap = min(seg["end"], t_end) - max(seg["start"], t_start)
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = seg["speaker"]
    return best_speaker


def group_transcript_by_speaker(transcript_segments: list[dict], diar_segments: list[dict]) -> dict[str, list[dict]]:
    """Buckets each transcript line under whichever diarized speaker was talking
    during it, for display ("what did this speaker say") -- same overlap rule
    used for claim resolution, just without the name-extraction step.
    """
    flat_sorted = sorted(diar_segments, key=lambda s: s["start"])
    by_speaker: dict[str, list[dict]] = {}
    for ts in transcript_segments:
        label = _overlapping_speaker(flat_sorted, ts["start"], ts["end"])
        if label is None:
            continue
        by_speaker.setdefault(label, []).append(
            {"start": ts["start"], "end": ts["end"], "text": ts["text"]}
        )
    return by_speaker


def resolve_claimed_speakers(transcript_segments: list[dict], diar_segments: list[dict]) -> dict[str, dict]:
    """Returns {speaker_label: {"name": str, "claim_type": "self" | "introduced"}}.

    Self-claims are bound directly to whichever speaker is talking during the
    claim. Other-claims ("Mr. X, please speak") are bound to the next speaker
    turn (by a different speaker) that starts after the claim. A self-claim
    always wins over an other-claim for the same speaker.
    """
    flat_sorted = sorted(diar_segments, key=lambda s: s["start"])
    claims: dict[str, dict] = {}

    for ts in transcript_segments:
        speaking_label = _overlapping_speaker(flat_sorted, ts["start"], ts["end"])

        self_name = extract_self_claim(ts["text"])
        if self_name and speaking_label:
            claims[speaking_label] = {"name": self_name, "claim_type": "self"}
            continue

        other_name = extract_other_intro(ts["text"])
        if other_name:
            for seg in flat_sorted:
                if seg["start"] >= ts["end"] and seg["speaker"] != speaking_label:
                    if claims.get(seg["speaker"], {}).get("claim_type") != "self":
                        claims[seg["speaker"]] = {"name": other_name, "claim_type": "introduced"}
                    break

    return claims

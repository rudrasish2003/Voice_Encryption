"""Short-lived local storage for per-speaker audio snippets, so a reviewer can
listen back to one speaker from a past identify job.

This is a deliberate, narrow exception to "never store raw audio": only that
speaker's own segments (not the whole file, not other speakers' voices), capped
the same length as the embedding extraction, and auto-expired by the worker
(see cleanup_expired()) rather than kept indefinitely.
"""
import re
import time
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from app.config import get_settings

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9_-]")


class AudioSnippetsRepo:
    def __init__(self, data_dir: Optional[str] = None):
        settings = get_settings()
        self.dir = Path(data_dir or settings.data_dir) / "pending_audio_snippets"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str, speaker_label: str) -> Path:
        safe_job = _SAFE_SEGMENT.sub("_", job_id)
        safe_label = _SAFE_SEGMENT.sub("_", speaker_label)
        return self.dir / f"{safe_job}__{safe_label}.wav"

    def save(self, job_id: str, speaker_label: str, samples: np.ndarray, sr: int) -> None:
        sf.write(str(self._path(job_id, speaker_label)), samples, sr)

    def get_path(self, job_id: str, speaker_label: str) -> Optional[Path]:
        p = self._path(job_id, speaker_label)
        return p if p.exists() else None

    def cleanup_expired(self, max_age_hours: float) -> int:
        """Deletes snippets older than max_age_hours. Returns how many were removed."""
        cutoff = time.time() - max_age_hours * 3600
        removed = 0
        for f in self.dir.glob("*.wav"):
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
                removed += 1
        return removed

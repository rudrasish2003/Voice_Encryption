"""Local-filesystem holding area for a speaker's embedding from an identify job,
so a human can confirm "Add to Library" later without needing the raw audio again
(which is already deleted by the time anyone looks at the result).

Consistent with the rest of the system: MongoDB is still only the job queue --
this, like every other voiceprint, lives encrypted on local disk. Entries are
deleted once consumed by an enroll action; uncollected ones are harmless (just
an encrypted vector keyed by job_id+speaker_label) but aren't auto-expired yet --
see IMPLEMENTATION_PLAN.md for a note on adding retention cleanup later.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import get_settings
from app.utils.crypto import decrypt_vector, encrypt_vector

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9_-]")


class PendingEmbeddingsRepo:
    def __init__(self, data_dir: Optional[str] = None):
        settings = get_settings()
        self.dir = Path(data_dir or settings.data_dir) / "pending_embeddings"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str, speaker_label: str) -> Path:
        safe_job = _SAFE_SEGMENT.sub("_", job_id)
        safe_label = _SAFE_SEGMENT.sub("_", speaker_label)
        return self.dir / f"{safe_job}__{safe_label}.json"

    def save(
        self,
        job_id: str,
        speaker_label: str,
        vector: np.ndarray,
        total_speech_sec: float,
        claimed_name: Optional[str],
    ) -> None:
        settings = get_settings()
        doc = {
            "job_id": job_id,
            "speaker_label": speaker_label,
            "vector": encrypt_vector(vector.astype(np.float32).tobytes(), settings.voiceprint_enc_key),
            "total_speech_sec": total_speech_sec,
            "claimed_name": claimed_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._path(job_id, speaker_label).write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def get(self, job_id: str, speaker_label: str) -> Optional[dict]:
        p = self._path(job_id, speaker_label)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def get_vector(self, doc: dict) -> np.ndarray:
        settings = get_settings()
        raw = decrypt_vector(doc["vector"], settings.voiceprint_enc_key)
        return np.frombuffer(raw, dtype=np.float32)

    def delete(self, job_id: str, speaker_label: str) -> None:
        p = self._path(job_id, speaker_label)
        if p.exists():
            p.unlink()

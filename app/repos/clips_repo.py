"""Local-filesystem store for registration-clip quality/consistency metadata.

Transient: entries can be purged once a person's voiceprint is built. Raw
audio is never written here -- only derived metrics and (optionally) the
per-clip embedding used for the consistency check.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import get_settings


class ClipsRepo:
    def __init__(self, data_dir: Optional[str] = None):
        settings = get_settings()
        self.dir = Path(data_dir or settings.data_dir) / "registration_clips"
        self.dir.mkdir(parents=True, exist_ok=True)

    def record(self, person_id: str, duration_sec: float, quality_checks: dict) -> dict:
        clip_id = str(uuid.uuid4())
        doc = {
            "_id": clip_id,
            "person_id": person_id,
            "duration_sec": duration_sec,
            "quality_checks": quality_checks,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (self.dir / f"{clip_id}.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
        return doc

    def list_for_person(self, person_id: str) -> list:
        docs = []
        for f in self.dir.glob("*.json"):
            doc = json.loads(f.read_text(encoding="utf-8"))
            if doc.get("person_id") == person_id:
                docs.append(doc)
        return docs

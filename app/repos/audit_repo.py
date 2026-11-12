"""Append-only local audit log (data/audit_log.jsonl), one JSON object per line."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import get_settings


class AuditRepo:
    def __init__(self, data_dir: Optional[str] = None):
        settings = get_settings()
        self.path = Path(data_dir or settings.data_dir) / "audit_log.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        action: str,
        actor_user_id: str,
        target_person_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> dict:
        entry = {
            "_id": str(uuid.uuid4()),
            "action": action,
            "actor_user_id": actor_user_id,
            "target_person_id": target_person_id,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def query(self, limit: int = 100) -> list:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        entries = [json.loads(line) for line in lines[-limit:] if line.strip()]
        entries.reverse()
        return entries

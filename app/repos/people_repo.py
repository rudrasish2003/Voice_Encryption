"""Local-filesystem store for people/voiceprints.

One JSON file per person under <data_dir>/people/<id>.json, plus a
name -> id index file for O(1) uniqueness checks. A MongoDB-backed
implementation can replace this later behind the same interface.
"""
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import get_settings
from app.utils.crypto import decrypt_vector, encrypt_vector

_lock = threading.Lock()


class PeopleRepo:
    def __init__(self, data_dir: Optional[str] = None):
        settings = get_settings()
        self.dir = Path(data_dir or settings.data_dir) / "people"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir / "_name_index.json"
        if not self.index_path.exists():
            self.index_path.write_text("{}", encoding="utf-8")

    def _path(self, person_id: str) -> Path:
        return self.dir / f"{person_id}.json"

    def _load_index(self) -> dict:
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, index: dict) -> None:
        self.index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def name_exists(self, name: str) -> bool:
        with _lock:
            return name.strip().lower() in self._load_index()

    def create(
        self,
        name: str,
        vector: np.ndarray,
        model_version: str,
        built_from_clips: list,
        quality_score: float,
        consent: dict,
        created_by_user_id: str,
    ) -> dict:
        settings = get_settings()
        with _lock:
            index = self._load_index()
            key = name.strip().lower()
            if key in index:
                raise ValueError(f"name '{name}' already registered")

            person_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            doc = {
                "_id": person_id,
                "name": name,
                "voiceprint": {
                    "vector": encrypt_vector(vector.astype(np.float32).tobytes(), settings.voiceprint_enc_key),
                    "model_version": model_version,
                    "built_from_clips": built_from_clips,
                    "quality_score": quality_score,
                    "created_at": now,
                    "updated_at": now,
                },
                "status": "active",
                "consent": {**consent, "withdrawal_at": None},
                "metadata": {"created_by_user_id": created_by_user_id},
            }
            self._path(person_id).write_text(json.dumps(doc, indent=2), encoding="utf-8")
            index[key] = person_id
            self._save_index(index)
            return doc

    def get(self, person_id: str) -> Optional[dict]:
        p = self._path(person_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def get_vector(self, doc: dict) -> np.ndarray:
        settings = get_settings()
        raw = decrypt_vector(doc["voiceprint"]["vector"], settings.voiceprint_enc_key)
        return np.frombuffer(raw, dtype=np.float32)

    def list_all(self, status: Optional[str] = None) -> list:
        docs = []
        for f in self.dir.glob("*.json"):
            if f.name == "_name_index.json":
                continue
            doc = json.loads(f.read_text(encoding="utf-8"))
            if status is None or doc.get("status") == status:
                docs.append(doc)
        return docs

    def list_active(self) -> list:
        return self.list_all(status="active")

    @staticmethod
    def to_public_dict(doc: dict) -> dict:
        """Shape a stored person document for API responses (never the raw vector)."""
        return {
            "id": doc["_id"],
            "name": doc["name"],
            "status": doc["status"],
            "model_version": doc["voiceprint"]["model_version"],
            "quality_score": doc["voiceprint"]["quality_score"],
            "created_at": doc["voiceprint"]["created_at"],
            "consent": doc["consent"],
        }

    def soft_delete(self, person_id: str) -> Optional[dict]:
        with _lock:
            doc = self.get(person_id)
            if doc is None:
                return None
            doc["status"] = "deleted"
            doc["consent"]["withdrawal_at"] = datetime.now(timezone.utc).isoformat()
            self._path(person_id).write_text(json.dumps(doc, indent=2), encoding="utf-8")
            index = self._load_index()
            index.pop(doc["name"].strip().lower(), None)
            self._save_index(index)
            return doc

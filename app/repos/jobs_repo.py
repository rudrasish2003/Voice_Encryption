"""MongoDB-backed job queue for identification jobs.

This is the ONLY thing MongoDB is used for in this phase -- people and
voiceprints live on local disk (see people_repo.py). Workers claim jobs with
an atomic find_one_and_update status transition so two workers never process
the same job.
"""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo import MongoClient, ReturnDocument

from app.config import get_settings


class JobsRepo:
    def __init__(self):
        settings = get_settings()
        self.client = MongoClient(settings.mongo_uri)
        self.db = self.client[settings.mongo_db_name]
        self.collection = self.db["identification_jobs"]
        self.collection.create_index("status")

    def create_job(self, input_meta: dict) -> str:
        doc = {
            "status": "queued",
            "lock": {"worker_id": None, "locked_at": None},
            "input_meta": input_meta,
            "results": [],
            "created_at": datetime.now(timezone.utc),
            "completed_at": None,
        }
        result = self.collection.insert_one(doc)
        return str(result.inserted_id)

    def claim_next_job(self, worker_id: str) -> Optional[dict]:
        doc = self.collection.find_one_and_update(
            {"status": "queued"},
            {
                "$set": {
                    "status": "processing",
                    "lock": {"worker_id": worker_id, "locked_at": datetime.now(timezone.utc)},
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def complete_job(self, job_id: str, results: list) -> None:
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "done", "results": results, "completed_at": datetime.now(timezone.utc)}},
        )

    def fail_job(self, job_id: str, error: str) -> None:
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": "failed",
                    "results": [{"error": error}],
                    "completed_at": datetime.now(timezone.utc),
                }
            },
        )

    def get_job(self, job_id: str) -> Optional[dict]:
        doc = self.collection.find_one({"_id": ObjectId(job_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

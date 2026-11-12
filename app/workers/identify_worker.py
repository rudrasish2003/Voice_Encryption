"""Polls the MongoDB identification_jobs queue and processes jobs.

Run as a separate process: python -m app.workers.identify_worker
"""
import logging
import os
import time
import uuid

from app.config import get_settings
from app.repos.audio_snippets_repo import AudioSnippetsRepo
from app.repos.jobs_repo import JobsRepo
from app.services.identification import identify_file
from app.services.matching import get_matcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("identify_worker")

POLL_INTERVAL_SEC = 2
SNIPPET_CLEANUP_INTERVAL_SEC = 1800  # scan for expired audio snippets every 30 min
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"


def run() -> None:
    jobs_repo = JobsRepo()
    matcher = get_matcher()
    snippets_repo = AudioSnippetsRepo()
    settings = get_settings()
    logger.info("identify worker %s started", WORKER_ID)

    last_cleanup = 0.0
    while True:
        now = time.time()
        if now - last_cleanup > SNIPPET_CLEANUP_INTERVAL_SEC:
            removed = snippets_repo.cleanup_expired(settings.audio_snippet_retention_hours)
            if removed:
                logger.info("cleaned up %d expired audio snippet(s)", removed)
            last_cleanup = now

        job = jobs_repo.claim_next_job(WORKER_ID)
        if job is None:
            time.sleep(POLL_INTERVAL_SEC)
            continue

        job_id = job["_id"]
        stored_path = job["input_meta"]["stored_path"]
        logger.info("processing job %s (%s)", job_id, stored_path)
        try:
            matcher.refresh()
            results = identify_file(stored_path, matcher, job_id)
            jobs_repo.complete_job(job_id, results)
            logger.info("job %s done", job_id)
        except Exception as exc:  # noqa: BLE001 - job failures must not kill the worker loop
            logger.exception("job %s failed", job_id)
            jobs_repo.fail_job(job_id, str(exc))
        finally:
            if os.path.exists(stored_path):
                os.unlink(stored_path)


if __name__ == "__main__":
    run()

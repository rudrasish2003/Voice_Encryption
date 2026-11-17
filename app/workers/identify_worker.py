"""Polls the MongoDB identification_jobs queue and processes jobs.

Run as a separate process: python -m app.workers.identify_worker
"""
import logging
import time
import uuid

from app.config import get_settings
from app.repos.audio_snippets_repo import AudioSnippetsRepo
from app.repos.identify_uploads_repo import cleanup_upload, resolve_to_local_path
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
        input_meta = job.get("input_meta") or {}
        source_desc = input_meta.get("s3_key") or input_meta.get("stored_path") or "<unknown>"
        logger.info("processing job %s (%s)", job_id, source_desc)
        local_path = None
        local_is_temp = False
        try:
            local_path, local_is_temp = resolve_to_local_path(input_meta)
            matcher.refresh()
            results = identify_file(local_path, matcher, job_id)
            jobs_repo.complete_job(job_id, results)
            logger.info("job %s done", job_id)
        except Exception as exc:  # noqa: BLE001 - job failures must not kill the worker loop
            logger.exception("job %s failed", job_id)
            try:
                jobs_repo.fail_job(job_id, str(exc))
            except Exception:  # noqa: BLE001 - even a DB write failure here must not kill the loop
                logger.exception("job %s: also failed to record the failure in Mongo", job_id)
        finally:
            try:
                cleanup_upload(input_meta, local_path=local_path, local_is_temp=local_is_temp)
            except Exception:  # noqa: BLE001
                logger.exception("job %s: failed to clean up input upload", job_id)


if __name__ == "__main__":
    run()

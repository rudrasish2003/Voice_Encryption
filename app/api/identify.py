import os
import tempfile
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.auth.security import require_scopes
from app.config import get_settings
from app.models.schemas import EnrollSpeakerIn, IdentifyJobOut, IdentifySubmitOut, PersonOut
from app.repos.audio_snippets_repo import AudioSnippetsRepo
from app.repos.audit_repo import AuditRepo
from app.repos.jobs_repo import JobsRepo
from app.repos.pending_embeddings_repo import PendingEmbeddingsRepo
from app.repos.people_repo import PeopleRepo
from app.services.matching import get_matcher
from app.services.registration import check_duplicate

router = APIRouter(prefix="/api/v1/identify", tags=["identify"])

jobs_repo = JobsRepo()
audio_snippets_repo = AudioSnippetsRepo()
audit_repo = AuditRepo()
people_repo = PeopleRepo()
pending_embeddings_repo = PendingEmbeddingsRepo()


@router.post("", response_model=IdentifySubmitOut, status_code=status.HTTP_202_ACCEPTED)
async def submit_identification(
    files: List[UploadFile] = File(...),
    payload: dict = Depends(require_scopes("identify:write")),
):
    settings = get_settings()
    upload_dir = os.path.join(settings.data_dir, "pending_uploads")
    os.makedirs(upload_dir, exist_ok=True)

    actor = payload.get("sub", "unknown")
    job_ids = []
    for f in files:
        content = await f.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"reason_code": "unsupported_format", "message": "file exceeds max upload size"},
            )
        suffix = os.path.splitext(f.filename or "")[1] or ".wav"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix, dir=upload_dir)
        with os.fdopen(fd, "wb") as out:
            out.write(content)

        job_id = jobs_repo.create_job({"filename": f.filename, "stored_path": tmp_path, "submitted_by": actor})
        job_ids.append(job_id)

    audit_repo.log("identify", actor, details={"job_ids": job_ids})
    return IdentifySubmitOut(job_ids=job_ids)


@router.get("/jobs/{job_id}", response_model=IdentifyJobOut)
def get_job_status(job_id: str, payload: dict = Depends(require_scopes("identify:read"))):
    doc = jobs_repo.get_job(job_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return IdentifyJobOut(id=doc["_id"], status=doc["status"], results=doc.get("results", []))


@router.get("/jobs/{job_id}/speakers/{speaker_label}/audio")
def get_speaker_audio(
    job_id: str,
    speaker_label: str,
    payload: dict = Depends(require_scopes("identify:read")),
):
    """Streams back a short-lived per-speaker audio snippet for playback in the
    results view. Auto-deleted a few hours after the job runs (see
    AudioSnippetsRepo.cleanup_expired) -- a 404 here often just means it expired.
    """
    path = audio_snippets_repo.get_path(job_id, speaker_label)
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason_code": "snippet_not_found", "message": "audio snippet missing or expired"},
        )
    return FileResponse(path, media_type="audio/wav")


@router.post("/speakers/enroll", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def enroll_speaker_from_job(
    body: EnrollSpeakerIn,
    payload: dict = Depends(require_scopes("people:write", "identify:read")),
):
    """Human-confirmed enrollment: a speaker from a past identify job, not
    auto-matched or auto-enrolled, gets added to the library by explicit choice
    (e.g. clicking "Add to Library" in the UI) rather than silently.
    """
    pending = pending_embeddings_repo.get(body.job_id, body.speaker_label)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "reason_code": "pending_embedding_not_found",
                "message": "no pending voice sample for this job/speaker (already enrolled, expired, or never eligible)",
            },
        )

    name = body.name.strip()
    if not name or not body.consent_given_by.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason_code": "invalid_input", "message": "name and consent_given_by are required"},
        )
    if people_repo.name_exists(name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason_code": "duplicate_name", "message": "name already registered"},
        )

    vector = pending_embeddings_repo.get_vector(pending)
    dup = check_duplicate(people_repo, vector)
    if dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason_code": "duplicate_voice",
                "message": f"matches existing person '{dup['name']}'",
                "score": dup["score"],
            },
        )

    settings = get_settings()
    actor = payload.get("sub", "unknown")
    doc = people_repo.create(
        name=name,
        vector=vector,
        model_version=settings.embedding_model,
        built_from_clips=[],
        quality_score=1.0,
        consent={
            "given_by": body.consent_given_by.strip(),
            "given_at": datetime.now(timezone.utc).isoformat(),
            "method": f"{body.consent_method.strip()} (confirmed from identify job {body.job_id}, "
            f"{pending['total_speech_sec']:.1f}s speech)",
        },
        created_by_user_id=actor,
    )
    pending_embeddings_repo.delete(body.job_id, body.speaker_label)
    get_matcher().refresh()
    audit_repo.log(
        "register",
        actor,
        target_person_id=doc["_id"],
        details={"source": "identify_tab_manual_enroll", "job_id": body.job_id, "speaker_label": body.speaker_label},
    )
    return PeopleRepo.to_public_dict(doc)

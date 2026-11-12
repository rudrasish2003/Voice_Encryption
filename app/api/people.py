import os
import tempfile
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.auth.security import require_scopes
from app.config import get_settings
from app.models.schemas import PersonOut
from app.repos.audit_repo import AuditRepo
from app.repos.clips_repo import ClipsRepo
from app.repos.people_repo import PeopleRepo
from app.services.matching import get_matcher
from app.services.registration import RegistrationError, build_voiceprint, check_duplicate

router = APIRouter(prefix="/api/v1/people", tags=["people"])

people_repo = PeopleRepo()
clips_repo = ClipsRepo()
audit_repo = AuditRepo()


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def register_person(
    name: str = Form(...),
    consent_given_by: str = Form(...),
    consent_method: str = Form(...),
    files: List[UploadFile] = File(...),
    payload: dict = Depends(require_scopes("people:write")),
):
    if people_repo.name_exists(name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason_code": "duplicate_name", "message": "name already registered"},
        )

    temp_paths: list[str] = []
    try:
        for f in files:
            suffix = os.path.splitext(f.filename or "")[1] or ".wav"
            fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            with os.fdopen(fd, "wb") as out:
                out.write(await f.read())
            temp_paths.append(tmp_path)

        try:
            vector, quality_score, analyses = build_voiceprint(temp_paths)
        except RegistrationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"reason_code": e.reason_code, "message": str(e)},
            )

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
            quality_score=quality_score,
            consent={
                "given_by": consent_given_by,
                "given_at": datetime.now(timezone.utc).isoformat(),
                "method": consent_method,
            },
            created_by_user_id=actor,
        )

        for a in analyses:
            clips_repo.record(doc["_id"], a.speech_duration_sec, a.quality_checks())

        get_matcher().refresh()
        audit_repo.log("register", actor, target_person_id=doc["_id"])
        return _public_person(doc)
    finally:
        for p in temp_paths:
            if os.path.exists(p):
                os.unlink(p)


@router.get("", response_model=list[PersonOut])
def list_people(payload: dict = Depends(require_scopes("people:read"))):
    return [_public_person(p) for p in people_repo.list_active()]


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: str, payload: dict = Depends(require_scopes("people:read"))):
    doc = people_repo.get(person_id)
    if doc is None or doc["status"] != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person not found")
    return _public_person(doc)


@router.delete("/{person_id}")
def delete_person(person_id: str, payload: dict = Depends(require_scopes("people:delete"))):
    doc = people_repo.soft_delete(person_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person not found")
    get_matcher().refresh()
    actor = payload.get("sub", "unknown")
    audit_repo.log("delete", actor, target_person_id=person_id)
    audit_repo.log("consent_withdraw", actor, target_person_id=person_id)
    return {"status": "deleted"}


_public_person = PeopleRepo.to_public_dict

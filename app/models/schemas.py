from typing import Optional

from pydantic import BaseModel, ConfigDict


class ConsentOut(BaseModel):
    given_by: str
    given_at: str
    method: str
    withdrawal_at: Optional[str] = None


class PersonOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    name: str
    status: str
    model_version: str
    quality_score: float
    created_at: str
    consent: ConsentOut


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class IdentifySubmitOut(BaseModel):
    job_ids: list[str]


class SpeakerMatchOut(BaseModel):
    person_id: Optional[str]
    name: Optional[str]
    score: float
    runner_up_score: float
    decision: str


class SpeakerResultOut(BaseModel):
    speaker_label: str
    segments: list[dict]
    total_speech_sec: float
    match: SpeakerMatchOut


class IdentifyJobOut(BaseModel):
    id: str = ""
    status: str
    results: list[dict] = []


class EnrollSpeakerIn(BaseModel):
    job_id: str
    speaker_label: str
    name: str
    consent_given_by: str
    consent_method: str

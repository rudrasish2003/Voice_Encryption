from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000

    # Local filesystem storage root for people/voiceprints/audit log.
    data_dir: str = "./data"

    # MongoDB is used ONLY as the background job queue (identification_jobs).
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "voice_biometric"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    admin_username: str = "admin"
    admin_password: str = "changeme"

    voiceprint_enc_key: str

    hf_token: str = ""

    diarization_model: str = "pyannote/speaker-diarization-3.1"
    embedding_model: str = "speechbrain/spkrec-ecapa-voxceleb"

    match_threshold: float = 0.70
    runner_up_margin: float = 0.08
    # Share of a registration clip's detected speech the top speaker must hold to be
    # treated as "really just one person" despite diarization emitting >1 label.
    dominant_speaker_min_ratio: float = 0.70
    min_registration_speech_sec: float = 30.0
    min_identify_speech_sec: float = 3.0
    max_identify_speech_sec: float = 60.0

    max_upload_duration_sec: int = 1800
    max_upload_size_mb: int = 200

    # --- Spoken self-introduction labeling ("I am Sanjana" / "Mr. X please speak") ---
    # A spoken name is only ever shown as a suggestion (decision "claimed_unverified")
    # for a human to confirm via "Add to Library" -- never auto-enrolled, regardless
    # of how much speech was collected.
    enable_spoken_name_labeling: bool = True
    whisper_model: str = "base"

    # Per-speaker audio snippets kept only so a reviewer can play back a speaker's
    # voice at the results screen; auto-deleted by the worker after this many hours.
    audio_snippet_retention_hours: float = 6.0


@lru_cache
def get_settings() -> Settings:
    return Settings()

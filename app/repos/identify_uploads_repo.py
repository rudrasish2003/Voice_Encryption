"""Storage for queued identification input audio (API -> worker handoff).

Supports local filesystem (<data_dir>/pending_uploads) for shared-disk setups and
S3 for deployments where API and worker do not share a filesystem. Workers always
receive a local temp file path for ffmpeg/processing (S3 objects are downloaded
to temp files).
"""
import os
import tempfile
import uuid
from typing import Optional

from app.config import get_settings


def _get_s3_client(settings):
    import boto3

    kwargs = {}
    if settings.s3_region:
        kwargs["region_name"] = settings.s3_region
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **kwargs)


def _s3_key_for(filename: Optional[str], settings) -> str:
    suffix = os.path.splitext(filename or "")[1] or ".bin"
    prefix = (settings.s3_prefix or "identify/pending_uploads/").lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return f"{prefix}{uuid.uuid4().hex}{suffix}"


def store_upload(content: bytes, filename: Optional[str]) -> dict:
    """Persist an identify upload and return job input_meta fields.

    Returns a dict to merge into job input_meta, e.g.
      local: {"storage": "local", "stored_path": "...", "filename": ...}
      s3:    {"storage": "s3", "s3_bucket": "...", "s3_key": "...", "filename": ...}
    """
    settings = get_settings()
    backend = (settings.identify_upload_backend or "local").lower()

    if backend == "s3":
        if not settings.s3_bucket or not settings.s3_region:
            raise RuntimeError("S3 identify upload storage requires S3_BUCKET and S3_REGION to be set")
        key = _s3_key_for(filename, settings)
        client = _get_s3_client(settings)
        client.put_object(Bucket=settings.s3_bucket, Key=key, Body=content)
        return {
            "storage": "s3",
            "s3_bucket": settings.s3_bucket,
            "s3_key": key,
            "filename": filename,
        }

    # local backend (default)
    upload_dir = os.path.join(settings.data_dir, "pending_uploads")
    os.makedirs(upload_dir, exist_ok=True)
    suffix = os.path.splitext(filename or "")[1] or ".wav"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix, dir=upload_dir)
    with os.fdopen(fd, "wb") as out:
        out.write(content)
    return {"storage": "local", "stored_path": tmp_path, "filename": filename}


def resolve_to_local_path(input_meta: dict) -> tuple[str, bool]:
    """Return (local_path, is_temp) for processing.

    For S3-backed inputs, downloads to a temp file and returns (path, True).
    For local/legacy inputs, returns (stored_path, False).
    """
    settings = get_settings()
    storage = input_meta.get("storage")

    # Legacy jobs stored only stored_path
    if storage == "s3" or ("s3_key" in input_meta and "stored_path" not in input_meta):
        bucket = input_meta.get("s3_bucket") or settings.s3_bucket
        key = input_meta.get("s3_key")
        if not bucket or not key:
            raise RuntimeError("S3-backed job is missing s3_bucket/s3_key")
        client = _get_s3_client(settings)
        suffix = os.path.splitext(key)[1] or ".bin"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            client.download_file(bucket, key, tmp_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        return tmp_path, True

    stored_path = input_meta.get("stored_path")
    if not stored_path:
        raise RuntimeError("job input_meta is missing stored_path/s3_key")
    return stored_path, False


def cleanup_upload(input_meta: dict, local_path: Optional[str] = None, local_is_temp: bool = False) -> None:
    """Best-effort cleanup of source upload and any materialized temp file."""
    settings = get_settings()
    storage = input_meta.get("storage")

    # Remove materialized temp download (S3 case)
    if local_is_temp and local_path and os.path.exists(local_path):
        try:
            os.unlink(local_path)
        except OSError:
            pass

    if storage == "s3" or ("s3_key" in input_meta and "stored_path" not in input_meta):
        bucket = input_meta.get("s3_bucket") or settings.s3_bucket
        key = input_meta.get("s3_key")
        if bucket and key:
            try:
                client = _get_s3_client(settings)
                client.delete_object(Bucket=bucket, Key=key)
            except Exception:
                pass
        return

    # Local/legacy: delete stored file (may be same as local_path when not temp)
    stored_path = input_meta.get("stored_path")
    if stored_path and os.path.exists(stored_path):
        try:
            os.unlink(stored_path)
        except OSError:
            pass

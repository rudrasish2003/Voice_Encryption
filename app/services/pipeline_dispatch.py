"""Single seam choosing local CPU execution vs. the Modal GPU pipeline for
diarization / transcription / embedding, based on settings.use_modal_gpu.

registration.py and identification.py import from HERE, never directly from
diarization.py / transcription.py / embedding.py / gpu_client.py -- so the
GPU-or-not decision lives in exactly one place.
"""
import numpy as np

from app.config import get_settings


def diarize(wav_path: str, model_name: str, hf_token: str) -> list[dict]:
    if get_settings().use_modal_gpu:
        from app.services.gpu_client import diarize_remote

        return diarize_remote(wav_path)
    try:
        from app.services.diarization import diarize as _local_diarize
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Local ML dependencies are not installed (missing module: "
            f"{e.name}). Set USE_MODAL_GPU=true to use the Modal GPU pipeline, "
            "or rebuild/install with local ML support (e.g. Docker build arg WITH_LOCAL_ML=true "
            "or `uv sync --extra local-ml`)."
        ) from e

    return _local_diarize(wav_path, model_name, hf_token)


def transcribe(wav_path: str, model_name: str) -> list[dict]:
    """`model_name` is ignored on the Modal path -- the GPU container uses its own
    fixed, more capable model (see modal_app.py's WHISPER_MODEL) now that GPU
    removes the speed penalty of a larger model.
    """
    if get_settings().use_modal_gpu:
        from app.services.gpu_client import transcribe_remote

        return transcribe_remote(wav_path)
    try:
        from app.services.transcription import transcribe as _local_transcribe
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Local ML dependencies are not installed (missing module: "
            f"{e.name}). Set USE_MODAL_GPU=true to use the Modal GPU pipeline, "
            "or rebuild/install with local ML support (e.g. Docker build arg WITH_LOCAL_ML=true "
            "or `uv sync --extra local-ml`)."
        ) from e

    return _local_transcribe(wav_path, model_name)


def embed_waveform(samples: np.ndarray, sr: int, model_name: str) -> np.ndarray:
    return embed_batch([samples], sr, model_name)[0]


def embed_batch(samples_list: list[np.ndarray], sr: int, model_name: str) -> list[np.ndarray]:
    """Embeds several speaker clips. On the Modal path, this is one container
    call for all of them rather than N separate round-trips.
    """
    if not samples_list:
        return []
    if get_settings().use_modal_gpu:
        from app.services.gpu_client import embed_batch_remote

        return embed_batch_remote(samples_list, sr)
    try:
        from app.services.embedding import embed_waveform as _local_embed
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Local ML dependencies are not installed (missing module: "
            f"{e.name}). Set USE_MODAL_GPU=true to use the Modal GPU pipeline, "
            "or rebuild/install with local ML support (e.g. Docker build arg WITH_LOCAL_ML=true "
            "or `uv sync --extra local-ml`)."
        ) from e

    return [_local_embed(s, sr, model_name) for s in samples_list]

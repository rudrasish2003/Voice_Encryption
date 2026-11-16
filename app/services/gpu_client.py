"""Client for the Modal-deployed GPU pipeline (see modal_app.py, project root).

Only used when settings.use_modal_gpu is true (see pipeline_dispatch.py) --
ships audio bytes to a Modal GPU container and returns the same data shapes
the local CPU functions return, so callers never need to know which path ran.
"""
import logging
import time
from functools import lru_cache
from io import BytesIO

import numpy as np
import soundfile as sf

from app.config import get_settings

logger = logging.getLogger("identify_worker")


@lru_cache(maxsize=1)
def _get_pipeline_cls():
    import modal

    settings = get_settings()
    cls = modal.Cls.from_name(settings.modal_app_name, "GPUPipeline")
    return cls()


def diarize_remote(wav_path: str) -> list[dict]:
    with open(wav_path, "rb") as f:
        audio_bytes = f.read()
    t0 = time.monotonic()
    result = _get_pipeline_cls().diarize.remote(audio_bytes)
    logger.info(
        "modal diarize: %.1fs round-trip (%d KB uploaded, container cold-start adds ~228s if cache was empty)",
        time.monotonic() - t0, len(audio_bytes) // 1024,
    )
    return result


def transcribe_remote(wav_path: str) -> list[dict]:
    with open(wav_path, "rb") as f:
        audio_bytes = f.read()
    t0 = time.monotonic()
    result = _get_pipeline_cls().transcribe.remote(audio_bytes)
    logger.info("modal transcribe: %.1fs round-trip (%d KB uploaded)", time.monotonic() - t0, len(audio_bytes) // 1024)
    return result


def embed_batch_remote(samples_list: list[np.ndarray], sr: int) -> list[np.ndarray]:
    clips = []
    for samples in samples_list:
        buf = BytesIO()
        sf.write(buf, samples, sr, format="WAV")
        clips.append(buf.getvalue())
    t0 = time.monotonic()
    vectors = _get_pipeline_cls().embed_batch.remote(clips)
    logger.info("modal embed_batch: %.1fs round-trip (%d clip(s))", time.monotonic() - t0, len(clips))
    return [np.array(v, dtype=np.float32) for v in vectors]

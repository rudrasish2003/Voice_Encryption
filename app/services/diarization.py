"""Speaker diarization via a pretrained pyannote.audio pipeline (CPU-only)."""
from functools import lru_cache

from app.utils.torch_compat import patch_torch_load


@lru_cache(maxsize=1)
def _get_pipeline(model_name: str, hf_token: str):
    patch_torch_load()
    from pyannote.audio import Pipeline

    pipeline = Pipeline.from_pretrained(model_name, use_auth_token=hf_token or None)
    return pipeline


def diarize(wav_path: str, model_name: str, hf_token: str) -> list[dict]:
    """Returns [{"speaker": "SPEAKER_00", "start": 1.2, "end": 4.5}, ...]."""
    pipeline = _get_pipeline(model_name, hf_token)
    diarization = pipeline(wav_path)
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append({"speaker": speaker, "start": float(turn.start), "end": float(turn.end)})
    return segments

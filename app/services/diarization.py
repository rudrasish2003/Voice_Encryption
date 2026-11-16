"""Speaker diarization via a pretrained pyannote.audio pipeline.

CPU by default. The `device` param exists so this exact code can also run
inside the Modal GPU container (see modal_app.py), which imports and calls
these same functions with device="cuda" -- one implementation, two places it
runs, rather than a separate GPU-side reimplementation to keep in sync.
"""
from functools import lru_cache

from app.config import get_settings
from app.utils.torch_compat import patch_torch_load


@lru_cache(maxsize=4)
def _get_pipeline(model_name: str, hf_token: str, device: str = "cpu"):
    patch_torch_load()
    import torch
    from pyannote.audio import Pipeline

    pipeline = Pipeline.from_pretrained(model_name, use_auth_token=hf_token or None)
    if device != "cpu":
        pipeline.to(torch.device(device))
    return pipeline


def diarize(wav_path: str, model_name: str, hf_token: str, device: str = "cpu") -> list[dict]:
    """Returns [{"speaker": "SPEAKER_00", "start": 1.2, "end": 4.5}, ...].

    Uses min/max_speakers hints to bound VBx clustering search and reduce EM iterations on CPU.
    """
    settings = get_settings()
    pipeline = _get_pipeline(model_name, hf_token, device)
    diarization = pipeline(
        wav_path,
        min_speakers=settings.diarization_min_speakers,
        max_speakers=settings.diarization_max_speakers,
    )
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append({"speaker": speaker, "start": float(turn.start), "end": float(turn.end)})
    return segments

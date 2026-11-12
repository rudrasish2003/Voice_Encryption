"""Speech-to-text via openai-whisper (CPU-only).

Used only to catch spoken self-/other-introductions ("I am X", "this is X
speaking", "Mr. X, please speak") so a voice can be auto-labeled the first
time someone introduces themselves on a call. Not used for anything else --
transcript text/accuracy isn't otherwise part of this system.
"""
from functools import lru_cache

from app.utils.torch_compat import patch_torch_load


@lru_cache(maxsize=1)
def _get_model(model_name: str):
    patch_torch_load()
    import whisper

    return whisper.load_model(model_name, device="cpu")


def transcribe(wav_path: str, model_name: str) -> list[dict]:
    """Returns [{"start": float, "end": float, "text": str}, ...] segments."""
    model = _get_model(model_name)
    result = model.transcribe(wav_path, fp16=False)
    return [
        {"start": float(seg["start"]), "end": float(seg["end"]), "text": seg["text"].strip()}
        for seg in result.get("segments", [])
    ]

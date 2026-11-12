"""Speaker-embedding extraction via SpeechBrain's ECAPA-TDNN model (CPU-only).

Embeddings are L2-normalized so cosine similarity reduces to a dot product
(see matching.py).
"""
from functools import lru_cache

import numpy as np

from app.utils.torch_compat import patch_torch_load


@lru_cache(maxsize=1)
def _get_model(model_name: str):
    patch_torch_load()
    from speechbrain.inference.speaker import EncoderClassifier
    from speechbrain.utils.fetching import LocalStrategy

    savedir = f"pretrained_models/{model_name.replace('/', '_')}"
    return EncoderClassifier.from_hparams(
        source=model_name,
        savedir=savedir,
        run_opts={"device": "cpu"},
        # Symlinking the HF cache into savedir needs Developer Mode / admin on
        # Windows; copy the files instead so this works out of the box.
        local_strategy=LocalStrategy.COPY,
    )


def embed_waveform(samples: np.ndarray, sr: int, model_name: str) -> np.ndarray:
    import torch

    if sr != 16000:
        raise ValueError(f"expected 16kHz audio, got {sr}Hz -- normalize first")

    model = _get_model(model_name)
    tensor = torch.from_numpy(np.ascontiguousarray(samples)).float().unsqueeze(0)
    with torch.no_grad():
        emb = model.encode_batch(tensor)
    vec = emb.squeeze().cpu().numpy().astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec

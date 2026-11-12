"""Windows/version compatibility shims for loading pyannote.audio / speechbrain models.

Two unrelated problems, both triggered only on first run:

1. torch 2.6 flipped torch.load's default to weights_only=True, which rejects
   pickled objects (e.g. torch.torch_version.TorchVersion) inside pyannote's and
   speechbrain's official checkpoints. Those checkpoints come from HF repos we
   explicitly authenticate against (gated, user-accepted), so defaulting back to
   weights_only=False here is the same trust boundary the models already
   crossed to get authenticated access -- not a new risk.

2. speechbrain's Pretrainer links HF-cached model files into its local savedir
   with os.symlink, which needs Developer Mode or admin on Windows. Falling
   back to a plain copy when symlinking isn't permitted avoids requiring every
   dev machine to change a Windows setting just to run this locally.
"""
import os
import shutil
from pathlib import Path

import torch

_patched = False


def patch_torch_load() -> None:
    global _patched
    if _patched:
        return

    original_load = torch.load

    def _patched_load(*args, **kwargs):
        # Force False rather than setdefault: callers (e.g. lightning_fabric)
        # pass weights_only explicitly, even when their own default is None/True.
        kwargs["weights_only"] = False
        return original_load(*args, **kwargs)

    torch.load = _patched_load

    original_symlink = os.symlink

    def _patched_symlink(src, dst, *args, **kwargs):
        try:
            return original_symlink(src, dst, *args, **kwargs)
        except OSError:
            if Path(src).is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    os.symlink = _patched_symlink

    _patched = True

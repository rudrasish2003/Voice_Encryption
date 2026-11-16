"""Modal GPU-backed diarization + transcription + speaker embedding.

Deploy / redeploy with:
    modal deploy modal_app.py

Redeploy whenever this file changes, or when app/services/embedding.py changes
(mounted and reused here, invoked with device="cuda", so local CPU runs and
Modal GPU runs always share the same embedding implementation).

Diarization is NOT shared with the local CPU path: this runs pyannote 4.x's
"speaker-diarization-community-1" pipeline (VBx clustering -- meaningfully
better quality than 3.x's agglomerative clustering), which needs a newer
pyannote.audio/torch than our local Windows CPU setup is pinned to, and the
two major pyannote versions can't coexist in one Python environment. So this
is a separate, Modal-only implementation -- same pattern as transcription
already uses (faster-whisper here vs. openai-whisper locally).

Scaling: min_containers=0 (the default) means this scales to zero when idle --
GPU is billed only while a container is warm processing requests, plus a
short `scaledown_window` buffer afterward in case more work arrives, not
continuously. The HF_TOKEN needed to download the gated pyannote models comes
from the Modal secret "voice-biometric-hf-token" (created via
`modal secret create voice-biometric-hf-token HF_TOKEN=<your token>`) -- the
app's local AES encryption key for voiceprints is deliberately never sent
here; this returns raw embedding vectors and the caller encrypts them locally.
"""
import modal

app = modal.App("voice-biometric-gpu")

DIARIZATION_MODEL = "pyannote/speaker-diarization-community-1"  # pyannote 4.x, VBx clustering
EMBEDDING_MODEL = "speechbrain/spkrec-ecapa-voxceleb"
WHISPER_MODEL = "medium"  # faster-whisper model size; GPU makes this fast enough to use by default
MIN_SPEAKERS_HINT = 1
MAX_SPEAKERS_HINT = 6  # bounds VBx clustering's search space; was 10, tightened after measuring
                       # multi-minute round-trips on real multi-speaker audio -- EM iterations
                       # scale with the search space, so this materially cuts clustering time

# Persists downloaded model weights (pyannote, speechbrain, faster-whisper) across
# cold starts. Without this, every scale-from-zero re-downloads several GB of
# weights -- measured ~228s on an empty cache vs. ~2s once cached -- which would
# otherwise turn "GPU only while processing" into "mostly paying to re-download
# the same models".
model_cache = modal.Volume.from_name("voice-biometric-model-cache", create_if_missing=True)
CACHE_DIR = "/cache"

image = (
    modal.Image.debian_slim(python_version="3.11")
    # Plain apt_install("ffmpeg") also pulls in ffmpeg's *recommended* packages --
    # a full GTK/X11/PulseAudio/Mesa desktop stack we don't need headless, which
    # makes the build dramatically slower (and flaky) for no benefit.
    .run_commands("apt-get update", "apt-get install -y --no-install-recommends ffmpeg")
    .pip_install(
        "torch==2.8.0",
        "torchaudio==2.8.0",
        # pyannote.audio pulls in torchcodec unpinned, which defaults to the latest
        # release -- that release (0.17.0) expects CUDA 13's libnvrtc.so.13, but
        # torch==2.8.0 bundles CUDA 12.8. 0.7.0 is the release actually matched to
        # torch 2.8 (see https://github.com/pytorch/torchcodec compatibility table).
        "torchcodec==0.7.0",
        "numpy>=2.1.3",
        "soundfile>=0.13.1",
        "pyannote.audio==4.0.4",  # requires huggingface_hub>=0.28.1, torch>=2.8.0, matplotlib>=3.10.0
        "huggingface_hub==0.28.1",
        "matplotlib>=3.10.0",
        "speechbrain==1.0.2",
        "faster-whisper==1.1.0",
    )
    .add_local_python_source("app")  # ships app/services/embedding.py + app/utils/torch_compat.py
)


@app.cls(
    image=image,
    # T4 instead of L4: L4 capacity on Modal was queuing requests for 200-500s+
    # ("waiting to be scheduled on a GPU_L4 worker") before any code even ran --
    # that queue wait, not compute, was the actual bottleneck. T4 has far better
    # availability and is plenty for diarization/embedding/whisper-medium.
    gpu="T4",
    cpu=8.0,  # VBx clustering (diarize) is CPU-bound EM iteration, not GPU inference.
    secrets=[modal.Secret.from_name("voice-biometric-hf-token")],
    scaledown_window=120,  # keep a container warm 2min after its last request, then scale to zero
    min_containers=0,  # no GPU billed at all while idle
    volumes={CACHE_DIR: model_cache},
)
class GPUPipeline:
    @modal.enter()
    def load_models(self):
        import os

        # Set these BEFORE importing anything that touches huggingface_hub (including
        # transitively, e.g. faster_whisper) -- several libraries read HF_HOME into a
        # module-level constant at import time, so setting it after import is too late.
        os.environ["HF_HOME"] = f"{CACHE_DIR}/huggingface"
        os.chdir(CACHE_DIR)  # so embedding.py's relative "pretrained_models/..." savedir lands here too

        import torch
        from pyannote.audio import Pipeline

        from app.services.embedding import _get_model as _get_embed_model
        from faster_whisper import WhisperModel

        hf_token = os.environ["HF_TOKEN"]

        self._diar_pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL, token=hf_token)
        self._diar_pipeline.to(torch.device("cuda"))

        # Pre-warm the same lru_cache-backed getter embed_waveform() uses, so the
        # container isn't marked ready until the embedding model is actually loaded.
        _get_embed_model(EMBEDDING_MODEL, device="cuda")
        self._whisper = WhisperModel(
            WHISPER_MODEL, device="cuda", compute_type="float16", download_root=f"{CACHE_DIR}/faster_whisper"
        )
        model_cache.commit()

    @modal.method()
    def diarize(self, audio_bytes: bytes) -> list[dict]:
        """Returns [{"speaker": "SPEAKER_00", "start": 1.2, "end": 4.5}, ...].

        No exact num_speakers hint (unlike the reference notebook's hardcoded
        num_speakers=4) -- we don't know speaker count ahead of time for general
        use. min/max_speakers just bounds VBx clustering's search space without
        forcing an exact count.
        """
        import os

        path = _write_temp_wav(audio_bytes)
        try:
            result = self._diar_pipeline(
                path, min_speakers=MIN_SPEAKERS_HINT, max_speakers=MAX_SPEAKERS_HINT
            )
            # pyannote 4.x wraps the Annotation in a DiarizeOutput; fall back to
            # treating the result as the Annotation directly in case that changes.
            diarization = getattr(result, "speaker_diarization", result)
            return [
                {"speaker": speaker, "start": float(turn.start), "end": float(turn.end)}
                for turn, _, speaker in diarization.itertracks(yield_label=True)
            ]
        finally:
            os.unlink(path)

    @modal.method()
    def transcribe(self, audio_bytes: bytes) -> list[dict]:
        import os

        path = _write_temp_wav(audio_bytes)
        try:
            segments, _info = self._whisper.transcribe(path, word_timestamps=False)
            return [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()} for s in segments]
        finally:
            os.unlink(path)

    @modal.method()
    def embed_batch(self, audio_clips: list[bytes]) -> list[list[float]]:
        """Embeds several speaker clips in one container call (cheaper than N round-trips)."""
        import os

        from app.services.embedding import embed_waveform
        from app.utils.audio import read_audio

        vectors = []
        for clip_bytes in audio_clips:
            path = _write_temp_wav(clip_bytes)
            try:
                samples, sr = read_audio(path)
                vec = embed_waveform(samples, sr, EMBEDDING_MODEL, device="cuda")
                vectors.append(vec.tolist())
            finally:
                os.unlink(path)
        return vectors


def _write_temp_wav(audio_bytes: bytes) -> str:
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".wav")
    import os

    with os.fdopen(fd, "wb") as f:
        f.write(audio_bytes)
    return path

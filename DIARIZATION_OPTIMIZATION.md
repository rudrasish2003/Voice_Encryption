# Diarization Speed Optimization Guide

## 🎯 Target
- **Current**: 2-3 min audio → 3-5+ minutes (CPU bottleneck)
- **Goal**: 2-3 min audio → 30-40 seconds
- **Status**: Achievable with optimizations below

---

## ⚡ Option 1: Enable Modal GPU (Recommended - 10-50x faster)

### Why GPU is fastest
- Pyannote 4.x on GPU: **~30-40s for 2-3 min audio** ✓
- CPU implementation on same hardware: **5-10 min**
- Your code already has this infrastructure built, just needs enabling

### Setup (3 steps, one-time)

**Step 1: Set environment variable**
```bash
# In .env file
USE_MODAL_GPU=true
```

**Step 2: Deploy Modal app**
```bash
# First time only
modal deploy modal_app.py
```

**Step 3: Create Modal secret**
```bash
# First time only; replace <token> with your HuggingFace token
modal secret create voice-biometric-hf-token HF_TOKEN=<your-token>
```

### Benefits
- ✅ Same code path (pipeline_dispatch.py automatically routes to GPU)
- ✅ Better quality (pyannote 4.x with VBx clustering)
- ✅ Scales to zero when idle (no GPU cost when not processing)
- ✅ Handles embedding/transcription faster too

### Cost
- ~$0.30-0.50 per hour of active GPU time (L4 GPU)
- With scaledown_window=120s, idle time costs nothing
- Typical meeting: 2-3 min processing → ~$0.001-0.002

---

## 📊 Option 2: CPU-side Optimizations (2-3x faster, no GPU)

**Already applied to your code:**

### 1. Speaker count hints
```python
# In diarization.py - now reads from config
pipeline(
    wav_path,
    min_speakers=1,  # Skip clustering if clearly single speaker
    max_speakers=4,  # Realistic meeting size, reduces EM iterations
)
```

- **Effect**: 2-3x speedup on CPU by reducing clustering iterations
- **Tradeoff**: Assumes ≤4 unique speakers (adjust in config if needed)

### 2. Configuration tuning
```python
# In .env or config.py - tune these for your use case
DIARIZATION_MIN_SPEAKERS=1
DIARIZATION_MAX_SPEAKERS=4
```

- Lower `max_speakers` → faster (more constrained search)
- Raise `max_speakers` if you have meetings with 5+ speakers

---

## 🎛️ Option 3: Advanced CPU Optimizations (if GPU unavailable)

### A. Audio Preprocessing (10-20% speedup)
```python
# Resample to 16kHz if audio is 48kHz
# Remove long silences before diarization
# Normalize audio level
```

### B. Smaller model options (not recommended for quality)
```python
# Instead of "pyannote/speaker-diarization-3.1"
# Not available on CPU in 4.x, but could use other models
```

### C. Parallel segment processing (advanced, risky)
- Process audio in overlapping chunks in parallel
- Requires careful overlap management to avoid speaker splits
- Not recommended without rigorous testing

---

## 📈 Performance Comparison

| Method | Audio | Time | Quality | Cost |
|--------|-------|------|---------|------|
| CPU baseline | 2-3 min | 5-10 min | Good | $0 |
| CPU + hints | 2-3 min | 2-3 min | Good | $0 |
| **GPU (recommended)** | **2-3 min** | **30-40s** | **Better** | **~$0.002** |

---

## ✅ Next Steps

1. **Quick win**: Current CPU optimization (min/max_speakers) is already applied
   - Test and measure improvement: `time python -m app.services.diarization`

2. **Recommended**: Set up Modal GPU
   - Execute the 3 setup steps above
   - Verify with: `modal status`

3. **Monitor**: Track actual processing times
   - Add timing logs to `registration.py` and `identification.py`
   - Compare before/after with real test files

---

## 🔧 Configuration Reference

### In `.env` or config.py:

```ini
# Enable GPU-backed diarization
USE_MODAL_GPU=true

# Or tune CPU for your meeting size
DIARIZATION_MIN_SPEAKERS=1
DIARIZATION_MAX_SPEAKERS=4

# For GPU, the model is fixed to pyannote 4.x community model
# For CPU, this controls the local model
DIARIZATION_MODEL=pyannote/speaker-diarization-3.1
```

---

## 🐛 Troubleshooting

**"GPU processing timed out"**
- Check Modal app is deployed: `modal status`
- Verify secret exists: `modal secret list`
- Logs: `modal logs <app-name>`

**"Still slow on CPU"**
- Verify `min_speakers` and `max_speakers` are being used
- Check if CPU is heavily loaded (other processes)
- Monitor: `python -c "import psutil; print(psutil.cpu_percent(interval=1))"`

**"Quality degraded"**
- If using max_speakers < 3, increase it
- GPU path (Option 1) has better clustering, try that
- Verify input audio quality (no artifacts, clear speech)

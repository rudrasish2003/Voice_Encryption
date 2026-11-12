# Voice Identification System

Phase 1 (registration) + Phase 2 (identification) scaffold. See `IMPLEMENTATION_PLAN.md`
for the full design and phase breakdown.

## Storage model

- **Local filesystem** (`data/`): people, voiceprints (AES-GCM encrypted), registration-clip
  quality metadata, and the audit log. No raw audio is ever persisted.
- **MongoDB**: used ONLY as the background job queue (`identification_jobs` collection) for
  async identification requests.

## Prerequisites

- Python 3.11
- `ffmpeg` installed and on PATH (audio normalization)
- Docker (to run MongoDB locally), or a MongoDB instance you already have
- A Hugging Face account + access token with the pyannote speaker-diarization model terms
  accepted (https://huggingface.co/pyannote/speaker-diarization-3.1)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

cp .env.example .env
python scripts/generate_keys.py   # paste JWT_SECRET and VOICEPRINT_ENC_KEY into .env
# also set ADMIN_PASSWORD and HF_TOKEN in .env

docker compose up -d              # starts MongoDB for the job queue
```

## Run

```bash
# API server
uvicorn app.main:app --reload --port 8000

# Background worker (separate terminal) -- processes /identify jobs
python -m app.workers.identify_worker
```

## Using it

1. Get a token:
   `POST /api/v1/token` (form body: `username`, `password` from `.env`)
2. Register a person:
   `POST /api/v1/people` (multipart: `name`, `consent_given_by`, `consent_method`, `files`)
3. Submit audio for identification:
   `POST /api/v1/identify` (multipart: `files`) -> returns `job_ids`
4. Poll the result:
   `GET /api/v1/identify/jobs/{job_id}`

All decision thresholds (`MATCH_THRESHOLD`, `RUNNER_UP_MARGIN`, etc.) live in `.env` — see
`IMPLEMENTATION_PLAN.md` Section 4. They are placeholders until Phase 3 tuning.

## Known gaps (tracked in IMPLEMENTATION_PLAN.md)

- Auth is a single dev admin credential, not real user management (Phase 5).
- SNR estimation is a rough energy-percentile approximation, not calibrated (Phase 3).
- No automated test suite yet (`tests/` is a placeholder).

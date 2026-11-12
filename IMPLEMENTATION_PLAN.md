# Voice Identification System — Implementation Plan & Requirements

Derived from the phased design plan. This document turns that plan into concrete technical
requirements: stack, architecture, data model, API contract, and a task breakdown per phase.

**Stack decisions locked in for this document:**
- Backend: **Python 3.11 + FastAPI**
- Diarization / embeddings: **pyannote.audio** (diarization pipeline) + **SpeechBrain** (ECAPA-TDNN
  speaker embeddings) — both run fine CPU-only, just slower than GPU.
- Compute: **CPU-only** (no GPU assumed). This caps practical throughput — see Phase 6 notes.
- Storage: **Local filesystem store, not a database, for now** (JSON/pickle files on disk for
  people/voiceprints, audit log as an append-only file). MongoDB is deferred — see Section 3a.
- Deployment target: open — cloud vs on-prem left as a Phase 0 decision (DPDP Act implications
  noted in Phase 5).

---

## 1. Architecture Overview

```
Client ──HTTPS──▶ FastAPI app
                     │
                     ├─▶ Auth/RBAC middleware
                     │
                     ├─▶ Registration service ──▶ Quality gate ──▶ Embedding service ──▶ MongoDB
                     │                                                   │
                     ├─▶ Identification service ──▶ Diarization service ◀┘
                     │         │                         │
                     │         ▼                         ▼
                     │   Embedding service          Segment store (temp)
                     │         │
                     │         ▼
                     │   Matcher (cosine sim vs library, in-memory index)
                     │
                     ├─▶ Job queue (MongoDB-backed `identification_jobs`) for long audio
                     │
                     └─▶ Audit log writer ──▶ MongoDB (separate collection)
```

Key components as separate modules from day one (even in a monolith) so they can later be
split into services: `registration/`, `identification/`, `diarization/`, `embedding/`,
`matching/`, `audit/`, `auth/`.

---

## 2. Technology Choices & Rationale

| Concern | Choice | Why |
|---|---|---|
| API framework | FastAPI | async, typed, auto OpenAPI docs, good for ML service wrapping |
| Diarization | pyannote.audio (pretrained pipeline, e.g. `pyannote/speaker-diarization-3.1`) | best open-source diarization quality, CPU-capable |
| Speaker embeddings | SpeechBrain ECAPA-TDNN (`speechbrain/spkrec-ecapa-voxceleb`) | strong open-source speaker verification embeddings, widely benchmarked |
| Similarity metric | Cosine similarity | standard for ECAPA embeddings |
| Vector storage (Phase 1-3) | In-memory NumPy array, refreshed on registration/delete | fine up to a few thousand people, no extra infra |
| Vector storage (Phase 6+, if needed) | FAISS (local, CPU) or move to MongoDB/Atlas Vector Search | only add once library size or latency demands it |
| Storage (now) | Local filesystem: one JSON/pickle file per person under `data/people/`, append-only JSONL for `data/audit_log.jsonl` | fastest way to start, no infra to stand up; swap for MongoDB later (Section 3a) without changing the service layer if accessed through a repository interface |
| Storage (later, deferred) | MongoDB (Atlas or self-hosted) | revisit once multi-process access, concurrent writers, or real backup/restore needs arise |
| Background jobs | MongoDB-backed queue: an `identification_jobs` collection with `status` field (`queued`/`processing`/`done`/`failed`), a small worker pool polling/locking it (`find_one_and_update` with atomic status transition), or Celery with `mongodb` as the broker/result backend | avoids adding Redis as infra; MongoDB already needed for the queue even while people/voiceprints stay in local files |
| Encryption at rest | App-level AES-GCM applied to the embedding vector bytes before writing the JSON/pickle file, key from env var / local secrets file outside the repo | plan requires voiceprints encrypted, key outside the data store, even in local-file mode |
| Audio I/O | `ffmpeg` (via `pydub`/`ffmpeg-python`) for format normalization | tolerate varied client input formats |
| Auth | JWT bearer tokens + role-based scopes (admin / registrar / identifier / reviewer) | plan requires restricting register/identify/list/delete separately |

---

## 3. Data Model

Split across two stores:
- **Local filesystem** — `people` and `registration_clips` (voiceprints, consent, quality
  metadata, audit log). One JSON file per person under `data/people/<id>.json`, loaded through
  a small repository class (`PeopleRepo`) so the storage backend can be swapped for MongoDB
  later without touching service code.
- **MongoDB** — `identification_jobs` only, used purely as the background job queue (see
  Section 2). No voiceprints or personal data live in Mongo in this phase.

### `people` (local file: `data/people/<id>.json`)
```json
{
  "_id": "uuid",
  "name": "string (unique, enforced by an index file data/people/_name_index.json)",
  "voiceprint": {
    "vector": "encrypted blob (float32[192] for ECAPA)",
    "model_version": "string, e.g. 'ecapa-voxceleb-v1'",
    "built_from_clips": ["clip_id", "..."],
    "quality_score": "float",
    "created_at": "datetime",
    "updated_at": "datetime"
  },
  "status": "active | deleted",
  "consent": {
    "given_by": "string (who obtained consent)",
    "given_at": "datetime",
    "method": "string (e.g. 'signed form', 'verbal + recorded confirmation')",
    "withdrawal_at": "datetime | null"
  },
  "metadata": { "created_by_user_id": "string" }
}
```

### `registration_clips` (local file: `data/registration_clips/<id>.json`, transient, deletable after voiceprint built)
```json
{
  "_id": "uuid",
  "person_id": "uuid",
  "duration_sec": "float",
  "quality_checks": {
    "speech_duration_sec": "float",
    "snr_db": "float",
    "clipping_detected": "bool",
    "single_speaker_confirmed": "bool",
    "format_ok": "bool"
  },
  "embedding_vector": "encrypted blob (per-clip, used for consistency check, not stored long-term by default)",
  "created_at": "datetime"
}
```
Note: raw audio bytes are **never** persisted here — ingestion pipeline processes the upload
in memory/temp disk and discards it after the voiceprint is built (configurable retention = 0
by default per plan's "never store raw audio" rule).

### `identification_jobs` collection (**MongoDB** — the one collection actually in Mongo)
```json
{
  "_id": "ObjectId",
  "status": "queued | processing | done | failed",
  "lock": { "worker_id": "string | null", "locked_at": "datetime | null" },
  "input_meta": { "filename": "string", "duration_sec": "float", "submitted_by": "string" },
  "results": [
    {
      "speaker_label": "SPEAKER_00",
      "segments": [{"start": 12.3, "end": 45.1}],
      "total_speech_sec": 32.8,
      "match": {
        "person_id": "uuid | null",
        "name": "string | null",
        "score": "float",
        "runner_up_score": "float",
        "decision": "matched | unknown | ambiguous | insufficient_speech"
      }
    }
  ],
  "created_at": "datetime",
  "completed_at": "datetime | null"
}
```
`lock` supports the polling worker pattern: a worker claims a job with an atomic
`find_one_and_update({"status": "queued"}, {"$set": {"status": "processing", "lock": {...}}})`
so two workers never process the same job.

### `audit_log` (local file: append-only `data/audit_log.jsonl`, one JSON object per line)
```json
{
  "_id": "uuid",
  "action": "register | identify | delete | consent_withdraw | threshold_change",
  "actor_user_id": "string",
  "target_person_id": "uuid | null",
  "details": { "...": "action-specific" },
  "timestamp": "datetime"
}
```

MongoDB index: `identification_jobs.status` (for the queue poll query). Local-file uniqueness
for `people.name` is enforced via the `_name_index.json` lookup file, checked+updated inside a
file lock to avoid races between concurrent registrations.

---

## 4. Decision Rules (initial defaults — to be tuned in Phase 3)

These are starting points, not final values — Phase 3 exists specifically to replace guesses
with measured thresholds.

- **Minimum registration speech**: 30s clean speech total (across clips), reject below this.
- **Match threshold**: cosine similarity ≥ 0.70 (ECAPA-typical starting point).
- **Runner-up margin**: best score must exceed second-best by ≥ 0.08, else → `ambiguous`.
- **Minimum speaker speech for identification**: 3s of speech; below this → `insufficient_speech`.
- **Duplicate-voice rejection at registration**: if new clip's embedding scores ≥ match
  threshold against any *other* existing person, reject registration.

All four values must be stored as configurable parameters (a local `config.json` or env-driven
settings object), not hardcoded — Phase 3/8 will change them.

---

## 4a. Spoken Self-Introduction Labeling + Human-Confirmed Enrollment (implemented ahead of schedule)

Requested directly: when a speaker says their own name on the call ("I am Sanjana") or
another speaker names them ("Mr. X, please speak"), identification should label that
speaker with the spoken name so a reviewer can tell who's who, and — if the reviewer
agrees the identification is correct — let them add that voice to the library with one
click, so later audio recognizes the same voice automatically.

**How it works** (`app/services/transcription.py`, `app/services/name_extraction.py`,
`app/repos/pending_embeddings_repo.py`, `app/repos/audio_snippets_repo.py`, wired into
`app/services/identification.py` and exposed via `app/api/identify.py`):
1. Whisper (`base` model, CPU) transcribes the whole file alongside diarization.
2. Regex patterns (not NLP/NER — deliberately simple) catch self-claims ("I am X", "my
   name is X", "this is X speaking", "myself X") and other-claims ("Mr. X, please speak"
   — bound to the *next* speaker turn, not whoever said the phrase). The transcript is
   also grouped per speaker for display regardless of any claim.
3. A claim is only used for a speaker who **didn't already match** a registered
   voiceprint — an existing registration always wins over a fresh spoken claim, so
   someone can't talk over/impersonate a real registrant by name alone.
4. **Nothing is ever auto-enrolled from a spoken claim.** A claim only ever produces
   decision `claimed_unverified` with the spoken name pre-filled as a suggestion — a
   transcript claim is not a verified identity, so every enrollment from it requires a
   human to click "Add to Library" and confirm (or edit) the name, same as any other
   unidentified speaker. Their embedding is held encrypted in a short-lived local
   pending-embedding file (keyed by job + speaker) specifically so this confirmation can
   happen after the original audio is already gone.
5. A short per-speaker audio snippet (that speaker's own segments only, not the whole
   recording) is also kept temporarily so the reviewer can play back the voice before
   deciding — auto-deleted by the worker after `AUDIO_SNIPPET_RETENTION_HOURS` (default
   6h). This is the one narrow, time-boxed exception to "never store raw audio."
6. Any speaker left with no match and no claim is labeled generically, `Speaker 0`,
   `Speaker 1`, … in order of first appearance in the file, via a `display_name` field
   on each result (`speaker_label` keeps the raw diarization tag like `SPEAKER_00` for
   debugging).

**Consent model:** manual "Add to Library" enrollments (`POST
/api/v1/identify/speakers/enroll`) go through the same duplicate-name and
duplicate-voice checks as normal registration, and record real consent fields supplied
by the reviewer at confirmation time — this is a deliberate, human-confirmed
registration, not an automatic one, so it doesn't need the special-cased consent
wording the earlier auto-enroll design required.

New config: `ENABLE_SPOKEN_NAME_LABELING` (default `true`), `WHISPER_MODEL` (default
`base`), `AUDIO_SNIPPET_RETENTION_HOURS` (default `6`).

---

## 5. API Contract (v1 draft)

```
POST   /api/v1/people                      — register a person (multipart: name, consent info, audio clip(s))
GET    /api/v1/people                      — list registered people (paginated, name/status filter)
GET    /api/v1/people/{id}                 — get person metadata (never returns raw vector)
DELETE /api/v1/people/{id}                 — soft-delete + consent withdrawal, audit logged

POST   /api/v1/identify                    — submit audio (one or more files) for identification
                                               → returns job_id (202 Accepted) for async processing
GET    /api/v1/identify/jobs/{job_id}      — poll job status / fetch results

GET    /api/v1/audit                       — query audit log (admin only)

GET    /api/v1/health                      — liveness/readiness
```

All endpoints require a bearer JWT; scopes: `people:write`, `people:read`, `people:delete`,
`identify:write`, `identify:read`, `audit:read`.

Error responses for registration rejections must include a machine-readable reason code:
`insufficient_speech`, `multi_speaker_detected`, `low_snr`, `clipping`, `unsupported_format`,
`duplicate_voice`, `duplicate_name`.

---

## 6. Phase-by-Phase Technical Tasks

### Phase 0 — Requirements & Decisions (no code)
- [ ] Fill in the plan's open questions (audio sources, library size now/later, languages,
      typical speakers/recording, unknown-speaker handling, on-prem vs cloud).
- [ ] Write down target false-identification rate and false-unknown rate as explicit numbers
      (e.g. "wrong-name rate < 1% at 500 registered people").
- [ ] Decide consent collection mechanism and who is authorized to register people.
- Output: a one-page requirements sheet (separate doc), referenced by Phase 3's test design.

### Phase 1 — Registration Pipeline
- [ ] `POST /api/v1/people`: accept multipart audio (wav/mp3/m4a), normalize via ffmpeg to
      16kHz mono WAV.
- [ ] Quality gate module: speech-duration check (via VAD, e.g. `pyannote` VAD or `webrtcvad`),
      SNR estimate, clipping detection (sample-value saturation check), format/sample-rate check.
- [ ] Single-speaker confirmation: run diarization on the registration clip(s); reject if >1
      speaker detected with significant speech share.
- [ ] Build voiceprint: run ECAPA embedding per clip, average/centroid across clips, record
      per-clip consistency (pairwise cosine sim; flag if clips disagree beyond a threshold).
- [ ] Duplicate check: compare new voiceprint against all existing voiceprints before commit.
- [ ] Unique name enforcement (DB unique index + pre-check).
- [ ] Consent record required field on every registration call; reject without it.
- [ ] `DELETE /api/v1/people/{id}`: soft delete, voiceprint purge, audit entry.
- Exit test: scripted registration with (a) clean sample → success, (b) noisy/short sample →
  rejected with correct reason code, (c) two-speaker sample → rejected, (d) re-registering a
  voice under a new name → rejected as duplicate.

### Phase 2 — Identification Pipeline
- [ ] `POST /api/v1/identify`: accept 1+ files, enqueue background job (insert into the
      MongoDB `identification_jobs` queue with `status: "queued"`), return `job_id` immediately.
- [ ] Diarization worker: run pyannote pipeline, get per-speaker time segments.
- [ ] Per-speaker embedding: build voiceprint from each speaker's concatenated segments, capped
      at e.g. 60s of speech to bound compute.
- [ ] Matcher: cosine similarity against in-memory library matrix (NumPy), rank candidates.
- [ ] Apply decision rules (Section 4) → `matched | unknown | ambiguous | insufficient_speech`.
- [ ] Persist results to `identification_jobs`; `GET /jobs/{id}` returns status + results.
- [ ] Support multiple files per request, each → its own set of per-speaker results, processed
      independently (can run as parallel job tasks).
- Exit test: single-speaker known-voice clip → correct match; single-speaker unknown voice →
  `unknown`; 3-speaker clip with 2 known + 1 unknown → correct per-speaker breakdown with time
  ranges.

### Phase 3 — Evaluation & Tuning
- [ ] Build labeled test set: known speakers (held-out clips, not used in registration),
      unknown speakers, multi-speaker recordings with ground-truth "who spoke when" (RTTM-style
      labels work well here since pyannote outputs are RTTM-compatible).
- [ ] Metrics harness (separate script/notebook, not part of the API):
      - identification accuracy, wrong-name rate, false-unknown rate (per Section 4 of the plan)
      - diarization error rate (DER) via `pyannote.metrics`
      - breakdown by noise condition, device, speaker count, speech duration, language
- [ ] Threshold sweep: grid-search match threshold + runner-up margin against the test set,
      pick values that hit the Phase 0 targets; update the config defaults in Section 4.
- [ ] Library-size scaling test: synthetically grow the library (50/500/5000 people) using a
      public speaker dataset (e.g. VoxCeleb) mixed with real samples, re-measure accuracy.
- Output: a tuning report (numbers, chosen thresholds, scaling curve) checked into the repo.

### Phase 4 — Accuracy Improvements
- [ ] Score normalization (e.g. adaptive s-norm against a cohort set) — implement only if
      Phase 3 shows it measurably helps.
- [ ] Multi-voiceprint-per-person support: extend `people.voiceprint` to a list, match against
      best-of; update matcher accordingly.
- [ ] Controlled voiceprint reinforcement: only from `matched` results above a very high
      confidence bar, with a cap on how much a single confirmed match can shift the stored
      vector (e.g. exponential moving average with small alpha), plus a rollback path.
- [ ] Review queue (`ambiguous`/low-confidence results) — simple collection + review UI (Phase 7).
- [ ] Overlap handling: use pyannote's overlapped-speech detection to exclude overlapped
      segments from voiceprint construction.

### Phase 5 — Security & Privacy
- [ ] JWT auth + scope checks on every endpoint (FastAPI dependency).
- [ ] Field-level encryption for `voiceprint.vector` (app-level AES-GCM with key from a secrets
      manager / env var injected at deploy time — never in code or DB).
- [ ] Confirm no code path writes raw audio bytes to disk/DB beyond processing-time temp files;
      temp files cleaned up in a `finally` block.
- [ ] Audit log writer wired into register/identify/delete/consent-withdraw/threshold-change.
- [ ] Consent withdrawal endpoint triggers full deletion incl. backup purge per retention policy.
- [ ] Legal review of consent wording and DPDP Act retention compliance (non-code task).
- [ ] Document spoofing limitation in API docs/README: identification alone must not gate
      sensitive actions.

### Phase 6 — Scale & Performance (CPU-only constraints)
- [ ] All identification requests go through the job queue — no synchronous long-audio
      processing in the request/response cycle.
- [ ] Upload size/duration caps enforced at the API layer (e.g. reject >30 min per file,
      configurable).
- [ ] Benchmark CPU-only throughput explicitly (e.g. realtime-factor for diarization +
      embedding on target hardware) — since no GPU is assumed, this governs worker pool sizing
      and expected turnaround time; surface this in capacity planning, not just "use a GPU."
- [ ] In-memory matcher: reload/refresh the NumPy library matrix on registration/delete events
      (pub/sub or simple version counter + lazy reload).
- [ ] Only evaluate FAISS/vector index if Phase 3's scaling test or production volume shows the
      in-memory linear scan is a bottleneck.

### Phase 7 — Integration & Operations
- [ ] Finalize OpenAPI spec (FastAPI auto-generates; review and freeze field names/enums).
- [ ] Minimal review UI: list `ambiguous`/low-confidence results, play segment audio (if
      retained transiently for review window only, per policy), confirm/correct, feeds back
      into Phase 4's reinforcement path.
- [ ] Monitoring: identification volume, unknown rate, ambiguous rate, job processing time,
      error rate — expose via `/metrics` (Prometheus) or structured logs + dashboard.
- [ ] Store `model_version` on every voiceprint; add a migration path/flag for re-registration
      if the embedding model changes.
- [ ] Backup/restore test for both stores: the `data/` filesystem tree (people, clips, audit
      log) and the MongoDB job queue; incident runbook doc.

### Phase 8 — Pilot & Rollout
- [ ] Run against real recordings with human review of every result; compare to pilot targets
      from Phase 0.
- [ ] Threshold adjustment based on observed pilot errors (prioritize wrong-name rate).
- [ ] Gradually reduce review coverage, keep it for low-confidence results only.
- [ ] Feedback loop: user-reported mistakes logged and added to the Phase 3 test set.

---

## 7. Suggested Repo Structure

```
voice-biometric/
├── app/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── api/                    # routers: people, identify, audit, health
│   ├── services/
│   │   ├── registration.py
│   │   ├── identification.py
│   │   ├── diarization.py
│   │   ├── embedding.py
│   │   └── matching.py
│   ├── repos/                   # storage layer: PeopleRepo, ClipsRepo (local files), JobsRepo (Mongo)
│   ├── workers/                 # job-queue polling worker(s) reading identification_jobs
│   ├── models/                  # Pydantic schemas
│   ├── auth/
│   ├── audit/
│   └── config.py                 # thresholds, model versions, env settings
├── data/                          # local storage root (gitignored)
│   ├── people/                   # <id>.json per person, _name_index.json
│   ├── registration_clips/
│   └── audit_log.jsonl
├── eval/                          # Phase 3 test harness, metrics scripts, test-set manifests
├── tests/                         # unit + integration tests
├── requirements.txt
├── docker-compose.yml            # app + MongoDB only (job queue)
└── README.md
```

---

## 8. Immediate Next Steps

1. Close out Phase 0's remaining open questions (audio sources, library size, languages,
   unknown-speaker handling, error-rate targets) — these numbers drive Phase 3's thresholds.
2. Scaffold the repo per Section 7.
3. Stand up MongoDB locally (docker-compose, used only for the job queue) and get
   `pyannote.audio` + `speechbrain` models downloading/running CPU-only as a smoke test,
   before writing any endpoint code — confirms the CPU-only performance envelope early.
4. Build Phase 1 (registration) end-to-end before touching Phase 2, since identification
   depends on having a populated, trustworthy library.

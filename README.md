# Talent Intelligence AI — RedRob Track 1

**Intelligent Candidate Discovery** — offline ranking pipeline for the RedRob Hackathon v4 challenge.

## 1. Project overview

**Talent Intelligence AI** is a job-description–grounded candidate discovery system. Given a released job description and a pool of 100,000 RedRob candidate profiles, it produces a ranked top-100 CSV with per-candidate reasoning.

The system does **not** rank candidates by AI keyword count. It prioritizes **career evidence** (what someone built and shipped) over skill-list keywords.

It is designed to handle common dataset traps, including:

- **Keyword stuffing** — many low-support AI skills with little career backing
- **Framework-only AI profiles** — LangChain/OpenAI/LLM labels without retrieval/ranking/production work history
- **Fake seniority** — long tenure with management-only language and weak ownership signals
- **Unavailable candidates** — strong on-paper profiles with weak engagement (addressed via secondary RedRob behavioral signals, not as a primary rank driver)

Official dataset files live under `data/` (see [Data setup](#7-data-setup)). The committed `submission.csv` at the repository root is the frozen competition output.

## 2. Architecture

```text
candidates.jsonl(.gz)
        |
Streaming Loader          (backend/dataset_intelligence/loader.py)
        |
RedRob Adapter            (backend/competition/redrob_adapter.py)
        |
Candidate Intelligence    (backend/intelligence/candidate_engine.py)
        |
JD Evidence Matching      (backend/parsers/jd_analyzer.py + competition score)
        |
Evidence Calibration      (backend/competition/evidence_calibrator.py)
        |
Top-100 Heap Ranking      (backend/competition/rank.py)
        |
submission.csv
```

### Repository layout

| Path | Purpose |
|------|---------|
| `backend/competition/` | Official **offline** challenge ranking pipeline (adapter, calibration, heap ranker, validation, benchmark). |
| `backend/intelligence/` | Candidate understanding, core signals, and evidence snippet extraction. |
| `backend/dataset_intelligence/` | Dataset exploration, profiling, audits, and evaluation reports. |
| `frontend/` | Optional recruiter interface (FastAPI + Next.js demo app; not required for competition reproduction). |
| `sandbox/` | Small-sample reproduction instructions for hosted demo environments. |
| `submission.csv` | Frozen top-100 submission (do not hand-edit). |
| `METHODOLOGY.md` | Judge-facing design narrative (Stages 4–5). |
| `submission_metadata.yaml` | Portal metadata mirror (fill `TODO` fields before upload). |

## 3. Exact reproduction command

**Stage 3 requires a single command** that regenerates the submission CSV from the official candidate pool and job description.

From the repository root (with official files in `data/`):

```bash
python -m backend.competition.rank \
  --candidates data/candidates.jsonl \
  --job data/job_description.docx \
  --output submission.csv
```

Compressed pool is also supported:

```bash
python -m backend.competition.rank \
  --candidates data/candidates.jsonl.gz \
  --job data/job_description.docx \
  --output submission.csv
```

The ranking step runs **CPU-only**, with **no external API calls** and **no hosted LLM** (see `configure_offline_environment()` in `backend/competition/rank.py`).

Dependencies: install from `backend/requirements.txt` (Python 3.10+ recommended). Run commands with the repository root on `PYTHONPATH` (default when using `python -m` from the repo root).

## 4. Validation command

Validate format before upload (100 rows, ranks 1–100, unique IDs, monotonic non-increasing scores):

```bash
python -m backend.competition.validate_submission submission.csv
```

Expected output on success: `Submission is valid.`

## 5. Benchmark command

Measure runtime, memory, and validation against official constraints:

```bash
python -m backend.competition.benchmark \
  --candidates data/candidates.jsonl \
  --job data/job_description.docx
```

Reported on the reference machine used for final packaging:

| Metric | Value |
|--------|--------|
| Candidates processed | **100,000** |
| Runtime | **~82 seconds** |
| Compute | **CPU only** |
| Network during ranking | **None** |

Limits enforced by the benchmark helper (`backend/competition/benchmark.py`): runtime ≤ 300s, peak RAM ≤ 16 GB.

## 6. Compute constraints

Per [official submission spec](data/submission_spec.docx):

| Constraint | Limit |
|------------|--------|
| **Runtime** | < 5 minutes (wall-clock for ranking step) |
| **RAM** | < 16 GB |
| **GPU** | Not required (CPU-only ranking) |
| **External APIs** | None during ranking (no OpenAI, Anthropic, Cohere, Gemini, or other hosted LLM calls) |

Intermediate disk usage should stay within organizer limits; the pipeline streams JSONL and does not load the full pool into memory.

## 7. Data setup

Place **official hackathon bundle files** in:

```text
data/
```

**Required for full reproduction:**

- `candidates.jsonl` **or** `candidates.jsonl.gz` (100,000 candidates)
- `job_description.docx` (released JD)

**Useful references** (included in many bundles, not required to run rank):

- `sample_candidates.json` — small schema inspection set
- `candidate_schema.json` — JSON Schema
- `submission_spec.docx`, `README.docx`, `redrob_signals_doc.docx` — official documentation

**Dataset files are not committed to this repository** (see `data/.gitignore`). Clone the repo, copy the official bundle into `data/`, then run the reproduction command in [Section 3](#3-exact-reproduction-command).

## 8. Tests

```bash
python -m unittest backend.test_redrob_competition
```

Uses `data/sample_candidates.json`, `data/candidates.jsonl` (first 100 lines), and `data/job_description.docx` when present locally.

## 9. Further reading

- `METHODOLOGY.md` — ranking philosophy, trap handling, reasoning, and metric alignment (Stages 4–5)
- `submission_metadata.yaml` — portal submission mirror
- `sandbox/README.md` — small-sample hosted demo
- `docs/system-technical-report.md` — full product architecture (optional recruiter UI)

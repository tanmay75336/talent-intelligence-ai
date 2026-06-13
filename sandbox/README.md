# Sandbox — Small-sample Reproducibility

This folder documents the hosted sandbox setup for verifying the OctaOps ranking pipeline on a small candidate sample.

The sandbox demonstrates that the ranking system runs end-to-end. Full 100,000-candidate reproduction is handled from the GitHub repository during the official reproduction stage.

---

## Google Colab Sandbox

Create a new Google Colab notebook and run the following cells.

```python
# Cell 1 — Clone repository
!git clone https://github.com/tanmay75336/talent-intelligence-ai.git
%cd talent-intelligence-ai
```

```python
# Cell 2 — Install dependencies
!pip install -r backend/requirements.txt
```

```python
# Cell 3 — Upload and arrange data

# Upload the official small sample from the hackathon bundle:
# - sample_candidates.json
# - job_description.docx
# Then move them to the data/ directory:
!mkdir -p data
!mv sample_candidates.json data/
!mv job_description.docx data/
```

```python
# Cell 4 — Run ranking pipeline

!python -m backend.competition.rank \
  --candidates data/sample_candidates.json \
  --job data/job_description.docx \
  --output demo_submission.csv
```

```python
# Cell 5 — Validate generated CSV

!python -m backend.competition.validate_submission demo_submission.csv
```

```python
# Cell 6 — Download generated CSV

from google.colab import files
files.download("demo_submission.csv")
```

---

## Local Sandbox Run

From the repository root (ensure `data/sample_candidates.json` and `data/job_description.docx` are present):

Run:

```bash
python -m backend.competition.rank --candidates data/sample_candidates.json --job data/job_description.docx --output demo_submission.csv
```

Inspect the output (validation is skipped for <100 candidates):

```bash
cat demo_submission.csv
```

---

## What this demonstrates

- Same ranking code path as the full submission pipeline
- Streaming candidate loading
- Candidate scoring and calibration
- Final ranking selection
- Reasoning generation
- CSV creation and validation
- CPU-only execution
- No external API calls during ranking

The sandbox is intentionally lightweight. Full architecture details and the complete 100K reproduction command are documented in the main `README.md` and `METHODOLOGY.md`.

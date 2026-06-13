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
# Cell 3 — Prepare sandbox sample

# The official sandbox only requires a small sample run.
# Use exactly 100 candidates so the generated CSV follows the same
# 100-row submission structure.

!head -n 100 data/candidates.jsonl > data/sample_100.jsonl
```

```python
# Cell 4 — Run ranking pipeline

!python -m backend.competition.rank \
  --candidates data/sample_100.jsonl \
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

From the repository root:

```bash
head -n 100 data/candidates.jsonl > data/sample_100.jsonl
```

Run:

```bash
python -m backend.competition.rank --candidates data/sample_100.jsonl --job data/job_description.docx --output demo_submission.csv
```

Validate:

```bash
python -m backend.competition.validate_submission demo_submission.csv
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

# Sandbox — Small-sample Reproducibility

This folder documents how to run the competition ranker on a small candidate sample for the **Stage 1 sandbox link** requirement.

The sandbox only needs to demonstrate end-to-end ranking on a subset — full reproduction (100K candidates) happens at Stage 3 from the GitHub repo.

---

## Quickest option: Google Colab

Create a new Colab notebook and run these cells:

```python
# Cell 1 — Install dependencies
!pip install pandas numpy pydantic
```

```python
# Cell 2 — Clone repository
!git clone https://github.com/tanmay75336/talent-intelligence-ai.git
%cd talent-intelligence-ai
```

```python
# Cell 3 — Upload data files
# Upload: job_description.docx and a small candidate JSONL (e.g. first 200 lines)
# from Google Drive or via Colab file upload widget

# Slice 200 candidates from the official pool:
!head -n 200 data/candidates.jsonl > data/sample_200.jsonl
```

```python
# Cell 4 — Run the ranker
!python -m backend.competition.rank \
  --candidates data/sample_200.jsonl \
  --job data/job_description.docx \
  --output demo_submission.csv
```

```python
# Cell 5 — Validate
!python -m backend.competition.validate_submission demo_submission.csv
```

```python
# Cell 6 — Download result
from google.colab import files
files.download('demo_submission.csv')
```

> **Note:** With fewer than 100 unique candidates, validation will fail the 100-row check. Use ≥100 candidates or treat the output as a pipeline smoke test rather than a valid submission format.

---

## Local quick run

From the repository root with data files in `data/`:

```bash
# Slice 200 candidates
head -n 200 data/candidates.jsonl > /tmp/sample_200.jsonl

# Run ranker
python -m backend.competition.rank \
  --candidates /tmp/sample_200.jsonl \
  --job data/job_description.docx \
  --output demo_submission.csv
```

---

## What this demonstrates

- Streaming JSONL load → profile normalisation → scoring → calibration → reasoning → CSV
- CPU-only execution with no external API calls
- Same pipeline code path as full 100K reproduction

The sandbox is intentionally minimal. The full system design is documented in `README.md` and `METHODOLOGY.md`.

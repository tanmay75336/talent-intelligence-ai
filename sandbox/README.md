# Sandbox — Small-sample reproduction

This folder documents how to run the **official competition ranker** on a small candidate sample for hosted demo environments (Stage 3 sanity check / portal sandbox link).

The full 100,000-candidate reproduction command is in the repository root [`README.md`](../README.md). The sandbox only needs to prove **end-to-end** ranking on a small input within the compute budget.

## Quick run (local)

From the repository root, with official bundle files under `data/`:

```bash
python -m backend.competition.rank \
  --candidates data/sample_candidates.json \
  --job data/job_description.docx \
  --output demo_submission.csv
```

Validate output:

```bash
python -m backend.competition.validate_submission demo_submission.csv
```

**Note:** `sample_candidates.json` contains fewer than 100 candidates. The ranker requires exactly 100 rows in a competition submission; for sandbox demos you may either:

- Use the first 100 records from `data/candidates.jsonl`, or
- Treat `demo_submission.csv` as a **pipeline smoke test** (validation will fail until 100 unique ranked rows exist).

For a valid 100-row demo on a subset, slice 100 lines from the official pool:

```bash
head -n 100 data/candidates.jsonl > /tmp/candidates_100.jsonl
python -m backend.competition.rank \
  --candidates /tmp/candidates_100.jsonl \
  --job data/job_description.docx \
  --output demo_submission.csv
python -m backend.competition.validate_submission demo_submission.csv
```

## What the sandbox demonstrates

- Streaming load → RedRob adapter → scoring → evidence calibration → top-100 heap → CSV + reasoning
- **CPU-only**, **no external APIs** during ranking (same as production reproduction)
- Reproducible commands documented for organizers

## Acceptable hosted platforms

Per official hackathon guidance (`data/submission_spec.docx` §10.5), any of these is acceptable:

- [Hugging Face Spaces](https://huggingface.co/spaces)
- [Streamlit Cloud](https://streamlit.io/cloud)
- [Replit](https://replit.com)
- [Google Colab](https://colab.research.google.com)
- **Docker / Binder** — public image or `docker run` recipe in README
- Other hosts that accept a small candidate upload and run the command above within **≤5 minutes on CPU**

The sandbox does **not** need to process the full 100K pool; full reproduction is verified from the GitHub repo at Stage 3.

## Suggested sandbox README snippet

Include in your hosted space:

1. Upload or mount `job_description.docx` and a candidate file (JSON/JSONL, ≤100–1000 rows).
2. Run: `python -m backend.competition.rank --candidates <input> --job <jd> --output submission.csv`
3. Download `submission.csv`.

Dependencies: `pip install -r backend/requirements.txt` from the repository root.

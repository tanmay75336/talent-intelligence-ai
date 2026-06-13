# Sandbox — Small-sample Reproducibility

This folder explains how we set up the hosted sandbox used to verify the OctaOps ranking pipeline on a small candidate sample.

## Hosted Demo

Google Colab sandbox:
https://colab.research.google.com/drive/12h8SmdQUZcTO4LkyQdWoHNU0DGOsgciX?usp=sharing

The hosted notebook runs the ranking flow end-to-end using the small candidate sample workflow.

The sandbox verifies:

- CPU-only execution
- No hosted LLM or external API calls during ranking
- Same ranking pipeline code path as the full submission
- Small sample input (≤100 candidates)
- Ranked CSV generation

We use the sandbox for quick reproducibility checks. The complete 100,000-candidate reproduction is handled from the GitHub repository during the official reproduction process.

---

## Google Colab Setup Steps

Open the hosted Colab notebook and run:

`Runtime → Run all`

If Google Colab shows the standard external notebook warning, select **Run anyway**.

By default, the sandbox uses the included sample files:

```text
sandbox/sample_data/sample_candidates.json
sandbox/sample_data/job_description.docx
```

These files allow the notebook to run end-to-end without requiring manual uploads.

For custom testing, the notebook also supports uploading another small candidate sample and job description.

By default:

```text
USE_CUSTOM_UPLOAD = False
```

The notebook automatically uses the included sandbox sample files.

To test custom files, change:

```text
USE_CUSTOM_UPLOAD = True
```

When the cell runs, Google Colab opens a file upload prompt where a reviewer can provide their own candidate sample and job description files.

The notebook flow:

```text
Clone repository
        ↓
Install dependencies
        ↓
Load included sandbox sample data
(or optional reviewer-uploaded input)
        ↓
Run ranking pipeline
        ↓
Generate demo_submission.csv
```

The ranking command executed inside the notebook is:

```bash
python -m backend.competition.rank \
  --candidates data/sample_candidates.json \
  --job data/job_description.docx \
  --output demo_submission.csv
```

The generated CSV can then be inspected or downloaded from the Colab environment.

---

## Local Sandbox Run

From the repository root, copy the included sandbox sample files into `data/` or provide your own small sample inputs:

Run:

```bash
python -m backend.competition.rank --candidates data/sample_candidates.json --job data/job_description.docx --output demo_submission.csv
```

Inspect the output (validation is skipped for <100 candidates):

```bash
cat demo_submission.csv
```

---

## What we verify here

- Same ranking code path as the full submission pipeline
- Streaming candidate loading
- Candidate scoring and calibration
- Final ranking selection
- Reasoning generation
- CSV creation and validation
- CPU-only execution
- No external API calls during ranking

The sandbox is intentionally lightweight and focused on execution verification. The full architecture details and complete 100K reproduction command are documented in the main `README.md` and `METHODOLOGY.md`.

# Phase 7C.1 — Reasoning Reproducibility Fix Report

**Date:** 2026-06-09  
**Status:** ✅ Complete

---

## 1. Files Changed

| File | Change |
|---|---|
| `backend/competition/rank.py` | Added `import hashlib`; replaced `hash()` with `hashlib.sha256()` for JD connection variant selection |
| `backend/competition/evidence_calibrator.py` | Added `import hashlib`; replaced `hash()` with `hashlib.sha256()` for evidence sentence selection |

---

## 2. hash() Usages Replaced

| File | Line | Before | After |
|---|---|---|---|
| `rank.py` | 272 | `hash(hit_text + verb) % 5` | `int(hashlib.sha256((hit_text + verb).encode("utf-8")).hexdigest(), 16) % 5` |
| `evidence_calibrator.py` | 531 | `hash(candidate_id) % len(candidates_pool)` | `int(hashlib.sha256(candidate_id.encode("utf-8")).hexdigest(), 16) % len(candidates_pool)` |

---

## 3. Determinism Verification

```
Run 1 → submission.csv (saved as submission_run1.csv)
Run 2 → submission.csv

diff submission_run1.csv submission.csv → EMPTY (no differences)

DETERMINISM: PASS — files are identical across two separate invocations.
```

---

## 4. Validation Result

```
python3 -m backend.competition.validate_submission submission.csv
→ Submission is valid.
```

Ranking freeze verified against Phase 7B.5 frozen baseline:
```
IDs match frozen baseline:    True
Ranks match frozen baseline:  True
Scores match frozen baseline: True
```

---

## 5. Benchmark Result

```
Candidates processed: 100,000
Runtime: 81.47 seconds
Limit: 300 seconds
Runtime status: PASS
Submission validation: PASS
```

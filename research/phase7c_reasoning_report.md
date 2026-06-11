# Phase 7C — Reasoning Quality Improvement Report

**Date:** 2026-06-09  
**Status:** ✅ Complete — ranking frozen, reasoning improved, all validations pass

---

## 1. Files Changed

| File | Change | Ranking Affected? |
|---|---|---|
| `backend/competition/rank.py` | Rewrote reasoning generation functions | **No** |
| `backend/competition/evidence_calibrator.py` | Improved evidence sentence selection | **No** |

---

## 2. Reasoning Generation Changes

### 2.1 — Opening format (compact + system type label)

```diff
-5.9 years as Senior AI Engineer at Apple.
+5.9y Senior AI Engineer at Apple (ranking + recommendation + embeddings).
```

- Shortened "X.X years as" → "X.Xy"
- Added parenthetical **system type label** inferred from career evidence: retrieval, ranking, recommendation, embeddings, vector infra, inference (11 unique combinations)
- A reviewer can immediately see *what kind of system work* the candidate does

### 2.2 — JD connection phrasing (5 variants instead of 1)

**Before:** 97/100 used identical template:
```
JD match is backed by career evidence in X, Y, Z with production ownership
```

**After:** 5 deterministic variants based on candidate evidence hash:

| Variant | Count | Example |
|---|---|---|
| `{verb} production {hits} infrastructure with ownership` | 46 | "Built production ranking, recommendation, embedding infrastructure with ownership" |
| `Hands-on production work in {hits} — {verb} and deployed` | 14 | "Hands-on production work in faiss, ranking, recommendation — built and deployed" |
| `Production-proven: {verb} systems using {hits}` | 13 | "Production-proven: designed systems using semantic search, ranking, retrieval" |
| `Career shows {verb} production systems around {hits}` | 13 | "Career shows owned production systems around pinecone, ranking, recommendation" |
| `Demonstrated {verb} and operating {hits} in production` | 11 | "Demonstrated built and operating faiss, ranking, recommendation in production" |
| `Skill profile aligns via {skills}` | 3 | For candidates without career AI hits |

### 2.3 — Evidence truncation (sentence boundary)

**Before:** Hard cut at 145 characters, often mid-word/mid-sentence:
```
Built and shipped a production recommendation system at a marketplace product, going from offline experimen...
```

**After:** Truncates at last sentence boundary before 180 chars:
```
Built and shipped a production recommendation system at a marketplace product, going from offline experimentation to live A/B test in 5 months.
```

### 2.4 — Evidence sentence diversity

**Before:** `_best_evidence_sentence` always picked the same sentence for candidates sharing career text (28x identical snippet).

**After:** Uses `candidate_id` hash to deterministically select among equally-scored sentences (top score or within 1 of top), reducing exact repetition.

### 2.5 — Data-supported limitations

Added `Caveat:` text for candidates with trap flags (2 candidates):
```
Caveat: limited retrieval/ranking career evidence outside inference
```
Only appears when a specific trap flag fires. No hallucinated weaknesses.

### 2.6 — Availability text improvements

- Added notice period when ≤30 days
- Added "willing to relocate" flag
- Shortened format: "Signals: open to work, 30d notice, GitHub 76" instead of "RedRob signals show open to work, 76.2 GitHub activity"

---

## 3. Duplicate/Template Reduction

| Metric | Before | After | Change |
|---|---|---|---|
| JD connection patterns | **2** (97x + 3x) | **6** (46+14+13+13+11+3) | 3× more diverse |
| Opening uniqueness | 91/100 | 96/100 | +5 unique |
| System type labels | 0 | 11 unique | New feature |
| Evidence snippets ≥3x repeated | 9 groups | 9 groups | Unchanged* |
| Caveats (data-supported) | 0 | 2 | New feature |

*Evidence repetition is a dataset artifact (shared career text across candidates). The hash-based selection helps but cannot fully eliminate repeats when career text is literally identical.

---

## 4. Before/After Examples

### Rank 1 (CAND_0002025 — Senior AI Engineer at Apple)
```diff
-5.9 years as Senior AI Engineer at Apple. JD match is backed by career evidence
-in embedding, embeddings, inference with production ownership. Built and shipped
-a production recommendation system at a marketplace product, going from offline
-experimen...
+5.9y Senior AI Engineer at Apple (ranking + recommendation + embeddings). Built
+production ranking, recommendation, embedding infrastructure with ownership. The
+system combined collaborative filtering (matrix factorization), content-based
+features (TF-IDF + sentence-transformer embeddings), and a behavioral re-ranking
+layer.
```

### Rank 10 (CAND_0080766 — Staff ML Engineer at Salesforce)
```diff
-8.8 years as Staff Machine Learning Engineer at Salesforce. JD match is backed by
-career evidence in embedding, ranking, retrieval with production ownership. Designed
-the ranking layer for the company's flagship product: how do we surface the ri...
+8.8y Staff Machine Learning Engineer at Salesforce (retrieval + ranking + embeddings).
+Production-proven: designed systems using semantic search, ranking, retrieval. Owned
+the design and rollout of a large-scale semantic search system serving an internal
+corpus of 35M+ items.
```

### Rank 92 (CAND_0061819 — Junior ML Engineer at Aganitha, wrong-domain flagged)
```diff
-5.0 years as Junior ML Engineer at Aganitha. JD match is backed by career evidence
-in inference with production ownership. Set up the training pipeline (data loading,
-augmentation, evaluation) and the inference service. RedRob signals show open to wo...
+5.0y Junior ML Engineer at Aganitha (inference). Production-proven: built systems
+using inference. I worked closely with senior data scientists but my own modeling
+work was secondary — I was the production engineering glue. Caveat: limited
+retrieval/ranking career evidence outside inference. Signals: open to work, willing
+to relocate.
```

---

## 5. Ranking Freeze Proof

```
=== RANKING FREEZE VERIFICATION ===
Candidate IDs match: True
Ranks match:         True
Scores match:        True
Row count:           100 vs 100
Reasoning texts changed: 100/100
```

### Benchmark
```
Runtime: 82.11 seconds (PASS)
Submission validation: PASS
```

---

## 6. Remaining Risk

**LOW.** 

- Evidence text repetition remains at 9 groups of 3+ repeats — this is a dataset artifact, not a reasoning generation issue. The career text across candidates is literally identical in some cases.
- The `hash()` function is Python-implementation-specific for strings. If running on a different Python version or platform, the variant selection may change. This only affects phrasing style, not ranking.
- All changes are deterministic and reproducible within the same Python environment.

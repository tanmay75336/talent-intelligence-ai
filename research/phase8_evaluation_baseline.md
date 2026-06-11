# Phase 8A — Evaluation Harness: Baseline Assessment

**Date:** 2026-06-09  
**Baseline:** Phase 7 stable (submission.csv, SHA-256 `9a7c902...c34b`)  
**Evaluator:** `backend/competition/evaluate.py`

---

## 1. Evaluation Approach — Grounded in Official Docs

### Official Scoring Weights (from `submission_spec.docx`)

| Metric | Weight | Tier coverage |
|---|---|---|
| NDCG@10 | 50% | Top 10 quality |
| NDCG@50 | 30% | Top 50 quality |
| MAP | 15% | Full top-100 precision |
| P@10 | 5% | Top 10 presence |

Our internal evaluator maps these weights to tier importance:
- **Top 10 weight: 55%** (NDCG@10 + P@10)
- **Top 50 weight: 30%** (NDCG@50)
- **Top 100 weight: 15%** (MAP)

### JD-Derived Evidence Signals

Extracted from `job_description.docx` — **not invented**:

| Signal Category | JD Source | Terms Used |
|---|---|---|
| Eval maturity | "Set up evaluation infrastructure — offline benchmarks, online A/B testing, recruiter-feedback loops" | ndcg, mrr, map, a/b test, evaluation framework, offline eval, correlation |
| Retrieval infra | "embeddings, retrieval... BM25 + rule-based... v2 with embeddings, hybrid retrieval" | bm25, faiss, hnsw, elasticsearch, pinecone, semantic search, dense retrieval, etc. |
| System ownership | "own the intelligence layer — ranking, retrieval, and matching" | ranking, retrieval, recommendation, search, ltr, two-stage |
| Production evidence | "ship a working ranker in a week... learn from real users" | production, deployed, scale, shipped, a/b, users, monitoring |
| Ownership depth | "Scrappy product-engineering attitude" | owned, architected, built, designed, led |

### Signal Philosophy

**Career evidence ≠ keyword matching.**

A candidate is scored on *both* production evidence AND ownership evidence existing simultaneously. A candidate who lists "ranking systems" as a skill without production or ownership context receives `surface_match_risk = True`.

### Behavioral Signal Use (from `redrob_signals_doc.docx`)

Per the doc: signals are "more predictive of whether a candidate can actually be hired" — they are **availability modifiers**, not primary quality signals.

Availability score (0–1.0):
- `open_to_work` +0.30
- Notice period ≤30 days +0.40
- Notice period ≤60 days +0.20
- Willing to relocate +0.30

Engagement score (0–1.0):
- `recruiter_response_rate` (0–1.0 direct)
- `interview_completion_rate` ×0.5
- `github_activity_score ≥ 40` +0.30

---

## 2. Phase 7 Baseline Assessment

### Composite JD Alignment Score

```
0.898 / 1.000
(NDCG@10 × 0.55) + (NDCG@50 × 0.30) + (MAP × 0.15)
```

---

## 3. Top-10 / Top-50 / Top-100 Tier Analysis

### TOP 10 — JD Alignment Score: 0.965

```
Eval maturity (NDCG/MRR/A-B): 90%  (9/10)
Retrieval infra (FAISS/BM25): 100%
System terms (rank/rec/search): 100%
Career evidence (prod+own):    100%
Ideal experience (5-9y):       100%
Trap flags: 0/10    Surface-match risk: 0
Avg Evidence Depth: 3.90 / 4.0
Behavioral avg availability: 0.53 / 1.0
```

**Top 10 individual breakdown:**

| Rank | Title | Company | Yrs | Depth | Eval | Retrieval | Available |
|---|---|---|---|---|---|---|---|
| 1 | Senior AI Engineer | Apple | 5.9 | 4/4 | a/b test | embedding | open, 30d notice, 80% resp |
| 2 | Staff ML Engineer | Paytm | 7.0 | 4/4 | ndcg, corr, a/b | bm25, sem-search, emb | open, relocate, 95% resp |
| 3 | Senior Data Scientist | Google | 6.5 | 4/4 | corr, a/b | embedding | open, relocate, 72% resp |
| 4 | Senior NLP Engineer | Mad Street Den | 8.0 | 4/4 | ndcg, corr, a/b | bm25, sem-search, emb | 30d notice |
| 5 | Rec Systems Engineer | CRED | 8.0 | 4/4 | eval fmwk, a/b | emb, pinecone | open, 77% resp |
| 6 | Lead AI Engineer | Razorpay | 6.7 | 4/4 | eval fmwk, ndcg | bm25, faiss, emb | open, 30d, relocate, 73% |
| 7 | Applied ML Engineer | Freshworks | 6.0 | 4/4 | a/b | embedding | open, GitHub 86 |
| 8 | ML Engineer | Razorpay | 6.0 | 3/4 | *(no eval)*| bm25, faiss, ES | GitHub 66 |
| 9 | Senior NLP Engineer | Ola | 7.8 | 4/4 | ndcg, corr, a/b | bm25, pinecone, emb | open, GitHub 53 |
| 10 | Staff ML Engineer | Salesforce | 8.8 | 4/4 | eval fmwk, ndcg | bm25, sem-search, emb | 0d notice, relocate |

> **Rank 8 note:** Sole top-10 candidate without explicit eval maturity terms. Has strong retrieval infra (BM25, FAISS, Elasticsearch, semantic search) with production+ownership evidence. Minor gap; all other signals are excellent.

### TOP 11-50 — JD Alignment Score: 0.841

```
Eval maturity: 75%   Retrieval infra: 78%
System terms: 98%    Career evidence: 100%
Ideal experience: 90%
Trap flags: 0    Surface-match risk: 0
Avg Evidence Depth: 3.50 / 4.0
```

### TOP 51-100 — JD Alignment Score: 0.767

```
Eval maturity: 64%   Retrieval infra: 62%
System terms: 94%    Career evidence: 100%
Ideal experience: 92%
Trap flags: 2    Surface-match risk: 0
Avg Evidence Depth: 3.20 / 4.0
```

> The 2 trap-flagged candidates (ranks 92, 95) were identified and penalized in Phase 7B.5.

---

## 4. False-Positive Analysis (Top 50)

7 candidates in the Top 50 are flagged as **"narrow: system background without retrieval infra"**:

| Rank | Candidate | Note |
|---|---|---|
| 31 | CAND_0088438 — Sr SWE (ML) @ Saarthi.ai | No retrieval terms, but has system + career evidence |
| 34 | CAND_0076163 — NLP Engineer @ Ola | Same pattern |
| 35 | CAND_0068081 — CV Engineer @ Glance | Same pattern |
| 41 | CAND_0066999 — Rec Systems Eng @ Microsoft | Same pattern |
| 43 | CAND_0081321 — Sr SWE (ML) @ Freshworks | Same pattern |
| 47 | CAND_0044262 — Data Scientist @ upGrad | Same pattern |
| 49 | CAND_0072660 — ML Engineer @ Unacademy | Same pattern |

**Assessment:** These 7 candidates have **career evidence** (production + ownership) and **system terms** (ranking/recommendation) but lack explicit retrieval infrastructure terms (FAISS, BM25, Pinecone, etc.) in their career text. This is a precision signal, not a false positive per se — they are likely genuine ML engineers who worked on non-retrieval ranking systems. The JD covers recommendation systems explicitly, so their inclusion is defensible.

**Risk level: LOW** — no candidate in the Top 50 is flagged for having only keywords without career evidence. Zero surface-match risks.

---

## 5. Recall Analysis

Scanned 5,000 non-top-100 candidates with depth ≥ 3.

| Class | Count | Meaning |
|---|---|---|
| A (acceptable exclusion) | 1 | Trap flags or out-of-experience-range |
| B (possible systematic miss) | 1 | 5-9y, no traps, depth ≥ 3 |

**Class B candidate:** CAND_0000031 — Rec Systems Engineer @ Swiggy (6.0y), depth=3, no retrieval infra terms in career text.

**Assessment:** One candidate in 5,000 scanned with strong evidence not in top 100. Recall is well-defended.

---

## 6. Behavioral Signal Consistency

Per `redrob_signals_doc.docx` intent — signals are availability modifiers:

| Tier | Avg Availability | Open to Work | Notice ≤30d | Response ≥70% |
|---|---|---|---|---|
| Top 10 | 0.53 | 70% | 40% | 50% |
| Top 11-50 | 0.48 | 68% | 28% | 53% |
| Top 51-100 | 0.58 | 74% | 32% | 46% |

Behavioral scores are **not inversely correlated with rank** (which would indicate over-weighting). Top 10 has slightly higher average availability than Top 11-50 but not dramatically so. This confirms behavioral signals are functioning as modifiers, consistent with official doc intent.

---

## 7. Future Experiment Comparison

Use:
```bash
python -m backend.competition.evaluate \
    --baseline submission.csv \
    --experiment new_experiment.csv
```

Reports:
- Per-tier JD alignment delta
- Top-10 membership changes
- Top-50 membership changes
- Biggest rank movers (top 20)
- Class B recall changes

**Regression detection:** An experiment is flagged as a regression if:
- Top-10 JD alignment score drops > 0.02
- Trap flags appear in top 50
- Surface-match risk candidates enter top 50

---

## 8. Evaluator Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Career text is evidence-grounded but uses term matching | May miss paraphrased evidence | Calibration depth check (prod+own required) |
| Evaluation terms only capture explicit mentions | Candidate may have eval maturity without naming NDCG | Treated as minor gap, not disqualifier |
| Recall scan covers first 5,000 only (not 100K) | May miss strong candidates later in file | Increases scan with `--recall-scan 50000` |
| JD alignment score is internal, not official NDCG | Cannot guarantee correlation with leaderboard | Use as relative improvement signal only |
| Behavioral availability is averaged, not hiring-probability weighted | High availability at rank 100 doesn't help ranking | Behavioral remains modifier-only in scoring |

---

## 9. Files Added / Modified

| File | Status | Description |
|---|---|---|
| `backend/competition/evaluate.py` | **NEW** | Phase 8 evaluation harness |
| `submission.csv` | **UNCHANGED** | SHA-256 fingerprint verified |
| All ranking files | **UNCHANGED** | No scoring/weight changes |

Validation:
```
python -m backend.competition.validate_submission submission.csv
→ Submission is valid.

submission.csv SHA-256: 9a7c902888da6d9d66e578a24a45c6b3b7d6eb2f2e8bca20fa84cbe98792c34b
Matches pre-phase fingerprint: True
```

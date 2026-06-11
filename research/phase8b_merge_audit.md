# Phase 8B — Merge Decision Audit

**Date:** 2026-06-10  
**Auditor scope:** Review only. No code changed.  
**Decision:** See Section 5.

---

## 1. Confirmed Improvements

### 1.1 Honeypot / Wrong-Domain Eviction

Two candidates that Phase 7 already penalized with `wrong_domain_standalone` trap flags were pushed out of the Top 100 entirely by Phase 8B's additional -0.050 trap penalty:

| Candidate | Title | Phase7 Rank | Phase8B Rank | Correct? |
|---|---|---|---|---|
| CAND_0061819 | Junior ML Engineer @ Aganitha | 92 | 258 | ✅ Yes — career text shows CV/inference, not retrieval |
| CAND_0089381 | Computer Vision Engineer @ Ola | 95 | 259 | ✅ Yes — vision-domain, no ranking/retrieval career evidence |

These two were sitting in the top 100 only because their base scores were high (0.529, 0.531 respectively — Phase 7 trap reduction had already partially penalized them). The Phase 8B trap penalty finishes the job. **This is a genuine improvement.**

### 1.2 Eviction of Genuinely Off-Domain Candidates (depth=2)

The candidates that left the top 100 in Phase 8B include profiles that are clearly not ML/retrieval engineers. Their career text confirms this:

| Candidate | Actual career text | Correct to evict? |
|---|---|---|
| CAND_0016259 — Content Writer @ TCS | "operations management role at a logistics company... content writing and SEO strategy..." | ✅ Yes |
| CAND_0029847 — Marketing Manager @ Wipro | "marketing leadership... demand-generation, content marketing, paid acquisition, SEO, email nurture..." | ✅ Yes |
| CAND_0039087 — Sales Executive @ Wipro | "operations management... business analyst at a consulting firm..." | ✅ Yes |

These candidates were ranked in Phase 7 due to a base-score anomaly (word overlap + experience fit), not genuine retrieval/ranking evidence. Evicting them is correct. **This is a genuine improvement.**

### 1.3 Top-10 Composition Remains Strong

All 10 candidates in Phase 8B's top 10 have `depth=4/4` except rank 14 (demoted from rank 8). No trap flags, no surface-match risk. This is stable.

---

## 2. Possible Regressions

### 2.1 CRITICAL: Double-Counting of Retrieval + Eval Evidence

**This is the most significant structural flaw in Phase 8B.**

Phase 7's calibration (`evidence_calibrator.py`) already rewards retrieval/eval career hits with up to +0.10 score adjustment. Phase 8B's `depth_bonus = depth * 0.015` then counts the **same signals again**:

- `depth` increments for `has_eval_maturity` — already counted in Phase 7's `EVALUATION_MATURITY_TERMS`
- `depth` increments for `has_retrieval` — already counted in Phase 7's `RETRIEVAL_EXCELLENCE_GROUPS`

**Concrete example:**

```
CAND_0079387 (AI Engineer @ Microsoft):
  P7 calibration adj: +0.100  (maxed, signals: elasticsearch, embedding)
  P8 depth_bonus:     +0.060  (depth=4, double-counts same eval+retrieval signals)
  Net Phase8B gain:   +0.068  vs P7
```

The candidates that benefit most from Phase 8B (+0.060-0.068 net) are those that *already received a large Phase 7 calibration bonus*. This means Phase 8B preferentially lifts candidates that Phase 7 already lifted — reinforcing the same signal twice, not adding new information.

**Assessment:** The ranking changes are not entirely wrong (depth=4 candidates are genuinely better than depth=2 candidates), but the mechanism is flawed. The result is correct by coincidence, not by design. If Phase 7's calibration were recalibrated upward, the double-counting would produce over-inflated scores.

### 2.2 MODERATE: Demotion of CAND_0051630 from Rank 8

**CAND_0051630 — ML Engineer @ Razorpay (6.0y)**

```
Phase7 rank: 8   Phase8B rank: 14
Phase7 adj: +0.077 (elasticsearch, faiss, ranking career hits)
P8 depth:   3/4   (eval=False -- lacks explicit NDCG/MRR/A-B terms in career text)
P8 depth_bonus: +0.045 (vs +0.060 for depth=4 peers)
```

Career text excerpt: *"owned the ranking layer for an e-commerce search product, evolving it from a hand-tuned scoring function to a learning-to-rank model over 9 months. designed the relevance labeling pipeline (mix of click-through data and explicit human judgments), the feature pipeline, and the training/eval workflow..."*

This candidate **built and owns a production ranking/LTR system with an explicit eval workflow** including relevance labeling and click-through data. The JD explicitly asks for this. The reason they score depth=3 instead of 4 is that their career text doesn't include the literal tokens "ndcg", "mrr", "a/b test", "evaluation framework" — yet they clearly have evaluation maturity. This is a false demotion caused by **term-matching as a proxy for evidence**, exactly the pattern Phase 7B was designed to fix.

**Assessment:** CAND_0051630 being pushed from rank 8 to 14 is a mild regression. The candidate is still top 20, so it does not disqualify Phase 8B, but it reveals the evaluator's vocabulary bias.

### 2.3 LOW: 4.9-Year Candidate in Top 100 (CAND_0012957)

Phase 8B admits CAND_0012957 (Search Engineer @ Razorpay, 4.9y) at rank 100 due to depth=4 bonus. The JD says "5-9 years (see what we mean by this)" and explicitly notes it is a range, not a hard requirement. The career text is strong (LTR, relevance pipeline, FAISS/BM25). This is an acceptable edge case, not a regression.

### 2.4 LOW: "AI Engineer @ Apple" (rank 68 → 95) Flagged

CAND_0008239 — depth=2, eval=False, ret=False, but career text shows ML platform/inference engineering. Apple title was high-ranking in Phase 7 partially due to base-score term overlap. The demotion to 95 is defensible by evidence but close to the boundary.

---

## 3. Evaluator Bias Analysis

### Did Phase 8B genuinely improve ranking, or just score well against Phase 8A?

**Conclusion: Partially both. The improvement is real but the measurement is circular.**

The Phase 8A evaluator and the Phase 8B reranker share the **same signal definitions**:
- Both use `JD_EVAL_MATURITY_TERMS` (ndcg, mrr, a/b test, ...)
- Both use `JD_RETRIEVAL_TERMS` (faiss, bm25, embedding, ...)
- Both compute `evidence_depth` the same way

When Phase 8B's reranker optimizes for `depth` (its bonus), and Phase 8A's evaluator scores by `eval_maturity_pct` and `retrieval_infra_pct`, **they will trivially agree** because they count the same tokens. The improvement in "JD Alignment Score" is partly real and partly tautological:

```
Phase 8B optimizes for → eval terms + retrieval terms in career text
Phase 8A measures →      eval terms + retrieval terms in career text
∴ Phase 8B scores well on Phase 8A by construction.
```

**What provides independent validation:**
- The eviction of the Content Writer, Marketing Manager, Sales Executive is validated by manual career text inspection — these are genuinely non-ML profiles.
- The top-10 stability (all depth=4, all strong career evidence) is valid.
- The double-counting issue was NOT caught by Phase 8A (since Phase 8A doesn't model the Phase 7 calibration signal).

**Risk:** If the hidden evaluation uses a different proxy for "real ranking quality" (e.g., recruiter engagement rate, human relevance judgments), Phase 8B's term-counting bias may not translate to leaderboard improvement.

---

## 4. Regression Search Summary

| Risk | Category | Severity | Impact |
|---|---|---|---|
| Double-counting retrieval+eval signals from Phase 7 | Structural flaw | **MEDIUM** | Inflated scores for depth=4 candidates (already at P7 max calibration); ordering is coincidentally correct but fragile |
| CAND_0051630 demoted rank 8→14 | Evidence mismatch | **LOW-MEDIUM** | Strong ranking engineer without eval keywords loses top-10 spot |
| Circular evaluator bias (Phase 8A + 8B share term sets) | Measurement bias | **MEDIUM** | Phase 8B "scores well" on the evaluator by construction, not by independent validation |
| 4.9y candidate admitted (CAND_0012957) | Minor boundary violation | **LOW** | Career is strong; JD treats experience as a range |
| Non-ML profiles correctly evicted | POSITIVE | — | Content Writer, Marketing Manager, Sales Executive removed |
| Two trap candidates fully evicted | POSITIVE | — | CAND_0061819 and CAND_0089381 correctly pushed out |

---

## 5. Merge Decision

### **MODIFY PHASE 8B FIRST**

**Rationale:**

Phase 8B produces **directionally correct improvements** — evicting off-domain candidates, reinforcing trap-flag detection, and admitting better-evidenced ML candidates. However, it has two structural issues that should be resolved before merging:

**Issue 1 — Double-counting:** The Phase 8B `depth_bonus` rewards the same retrieval/eval signals that Phase 7 calibration already rewards. The bonus should be scoped only to signals **not** already captured in `calibration.adjustment`. A simple fix: only apply the depth bonus when the Phase 7 calibration was below its max (~0.100). This ensures the reranker adds information rather than amplifying existing signals.

**Issue 2 — Evaluator circularity:** Phase 8A cannot serve as independent validation for Phase 8B because they share signal definitions. A future evaluation pass should compare against an *independently-defined* quality signal (e.g., career-text sentence quality score, not term counts) to break the circularity.

**What can be merged as-is:**
- The trap-flag reinforcement (-0.050 additional penalty) is clean and non-redundant. This could be folded into Phase 7's calibration.
- The eviction of non-ML profiles (Content Writer, Marketing Manager, Sales Executive) is correct. These were Phase 7 base-score false positives.
- The Top 10 ordering is acceptable. No candidate with serious issues entered the top 10.

**Recommendation:** Fix the depth_bonus double-counting scope before replacing `submission.csv` with `submission_phase8b.csv`. The current Phase 8B experiment should not be the final submission without that correction.

---

## 6. Files Reviewed (no changes made)

| File | Purpose |
|---|---|
| `backend/competition/rerank_experiment.py` | Phase 8B reranker implementation |
| `backend/competition/evaluate.py` | Phase 8A evaluator (signal definitions shared with reranker) |
| `backend/competition/evidence_calibrator.py` | Phase 7 calibration (source of double-counting concern) |
| `backend/competition/rank.py` | Phase 7 base scoring |
| `submission.csv` | Phase 7 baseline (unchanged, SHA-256 verified) |
| `submission_phase8b.csv` | Phase 8B experiment output |

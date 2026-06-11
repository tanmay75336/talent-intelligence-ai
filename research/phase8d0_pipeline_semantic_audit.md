# Phase 8D.0 — Current Ranking Architecture Trace + Semantic Feasibility Audit

**Date:** 2026-06-11  
**Status:** Architecture audit complete. No implementation.  
**Target Submission:** `submission_phase8c4.csv`  

---

## Task 0: True Execution Path

The exact execution path that generated `submission_phase8c4.csv` originates from `backend/competition/phase8c4_experiment.py`.

**Trace:**
1. **Entry Point:** `run_phase8c4(candidates_path, job_path, output_path)` in `backend/competition/phase8c4_experiment.py`.
2. **Setup:** 
   - `job_text = read_job_text(job_path)`
   - `job_analysis = analyze_job_description(job_text)`
   - `job_terms = _important_terms(job_text)`
3. **Candidate Loading:** Iterates over all candidates using `iter_dataset_records` in `backend/dataset_intelligence/loader.py`, adapted via `adapt_redrob_candidate` in `backend/competition/redrob_adapter.py`.
4. **Feature Extraction (Base):**
   - Core signals extracted via `build_competition_core_signals(p)` in `backend/intelligence/candidate_engine.py`.
   - Base score computed via `_competition_score_c4(p, core, job_analysis, job_terms)` in `backend/competition/phase8c4_experiment.py`. This includes the 0.5× `_career_evidence_score` multiplier for production disclaimers.
5. **Candidate Reduction 1 (Early Exit):**
   - Candidates are maintained in a min-heap (`top_candidates`) of size 300.
   - If `base + MAX_EVIDENCE_ADJUSTMENT < top_candidates[0][0]`, the candidate is immediately skipped to save computation.
6. **Feature Extraction (Calibration):**
   - `calibrate_candidate_evidence(p)` in `backend/competition/evidence_calibrator.py` processes the text into bonuses and penalties.
7. **Scoring:**
   - `score = _calibrated_score(base, cal)` in `backend/competition/rank.py`.
8. **Reranking:**
   - The top 300 candidates (`pool`) undergo Phase 8B.3 reranking in `phase8c4_experiment.py`.
   - Uses `_extract_career_signals` and `_extract_behavioral_signals` from `backend/competition/evaluate.py`.
   - Uses `_headroom_depth_bonus` from `backend/competition/rerank_experiment.py`.
9. **Candidate Reduction 2 (Final):**
   - The 300 candidates are sorted descending by `new_score`.
   - Sliced to `top100 = reranked[:100]`.
10. **Reasoning & CSV Generation:**
   - `_competition_reasoning(...)` in `backend/competition/rank.py`.
   - Written using `csv.DictWriter`.

---

## Task 1: Pipeline Flow Reconstruction

```text
Raw candidates (data/candidates.jsonl)
      |
      ↓
(Candidate Engine + Base Scoring + Heap Filter) -> backend/competition/phase8c4_experiment.py
(~100,000 candidates processed, early-exit filter applied)
      |
      ↓
(Evidence Calibrator + Calibrated Score) -> backend/competition/evidence_calibrator.py
(300 candidates enter the intermediate pool)
      |
      ↓
(Reranker Phase 8B.3 Logic) -> backend/competition/phase8c4_experiment.py
(300 candidates reranked)
      |
      ↓
(Top 100 Selection) -> backend/competition/phase8c4_experiment.py
(100 candidates)
      |
      ↓
Final output: submission_phase8c4.csv
```

---

## Task 2: Active vs Unused Code

**ACTIVE:** (Used in the generation of `submission_phase8c4.csv`)
- `backend/competition/phase8c4_experiment.py` (Orchestrator, Base Score, Reranker orchestrator)
- `backend/competition/rank.py` (`_calibrated_score`, `_ratio`, `_experience_fit`, `_important_terms`, `_competition_reasoning`)
- `backend/competition/evidence_calibrator.py` (Calibration extraction)
- `backend/competition/evaluate.py` (`_extract_career_signals`, `_extract_behavioral_signals`)
- `backend/competition/rerank_experiment.py` (`_headroom_depth_bonus`, `_has_eval_context`)
- `backend/intelligence/candidate_engine.py` (`build_competition_core_signals`)
- `backend/parsers/jd_analyzer.py` (`analyze_job_description`)
- `backend/competition/redrob_adapter.py` (`adapt_redrob_candidate`)

**EXPERIMENTAL / UNUSED:** (Present but inactive for final ranking)
- `backend/competition/phase8c3_experiment.py`
- `backend/competition/phase8b2_experiment.py` (and related older phase scripts)
- `backend/competition/rank.py`'s `run_competition` function (bypassed entirely by Phase 8 scripts).

---

## Task 3: Complete Signal Discovery

All signals are determined deterministically using token overlap, ratio calculations, and substring searches.

**1. Base Score Signals (Scope: All Candidates)**
- **`skill_overlap`:** Overlap of candidate skills vs JD core skills (Weight: 0.26).
- **`group_overlap`:** Overlap of active skill groups (Weight: 0.16).
- **`term_overlap`:** Overlap of extracted terms in profile text vs JD text (Weight: 0.18).
- **`experience_fit`:** Gaussian-like decay around target years (Weight: 0.12).
- **`signal_average`:** Aggregate of core signals from `candidate_engine` (Weight: 0.20).
- **`career_evidence`:** Hits of `AI_INFRA_TERMS` in career text, with 0.5× penalty if `PROD_DISCLAIMER_PHRASES` are present (Weight: 0.08).

**2. Calibration Signals (Scope: Top ~1,000 candidates that pass the `base + MAX_ADJUSTMENT` threshold to reach the heap)**
- **`career_ai_hits` bonus:** up to +0.030 for AI infra terms.
- **`production ownership` bonus:** up to +0.024 if production, ownership, and AI infra terms are all present.
- **`experience range` bonus:** +0.010 for 5-9 YoE with ownership + domain relevance.
- **`high experience` penalty:** -0.010 for >=15 YoE.
- **`startup` bonus:** +0.006 for startup + ownership + domain relevance terms.
- **`retrieval excellence` bonus:** up to +0.015 for specialized retrieval tool overlaps.
- **`evaluation maturity` bonus:** up to +0.015 for eval metric overlaps (NDCG, MRR, etc.).
- **`behavioral tie breaker`:** up to +0.012 based on GitHub, open-to-work, assessments.
- **`close call weak ai` penalty:** -0.010 to -0.015 for keyword-heavy profiles without depth.
- **`trap penalties`:** -0.020 to -0.060 for honeypots, framework-only profiles, etc.

**3. Reranker Signals (Scope: Top 300 Pool)**
- **`depth_bonus`:** Headroom-scaled depth bonus (up to +0.030) rewarding comprehensive evidence traces without double counting.
- **`behavioral_bonus`:** `(availability + engagement) * 0.005`.
- **`surface_penalty`:** -0.030 for superficial skill match risk.
- **`trap_penalty`:** -0.050 hard penalty applying calibrator trap flags again at rerank stage.

---

## Task 4: Current Bottleneck Identification

**A) Candidate Discovery / Recall Issue is the primary bottleneck.**

*Evidence:* The entire pipeline relies on an early-exit heap of size 300 (`top_candidates`). A candidate *must* score high enough on the Base Score (`_competition_score_c4`) to enter this pool, otherwise their calibration and reranking are skipped. The Base Score allocates 60% of its weight to exact token overlaps (`skill_overlap`, `group_overlap`, `term_overlap`). 
If a candidate uses equivalent but non-matching vocabulary (e.g., "relevance optimization platform" instead of "search ranking", or "nearest neighbor lookups" instead of "vector database"), their base score will be artificially low, and they will be discarded during the pass over 100,000 candidates before their actual evidence can be evaluated.

---

## Task 5: Semantic Value Analysis

**Role:** OPTION 1: Semantic Candidate Discovery
- **What weakness it solves:** Bypasses the exact-token overlap bottleneck in the Base Score.
- **Expected benefit:** Surfaces candidates who have strong, equivalent experience but use different vocabulary, bringing them into the Top 300 pool where the evidence calibrator and reranker can evaluate them fairly.
- **Failure risk:** High false positives if semantic matching misinterprets generic AI as specific AI infra.
- **Runtime impact:** Cannot run heavy embeddings on 100,000 candidates synchronously in a CPU-bound benchmark. Must rely on fast/pre-computed semantic indices or lightweight heuristic expansions.

**Other Roles Rejected:**
- Semantic Evidence Interpretation (Option 2): Not needed yet; the current string-based calibrator is highly effective once candidates reach the top 300.
- Semantic Reranking Support (Option 3): The top 100 ordering is already very accurate per Phase 8C.4 testing.

---

## Task 6: Where Semantic Discovery Should Fit

Architecture evaluation:
```text
Existing Base Score Discovery (exact overlap)  +  Semantic Discovery (vector/embedding)
                     ↓                                            ↓
               Top 300 candidates                         Top 300 candidates
                                     ↘        ↙
                        Combined Candidate Pool (~600 max)
                                         ↓
                     Existing Evidence Calibration + Reranking
                                         ↓
                                  Top 100 Final
```
Semantic should **only** influence candidate discovery (recall). It should bypass the base score entry gate to nominate candidates into the intermediate pool. It should **not** influence the final score weights, preserving the deterministic and proven Phase 8C.4 evidence calibration and reranking logic.

---

## Task 7: Final Decision

**B) TEST SEMANTIC CANDIDATE DISCOVERY**

**Reason:** A structural recall bottleneck exists. Candidates who don't match exact JD terminology in their base profile are filtered out before the top 300 pool, meaning the sophisticated evidence calibrator and reranker never see them. Testing semantic discovery to feed candidates into the proven 8C.4 evidence pipeline is the safest, highest-ROI next step.

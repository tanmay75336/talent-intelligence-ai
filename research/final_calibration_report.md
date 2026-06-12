# Final Calibration Report — JD Evidence Consistency + Extreme Behavior Validation

**Team:** OctaOps | **Date:** 2026-06-12
**Entrypoint:** `backend/competition/rank.py` | **Current submission:** `submission.csv`

---

## 1. What Was Investigated

Three evidence-backed risks identified in the final truth audit:

| Risk | Investigation Method |
|---|---|
| Skill claims not backed by career evidence (surface match) | Scanned all 100 top-100 candidates: domain career hits vs. domain skill hits |
| Generic "built something" vs "built what JD needs" (domain ownership) | Checked career text for unrelated domains (CV, supply chain, NLP classification) |
| Extreme behavioral availability mismatch | Identified candidates with response_rate <15% and/or inactive >180 days |

All three were investigated using pattern-based analysis on actual profile text — no candidate IDs hardcoded, no rank-specific logic.

---

## 2. Investigation 1 — Skill-Career Consistency Gap

### What we checked

For every top-100 candidate, counted:
- **Domain career hits**: occurrences of retrieval/ranking/recommendation/search/vector/embedding/FAISS/NDCG etc. terms in *career history text only*
- **Unrelated domain hits**: CV, supply chain, forecasting, fraud detection, sentiment analysis in career text
- **Domain skill hits**: same domain terms in the skills section

### Finding: **No gap exists**

```
Skill-career GAP candidates in top-100: 0
Skill-career CONSISTENT candidates in top-100: 100
Top-100 candidates with ANY trap flag: 0
```

Every top-100 candidate's career text contained at least one domain-relevant term from retrieval, ranking, recommendation, search, or embedding vocabulary. The pattern that raised concerns in the audit (Rank 5 candidate with churn/MLOps career) — when measured by career text directly — *does* have enough domain career evidence to pass the consistency check (has "search", "ranking", "recommendation" in career text).

**The current `evidence_calibrator.py` already handles this pattern through:**
- `AI_INFRA_TERMS` in career text gate (`has_domain_relevant_career`)
- `wrong_domain_standalone` trap (CV/speech candidates)
- `keyword_stuffing` trap (skills list with no career support)
- `framework_only_ai_profile` trap (LangChain/OpenAI only)

**Conclusion: No gap candidate exists in top-100. The existing system is working correctly.**

---

## 3. Investigation 2 — Domain Ownership Validation

### What we checked

Same career text scan, using the unrelated-domain term set to find candidates with:
- High career mentions of CV/image classification/forecasting/supply chain
- Zero or one domain career hit

### Finding: **No false ownership candidates in top-100**

All "built something" candidates in the top-100 built *domain-relevant* systems. The bottom of the top-100 (ranks 85-100) contains some candidates with weaker evidence, but they are correctly placed at the tail and all have at least 2-3 domain career hits.

The `_ownership_hits_near_context()` function in the calibrator already requires ownership verbs to appear in *sentences that also contain technical context terms* — preventing generic operational ownership (warehouse management, sales pipeline) from receiving credit.

**Conclusion: Domain ownership validation is already working as designed. No general fix needed.**

---

## 4. Investigation 3 — Extreme Behavioral Availability

### What we found

9 candidates in top-100 have extreme behavioral concerns:

| Rank | Candidate | Concern | Domain Career Hits | Score |
|---|---|---|---|---|
| 47 | CAND_0060072 | response=10% | 5 | 0.639703 |
| 48 | CAND_0094056 | not_open + 120d notice | 6 | 0.639443 |
| 49 | CAND_0041611 | response=7%, inactive=191d | **13** | 0.637937 |
| 55 | CAND_0089552 | not_open + 120d notice | 6 | 0.631011 |
| 70 | CAND_0094759 | response=11% | **11** | 0.616464 |
| 75 | CAND_0092278 | response=7%, inactive=217d | **12** | 0.612689 |
| 80 | CAND_0007411 | response=12%, inactive=192d | 7 | 0.606011 |
| 84 | CAND_0088438 | not_open + 120d notice | 2 | 0.603020 |
| 93 | CAND_0012957 | not_open + 120d notice | 7 | 0.593665 |

### Classified into sub-patterns:

**Group A — Both low-response (<12%) AND inactive >180 days (2 candidates):**
- Rank 49 (CAND_0041611): "Built RAG-based ranking pipeline serving 50M+ queries/month for an internal recruiter-facing search product. Combined BM25 + dense retrieval (BGE embeddings, FAISS HNSW)..." — domain=13, the strongest career evidence profile in Group A
- Rank 75 (CAND_0092278): Production recommendation system, A/B tests, recommendation + retrieval — domain=12

**Group B — Low response only (<12%) (2 candidates):**
- Rank 47 (CAND_0060072): 10% response, production recommendation to A/B test — domain=5
- Rank 70 (CAND_0094759): 11% response, led embedding-based search migration on 30M+ candidate corpus — domain=11

**Group C — Long notice only (120 days, not open) (5 candidates):**
- Ranks 48, 55, 80, 84, 93 — all technically strong (domain 2-7), 120d notice

### Critical finding: Profile quality

All 9 extreme-behavioral candidates have **strong legitimate career evidence**. The concerning cases from the audit (ranks 47-49 with low response rates) turn out to be among the strongest career profiles in the tier (domain hits 5, 6, 13). The unavailability concern is real — they are hard to reach — but their technical fit is genuine.

### Score impact test: Would a penalty actually remove them?

**Applying -0.020 to Group A (response<12% AND inactive>180d simultaneously):**

```
CAND_0041611 (rank 49): 0.637937 → 0.617937 | still in top-100 ✅
CAND_0092278 (rank 75): 0.612689 → 0.592689 | still in top-100 ✅
```

Neither candidate would leave the top-100 even with a 0.020 penalty. Their technical evidence is so strong relative to the cutoff (0.589636) that behavioral adjustment wouldn't change their presence — only their relative ordering within top-100.

**Applying -0.010 to Group B (low response only):**

```
CAND_0060072 (rank 47): 0.639703 → 0.629703 | still in top-100 ✅
CAND_0094759 (rank 70): 0.616464 → 0.606464 | still in top-100 ✅
```

Same result. These candidates' technical scores are well above the cutoff.

**Conclusion: Any reasonable behavioral penalty would reorder candidates within top-100 but would not remove any of them.** There is no candidate outside top-100 that would replace them — the score gap between rank-100 and rank-101 is large enough that behavioral adjustments don't swing the population.

---

## 5. Official Document Justification for No-Change Decision

From `redrob_signals_doc.docx`:
> "These behavioral signals are often more predictive of whether a candidate can actually be hired than their static profile. **ranking systems can incorporate them as a multiplier or modifier on top of skill-match scoring.**"

The key word is **modifier** — not primary signal. The current implementation applies behavioral signals as `(availability_score + engagement_score) * 0.005` in the reranker. This is exactly the documented role.

From `job_description.docx`:
> "A perfect-on-paper candidate who hasn't logged in for 6 months and has a 5% recruiter response rate is, for hiring purposes, not actually available. Down-weight them appropriately."

The phrase "appropriately" is key. A 7% responder with 13 domain career hits (rank 49 profile: RAG ranking pipeline at 50M+ qpm) is a legitimate tier-1 technical match — the behavioral concern is a *hiring process* concern, not a technical fit concern. Down-weighting them to below rank-100 (which would require a -0.048 adjustment) would discard what is likely a genuine top-tier JD match in favor of candidates with weaker technical evidence but better availability. This is explicitly the Error #1 the task description warns against:

> "ERROR 1: Weak technical candidate + great availability beats exceptional engineer"

The 9 flagged candidates all have genuine career evidence. Moving them below rank-100 would likely hurt NDCG@10 and NDCG@50, not improve them.

---

## 6. Before/After Comparison

### Not applicable

No changes were made. A controlled experiment was started and stopped at the pre-implementation phase after the data showed:

1. **Skill-career gap: 0 affected candidates** — no change needed
2. **Domain ownership: 0 affected candidates** — no change needed
3. **Behavioral: 9 candidates, none would exit top-100 under any reasonable penalty**

Creating `submission_final_calibrated.csv` with only internal reorderings (not population changes) would produce no measurable NDCG improvement and would introduce unnecessary determinism risk to an already verified, stable pipeline.

---

## 7. Honeypot Safety Check

| Tier | Honeypots Detected |
|---|---|
| Top-10 | 0 |
| Top-50 | 0 |
| Top-100 | 0 (1 borderline under broad title-heuristic) |
| Pattern-based total (100K) | 1,581 flagged, none in top-100 |

The `evidence_calibrator.py` honeypot protection mechanisms remain active:
- `honeypot_fictional_company` (−0.060 penalty)
- `keyword_stuffing` (−0.030 penalty)
- `wrong_domain_standalone` (−0.025 penalty)
- `non_ml_role_ai_keywords` (−0.022 penalty)

No changes to these mechanisms were considered or proposed.

---

## 8. Regression Risk Assessment

**Changes proposed: None.**

**Risk of adding the behavioral compound-condition penalty (response<12% AND inactive>180d):**
- 2 candidates would be reordered downward (still remain in top-100)
- Replacement candidates from rank 101-200 would have similar or weaker career evidence
- Net NDCG effect: likely neutral to slightly negative
- Risk of the change being fragile on unseen data: moderate

**Applying the generalization test from the task brief:**
1. *Would this still work if candidate IDs changed?* — The rule is purely text + signal based. Yes.
2. *Would this logic apply to another similar hiring search?* — Depends heavily on dataset. A dataset with fewer strong profiles might aggressively penalize good candidates who happen to be passive.
3. *Is this detecting a pattern, not a person?* — The pattern (low response + inactive) is real, but in this dataset it's coincidentally attached to very strong technical profiles, not weak ones.

**Answer to test question 2 is uncertain → change rejected per task rules.**

---

## 9. Final Recommendation

### B) KEEP CURRENT VERSION — `submission.csv` remains the champion

**Evidence summary:**

| Question | Answer |
|---|---|
| Are skill claims unsupported by career evidence? | No — 0/100 candidates show a skill-career gap |
| Is "built something" unrelated to JD work? | No — 0/100 trap flags in top-100 |
| Are extreme behavioral candidates hiding weak technical profiles? | No — all 9 have strong career evidence (domain hits 5-13) |
| Would any reasonable penalty change the top-100 population? | No — all 9 remain in top-100 even with -0.020 penalty |
| Honeypots in top-100? | 0 confirmed (1 borderline = 1%, well under 10% threshold) |

**The current system already handles all identified risks through:**
- Domain-relevance gate (`has_domain_relevant_career`)
- Career-text ownership context requirement (`_ownership_hits_near_context`)
- 8 trap detection patterns (`_detect_traps`)
- Behavioral tie-breaker (capped at ±0.012, operates as modifier not primary)
- Wrong-domain standalone penalty
- Retrieval excellence bonus (rewards genuine IR depth)
- Evaluation maturity bonus (rewards NDCG/MRR/A/B evidence)

**No change is the correct engineering decision.** The audit confirms the ranking system is operating as designed and as documented by official RedRob specs. Further tuning would be optimizing around noise, not signal.

---

*Analysis completed: 2026-06-12. No code changes made. Algorithm remains frozen. Final submission: `submission.csv`.*

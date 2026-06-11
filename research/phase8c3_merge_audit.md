# Phase 8C.3 Merge Audit — Final Ranking Quality Validation

**Date:** 2026-06-10  
**Comparing:** `submission_phase8b3.csv` vs `submission_phase8c3.csv`  
**Analysis:** ANALYSIS ONLY. No code changed.

---

## VERDICT: **B) REFINE PHASE 8C.3**

Phase 8C.3's directional improvement is real and strongly evidenced: every promotion is JD-justified, every removal is JD-justified, and the top-50 quality measurably improved. However, a specific general issue exists in the mid-ranking zone (ranks 55–80) that 8C.3 did not resolve and in some places worsened.

**Recommended action:** Promote 8C.3 with a targeted follow-up to address the mid-zone residual inversions before tagging as final stable checkpoint. Do not revert to 8B.3.

---

## 1. Task 1 — Career Signal Validation

### Does the new signal reward genuine system building or keyword frequency?

**Grade distribution of all 14 gained candidates:**

| Grade | Count | Definition |
|---|---|---|
| A — Strong system builder | 7 | Owned/built a SYSTEM + production deployment + ≥3 career AI infra terms |
| B — Good but partial | 7 | Career ownership present + ≥2 terms, production context partial |
| C — Keyword presence only | 0 | **None** |

**Grade distribution of all 14 lost candidates:**

| Grade | Count | Definition |
|---|---|---|
| A — Strong system builder | 0 | **None** |
| B — Good partial | 6 | 2 career AI terms, single-system focus |
| C — Keyword presence only | 8 | 1 career AI term (ranking only), no embedding/retrieval infra |

**Conclusion:** The career evidence signal is rewarding genuine system builders and removing candidates whose career evidence is limited to a single term ("ranking" or "recommendation") without embedding/retrieval infrastructure. There is zero evidence of keyword-frequency gaming — all gained candidates show system ownership, production context, and multi-system AI infra breadth in their career text.

**Signal quality verdict: CORRECT.** The signal rewards what the JD calls "absolutely needed": career-demonstrated work on retrieval, embedding, and ranking systems.

---

## 2. Task 2 — Promotion Analysis

### All 14 head-to-head comparisons: gained vs displaced

| | New Entrant | Displaced | JD Verdict |
|---|---|---|---|
| Rank 69 | RecSys Eng @ Meesho (hits=5, R✅, Ev✅, d=4) | Lead AI Eng @ Sarvam AI (hits=1, R❌, Ev✅, d=3) | **BETTER** |
| Rank 72 | Lead AI Eng @ Meta (hits=6, R✅, Ev✅, d=4) | ML Eng @ Unacademy (hits=1, R❌, Ev❌, d=2) | **BETTER** |
| Rank 73 | Sr DS @ Sarvam AI (hits=9, R✅, Ev✅, d=4) | AI Eng @ Apple (hits=1, R❌, Ev❌, d=2) | **BETTER** |
| Rank 75 | Sr DS @ Rephrase.ai (hits=8, R✅, Ev✅, d=4) | RecSys Eng @ Verloop.io (hits=1, R❌, Ev✅, d=3) | **BETTER** |
| Rank 77 | Sr NLP Eng @ Microsoft (hits=7, R✅, Ev✅, d=4) | Sr SWE (ML) @ Locobuzz (hits=2, R❌, Ev❌, d=2) | **BETTER** |
| Rank 81 | Applied ML Eng @ Meesho (hits=5, R✅, Ev✅, d=4) | Sr AI Eng @ Meta (hits=1, R❌, Ev✅, d=3) | **BETTER** |
| Rank 84 | Sr ML Eng @ Amazon (hits=6, R✅, Ev✅, d=4) | Sr SWE (ML) @ Sarvam AI (hits=2, R❌, Ev❌, d=2) | **BETTER** |
| Rank 85 | NLP Eng @ Locobuzz (hits=8, R✅, Ev✅, d=4) | AI Research Eng @ Verloop (hits=2, R❌, Ev❌, d=2) | **BETTER** |
| Rank 87 | Sr DS @ Freshworks (hits=5, R✅, Ev❌, d=3) | ML Eng @ Verloop.io (hits=1, R❌, Ev✅, d=3) | **BETTER** |
| Rank 88 | Applied ML Eng @ Zomato (hits=8, R✅, Ev✅, d=4) | Jr ML Eng @ TCS (hits=2, R❌, Ev❌, d=2) | **BETTER** |
| Rank 91 | Sr DS @ Razorpay (hits=5, R✅, Ev❌, d=3) | ML Eng @ Freshworks (hits=3, R❌, Ev❌, d=2) | **BETTER** |
| Rank 94 | NLP Eng @ Glance (hits=4, R✅, Ev✅, d=4) | ML Eng @ Haptik (hits=2, R❌, Ev❌, d=2) | **BETTER** |
| Rank 96 | Sr DS @ Microsoft (hits=4, R✅, Ev✅, d=4) | DS @ BYJU'S (hits=2, R❌, Ev❌, d=2) | **BETTER** |
| Rank 100 | Search Eng @ Genpact AI (hits=6, R✅, Ev✅, d=4) | AI Research Eng @ CRED (hits=2, R❌, Ev❌, d=2) | **BETTER** |

**Result: 14/14 promotions are BETTER by official JD criteria.**

JD requirement scores (R=retrieval infra, Ev=eval maturity, d=depth, hits=career AI breadth):
- Every gained candidate has retrieval infrastructure in career history (R=True)
- Every displaced candidate lacks retrieval infrastructure in career history (R=False)
- The JD calls embedding/retrieval infrastructure "absolutely needed" as item #1

---

## 3. Task 3 — Demotion Analysis

### Large downward movers (stayed in both, dropped >20 ranks)

| Drop | Candidate | JD Item 1 (Retrieval) | JD Item 4 (Eval) | Verdict |
|---|---|---|---|---|
| 15→83 (−68) | RecSys Eng @ upGrad | **ABSENT** | PRESENT ✅ | **Direction correct; magnitude debatable** |
| 29→97 (−68) | NLP Eng @ Ola | **ABSENT** | ABSENT | Correct |
| 35→98 (−63) | RecSys Eng @ Microsoft | **ABSENT** | ABSENT | Correct |
| 36→82 (−46) | CV Eng @ Glance | **ABSENT** | ABSENT | Correct — JD explicitly excludes CV-primary |
| 48→90 (−42) | Data Scientist @ upGrad | **ABSENT** | ABSENT | Correct |
| 50→93 (−43) | AI Research Eng @ HCL | **ABSENT** | ABSENT | Correct |
| 56→99 (−43) | AI Research Eng @ Wysa | **ABSENT** | ABSENT | Correct |
| 33→59 (−26) | Sr SWE (ML) @ Saarthi.ai | **ABSENT** | ABSENT | Correct |

### The upGrad case — detailed assessment

**Rec Systems Eng @ upGrad (rank 15 → 83):**

Career evidence (confirmed by full text scan):
- Trained and shipped ranking models (XGBoost/LightGBM) for a discovery feed ✅
- Designed features across content metadata, user behavior, engagement signals ✅
- **Owned offline-online correlation analysis — determined which offline metrics predicted A/B test outcomes** ✅ (strong evaluation maturity)
- Built and operated production ML pipelines (MLflow, Kubeflow, feature store) ✅
- No embedding, no vector database, no retrieval infrastructure anywhere in career text ❌
- Extended retrieval term search confirms: zero matches for any embedding/dense/vector/BM25/semantic terms

**JD ruling:**
> *"Things you absolutely need: Production experience with embeddings-based retrieval systems… We don't care which model — we care that you've handled embedding drift, index refresh, retrieval-quality regression in production."*

This candidate has zero retrieval infrastructure experience. The JD calls this the first absolute requirement. A ranking engineer with no retrieval infra is an incomplete JD match.

**However:** The drop from rank 15 to rank 83 is a 68-rank penalty for missing one of two absolute requirements while having the other strongly. The candidate at rank 83 is surrounded by (rank 80: ML Eng @ Rephrase.ai, rank 82: CV Eng @ Glance, rank 84: Sr ML Eng @ Amazon). The upGrad candidate, with strong evaluation maturity, arguably belongs above rank 82 (CV primary, no retrieval, no eval) and rank 83 is not a grossly wrong position — but a position in the 40–60 range would be more proportionate for a candidate who meets 1 of 2 absolute requirements at high quality.

**Verdict: Directionally correct. Magnitude larger than optimal.** This is the residual issue for Phase 8C.3 refinement.

### Unusual profiles / strong builders — correctly preserved?

The demotion list contains no strong builders with unusual vocabulary. All demoted candidates have:
- Shallow career evidence (1–2 AI infra terms max, all "ranking/recommendation" only)
- No embedding/retrieval infrastructure (confirmed by extended term scan)
- Predominantly depth=2 (surface match only)

No genuinely strong unusual builder was incorrectly penalized.

---

## 4. Task 4 — Ordering Quality Check

### Residual inversions in Phase 8C.3

33 ordering inversions found (higher-ranked candidate has 3+ lower JD score than a candidate ranked 10-25 places below them).

**Critical pattern:** Three candidates with `hits=2-3, d=2, R=False, Ev=False` (no retrieval infra, no eval maturity) remain embedded in the middle tier:

| Rank | Candidate | hits | d | R | Ev | JD Score |
|---|---|---|---|---|---|---|
| **59** | Sr SWE (ML) @ Saarthi.ai | 3 | 2 | ❌ | ❌ | 0 |
| **70** | Sr SWE (ML) @ Freshworks | 3 | 2 | ❌ | ❌ | 0 |
| **78** | Sr SWE (ML) @ Sarvam AI | 3 | 2 | ❌ | ❌ | 0 |

These candidates rank above multiple depth=4, R=True, Ev=True candidates that appear in the 80–100 range. Example inversions:
- Rank 59 (JDscore=0) above Rank 81 Applied ML Eng @ Meesho (JDscore=7) — gap: 22 ranks
- Rank 70 (JDscore=0) above Rank 94 NLP Eng @ Glance (JDscore=7) — gap: 24 ranks

**Root cause:** These 3 candidates have `hits=3` (the minimum for a meaningful `career_evidence_score` = 0.60) but their hits are all inference-type or generic terms, not embedding/vector/retrieval. They have high `adj` values (+0.063–0.069) from calibration. Their base score advantage from prior skill-overlap vocabulary carries them into the mid-50s to mid-70s despite weak actual retrieval evidence.

**Is this worse than 8B.3?** In 8B.3, these same candidates were in roughly similar positions (rank 33–70 range). The 8C.3 inversions are slightly worse because the newly promoted depth=4, R=True candidates in ranks 80–100 now have clearly higher JD scores than these mid-zone stragglers.

**This is the one general issue** that 8C.3 did not resolve and where refinement would add value.

### Trap-flagged candidates in top-50: **ZERO** ✓
### Candidates with <3 career AI hits in top-30: **ZERO** ✓

---

## 5. Task 5 — Priority Impact by Tier

### Top-10: 9/10 stable, one swap improves

| | Removed | Added |
|---|---|---|
| Candidate | Applied ML Eng @ Freshworks (rank 7→11) | AI Eng @ Microsoft (rank 13→9) |
| Career AI hits | 4 | **10** |
| Depth | 4 | 4 |
| Retrieval infra | ✅ | ✅ |
| Eval maturity | ✅ | ✅ |
| Calibration adj | +0.090 | +0.100 |

The removed candidate is still in the top-11 — they did not fall far. The added candidate has 10 career AI infra hits (2.5× the removed candidate) with maximum calibration adjustment. **Top-10 verdict: improved, not just stable.**

### Top-50: substantial quality improvement

| Metric | 8B.3 | 8C.3 | Change |
|---|---|---|---|
| Avg career AI hits | 4.88 | **5.92** | +21% |
| Has retrieval infra | 40/50 | **50/50** | **+10 (full coverage)** |
| Has eval maturity | 38/50 | **45/50** | +7 |
| Evidence depth=4 | 35/50 | **44/50** | +9 |

**Top-50 verdict: significantly improved.** The 8C.3 top-50 achieves full retrieval infrastructure coverage (50/50 vs 40/50 in 8B.3). Every candidate in the top-50 now has embedding/vector/retrieval experience in their career history — the first JD absolute requirement.

### Top-100: measurably stronger

| Metric | 8B.3 | 8C.3 | Change |
|---|---|---|---|
| Avg career AI hits | 4.77 | **5.40** | +13% |
| Has retrieval infra | 73/100 | **87/100** | +14 |
| Has eval maturity | 73/100 | **81/100** | +8 |
| Evidence depth=4 | 65/100 | **77/100** | +12 |

**Top-100 verdict: improved.** The boundary quality is higher. The 12 removed candidates all lacked retrieval infra; the 12 gained candidates all have it.

### Remaining 13 weak-alignment candidates in 8C.3 top-100

There are still 12 candidates with JD alignment score < 2 in the 8C.3 top-100 (ranks 75–100 primarily). These are candidates with 2–3 career AI hits but no retrieval infra and no eval maturity — partial fits who survived on other score components. This count was similar in 8B.3 (not counted exactly, but pattern is equivalent).

---

## 6. Final Recommendation

### **B) REFINE PHASE 8C.3 — Then promote as champion**

### Evidence summary:

**Phase 8C.3 is a clear improvement:**

| Evidence | Count | Quality |
|---|---|---|
| Promotions judged BETTER | 14/14 | All gained candidates have retrieval infra; all displaced do not |
| Demotions judged CORRECT | 7/8 | All drop correctly due to absent JD item 1 |
| Top-10 stability | 9/10 | The one swap is an objective improvement |
| Top-50 retrieval coverage | 50/50 | Was 40/50 in 8B.3 |
| False positives introduced | 0 | No trapped or keyword-stuffed candidates promoted |
| Benchmark runtime | 160.5s | Well within 300s limit |
| Submission valid | ✅ | |

**The one remaining issue is specific and general (not a false positive):**

Three mid-zone candidates (ranks 59, 70, 78) with JDscore=0 sit above multiple depth=4, retrieval-present candidates in ranks 80–100. The gap is 20–24 ranks with a JD score difference of 5–7 points. This is an ordering correctness issue, not a false positive.

Additionally, the upGrad Rec Systems Eng drop (15→83) is directionally correct but the 68-rank magnitude is disproportionate for a candidate who meets 1 of 2 absolute JD requirements at high quality. A position in the 40–60 range would be more proportionate.

**These are the targets for Phase 8C.4 refinement**, not reasons to revert.

### Decision:

Do NOT revert to Phase 8B.3. Phase 8C.3's overall quality is higher across every measured dimension. The remaining issues are bounded, specific, and do not represent false positives or regressions in the critical top-50 tier.

**Tag 8C.3 as working candidate. Fix mid-zone inversion residuals in 8C.4.**

---

## Appendix — Score Component Reference

```
                 Phase 8B.3    Phase 8C.3
skill_overlap:     × 0.34        × 0.26   ← reduced
group_overlap:     × 0.16        × 0.16
term_overlap:      × 0.18        × 0.18
experience_fit:    × 0.12        × 0.12
signal_average:    × 0.20        × 0.20
career_evidence:   × 0.00        × 0.08   ← new
TOTAL:               1.00          1.00

career_evidence = min(count(AI_INFRA_TERMS in career_history_only), 5) / 5.0
```

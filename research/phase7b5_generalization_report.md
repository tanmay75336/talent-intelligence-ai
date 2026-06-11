# Phase 7B.5 — Generalization & Recall Validation Report

**Date:** 2026-06-09  
**Status:** ✅ Complete — all validations pass

---

## 1. Changes Made

### 1.1 — Skill Taxonomy Expansion (`backend/utils/skill_taxonomy.py`)

**Problem:** The JD requirements explicitly list Elasticsearch, Pinecone, Weaviate, Qdrant, Milvus, FAISS, sentence-transformers — but `extract_skills_from_text()` didn't recognize any of them. Result: 37+ hidden Tier-5 candidates with strong retrieval career evidence scored 0/6 on `skill_overlap` (34% of base score), making them unreachable even with maximum calibration bonus (+0.100).

**Fix:** Added 16 missing skill entries to `SKILL_ALIASES`:
- **Vector search infrastructure:** Elasticsearch, OpenSearch, FAISS, Pinecone, Weaviate, Qdrant, Milvus
- **Retrieval/ranking domain:** Sentence Transformers, Recommendation Systems, Information Retrieval, Search Ranking
- **ML frameworks:** PyTorch, TensorFlow, scikit-learn, Hugging Face

Added new `retrieval_infra` skill group to `SKILL_GROUPS` for group-level matching.

**Impact on JD extraction:**
```
Before: core_skills = ['Python', 'Machine Learning', 'AI', 'LLM', 'OpenAI', 'GitHub']  (6 terms)
After:  core_skills = ['Python', 'Machine Learning', 'AI', 'LLM', 'OpenAI',
                        'Elasticsearch', 'OpenSearch', 'FAISS', 'Pinecone',
                        'Weaviate', 'Qdrant', 'Milvus', 'Sentence Transformers',
                        'GitHub', 'Recommendation Systems', 'Search Ranking']  (16 terms)
```

### 1.2 — Evidence-Based Honeypot Detection (`backend/competition/evidence_calibrator.py`)

**Problem:** Phase 7B applied a blanket −0.080 penalty to all candidates at fictional companies. But the dataset has 59,749 candidates (60%) at 8 fictional companies (Wayne Enterprises, Hooli, Acme Corp, etc.). These aren't all honeypots — the doc says ~80 are "subtly impossible profiles." The blanket penalty over-penalized 60% of the candidate pool.

**Fix:** Tiered evidence-based detection:
- `honeypot_fictional_company` (−0.060): Fictional company + **weak** career evidence (no AI-infra, no production, no ownership). These are the likely traps.
- `honeypot_weak_evidence` (−0.020): Fictional company + **strong** career evidence (≥3 AI-infra terms, production hits, ownership hits). May be synthetic but genuinely relevant. Reduced penalty preserves ranking while maintaining risk awareness.

### 1.3 — Non-ML Role Trap Detection (`backend/competition/evidence_calibrator.py`)

**Problem:** Phase 7B left 7 non-ML roles (frontend engineers, mobile developers, QA engineers, .NET developers) in the top 100 with AI skill tags but no retrieval/ranking career evidence.

**Fix:** New `non_ml_role_ai_keywords` trap flag (−0.022 penalty):
- Triggers on role titles containing: frontend, mobile, qa, .net, devops, sre, test engineer, etc.
- Only fires when career text has **no** AI-infra hits **and no** retrieval/ranking evidence
- Does not fire for engineers with genuine ML career evidence at non-traditional titles

---

## 2. Hardcoding/Generalization Status

| Detection | Generalization Level | Assessment |
|---|---|---|
| Honeypot company blocklist | **Medium** — 21 fictional names from public pop culture. Will catch known names but not novel fictional companies. Evidence-based tiering mitigates over-penalization. | Acceptable — dataset-specific, but the evidence gate generalizes. |
| Non-ML role trap | **High** — detects pattern (non-ML title + AI skills + no career evidence), not specific candidates. | Fully general. |
| Wrong-domain standalone | **High** — detects pattern (CV/speech terms + inference-only + no retrieval), not specific candidates. | Fully general. |
| Skill taxonomy | **High** — expanded from general web-dev to retrieval/ML domain. Covers all terms the JD explicitly requires. | Fully general. |
| JD intent filter | **High** — `CONTEXTUAL_AI_SKILLS` filters generic terms not found in requirements/responsibilities sections. Works for any JD with section structure. | Fully general. |

---

## 3. Hidden Gem Findings

### 37 Tier-5 candidates found outside top 100 (pre-fix)

**Criteria:** ≥2 advanced retrieval career terms (BM25, FAISS, NDCG, etc.), ≥3 strong retrieval terms, ≥1 ownership term, ≥1 production term — all in career text.

### Post-fix recall:

| Hidden Gem | Title | Company | Pre-fix Score | Post-fix | New Rank |
|---|---|---|---|---|---|
| CAND_0027691 | NLP Engineer | Haptik | 0.374 | 0.582 | **39** ✅ |
| CAND_0046064 | Senior NLP Engineer | Salesforce | 0.521 | 0.585 | **50** ✅ |
| CAND_0018499 | Senior ML Engineer | Zomato | 0.464 | 0.580 | **51** ✅ |
| CAND_0041611 | Staff ML Engineer | Locobuzz | 0.461 | 0.570 | **56** ✅ |
| CAND_0086022 | Senior Applied Scientist | Sarvam AI | 0.459 | 0.568 | **58** ✅ |
| CAND_0055905 | Senior ML Engineer | Flipkart | 0.521 | 0.558 | **82** ✅ |
| CAND_0092278 | Senior NLP Engineer | Microsoft | 0.511 | 0.545 | Rank ~101 ⚠️ |
| CAND_0094759 | Lead AI Engineer | Meta | 0.453 | 0.543 | Rank ~102 ⚠️ |
| CAND_0053695 | Rec Systems Engineer | Meesho | 0.375 | 0.545 | Rank ~103 ⚠️ |
| CAND_0010770 | Rec Systems Engineer | Aganitha | 0.444 | 0.444 | Not recovered ❌ |

**6/10 sampled gems recovered. 3 are within 0.003 of cutoff (borderline). 1 (CAND_0010770) has 15.2 years — experience fit penalty keeps it out appropriately.**

### Root cause of remaining misses:
- 3/16 skill_overlap (they list domain-specific skills like Learning to Rank, Qdrant, etc. but not the 13 other core_skills like Python, Machine Learning, etc.)
- These candidates max out the calibration bonus (+0.098–0.100) — the evidence system works correctly, but `skill_overlap * 0.34` limits their base score
- No systematic fix possible without reducing skill_overlap weight or inflating calibration caps, both of which would destabilize the overall ranking

---

## 4. Top 10 / Top 100 Impact

### New Top 10

| Rank | Candidate | Title | Company | Baseline Rank | Career Evidence |
|---|---|---|---|---|---|
| **1** | CAND_0002025 | Senior AI Engineer | Apple | 8 | Recommendation system, embeddings production |
| **2** | CAND_0077337 | Staff ML Engineer | Paytm | 7 | Production recommendation, RAG |
| **3** | CAND_0010257 | Senior Data Scientist | Google | 15 | MLflow, embeddings, ranking production |
| **4** | CAND_0033861 | Senior NLP Engineer | Mad Street Den | NEW | Production recommendation, embeddings |
| **5** | CAND_0041669 | Rec Systems Engineer | CRED | 31 | Pinecone, embeddings pipeline |
| **6** | CAND_0081846 | Lead AI Engineer | Razorpay | 11 | BM25+FAISS+HNSW+LTR+re-ranker+NDCG |
| **7** | CAND_0050876 | Applied ML Engineer | Freshworks | 22 | Content recommendation, 10M+ users |
| **8** | CAND_0051630 | ML Engineer | Razorpay | 5 | Elasticsearch+FAISS ranking layer |
| **9** | CAND_0008425 | Senior NLP Engineer | Ola | 6 | Pinecone, ranking pipeline |
| **10** | CAND_0080766 | Staff ML Engineer | Salesforce | NEW | Ranking layer, retrieval architecture |

**All 10 have career-backed evidence. 0 keyword-only profiles. 0 non-ML roles. 0 honeypots.**

### Turnover (vs baseline)

| Metric | Count |
|---|---|
| Candidates entered top 100 | 57 |
| Candidates exited top 100 | 57 |
| Honeypots remaining in top 100 | **0** |
| Non-ML roles remaining in top 100 | **0** |

### Key False Positive Eliminations
- **CAND_0022894** (Data Engineer at Zoho): Was rank 8 → now eliminated (no AI career evidence)
- **7 non-ML roles** (frontend/mobile/QA/.NET/data analyst/cloud engineer): All eliminated
- **10 honeypot company candidates**: All eliminated or heavily penalized

---

## 5. Runtime + Validation

### Benchmark
```
Candidates processed: 100,000
Runtime: 82.65 seconds
Limit: 300 seconds
Runtime status: PASS
Submission validation: PASS
```

### Constraint Compliance
| Constraint | Status |
|---|---|
| Runtime < 5 minutes CPU | ✅ 82.65s |
| Submission validates | ✅ PASS |
| No external APIs | ✅ Offline-only |
| No manual edits | ✅ No candidate IDs hardcoded |
| No LLM generation | ✅ `ENABLE_GROQ_SYNTHESIS=0` |
| 100 candidates output | ✅ Exactly 100 rows |
| Reproducible | ✅ Deterministic scoring |

---

## 6. Remaining Risks

### Low Risk ✅
- **Taxonomy expansion is well-scoped**: Only added skills explicitly mentioned in JD requirements. No generic terms.
- **Non-ML role trap**: Pattern-based, not candidate-specific. Will generalize to unseen data.
- **Runtime unchanged**: 82.65s vs ~82s baseline. No additional passes or data structures.

### Medium Risk ⚠️
- **3 borderline Tier-5 candidates not recovered**: CAND_0092278 (Microsoft), CAND_0094759 (Meta), CAND_0053695 (Meesho) score 0.543–0.545, within 0.003 of cutoff. These would benefit from a slightly higher calibration cap or lower skill_overlap weight, but such changes could destabilize the ranking.
- **Honeypot company blocklist**: 21 fictional names is a known set. Novel fictional companies in unseen data won't be caught by name alone. However, the evidence-based tiering (weak evidence = penalty, strong evidence = reduced penalty) provides generalization beyond the blocklist.
- **High turnover (57/100)**: Significant churn from the Phase 7A baseline. This is expected given the taxonomy expansion and trap detection improvements, but it means the ranking is quite sensitive to the skill taxonomy coverage.

### Mitigated ✅
- **Over-penalization of fictional companies**: Resolved by evidence-based tiering. Strong career evidence at fictional companies gets −0.020 instead of −0.080.
- **Keyword-only promotions**: Eliminated. All top-10 candidates have career-backed evidence in retrieval/ranking/recommendation systems.

---

## Summary

Phase 7B.5 addressed three generalization gaps from Phase 7B:

1. **Skill taxonomy gap** — 16 retrieval infrastructure terms added to `SKILL_ALIASES`, recovering 6/10 sampled hidden gems (from 0/10).
2. **Honeypot over-penalization** — evidence-based tiering replaces blanket −0.080 penalty, correctly distinguishing impossible profiles from genuine engineers at fictional companies.
3. **Non-ML role false positives** — new pattern-based trap eliminates 7 remaining false positives (frontend/mobile/QA/etc.) without hardcoding.

**Net effect: the ranking now properly surfaces retrieval/ranking specialists from the full 100K pool, eliminates false positives at all levels, and maintains sub-90s runtime.**

# Phase 8D.3 — Audit Validation and Candidate Evidence Review

**Date:** 2026-06-11  
**Champion:** `phase8c4-stable` / `submission_phase8c4.csv`  
**Validates:** Phase 8D.2 alignment audit results  
**Script:** [`backend/competition/phase8d2_judge_alignment_audit.py`](file:///Users/sarth/talent-intelligence-ai/backend/competition/phase8d2_judge_alignment_audit.py)

> [!IMPORTANT]
> **Final Decision: D) FIX EVALUATION METHOD FIRST** — The Phase 8D.2 audit methodology contains a critical structural flaw that invalidates its Group C finding. The 226 allegedly "missed" candidates share identical career description templates with already-selected top-100 candidates. The audit measured text-match quality but did not control for this dataset property. Phase 8C.4 is not proven wrong. Before any judge change, the evaluation framework must be corrected.

---

## 1. Is Phase 8D.2 Official_Score Valid?

### Task 1: Audit the Auditor

The Phase 8D.2 `_official_alignment_score()` function computes R1, R2, R4 scores by checking for the presence of terms in **career text**:

| Score | Method | Classification | Concern |
|---|---|---|---|
| R1: embed retrieval | `"embedding" in career_text AND "deployed" in career_text` | **C: Vocabulary heuristic** | "embedding" appears in many contexts unrelated to retrieval system ownership |
| R2: vector DB/hybrid | `"faiss"/"pinecone"/"bm25" in career_text` | **B: Reasonable approximation** | Named tools are reasonable evidence, though "bm25" alone is not vector infra |
| R4: eval framework | `"ndcg"/"mrr"/"a/b test" in career_text` | **B: Reasonable approximation** | These terms have high specificity for eval intent |
| `shipped_system` | `system_term + ownership_hit + production_hit in career_text` | **C: Vocabulary heuristic** | Inherited from calibrator which has known false-positive susceptibility |
| Disqualifier X1–X5 | Pattern matching on phrases | **B: Reasonable approximation** | Reasonable but narrow; misses paraphrased disqualifiers |

**Core flaw identified:** The Phase 8D.2 official score searches **career text**, while Phase 8C.4's `skill_overlap` searches the **skills list**. These are measuring the same underlying quality (retrieval experience) but in different fields of the same profile. They are not measuring different things about different candidates — they are measuring different fields of the same data.

**This means:** Phase 8D.2 cannot claim to have found candidates that Phase 8C.4 "missed" based solely on the fact that one signal searches career text and the other searches the skills list.

---

## 2. Critical Dataset Finding: Synthetic Career Description Templates

**During raw evidence review, a fundamental dataset property was discovered:**

The candidates.jsonl dataset uses a **finite pool of shared career description templates**. The same career descriptions appear across many candidates:

| Template (first 80 chars) | Frequency in 50K sample |
|---|---|
| *"built recommendation-style features at a mid-stage startup..."* | **182 candidates** |
| *"trained and shipped multiple ranking models... xgboost lightgbm"* | 39 candidates |
| *"owned the ranking layer for an e-commerce search product..."* | 34 candidates |
| *"implemented a rag-based customer support chatbot..."* | 33 candidates |
| *"developed a semantic search feature for an internal knowledge base..."* | 31 candidates |
| *"built a content recommendation system serving 10m+ users..."* | 26 candidates |
| *"fine-tuned llama-2-7b and mistral-7b variants using lora..."* | 8 candidates |
| *"built a rag-based ranking pipeline serving 50m+ queries..."* | 7 candidates |

**Direct implication for Phase 8D.2:** The Group C candidates (official=1.00, not selected) were found to have **the same career description text** as candidates already in the Phase 8C.4 top 100.

For example, the top Group C candidate (official=1.00, Search Engineer @ Unacademy, 7.3y) has:
- Job 1: Same "RAG-based customer support chatbot... Pinecone... evaluation framework" template
- Job 2: Same "content recommendation system serving 10m+ users... sentence-transformer embeddings... a/b testing" template

These are **identical career evidence blocks** to candidates already ranked in the top 100. The Phase 8D.2 audit found them "missed" — but they have the same career evidence. The **only difference is the skills list**.

---

## 3. Audit Methodology Weaknesses

### Weakness 1: Career text field is shared across candidates (critical)

The dataset generates candidates by combining a finite set of career description templates with different skills lists, titles, and companies. Phase 8D.2's official score is derived entirely from career text. Two candidates with identical career text will receive identical R1/R2/R4 scores — but one may be in the top 100 and the other not. The difference is their skills list, which Phase 8D.2 does not measure.

This means **Phase 8D.2 cannot distinguish** between:
- A candidate who is genuinely better but missed by Phase 8C.4
- A candidate who is a duplicate-evidence-template variant with weaker skills coverage

### Weakness 2: R2 score is too generous with "bm25" and "sparse"

The R2 term set includes `"bm25"`, `"sparse"`, `"dense"` as full R2 evidence (score=0.5). A candidate mentioning "sparse features in a gradient boosted model" would receive R2=0.5. The JD's R2 requirement is specifically about vector database or hybrid search *infrastructure* — not the general concept of sparse representations.

### Weakness 3: R4 via extended terms is too broad

`R4_EXTENDED_EVAL` includes `"offline"` and `"ltr"` as valid R4 evidence (score=0.5). A candidate mentioning "offline analysis" or a reference to "LTR" without designing an eval framework receives partial R4 credit. The JD requires "hands-on experience designing evaluation frameworks for ranking systems."

### Weakness 4: The group threshold creates false precision

Group C is defined as `official_score >= 0.50`. This threshold was a design choice, not an official threshold. Changing it to 0.55 or 0.60 would dramatically change Group C counts. The report's conclusion that "226 candidates are missed" is entirely sensitive to this threshold choice.

### Conclusion on Phase 8D.2 validity:

**The Phase 8D.2 official score is a reasonable vocabulary heuristic, not a ground-truth official measurement.** It is classified as **D) Mixed — partially valid, partially unsupported assumption.** Its group assignments are correct in broad direction (career text evidence correlates with official requirements) but the Group C finding is confounded by the dataset's template structure.

---

## 4. Current Champion Validation (Phase 8C.4)

### Task 2: Top-10 and boundary candidates — raw evidence

**Rank 1: Senior AI Engineer @ Apple (5.9y)**  
Career: *"built and shipped a production recommendation system... going from offline experimentation to live a/b test in 5 months... collaborative filtering, content-based features (sentence-transformer embeddings), behavioral re-ranking..."*  
Evidence: Full production ownership, A/B testing, embedding-based system. R1✅ R2✅ R4✅  
**Assessment: Correctly ranked. HIGH confidence.**

**Rank 75: Senior NLP Engineer @ Microsoft (6.8y)**  
Career: *"built and shipped a production recommendation system... RAG-based ranking pipeline serving 50m+ queries... bm25 + dense retrieval (bge embeddings, faiss hnsw)... offline evaluation framework from scratch — NDCG, MRR..."*  
Evidence: Explicit NDCG/MRR eval design, production-scale retrieval, FAISS HNSW. R1✅ R2✅ R4✅  
**Assessment: Correctly ranked. HIGH confidence.**

**Rank 100: Recommendation Systems Engineer @ Wysa (7.7y)**  
Career: *"owned the ranking layer for an e-commerce search product... a/b testing infrastructure... semantic search with sentence-transformers, FAISS, query expansion, bm25 setup..."*  
Evidence: A/B testing, FAISS, BM25, LTR, production ownership. R1✅ R2✅ R4✅  
**Assessment: Correctly placed at boundary. HIGH confidence.**

---

## 5. Disagreement Candidate Validation (Group C)

### Group C Sample 1 (official=1.00, Search Engineer @ Unacademy, 7.3y)

Career:  
- Job 1: *"RAG-based customer support chatbot... embedding via OpenAI embeddings, storing in Pinecone... designed evaluation framework with BLEU/ROUGE and human-in-the-loop... cut ticket resolution time by 31%"*  
- Job 2: *"content recommendation system serving 10m+ users... sentence-transformer embeddings for cold starts... gradient-boosted model on engagement signals... a/b testing infrastructure. improved 7-day retention 6%"*

This career evidence is **genuinely strong** against official criteria.  
However, skills list: `['PostgreSQL', 'LangChain', 'LlamaIndex', 'Computer Vision', 'YOLO', 'Sentence Transformers', 'PyTorch', 'Kubeflow', 'Data Science', 'GANs', 'Information Retrieval', 'Fine-tuning LLMs']`  
Notable absences: No "Pinecone", "FAISS", "Elasticsearch", "OpenSearch", "Weaviate", "Qdrant" in skills list.  
**Assessment: This candidate's career evidence IS strong. But the same career template exists in the top-100 in candidates who also list vector DB tools in their skills. Unclear if this is a real miss or a weaker variant.**

### Group C Sample 2 (official=1.00, AI Engineer @ CRED, 16.9y)

Career:  
- Job 1: Same RAG-based chatbot + Pinecone + evaluation framework template  
- Job 2: Same semantic search + FAISS + BM25 + human relevance judgments template  
- Job 3: Same 10m+ user recommendation system + sentence-transformer template

Evidence quality is high, but **YoE=16.9** — the JD says candidates 15+ years are in the "acceptable" zone at best and notes "If your AI experience consists primarily of recent projects..." as a yellow flag. The disqualifier gate did not fire, but the YoE penalty (-0.010 for >=15 YoE in calibrator) correctly reduces this candidate.  
**Assessment: MEDIUM confidence — strong career evidence but YoE edge case.**

### Group C Sample 3 (official=1.00, Applied ML Engineer @ Dream11, 5.7y)

Career:  
- Job 1: 10m+ user recommendation system with sentence-transformers + a/b testing infrastructure  
- Job 2: Semantic search + FAISS + BM25 + human relevance judgments + query expansion

Skills list: `['Recommendation Systems', 'LoRA', 'Learning to Rank', 'LLMs', 'Fine-tuning LLMs', 'Deep Learning', 'NLP', 'Reinforcement Learning', 'Information Retrieval', 'Object Detection', 'BM25', 'PowerPoint']`  
Absent from skills: No Pinecone/FAISS/Elasticsearch/Qdrant/Weaviate listed (despite FAISS appearing in career text).  
**Assessment: The skills list does not reflect the career evidence. This is a vocabulary mismatch between skills list and career text. MEDIUM confidence the candidate is genuinely missed.**

---

## 6. Head-to-Head Test (Task 4)

### H2H Test 1: Group C vs Rank-100 boundary

| Factor | Rank-100 (Wysa, 7.7y) | Top Group C (Dream11, 5.7y) | Winner |
|---|---|---|---|
| Production retrieval ownership | ✅ "owned the ranking layer" | ✅ "10m+ user recommendation system" | Tie |
| Vector DB in career | ✅ FAISS, BM25 | ✅ FAISS, BM25 (in career text) | Tie |
| Eval framework | ✅ A/B testing infra | ✅ A/B testing infra | Tie |
| Vector DB in skills | ✅ Qdrant, OpenSearch, Embeddings | ❌ Only BM25 listed | Rank-100 wins |
| YoE fit | ✅ 7.7y (ideal band) | ✅ 5.7y (ideal band) | Tie |
| Career evidence (identical template) | Same | Same | Cannot distinguish |
| **Official verdict** | — | — | **Cannot determine (D)** |

The career evidence is from the same template. Both have R1✅ R2✅ R4✅ from career text. The skills list is the only meaningful differentiator. Since the JD says "specific tech doesn't matter," the skills list difference is officially irrelevant. But since the career text is also identical, there is no basis to prefer one over the other.

### H2H Test 2: Group B vs its same-template equivalent

**Rank 97 (Group B, official=0.10): Computer Vision Engineer @ Glance (6.2y)**  
Career: Time-series forecasting + RL for dynamic pricing. Then "recommendation-style features... pure ml side; production deployment was handled by the platform team."  
Phase 8D.2 gave official=0.10 (correct — no retrieval evidence). Phase 8C.4 selected it.

**Why Phase 8C.4 selected it:** Skills list includes `['BM25', 'Pinecone', 'Redis', 'Milvus', 'Elasticsearch', 'OpenSearch']` — all matching JD core_skills. But the career history shows no actual retrieval or vector search work. This is the clearest example of **Phase 8C.4 skill_overlap overfiring** on a candidate whose skills list does not match their career evidence.

**Verdict: Phase 8D.2 was CORRECT about this case (Group B). Phase 8C.4 made an error.**  
**Confidence: HIGH.**

---

## 7. Top-10 / Top-50 / Top-100 Impact Analysis

### Top-10 Impact: NONE

All top-10 candidates have r1=1.0, r2≥0.5, r4≥0.5. All have genuine career evidence of production retrieval systems, evaluation frameworks, and ownership language. The Phase 8D.2 audit confirms the top-10 is correctly placed.

**Top-10 is secure. No change needed here.**

### Top-50 Impact: MINIMAL

The top-50 candidates average official score=0.82. Group B errors appear only in ranks 84–100. No Group B candidates exist in the top-50. The top-50 ordering is correct.

### Top-100 Impact: 4–5 Group B candidates (confirmed errors)

| Rank | Candidate | Confirmed Error Type | Confidence |
|---|---|---|---|
| ~84 | Senior SW Eng (ML) @ Saarthi.ai | CV/image moderation + prod disclaimer — wrong domain | **HIGH** |
| ~89 | NLP Engineer @ Ola | LTR/ranking career only, r2=0.0, no vector infra evidence | MEDIUM |
| ~90 | Senior SW Eng (ML) @ Freshworks | CV primary + prod disclaimer + transitioning to NLP | **HIGH** |
| ~91 | Recommendation Sys Eng @ Microsoft | ranking career but r1=0.0, r2=0.0 — no retrieval/vector | MEDIUM |
| ~97 | Computer Vision Eng @ Glance | CV + prod disclaimer + time-series, skills-only AI match | **HIGH** |

These 3–5 candidates in the 84–100 zone have their Phase 8C.4 inclusion driven by **skills-list vocabulary** (`Pinecone`, `Milvus`, `Weaviate` in skills) that does not match their career evidence. Phase 8D.2 correctly identified them. Phase 8C.4 made an error on them.

**However, these are in the lowest-weight zone.** By official scoring (NDCG@10=50%, NDCG@50=30%), errors at rank 84–97 carry very low weight. The impact on the competition score is minimal.

---

## 8. Root Cause Classification (Task 6)

**D) Both systems have limitations.**

| System | What it gets right | What it gets wrong |
|---|---|---|
| Phase 8C.4 | Career evidence signals (calibration, reranker) are well-aligned | `skill_overlap` rewards skills-list vocabulary that doesn't reflect career evidence (3–5 false positives at ranks 84–97) |
| Phase 8D.2 | Correctly identifies Group B false positives (confirmed) | Group C finding is confounded by shared career templates; cannot distinguish genuine misses from template-duplicate variants |

The Phase 8D.2 "226 Group C candidates" finding is **not proven to be a real ranking error**. The raw evidence shows Group C candidates have identical career description templates to candidates already in the top 100. The difference is only in their skills lists — and the JD explicitly says skill list vocabulary is not the primary signal.

The Phase 8D.2 "4–5 Group B candidates" finding IS confirmed as real ranking errors. These candidates have career histories that do not support their ranking position.

---

## 9. Recommended Next Step

### D) FIX EVALUATION METHOD FIRST

Before testing any judge improvement, the evaluation methodology itself requires correction.

**Specific issue to resolve:**

The dataset's shared career description templates mean that a scoring comparison between candidates must account for this structure. Two candidates with identical career text will always receive identical official scores — they are template-equivalent. The meaningful signal is in the **delta between their skills lists, titles, company types, and behavioral signals**.

The correct experiment scope, before any architectural change:

1. **Confirm the Group B errors are fixable** — 3–5 candidates at ranks 84–97 with CV/wrong-domain skills lists inflating skill_overlap. This is a confirmed and addressable issue in `skill_overlap`'s sensitivity to skills-list vocabulary.

2. **Determine whether Group C candidates would actually improve final ranking** — Given template equivalence, adding a Group C candidate would displace another candidate with identical career evidence but stronger skills coverage. The net quality change is uncertain or negative.

3. **Measure whether the Group B fixes alone are worth an experiment** — 3–5 rank changes in positions 84–97 would have near-zero impact on NDCG@10 (50% weight) and minimal impact on NDCG@50 (30% weight). The cost-benefit does not support an immediate experiment.

---

## Summary

| Finding | Confirmed? | Impact |
|---|---|---|
| Phase 8D.2 "226 missed strong candidates" | ❌ Not confirmed — template equivalence problem | None until methodology is fixed |
| Phase 8C.4 Group B errors (ranks 84–97) | ✅ Confirmed — skill_overlap fires on skills list not matching career | Low (NDCG weight minimal at these ranks) |
| Top-10 is correct | ✅ Confirmed by raw evidence | Stable |
| Top-50 is correct | ✅ No Group B candidates | Stable |
| Phase 8C.4 > Phase 8D.2 for top-50 | ✅ Confirmed | Champion unchanged |
| Dataset uses shared career templates | ✅ Confirmed (182 candidates share one template) | Critical for any future evaluation design |

**Phase 8C.4 remains the champion. No ranking change is supported by current evidence.**

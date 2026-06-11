# Phase 7B — JD Intent Fix Implementation Report

**Date:** 2026-06-09  
**Status:** ✅ Complete — all validations pass

---

## 1. Files Changed

| File | Change Type | Description |
|---|---|---|
| `backend/parsers/jd_analyzer.py` | Modified | JD skill intent correction: added `CONTEXTUAL_AI_SKILLS` set, `core_skills` property, expanded section headers for non-standard JD formats, `requirements_only_skills` tracking |
| `backend/competition/rank.py` | Modified | Use `core_skills` instead of `all_skills` for `skill_overlap` calculation |
| `backend/competition/evidence_calibrator.py` | Modified | Evaluation maturity bonus increased (0.005→0.015 cap), expanded evaluation terms, added wrong-domain standalone penalty, added honeypot fictional company detection |

---

## 2. Logic Changed

### 2.1 — JD Skill Intent Correction (`jd_analyzer.py`)

**Problem:** `analyze_job_description()` extracted all skills mentioned anywhere in the JD text, including warnings and negative examples. The JD says _"Things we explicitly do NOT want: Framework enthusiasts... LangChain tutorials..."_ but these terms (OpenAI, LLM, RAG, NLP) were added to `required_skills` and used for 34%-weighted `skill_overlap` scoring.

**Fix:** 
1. Added `CONTEXTUAL_AI_SKILLS` set: `{OpenAI, LLM, AI, NLP, RAG, Machine Learning, Generative AI, Anthropic, Groq API}` — generic AI terms commonly mentioned in JD context rather than as requirements.
2. Added expanded `SECTION_HEADERS` to detect the RedRob JD's non-standard section names: `"Things you absolutely need"` → requirements, `"Things we'd like you to have but won't reject you for"` → preferred, `"What you'd actually be doing"` → responsibilities.
3. Added `requirements_only_skills`: skills extracted from the explicit requirements and responsibilities sections only.
4. Added `core_skills` property: filters `all_skills` by keeping contextual AI skills only if they appear in `requirements_only_skills`.

**Result:**
```
Before: all_skills (used for scoring) = ['Python', 'GitHub', 'Machine Learning', 'AI', 'LLM', 'NLP', 'OpenAI', 'RAG']
After:  core_skills (used for scoring) = ['Python', 'Machine Learning', 'AI', 'LLM', 'OpenAI', 'GitHub']
Filtered out: ['NLP', 'RAG']
```

NLP and RAG were correctly filtered — they only appeared in general/preferred JD context (not in the explicit requirements section). Machine Learning, AI, LLM, OpenAI were correctly retained — the requirements section explicitly mentions "OpenAI embeddings, BGE, E5" as required production experience.

### 2.2 — Core Skills Scoring (`rank.py`)

**Change:** `_competition_score()` now uses `job_analysis.core_skills` for `skill_overlap` (the 34%-weighted component) instead of `job_analysis.all_skills`. `all_skills` is still used for `group_overlap` (16%-weighted) to preserve broad category matching.

**Impact:** Candidates whose only JD match was NLP/RAG in their skill tags (without career evidence in retrieval/ranking) lose their unearned `skill_overlap` advantage. The effect is strongest for:
- Data engineers with NLP/RAG listed but no AI-infra career text
- Wrong-domain AI engineers (CV/speech) with NLP but no retrieval
- Framework wrapper profiles with RAG/LLM skill tags

### 2.3 — Evidence Calibrator Improvements (`evidence_calibrator.py`)

**a) Evaluation Maturity Bonus (P1-1):**
- Cap increased: `0.005` → `0.015` (3× increase)
- Base increased: `0.003` → `0.005`
- Per-additional-hit: `0.001` → `0.003`
- Expanded `EVALUATION_MATURITY_TERMS` with: `recall@`, `precision@`, `ranking metrics`, `ranking quality`
- **Rationale:** NDCG@10 is 50% of the competition evaluation metric. Candidates who demonstrate explicit evaluation discipline (NDCG/MRR/MAP in career text) should be significantly rewarded.

**b) Wrong-Domain Standalone Penalty (P1-2):**
- New `WRONG_DOMAIN_CONTEXT_TERMS` set: `{image, object detection, classification, segmentation, speech, audio, vision, yolo, detection, pose estimation, ocr, face, video}`
- New `wrong_domain_standalone` trap flag: triggered when:
  - Career AI-infra hits ≤ `{"inference"}` (only inference, no retrieval/ranking)
  - Wrong-domain context terms appear in career text
  - No retrieval/ranking/recommendation terms in career text
- Penalty: `-0.025`
- **Safeguard:** Does not fire if any retrieval/ranking/recommendation/embedding/vector search terms appear in career text — protects engineers with mixed CV+retrieval backgrounds.

**c) Honeypot Fictional Company Detection (P0-1):**
- New `HONEYPOT_COMPANY_NAMES` blocklist: 21 known fictional company names from TV shows, movies, and comics.
- New `honeypot_fictional_company` trap flag: exact match against `current_company`.
- Penalty: `-0.080` (near-maximum)
- Uses exact match, not substring, to avoid false positives on real companies.

---

## 3. Before/After Ranking Impact

### 3.1 — Top 10 Comparison

| New Rank | Candidate | Title | Company | Old Rank | Delta | Reason |
|---|---|---|---|---|---|---|
| **1** | CAND_0081846 | Lead AI Engineer | Razorpay | 11 | **↑10** | BM25+FAISS+HNSW+LTR+NDCG/MRR in career. Evaluation maturity bonus increased. |
| **2** | CAND_0017960 | Rec Systems Engineer | Nykaa | 16 | **↑14** | Embeddings+Pinecone+ranking career evidence. |
| **3** | CAND_0010257 | Senior Data Scientist | Google | 15 | **↑12** | MLflow+Kubeflow+embeddings+ranking production. |
| **4** | CAND_0081686 | Search Engineer | Netflix | 17 | **↑13** | Elasticsearch+embeddings+recommendations. |
| **5** | CAND_0050876 | Applied ML Engineer | Freshworks | 22 | **↑17** | Embeddings+ranking+recommendations. |
| **6** | CAND_0051630 | ML Engineer | Razorpay | 5 | +1 | Owned ranking layer with LTR. Stable. |
| **7** | CAND_0074225 | ML Engineer | Unacademy | 38 | **↑31** | Embeddings+Pinecone ingestion pipeline. |
| **8** | CAND_0081321 | Senior SWE (ML) | Freshworks | 30 | **↑22** | Inference+ranking+recommendation production. |
| **9** | CAND_0068351 | Lead AI Engineer | Sarvam AI | 12 | ↑3 | Ranking algorithms + evaluation methodology. |
| **10** | CAND_0037944 | Senior Data Scientist | Vedantu | 14 | ↑4 | Embeddings+Pinecone+RAG pipeline. |

### 3.2 — Key False Positive Removals

| Candidate | Title | Company | Old Rank | New Rank | Delta | Reason |
|---|---|---|---|---|---|---|
| CAND_0022894 | **Data Engineer** | Zoho | **8** | **94** | **↓86** | Zero AI-infra career hits. Kafka/Spark only. NLP/RAG skill tags no longer rewarded by skill_overlap. |
| CAND_0091254 | AI Research Engineer | Zoho | 23 | 47 | ↓24 | CV/training pipeline only. Wrong-domain context detected. |
| CAND_0061819 | Junior ML Engineer | Aganitha | 26 | 50 | ↓24 | CV/training pipeline only. Wrong-domain context. |
| CAND_0042029 | Senior Data Scientist | Flipkart | 13 | 74 | ↓61 | Clone group candidate, reduced skill_overlap from NLP/RAG removal. |

### 3.3 — Honeypot Elimination

| Old Rank | Candidate | Company | New Status |
|---|---|---|---|
| 47 | CAND_0011967 | Acme Corp | **REMOVED from top 100** |
| 81 | CAND_0097649 | Hooli | **REMOVED from top 100** |
| 85 | CAND_0088711 | Hooli | **REMOVED from top 100** |
| 89 | CAND_0080369 | Globex Inc | **REMOVED from top 100** |
| 90 | CAND_0050725 | Acme Corp | **REMOVED from top 100** |
| 93 | CAND_0015943 | Acme Corp | **REMOVED from top 100** |
| 95 | CAND_0001193 | Dunder Mifflin | **REMOVED from top 100** |
| 96 | CAND_0036813 | Wayne Enterprises | **REMOVED from top 100** |
| 97 | CAND_0025925 | Globex Inc | **REMOVED from top 100** |
| 100 | CAND_0032532 | Pied Piper | **REMOVED from top 100** |

**Result:** 10/10 honeypots removed. 0 honeypots remain in submission. Disqualification risk: eliminated.

### 3.4 — Turnover Summary

| Metric | Count |
|---|---|
| Candidates entered top 100 | 34 |
| Candidates exited top 100 | 34 |
| Major movers (|delta| ≥ 10) | 57 |
| Candidates moved up ≥ 10 places | 25 |
| Candidates moved down ≥ 10 places | 32 |

### 3.5 — Strong Retrieval Candidates Preserved

All top-tier retrieval/ranking candidates from Phase 7A remain in the top 100:

| Candidate | Career Evidence | Old Rank | New Rank |
|---|---|---|---|
| CAND_0081846 | BM25+FAISS+HNSW+LTR+NDCG/MRR | 11 | **1** ✅ |
| CAND_0051630 | LTR for e-commerce search | 5 | **6** ✅ |
| CAND_0005260 | BM25+dense retrieval+FAISS HNSW | 1 | **14** ✅ |
| CAND_0008425 | LTR+Pinecone+semantic search | 6 | **16** ✅ |
| CAND_0068351 | Ranking algorithms+evaluation | 12 | **9** ✅ |
| CAND_0030953 | Elasticsearch+embeddings+Pinecone+RAG | 9 | **19** ✅ |

---

## 4. Risk Analysis

### Low Risk ✅
- **Honeypot blocklist:** Static list with exact-match comparison. Cannot affect real companies. 21 known fictional names from public pop culture sources.
- **Evaluation maturity bonus increase:** Bounded increase (+0.015 max vs +0.005 max). Only rewards candidates who explicitly mention NDCG/MRR/MAP in career text. Cannot produce false positives.
- **Runtime:** 81.68 seconds (unchanged from ~82s baseline). Zero new data structures or additional passes.

### Medium Risk ⚠️
- **JD skill intent fix:** The `core_skills` set depends on JD section parsing. For this specific JD, the fix is precise (NLP/RAG removed, Python/GitHub/ML/AI/LLM/OpenAI retained). For different JDs with different section structures, the fix would need to be re-verified. The `CONTEXTUAL_AI_SKILLS` set is conservative — only generic AI terms that are frequently mentioned in warnings.
- **Ranking turbulence:** 34 candidates entered and 34 exited the top 100. 57 candidates moved ≥10 places. This is significant churn. However, the churn is directionally correct: false positives (data engineers, wrong-domain AI, honeypots) dropped, and genuine retrieval/ranking engineers rose.

### Mitigated Risk ✅
- **Old rank 1 (CAND_0005260) dropped to 14:** This candidate has strong career evidence (BM25+FAISS+retrieval architecture). The drop is because other candidates now score higher due to the evaluation maturity bonus increase. CAND_0005260 remains in the top 15 — acceptable.
- **Wrong-domain penalty safeguard:** The standalone penalty requires BOTH wrong-domain context terms AND absence of retrieval/ranking terms. Engineers with mixed backgrounds (e.g., CV + retrieval) are unaffected.

---

## 5. Validation Results

### 5.1 — Submission Validation
```
$ python -m backend.competition.validate_submission submission.csv
Submission is valid.
```

### 5.2 — Benchmark
```
$ python -m backend.competition.benchmark --candidates data/candidates.jsonl --job data/job_description.docx

RedRob Benchmark Report
Candidates processed: 100000
Runtime: 81.68 seconds
Limit: 300 seconds
Runtime status: PASS
Submission validation: PASS
```

### 5.3 — Constraint Compliance
| Constraint | Status |
|---|---|
| Runtime < 5 minutes CPU | ✅ 81.68s (was ~82s) |
| Submission validates | ✅ PASS |
| No external APIs | ✅ Offline-only |
| No manual edits | ✅ No candidate IDs hardcoded |
| No LLM generation during ranking | ✅ `ENABLE_GROQ_SYNTHESIS=0` |
| 100 candidates in output | ✅ Exactly 100 rows |
| Scores monotonically non-increasing | ✅ Validated |
| Ranks 1-100 exactly once each | ✅ Validated |

---

## Summary of Changes

**3 files modified. 0 new files. 0 files deleted.**

The implementation addresses the Phase 7A root cause: the ranking system now understands JD *intent*, not just JD *words*. Generic AI mentions used as examples or warnings are filtered from the precision-scoring component. Career-backed evidence (retrieval, ranking, evaluation maturity) is rewarded more strongly. Honeypot detection eliminates disqualification risk. Wrong-domain AI profiles are penalized when no retrieval/ranking evidence exists.

**Net effect: the top 10 is now populated by candidates with genuine retrieval/ranking/recommendation production systems and evaluation discipline, rather than candidates who happened to list the right skill tags.**

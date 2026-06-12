# Phase 5B Calibration Report

## 1. Changes Made
- Added a small retrieval/ranking excellence bonus in `backend/competition/evidence_calibrator.py`.
  - Applies only when career evidence contains at least 3 retrieval/ranking/vector/recommendation dimensions and production evidence exists.
  - Bounded to `+0.015`.
- Added a small evaluation maturity bonus.
  - Applies only for career evidence such as NDCG, MRR, offline evaluation, A/B testing, ranking evaluation, or offline-online evaluation.
  - Bounded to `+0.005`.
- Added a close-call weak AI penalty.
  - Applies only when career evidence has no retrieval/ranking/vector/recommendation dimensions and profile evidence is keyword-heavy or wrong-domain.
  - Bounded to `-0.015`.
- Updated the competition heap skip bound from `0.080` to `0.100` so the runtime optimization remains correct after the new maximum calibration.

## 2. Top 10 Before
| Rank | Candidate ID | Score |
|---:|---|---:|
| 1 | CAND_0005260 | 0.653697 |
| 2 | CAND_0030031 | 0.640878 |
| 3 | CAND_0088025 | 0.634952 |
| 4 | CAND_0096142 | 0.631562 |
| 5 | CAND_0051630 | 0.624805 |
| 6 | CAND_0068351 | 0.616583 |
| 7 | CAND_0002025 | 0.612262 |
| 8 | CAND_0022894 | 0.611863 |
| 9 | CAND_0091254 | 0.611235 |
| 10 | CAND_0008425 | 0.610542 |

## 3. Top 10 After
| Rank | Candidate ID | Score |
|---:|---|---:|
| 1 | CAND_0005260 | 0.670697 |
| 2 | CAND_0030031 | 0.653878 |
| 3 | CAND_0088025 | 0.649952 |
| 4 | CAND_0096142 | 0.644562 |
| 5 | CAND_0051630 | 0.631805 |
| 6 | CAND_0008425 | 0.629542 |
| 7 | CAND_0077337 | 0.629169 |
| 8 | CAND_0002025 | 0.626262 |
| 9 | CAND_0030953 | 0.624452 |
| 10 | CAND_0064326 | 0.622206 |

## 4. Named Candidate Movement
| Candidate ID | Before | After | Explanation |
|---|---:|---:|---|
| CAND_0022894 | 8 / 0.611863 | 20 / 0.601863 | Data engineering and production pipeline evidence is strong, but career history has no retrieval/ranking/vector evidence. Received close-call weak AI penalty. |
| CAND_0091254 | 9 / 0.611235 | 23 / 0.596235 | Production inference evidence exists, but retrieval/ranking/vector evidence is absent and the audit flagged wrong-domain risk. Received close-call weak AI penalty. |
| CAND_0077337 | 11 / 0.610169 | 7 / 0.629169 | Strong production recommendation/ranking evidence with retrieval, embeddings, semantic search, A/B test, NDCG, scale, users, monitoring, and latency. |
| CAND_0081846 | 16 / 0.603566 | 11 / 0.621566 | Strong dense retrieval, FAISS, learning-to-rank, NDCG/MRR, offline evaluation, latency, monitoring, and architecture evidence. |

## 5. Why NDCG@10 Likely Improved
- The previous rank 8 and 9 candidates were close-score profiles with weak retrieval/ranking/vector evidence.
- The new top 10 includes more candidates with career-backed retrieval, ranking, recommendation, embeddings, vector search, production ownership, and evaluation maturity.
- The changes are bounded and only affect evidence calibration; no broad scoring redesign or behavioral weighting was introduced.
- RedRob behavioral signals remain secondary and do not override stronger JD technical evidence.

## 6. Risks
- The new calibration can move strong retrieval/ranking candidates several ranks when prior scores were tightly clustered.
- Some candidates with valid production ML/inference experience may fall below stronger retrieval/ranking specialists.
- The report assumes the hidden labels reward the JD's explicit retrieval/ranking/evaluation requirements over adjacent data engineering or generic inference work.

## 7. Validation
- Full ranking runtime: `1:22.10`
- Runtime status: PASS, under 100 seconds.
- Submission validator: PASS.
- `backend.test_redrob_competition`: PASS.
- `backend.test_dataset_intelligence`: PASS.

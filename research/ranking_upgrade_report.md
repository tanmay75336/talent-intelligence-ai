# Phase 4A Ranking Upgrade Report

## 1. Previous Top 10
| Rank | Candidate ID | Score |
|---:|---|---:|
| 1 | CAND_0005260 | 0.573697 |
| 2 | CAND_0088025 | 0.563952 |
| 3 | CAND_0030031 | 0.562878 |
| 4 | CAND_0022894 | 0.562863 |
| 5 | CAND_0068351 | 0.557583 |
| 6 | CAND_0096142 | 0.556562 |
| 7 | CAND_0091254 | 0.556235 |
| 8 | CAND_0051630 | 0.554805 |
| 9 | CAND_0061819 | 0.550571 |
| 10 | CAND_0098288 | 0.548928 |

## 2. New Top 10
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

## 3. Candidates Promoted
| Candidate ID | Previous Rank | New Rank | Evidence-Based Reason |
|---|---:|---:|---|
| CAND_0030031 | 3 | 2 | AI Engineer with 5.7 years; career evidence includes embeddings, ranking, and recommendation. Evidence: built a content recommendation system serving 10M+ users. |
| CAND_0096142 | 6 | 4 | Applied ML Engineer with 5.0 years; career evidence includes embeddings, ranking, and recommendation plus shipped/pipeline/users production terms. |
| CAND_0051630 | 8 | 5 | Machine Learning Engineer with 6.0 years; career evidence includes Elasticsearch, FAISS, ranking, retrieval, and semantic search. |
| CAND_0002025 | 15 | 7 | Senior AI Engineer with 5.9 years; career evidence includes embeddings, inference, ranking, recommendation, deployed production systems, latency, and users. |
| CAND_0008425 | 16 | 10 | Senior NLP Engineer with 7.8 years; career evidence includes Pinecone, retrieval, ranking, semantic search, inference, monitoring, and latency. |

## 4. Candidates Demoted
| Candidate ID | Previous Rank | New Rank | Evidence-Based Reason |
|---|---:|---:|---|
| CAND_0022894 | 4 | 8 | Strong data engineering profile, but AI infrastructure appears outside career history; career evidence centers on streaming data pipelines rather than retrieval/ranking systems. |
| CAND_0098288 | 10 | 69 | Model-serving/API evidence exists, but no career-backed AI infrastructure hits were found; adjustment was limited to 0.010. |
| CAND_0040200 | 11 | 27 | Production NLP pipeline evidence is present, but no career-backed retrieval/ranking/vector evidence was found. |
| CAND_0028287 | 12 | 24 | Production model-serving integration evidence is present, but AI infrastructure appears outside career history. |
| CAND_0011967 | 14 | 32 | Backend/model-serving integration evidence is present, but the candidate explicitly worked on integration/observability rather than the model itself. |

## 5. Trap Candidates Removed From Top Positions
- Old top 10 trap-flagged candidates: 0
- New top 10 trap-flagged candidates: 0
- Old top 100 trap-flagged candidates: 0
- New top 100 trap-flagged candidates: 0

No top-position trap removals were recorded by the Phase 4A detector. The main quality change was promotion of candidates with career-backed retrieval, ranking, recommendation, vector search, and production ownership evidence.

## 6. Runtime Comparison
- Previous full ranking runtime: 4:24.55
- Phase 4A full ranking runtime: 4:53.77
- Runtime budget: under 5:00
- Status: PASS

## 7. Validation
- Submission validator: PASS
- Output rows: 100
- Output format: candidate_id,rank,score,reasoning
- External API calls: none added

## 8. Summary
Phase 4A adds a bounded competition-only evidence calibration layer. It separates skills listed in the profile from skills proven in career history, rewards production ownership near AI infrastructure work, uses RedRob platform signals only as a small tie breaker, and improves competition CSV reasoning with concrete candidate evidence.

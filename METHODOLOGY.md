# Methodology — OctaOps | RedRob Track 1

This document explains the decisions behind our ranking system: what trade-offs we made, why certain signals were prioritized, and how we approached candidate quality beyond simple keyword matching.

---

## 1. Problem framing

We read the job description before writing any code. The JD is not asking for "the most AI-skilled candidate" — it is asking for someone who has **owned production retrieval and ranking systems** and has the measurement discipline to improve them over time.

That distinction shapes everything. A candidate whose skills section lists FAISS, Weaviate, and Qdrant but whose career history shows no evidence of building or operating such systems is not the right hire. A candidate whose career shows they built a recommendation engine at a product company — even if they don't use the exact vocabulary from the JD — is a much better match.

Our system is designed to detect that difference.

---

## 2. Scoring design

We score each candidate on six signals:

```
score = skill_overlap    × 0.26
      + group_overlap    × 0.16
      + term_overlap     × 0.18
      + experience_fit   × 0.12
      + execution_signals × 0.20
      + career_evidence   × 0.08
```

**Why these weights?**

The first three terms (skill, group, term overlap) form the JD-matching backbone. Together they account for 60% of the base score. We separated skill overlap from group overlap because the JD mentions specific technologies (vector databases, ranking systems) but also implies broader system categories — a candidate with strong retrieval expertise who uses different tool names should still be visible.

`experience_fit` rewards the 5–9 year target band without hard-excluding people outside it. The JD itself says "5-9 years is a range, not a requirement." We honour that.

`execution_signals` captures depth, domain relevance, and startup readiness extracted from the candidate's career profile structure — rewarding people who have shipped things, not just studied them.

`career_evidence` was added after we noticed that strong keyword overlap could come from profiles that list AI terms in skills but have no matching career history. This term counts JD-relevant AI infrastructure terms found **only in career history text** — not in skills or summaries — capped at 5 hits. It rewards demonstrated experience, not claimed experience.

---

## 3. Evidence calibration

After base scoring, we apply a bounded ±0.10 adjustment from `evidence_calibrator.py`.

The calibrator looks at career text for:
- **Production ownership evidence**: terms like "built," "owned," "shipped" combined with production-context words
- **Retrieval system indicators**: vector database, ranking, recommendation, embedding language in a work context
- **Red flags**: trap patterns described in the next section

Calibration is intentionally bounded. A weak base scorer cannot be rescued by calibration, and a strong base scorer cannot be punished unfairly. The maximum swing is ±0.10.

---

## 4. Production disclaimer detection

The JD contains this disqualifier: *"If you've spent your career in pure research environments without any production deployment — we will not move forward."*

During testing, we found profiles where candidates explicitly described themselves as working on "the pure ML side" while "production deployment was handled by the platform team." Those candidates were ranking too high because the word "production" appeared in their career text — even in a sentence explaining they hadn't done it.

We detect a set of explicit disclaimer phrases in career text. When detected, the career evidence term receives a 0.5× multiplier — not a hard exclusion, since the candidate may still have genuine ML depth — but enough to ensure they don't outrank candidates who actually owned the production systems.

---

## 5. Reranking

After base scoring and calibration, we maintain a pool of the top 300 candidates. Over this pool, we apply per-candidate adjustments:

**Headroom-scaled depth bonus:** The calibrator already rewards some evidence signals. The reranker adds a bonus proportional to the *unused headroom* in the calibration adjustment — so candidates who already received the full calibration bonus get near-zero extra credit, while candidates with strong evidence depth who were slightly underrewarded get a modest lift. Maximum effect: +0.030.

**Behavioral bonus:** A small additional signal from `open_to_work_flag`, `recruiter_response_rate`, and engagement patterns. This is not a primary driver — it acts as a tie-breaker when technical evidence is comparable. Maximum effect: ~+0.010.

**Surface-match penalty (−0.030):** Applied to candidates who match system vocabulary (ranking, retrieval, recommendation) but show no production or ownership evidence. They look right on paper but the career evidence doesn't back it up.

**Trap penalty (−0.050):** Applied when the calibrator's trap flags fire (keyword stuffing, framework-only profile, research-only mismatch, hands-off seniority). Reinforces calibration for borderline cases.

The top 100 from this reranked pool become the final submission.

---

## 6. Trap handling

The dataset documentation describes additional candidate signals and behavioral fields. We use these signals carefully and avoid relying only on surface-level matches. We do not hard-code candidate IDs — our trap detection is pattern-based.

| Pattern | How we detect it |
|---------|-----------------|
| Keyword stuffing | AI-tagged skills with low endorsement/duration and no career AI infrastructure hits |
| Framework-only AI profile | LangChain/OpenAI/LLM skill labels without retrieval, ranking, or production work history |
| Research-only mismatch | Research-context vocabulary (papers, labs, thesis) without production/ownership evidence |
| Hands-off seniority | Very long tenure with management-track language and weak ownership verbs in career text |
| Impossible timelines | Implicit in career field parsing — we do not special-case IDs |

These rules came from inspecting candidate patterns and failure cases during development. The goal was to make keyword-only profiles naturally score lower, not to build a separate classifier.

---

## 7. Behavioral signals

We evaluate the documented RedRob behavioral signal set selectively. A perfect technical fit candidate who is unavailable should still rank above a mediocre but very available candidate. The behavioral adjustment is small and secondary.

Signals we explicitly consider:
- `open_to_work_flag` — direct availability signal
- `recruiter_response_rate` — reachability for hiring
- `github_activity_score` — correlated with active engineering practice
- `notice_period_days` — practical logistics
- `willing_to_relocate` — relevant for Noida/Pune preference in JD

Not every available behavioral field is treated as a ranking-quality signal. Signals like `endorsed_by_recruiters` and `linkedin_connected` are intentionally excluded because they primarily measure platform engagement rather than evidence of role fit.

---

## 8. Reasoning generation

Each top-100 candidate receives a 1–2 sentence explanation. We generate this deterministically from the candidate's own data — no hosted LLM during ranking.

What each explanation contains:
1. **A fact anchor**: years of experience, current title, current company (pulled from structured profile)
2. **JD connection**: the specific retrieval/vector/evaluation technologies found in their career history, with action verbs (built, shipped, owned)
3. **Behavioral note**: availability, notice period, or GitHub score when materially notable
4. **Honest caveats**: if a candidate is below the experience target band, we say so. If their evidence is thinner than top candidates, the phrasing reflects that.

We avoided rigid explanation templates because the reasoning should be useful to a recruiter reviewing the candidate, not just a list of matched signals.

---

## 9. NDCG optimisation

The official metric composite is NDCG@10 (50%) + NDCG@50 (30%) + MAP (15%) + P@10 (5%).

Because the evaluation strongly rewards the highest-ranked candidates, we focused most on ranking quality at the top:
- The top of the heap should contain candidates with the strongest combination of career evidence, calibration rewards, and clean trap detection
- The reranker bonus is designed to elevate candidates with deep evidence who were slightly underscored by the base formula
- The surface-match penalty and trap penalty protect the top 10 from keyword-stuffed profiles

We do not claim to have optimised NDCG@50 separately — our pipeline produces a consistent scoring function across the full 300-candidate pool, which should naturally handle ranking depth.

---

## 10. What we did not do

- We did not use embeddings or semantic similarity during ranking (CPU budget and latency constraints)
- We did not use any hosted LLM during the ranking step
- We did not special-case specific candidate IDs
- We did not train a machine learning model (the system is a hand-designed scoring function)
- We did not tune weights using the ground truth (there is no ground truth available to us)

The weights were chosen by repeatedly comparing signals against the JD requirements and checking whether they represented real evidence of candidate fit.

---

## 11. Reproducibility

```bash
python -m backend.competition.rank --candidates data/candidates.jsonl --job data/job_description.docx --output OctaOps.csv

python -m backend.competition.validate_submission OctaOps.csv
# Submission is valid.
```

Runtime varies by CPU and execution environment. Tested benchmark runs complete within the official 300-second CPU-only limit.

The ranking pipeline is deterministic for the same input files and code version.

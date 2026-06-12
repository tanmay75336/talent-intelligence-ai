# Phase 8C.0 — Ranking System Audit

**Date:** 2026-06-10  
**Current submission:** `submission_phase8b3.csv` ✅  
**Analysis scope:** Complete ranking pipeline as implemented.

---

## 1. How Ranking Currently Works — Beginner Explanation

> *"If a new candidate walks through the door, how does the system decide where they rank?"*

**Step 1 — Read the profile.**  
The system loads the candidate's JSON record: their job titles, career history descriptions, skill list, education, certifications, and platform signals (GitHub activity, recruiter response rate, open-to-work status, etc.).

**Step 2 — Compute a base score.**  
The system compares the candidate to the job description across four dimensions:

- **Skill match** (34%): How many of the JD's core technical skills appear in the candidate's skill list? (e.g., does the JD ask for FAISS and does the candidate have it?)
- **Skill category match** (16%): Even if exact skills differ, do they belong to the same domain groups? (e.g., "Pinecone" and "Weaviate" both map to the "vector database" group)
- **Term overlap** (18%): Do the important words in the JD appear in the candidate's overall profile text?
- **Experience fit** (12%): Is their experience in the 5–9 year range the JD targets? (full credit inside, reduced outside)
- **Intelligence signals** (20%): A composite of technical depth, execution maturity, startup readiness, transferability, and domain relevance — computed by the candidate intelligence engine.

**Step 3 — Calibrate with career evidence.**  
The base score is adjusted (-0.06 to +0.10) based on what the system finds in the candidate's actual *career history text* — not their skill tags. It looks for:

- Did they work with real AI infrastructure (retrieval systems, embeddings, ranking pipelines, vector databases) *in their career roles*?
- Did they *produce and own* those systems (verbs like "built", "shipped", "owned" near technical context)?
- Do they show evaluation maturity (NDCG, A/B testing, held-out benchmarks)?
- Do they raise red flags — only using frameworks without systems, pure research without shipping, or wrong domain (CV/robotics) work?

This step is the most important quality layer. It separates candidates who *have retrieval on their résumé* from candidates who *built retrieval systems in production*.

**Step 4 — Rerank with depth + behavioral signals.**  
Among the top 300 candidates, a second pass adjusts scores using:

- **Depth bonus** (up to +0.03): How many independent evidence dimensions does the candidate show (eval maturity, retrieval infra, system terms, production+ownership)? Scaled by headroom in Phase 7's calibration — candidates Phase 7 already fully rewarded get near-zero extra.
- **Behavioral signals** (up to +0.01): Platform signals from RedRob — GitHub activity, recruiter response rate, recently active, open-to-work.
- **Surface match penalty** (-0.03): System keywords with no production/ownership backing → risk signal.
- **Trap penalty** (-0.05): Candidates already flagged as wrong-domain, framework-only, etc.

**Step 5 — Sort and output top 100.**  
Candidates are sorted by final score (descending). The top 100 are written to CSV with rank, score, and a reasoning string. The reasoning is generated deterministically from career evidence — not from an AI API.

---

## 2. Architecture Diagram

```
candidates.jsonl  →  [adapt_redrob_candidate]  →  CandidateProfile
                              ↓
                   profile.skills, career_history,
                   redrob_signals, years_of_experience
                              ↓
                  [build_competition_core_signals]
                              ↓
          technical_depth, execution_maturity,
          startup_readiness, transferability,
          domain_relevance  (0-100 each)
                              ↓
                  [_competition_score]
                              ↓
    skill_overlap×0.34 + group_overlap×0.16
  + term_overlap×0.18 + experience_fit×0.12
  + signal_average×0.20   →  BASE SCORE (0–1)
                              ↓
                  [calibrate_candidate_evidence]
          scans career_history text for AI_INFRA_TERMS,
          PRODUCTION_TERMS, ownership verbs, trap patterns,
          excellence signals, evaluation maturity
                              ↓
         ADJUSTMENT  (-0.060 to +0.100) gates on
         has_domain_relevant_career (Phase 8B.3)
                              ↓
              PHASE 7 SCORE = base + adjustment
                              ↓
         ┌─── heapq top-300 pre-selection ───┐
         │                                   │
    [rerank_experiment.py — Phase 8B.3]      │
    _headroom_depth_bonus + behavioral        │
    + surface_penalty + trap_penalty         │
         └─────────── FINAL SCORE ───────────┘
                              ↓
              Sort → Top 100 → generate reasoning
                              ↓
                   submission_phase8b3.csv
```

---

## 3. Candidate Ranking Walkthrough

### Strong Candidate — Rank 1: Senior AI Engineer @ Apple (5.9y)

**Final score: 0.703812**

| Component | Value | Contribution |
|---|---|---|
| Skill overlap (× 0.34) | 0.438 | **0.1488** — top contributor |
| Group overlap (× 0.16) | 1.000 | 0.1600 — full group match |
| Term overlap (× 0.18) | 0.169 | 0.0305 |
| Experience fit (× 0.12) | 1.000 | 0.1200 — in 5–9y window |
| Intelligence signals (× 0.20) | 0.684 | 0.1368 |
| **Base score** | | **0.596** |
| Calibration adj | — | **+0.099** (near max) |
| Depth bonus | — | +0.0003 (near 0 — P7 already maxed) |
| Behavioral | — | +0.009 (GitHub 97, response 80%, open) |
| **Final score** | | **0.7038** |

**What helped:** This candidate built and shipped a production recommendation system combining collaborative filtering, sentence-transformer embeddings, and a behavioral re-ranking layer. Their career text contains `embedding`, `embeddings`, `inference`, `ranking`, `recommendation` (all AI_INFRA_TERMS), plus `deployed`, `latency`, `pipeline` (PRODUCTION_TERMS), plus `built`, `deployed`, `shipped` (OWNERSHIP_TERMS). The retrieval excellence bonus (+0.009) and eval maturity bonus (+0.008) both fire. GitHub score of 97, 80% recruiter response rate.

**What limited them:** The behavioral depth bonus is near-zero because the Phase 7 calibration already awarded near-maximum (+0.099). The headroom formula correctly avoids double-counting.

---

### Middle Candidate — Rank 45: Senior Software Engineer (ML) @ Freshworks (5.3y)

**Final score: 0.592**

| Component | Value | Contribution |
|---|---|---|
| Skill overlap (× 0.34) | 0.250 | 0.0850 |
| Group overlap (× 0.16) | 1.000 | 0.1600 |
| Term overlap (× 0.18) | 0.115 | 0.0206 |
| Experience fit (× 0.12) | 1.000 | 0.1200 |
| Intelligence signals (× 0.20) | 0.625 | 0.1250 |
| **Base score** | | **0.511** |
| Calibration adj | — | **+0.069** |
| Depth bonus | — | +0.005 (depth=2, headroom=31%) |
| Behavioral | — | +0.008 |
| **Final score** | | **0.592** |

**What helped:** Career hits on `inference`, `ranking`, `recommendation` pass the domain gate. Has production and ownership language in an ML context. In the 5–9y range.

**What limited them:** `evidence_depth = 2/4` — no explicit eval maturity (ndcg/a-b terms) and no retrieval infra terms (FAISS/embedding). Excellence and eval maturity bonuses don't fire. Lower skill overlap (0.25 vs 0.44). Career snippet reveals CV/NLP work: *"built CV models for image moderation; interested in transitioning toward NLP"* — the ranking work is real but lighter-weight.

**Key lesson:** This candidate sits in the middle because the system correctly gives partial credit for ML production work without the depth of specialist retrieval experience.

---

### Borderline Candidate — Rank 90: Senior Data Scientist @ Amazon (7.6y)

**Final score: 0.559**

| Component | Value | Contribution |
|---|---|---|
| Skill overlap (× 0.34) | 0.188 | 0.0638 — low skill match |
| Group overlap (× 0.16) | 0.667 | 0.1067 |
| Term overlap (× 0.18) | 0.132 | 0.0237 |
| Experience fit (× 0.12) | 1.000 | 0.1200 |
| Intelligence signals (× 0.20) | 0.706 | 0.1412 |
| **Base score** | | **0.455** |
| Calibration adj | — | **+0.095** (near max) |
| Depth bonus | — | +0.002 (depth=4, headroom=5%) |
| Behavioral | — | +0.008 |
| **Final score** | | **0.559** |

**What helped:** Excellent career evidence — `embedding`, `pinecone`, `rag`, `ranking` in career text; full depth=4 (eval maturity + retrieval + system + production+ownership); offline-online correlation analysis and A/B testing in career. High intelligence signals (0.706). This is a genuinely strong candidate.

**What limited them to rank 90:** The base score is only 0.455, dragged down by **low skill overlap** (0.188 — their listed skills include `Haystack`, `MLOps`, `Time Series` which are not among the JD's core skills). The calibration lifts them by nearly the maximum (+0.095) but cannot overcome the 0.14 gap in base score vs rank-1.

**Key observation:** This reveals a structural ordering constraint — a candidate with strong career evidence but weak skill-tag match can be outranked by a candidate with better skill overlap even with moderate career evidence. This is an inherent base-score tension.

---

## 4. Signal Map

| Signal | Source | What it Measures | Weight/Range | Doc Support |
|---|---|---|---|---|
| `skill_overlap` | `profile.skills` ∩ JD core skills | Exact technical skill match | ×0.34 (largest weight) | JD: "Deep technical depth in modern ML systems — embeddings, retrieval, ranking" |
| `group_overlap` | Skill taxonomy groups | Broad domain alignment (e.g. "vector DB" family) | ×0.16 | JD: general technical depth |
| `term_overlap` | Full profile text ∩ JD terms | Vocabulary alignment | ×0.18 | Submission spec: general alignment |
| `experience_fit` | `years_of_experience` | 5–9y = 1.0, step-down outside | ×0.12 | JD: "5-9 years — this is a range, not a requirement" |
| `signal_average` | Intelligence engine composite | Technical depth, execution maturity, startup readiness | ×0.20 | JD: "founding team", "scrappy" |
| `career_ai_hits` | Career text ∩ AI_INFRA_TERMS | AI infrastructure in work history | Up to +0.030 | JD: "built retrieval/ranking systems" |
| `prod+own bonus` | Career text: PRODUCTION + OWNERSHIP terms, gated on domain | Production system ownership | Up to +0.024 | JD: "shipped at least one end-to-end system" |
| `experience+own bonus` | years in range + ownership_hits | Builder in target experience range | +0.010 | JD: experience range |
| `startup+own bonus` | STARTUP_TERMS + ownership | Founding-engineer attitude | +0.006 | JD: "scrappy product-engineering" |
| `retrieval excellence` | Career text ∩ RETRIEVAL_EXCELLENCE_GROUPS (≥3 groups + production) | Specialist retrieval infra | Up to +0.015 | JD: "embeddings, vector databases" |
| `eval maturity bonus` | Career text ∩ EVALUATION_MATURITY_TERMS | Measurement discipline | Up to +0.015 | JD: "set up evaluation infrastructure — offline benchmarks, online A/B" |
| `behavioral tie-breaker` | RedRob platform signals (GitHub, response rate, etc.) | Candidate availability/engagement | Up to +0.012 | redrob_signals_doc: "predictive of whether candidate can be hired" |
| `trap penalties` | Pattern detection (framework-only, hands-off, wrong-domain, honeypot) | Prevents false-positive inflation | -0.020 to -0.060 | JD: "that's a trap we've explicitly built into the dataset" |
| `depth bonus (P8)` | Career eval+retrieval+system+prod signals, headroom-scaled | Remaining evidence quality after P7 | Up to +0.030 | JD: all four evidence dimensions required |
| `behavioral bonus (P8)` | RedRob availability + engagement | Recruiter-accessible strong candidates | Up to +0.010 | redrob_signals_doc |
| `surface match penalty` | System terms without production/ownership | Risk of keyword-only match | -0.030 | JD: "the right answer is not AI keywords" |
| `trap penalty (P8)` | Existing trap_flags reinforced | Suppresses already-flagged candidates | -0.050 | JD: "explicit trap" |

### Domain relevance gate (Phase 8B.3)
All ownership/production/startup bonuses require `career_ai_hits` to be non-empty. Generic operational ownership ("owned warehouse") does not qualify.

---

## 5. Current Strengths

### ✅ Top-30 is clean
No candidate in the top 30 has evidence depth below 3. All have confirmed AI infrastructure career evidence. Zero high-confidence false positives in this critical tier.

### ✅ Top-50 is stable
All top-50 candidates are in the 5–9y experience range. Zero skill-overlap outliers (no candidate with zero career_ai_hits has high group_overlap enough to inflate into top-50). Zero candidates with no career_ai_hits in top-50.

### ✅ Traps are robustly detected
Honeypot candidates (wrong-domain, CV engineers, framework-only, research-only) receive compound penalties from Phase 7 calibration + Phase 8 reranker. Two confirmed wrong-domain candidates (CV domain, `wrong_domain_standalone`) correctly evicted from top-100 entirely.

### ✅ Double counting eliminated
Phase 8B.1 fixed the headroom scaling. Candidates at Phase 7 calibration ceiling (~+0.100) receive near-zero additional depth bonus. No signal is substantially counted twice.

### ✅ Eval maturity and context-pattern detection
Phase 8B.1 added context-pattern detection for evaluation maturity — candidates who describe "learning-to-rank", "relevance labeling", "held-out eval sets", "click-through data" are correctly credited even without literal "ndcg" or "a/b test" tokens. Prevents vocabulary-bias penalizing genuine builders.

### ✅ Domain coupling fixed
Phase 8B.3 ensures all ownership/production bonuses require actual ML infrastructure career evidence. "Owned fulfillment operations" no longer receives the same credit as "owned the ranking pipeline."

---

## 6. Remaining Weaknesses

### ⚠️ BASE SCORE IS THE DOMINANT DIFFERENTIATOR

**Spread analysis:**

| Layer | Spread across top-100 |
|---|---|
| Base score | **0.1473** — controls most of the ordering |
| P7 calibration adj | 0.0530 — important secondary signal |
| P8 depth bonus | 0.0119 — minor fine-tuning |
| P8 behavioral | 0.0067 — tie-breaker only |

The base score — driven primarily by **skill-tag overlap (34%)** — has more than twice the sorting power of the calibration layer. A candidate with strong career evidence but mismatched skill tags (e.g., using "Haystack" instead of "FAISS" for the same retrieval work) can be consistently outranked by a candidate with weaker evidence but better-matched skill vocabulary.

**Evidence:** Rank-90 candidate (Senior Data Scientist @ Amazon, depth=4, near-max adj=+0.095) has base score 0.455 vs Rank-1's 0.596. The 0.141 base gap is too large for even maximum calibration to overcome. Yet this candidate built ranking models, A/B testing infrastructure, and a full offline-online correlation workflow.

### ⚠️ 4 DEPTH=4 CANDIDATES OUTSIDE TOP-100 (HIDDEN GEMS)

Within the first 15,000 candidates scanned, 4 candidates with `evidence_depth=4`, no trap flags, and 5–9y experience are below rank 100:

| Candidate | Estimated Score | Career AI | Reason Outside Top-100 |
|---|---|---|---|
| NLP Engineer @ Paytm (7.9y) | 0.553 | `embedding, ranking` | Base score too low (adj=+0.087 not enough to compensate) |
| Senior Data Scientist @ Sarvam AI (7.4y) | 0.545 | `elasticsearch, embedding` | Same pattern |
| Senior ML Engineer @ Amazon (8.0y) | 0.536 | `embedding, pinecone` | Same pattern |
| Senior AI Engineer @ Adobe (5.9y) | 0.510 | `embedding, ranking` | Lower base score (skill tag mismatch) |

These are candidates where the calibration layer gives the maximum possible reward but the base score gap is too large to bridge. This suggests the base score's 34% skill-overlap weight may be too dominant.

### ⚠️ TERM OVERLAP CONTRIBUTES LITTLE (0.018% spread)

The `term_overlap × 0.18` component has narrow actual range because most ML candidates use similar technical vocabulary. In the top-100, term overlap ranges from ~0.11 to ~0.17, contributing only about ±0.01 to the final score. This makes it a relatively weak discriminator.

### ⚠️ BEHAVIORAL SIGNALS ARE NEAR-UNIFORM IN TOP-50

The behavioral bonus range is 0.003–0.010, but within the top-50, most candidates have high engagement scores. The signal is not meaningfully differentiating candidates in the critical tiers — it acts more as a noise layer than a discriminator.

### ⚠️ SIGNAL_AVERAGE IS A BLACK BOX

The `signal_average` (×0.20, second-largest weight) is computed by `build_competition_core_signals()` — a composite of technical_depth, execution_maturity, startup_readiness, transferability, domain_relevance. This is the least auditable component: it's not traced in detail, and its sub-signals are not directly inspectable in the ranking output.

---

## 7. Improvement Opportunities — Ranked by Evidence

### Opportunity 1 — Re-balance skill overlap vs career evidence weight
**Current limitation:** Base score skill_overlap (34%) dominates over career evidence calibration (max +0.100). A candidate with strong career evidence can be blocked by skill tag vocabulary mismatch.  
**Evidence:** 4 depth=4 candidates outside top-100; Rank-90 candidate (Amazon, depth=4) vs Rank-20 region candidates with depth=2 but better skill tags.  
**Expected benefit:** Better recall of genuinely strong builders with non-standard skill tag vocabulary.  
**Regression risk:** MEDIUM — changes the fundamental scoring function. Could move candidates throughout the entire list. Requires careful A/B test on benchmark.

### Opportunity 2 — Improve recall mechanism for hidden gems
**Current limitation:** The Phase 7 base score pre-selection (heapq with `base_score + MAX_EVIDENCE_ADJUSTMENT` threshold) filters out candidates before calibration runs, so a depth=4 candidate with low base score may never receive full calibration.  
**Evidence:** The pre-selection threshold is `base_score + 0.100 < top_candidates[0][0]`. If the minimum top-300 score is 0.58, candidates with base score below 0.48 are discarded. A candidate with base=0.46 but true final score of 0.55 would be silently excluded.  
**Expected benefit:** Recover hidden gems currently below the pre-selection floor.  
**Regression risk:** LOW-MEDIUM — would increase computation time but not change ranking logic for already-included candidates.

### Opportunity 3 — Audit and expose `signal_average` sub-components
**Current limitation:** `signal_average` (×0.20) is opaque. If `build_competition_core_signals()` mis-scores specific candidate types (e.g., founders, cross-domain builders), it would be undetectable.  
**Evidence:** Not directly confirmed but theoretically possible. The signal is untested at this audit level.  
**Expected benefit:** Auditability, potential correction.  
**Regression risk:** LOW (audit first, fix only if problem found).

### Opportunity 4 — Behavioral signals: use open-to-work flag as a harder filter
**Current limitation:** Behavioral signals add up to +0.010 and can only modestly lift or lower candidates. The JD explicitly says a candidate who hasn't logged in for 6 months is "for hiring purposes, not actually available."  
**Evidence:** redrob_signals_doc is explicit. The current behavioral implementation treats this as a soft modifier. Candidates who are demonstrably unavailable (logged out months ago, 0% response rate) are only mildly penalized.  
**Expected benefit:** Better recruiter-relevance for top-10 candidates where availability matters.  
**Regression risk:** LOW — doesn't affect recall, only ordering within close-scored candidates.

---

## 8. Final Decision

### **B) CONTINUE IMPROVING**

**Recommended next investigation: Opportunity 1 — Base Score Re-balancing**

The base score's 34% skill-overlap weight is the most impactful lever in the ranking system and the most under-investigated one. There are 4 confirmed depth=4 candidates outside the top-100 whose exclusion traces directly to base score gaps caused by skill-tag vocabulary mismatch, not lack of actual system-building experience.

**Why this is the highest-impact next step:**
- Skill overlap is the largest single weight in the formula (0.34)
- The gap between base score spread (0.147) and calibration spread (0.053) means the calibration cannot meaningfully re-order candidates where the base score already strongly separates them
- All other improvements (behavioral, depth bonus, domain coupling) are already implemented. They collectively contribute <0.02 of sorting power
- The 4 hidden gems are not recoverable under the current base score architecture regardless of calibration improvements

**Suggested investigation:** Check whether reducing `skill_overlap` weight from 0.34 → 0.25 and increasing calibration ceiling from 0.100 → 0.130 produces better top-100 membership without introducing false positives. Must be benchmarked and validated before merging.

**Caution:** Any weight change affects the entire ordering from rank 1 to 100. This is the highest-risk investigation in the roadmap. It requires the full Phase 8A evaluation harness + benchmark before any merge.

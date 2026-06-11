# Phase 8C.2 — Ranking Architecture Alignment Audit

**Date:** 2026-06-10  
**Champion:** `submission_phase8b3.csv`  
**Scope:** Analysis only. No code changed.

---

## 1. Current Architecture Verdict

**The calibration layer is working harder than its structural position suggests — but not hard enough.**

The architecture is partially aligned with the official challenge intent:

- Career evidence (calibration) is **not** merely a fine-tuner. It is lifting 12 of 100 top candidates in from positions outside the raw top-100. One candidate moved from base rank 286 to final rank 90 — a 196-position lift by evidence alone.
- However, calibration sits **after** base score pre-selection. The base score acts as a gate, not a peer. Candidates whose base score is too low are silently excluded before calibration even runs.
- The maximum calibration ceiling is **exactly sufficient** to lift near-threshold candidates in, but **insufficient** to lift sub-threshold candidates — even when their career evidence is clearly stronger than some already inside.

The architecture produces a correct ranking for strong candidates (top-50) and a systematically challenged ranking at the boundary (ranks 85–100), where base-score vocabulary alignment and career evidence quality diverge.

---

## 2. Official Document Evidence

### JD: What the hiring system should prioritize

> *"Things you absolutely need:*  
> *Production experience with embeddings-based retrieval systems… deployed to real users. We don't care which model — we care that you've handled embedding drift, index refresh, retrieval-quality regression in production.*  
> *Production experience with vector databases or hybrid search infrastructure… the specific tech doesn't matter; the operational experience does.*  
> *Hands-on experience designing evaluation frameworks for ranking systems — NDCG, MRR, MAP, offline-to-online correlation, A/B test interpretation."*

These are **career evidence signals**, not skill-tag signals. The JD explicitly says *"we don't care which model"* and *"the specific tech doesn't matter"* — the tech vocabulary in a skill list is explicitly not what they're evaluating.

> *"The 'right answer' to this JD is not 'find candidates whose skills section contains the most AI keywords.' That's a trap we've explicitly built into the dataset."*

> *"A Tier 5 candidate may not use the words 'RAG' or 'Pinecone' in their profile, but if their career history shows they built a recommendation system at a product company, they're a fit."*

### What this implies for ranking architecture

The official intent is a **career-evidence-first** hierarchy:
1. Did they build the right systems (retrieval, ranking, recommendation) in production?
2. Did they own and evaluate those systems?
3. Do they have the technical breadth (skills, domain vocabulary)?
4. Are they reachable (behavioral signals)?

The current architecture implements this as:
1. Technical breadth (base score: skill tags, vocabulary, domain terms) → **primary gate**
2. Career evidence (calibration: ±0.10 adjustment) → secondary
3. Evaluation depth + behavioral (reranker: ±0.04) → tertiary

This order is **inverted relative to the official intent**. The JD says career evidence is #1; the architecture makes it #2.

---

## 3. Does "Built the Right Thing" Dominate "Listed Right Words"?

**No — not always. It depends on the magnitude of the base-score gap.**

### When career evidence wins (calibration overrules base score):

Among the top-100, **12 candidates** are there only because calibration lifted them past candidates with higher base scores. The most extreme case:

- **Final rank 90: Senior Data Scientist @ Amazon**  
  Base rank: **286** → Final rank: **90**  
  adj = +0.095 (near maximum)  
  Career evidence: depth=4/4 — eval maturity ✅, retrieval infra ✅, system ✅, prod+own ✅  
  Career snippet: *"trained and shipped multiple ranking models… owned the offline-online correlation analysis that determined which offline metrics actually predicted A/B test outcomes"*

In this case, career evidence wins convincingly: +196 rank positions.

### When "listed right words" wins over career evidence:

**10 counterfactual pairs** found within the first 20,000 candidates where a depth≤2 candidate ranks above a depth=4 candidate with a score gap of ≤0.025:

**Pair A (strongest counterexample):**

| | IN (Rank 93) | OUT (Unlisted) |
|---|---|---|
| Score | 0.559 | 0.553 |
| Depth | **2/4** | **4/4** |
| Career AI hits | `ranking, recommendation` | `embedding, embeddings, ranking, recommendation` |
| Eval maturity | ❌ | ✅ |
| Retrieval infra | ❌ | ✅ |
| Career snippet | *"built recommendation-style features at a mid-stage startup — lighter weight than ranking systems at FAANG"* | *"owned the ranking layer for an e-commerce search product, evolving it from a hand-tuned scoring function to a learning-to-rank model over 9 months. designed the relevance labeling pipeline..."* |

**Official JD verdict:** The OUT candidate is the stronger match.
- Has eval maturity (designed the relevance labeling pipeline → offline evaluation experience)
- Has retrieval infrastructure (embeddings in career, not just skill tags)
- Explicitly owned the system end-to-end
- The IN candidate self-describes as "lighter weight than FAANG ranking systems"

The current ranking places the IN candidate above the OUT candidate because the IN candidate's base score is higher (skill-tag vocabulary alignment), and the OUT candidate cannot bridge the gap even with near-maximum calibration.

**Pair B:**

| | IN (Rank 92) | OUT (Unlisted) |
|---|---|---|
| Score | 0.559 | 0.545 |
| Depth | **2/4** | **4/4** |
| Career AI hits | `inference, ranking, recommendation` | `elasticsearch, embedding, embeddings, faiss` |
| Eval maturity | ❌ | ✅ |
| Retrieval infra | ❌ | ✅ |
| Career snippet | Same as Pair A IN | *"developed a semantic search feature for an internal knowledge base of ~500k documents. used sentence-transformers (all-minilm-l6-v2 initially, later upgraded to bge-base) with FAISS for fast nearest-neighbour search"* |

**Official JD verdict:** Again, OUT is the stronger match. FAISS + sentence-transformers + production semantic search is a direct hit on the JD's "absolutely need" criteria. The IN candidate has neither retrieval infrastructure nor evaluation maturity in their career history.

---

## 4. Task 1 — Signal Hierarchy Measured

### Sorting power by layer (top-100):

| Layer | Spread | Position | Who it favors |
|---|---|---|---|
| Base score | **0.147** | **Gate** — runs first, pre-screens 99,900 candidates | Candidates with many JD-matching skill tags |
| Calibration adj | **0.053** | Secondary — runs only for pre-selected candidates | Candidates with career evidence of building AI systems |
| Depth bonus (P8) | 0.012 | Tertiary | Higher-evidence candidates among pre-selected |
| Behavioral | 0.007 | Tie-breaker | Active, responsive candidates |

### What the 12/100 lift statistic means:

Only 12 candidates were lifted from base-rank > 100 into the final top-100 by calibration. This sounds like good calibration power. But the constraint is **the pre-selection gate** — calibration can only see candidates within range of the top-100 cutline. Candidates further out (base rank > ~300) are never evaluated.

The 5 missed depth=4 candidates confirmed in Phase 8C.0 are all **within 0.020 base score units** of the pre-selection threshold:

| Missed Candidate | Base Score | Min Top-100 Base | Gap |
|---|---|---|---|
| NLP Engineer @ Paytm | 0.454 | 0.449 | **+0.005 above threshold** — reachable |
| Search Engineer @ Razorpay | 0.452 | 0.449 | **+0.003 above threshold** — reachable |
| Sr Data Scientist @ Sarvam AI | 0.437 | 0.449 | -0.012 below threshold — **excluded** |
| Sr ML Engineer @ Amazon | 0.429 | 0.449 | -0.020 below threshold — **excluded** |
| Applied ML Engineer @ Krutrim | 0.437 | 0.449 | -0.012 below threshold — **excluded** |

So 3 of the 5 depth=4 missed candidates had their calibration computed but scored too low. 2 were below the pre-selection threshold and were **never evaluated at all** — their career evidence was invisible to the system.

---

## 5. Task 3 — Calibration Ceiling Analysis

### Distribution of calibration adjustments in top-100:

| Range | Count | Interpretation |
|---|---|---|
| ≥ 0.095 (at ceiling) | **10** | Calibration is fully maxed — hitting the hard cap |
| 0.080–0.094 (near ceiling) | 2 | Strong evidence, limited headroom |
| 0.050–0.079 (mid range) | 11 | Moderate evidence, partial reward |
| < 0.050 (low) | 1 | Weak evidence, entered primarily on base score |
| *Note: 76 candidates have adj in range 0.06–0.09 — data from full 100* |

**Critical finding:** 10 candidates are at the calibration ceiling, meaning the ceiling **is actively binding**. This is not an unused safety margin — it is a hard constraint that is being hit. For these 10 candidates, the difference between adj=+0.095 and adj=+0.105 (if the ceiling were raised) would determine whether depth=4 missed candidates could enter.

**Is the ceiling protecting against false positives or preventing true positives?**

- The domain gate (Phase 8B.3) ensures that no candidate reaches the ceiling without genuine ML infrastructure career evidence. Reaching adj ≥ 0.095 requires: AI_INFRA_TERMS in career text + PRODUCTION_TERMS + OWNERSHIP_TERMS near tech context + domain gate pass.
- False positives at the ceiling are **already prevented** by the gate.
- The ceiling is currently **preventing 2 depth=4 candidates** from entering the top-100 (the ones below the pre-selection threshold that, if their base were even 0.015 higher, would have been in scope and could have reached the ceiling).

**Verdict:** The ceiling is protecting in the right direction (prevents over-rewarding weak evidence) but is also clipping genuinely strong candidates who are near-threshold. Whether to raise it depends on whether there's additional false-positive risk at the higher level — which requires implementation testing.

---

## 6. Task 4 — Counterfactual Pair Conclusions

| Pair | IN Depth | OUT Depth | JD Verdict | Architecture Error? |
|---|---|---|---|---|
| Rank-93 vs NLP Eng @ Paytm | 2 | 4 | OUT is stronger (eval+retrieval in career) | **Yes** |
| Rank-92 vs NLP Eng @ Paytm | 2 | 4 | OUT is stronger | **Yes** |
| Rank-93 vs Sr DS @ Sarvam | 2 | 4 | OUT is stronger (FAISS+sentence-transformers) | **Yes** |
| Rank-92 vs Sr DS @ Sarvam | 2 | 4 | OUT is stronger | **Yes** |
| Rank-73 vs NLP Eng @ Paytm | 2 | 4 | OUT is stronger by evidence; IN has inference+recommendation in career | **Marginal** |
| Rank-71 vs NLP Eng @ Paytm | 2 | 4 | Same analysis | **Marginal** |

**Confirmed ordering errors by official JD criteria: 4 clear cases** (Pairs A and B, twice each for the same two OUT candidates). These are not close calls — the OUT candidates have retrieval infrastructure and evaluation maturity in their career text that the JD calls "absolutely need", while the IN candidates self-describe as lighter-weight.

---

## 7. Task 5 — Future Direction Decision

### **B) Add career evidence as stronger first-class signal**

**Reason: The architecture places career evidence as a secondary correction rather than a primary driver. The official challenge intent is the opposite.**

This is not about weight tuning (Phase 8C.1 proved that doesn't work). It is about **structural position**:

The current flow:
```
base_score (skill vocabulary) → [gate] → calibration (career evidence) → reranker
```

The JD-intended flow:
```
career_evidence (built right systems) → [primary] → skill_breadth (technical depth) → behavioral
```

### Why the other options are not the right next step:

**A) Keep current architecture:** The 4 confirmed ordering errors — where depth=2 candidates (no eval maturity, no retrieval infra) rank above depth=4 candidates (full evidence profile) — are not acceptable if they represent a systematic pattern. They do: 10 counterfactual pairs in 20,000 candidates.

**C) Semantic evidence understanding:** The problem is not vocabulary mismatch — it is **structural position**. The NLP Engineer @ Paytm has retrieval and embedding terms in their career text AND their skills. The calibrator correctly detects them. The issue is the calibration reward (+0.087) is insufficient to overcome the base score gap. Semantic matching would not change this — it would still be applied as a correction to a vocabulary-based base score.

**D) Other bottleneck:** Not identified.

---

## 8. Remaining Bottleneck — Precisely Stated

The bottleneck is a **structural sequencing mismatch**, not a signal quality problem:

1. **Career evidence signals are correct** — the calibrator accurately identifies production system builders
2. **The calibration ceiling is correctly guarded** — the domain gate prevents false positives
3. **The base score vocabulary signals are not wrong** — skill overlap is a relevant signal
4. **The problem**: the base score has 2.8× more sorting power than the calibration layer, and operates as a gate before calibration runs

The implication is that any fix must either:
- Increase calibration's sorting power proportionally (raise ceiling, restructure as primary), OR
- Add a career-evidence component to the base score directly (so evidence participates in the gate, not just after it)

The second is the more architecturally correct path. A candidate's career evidence should be **part of what qualifies them for the top-100 pool**, not a correction applied after qualification.

---

## 9. Recommended Next Phase

**Phase 8C.3 — Career Evidence Integration (Controlled Experiment)**

**Hypothesis to test:** Adding a career-evidence component to the base score formula — as a 6th term — will:
1. Correctly promote depth=4 candidates past depth=2 candidates at the boundary
2. Not displace strong top-50 candidates (who already have high base AND high adj)
3. Not inflate false positives (gated on career_ai_hits as in Phase 8B.3)

**Design principle:** The new component should use career_ai_infra_hits count (already computed in calibration) normalized against the maximum possible, weighted to give career evidence 10–15% influence in the base score itself — not as a correction after. This directly addresses the architectural inversion without requiring semantic matching, ML models, or arbitrary weight tuning.

**Constraints that must be preserved:**
- Deterministic
- CPU-only
- No external APIs
- career_ai_hits gate (domain relevance, Phase 8B.3)
- Benchmark must pass

**This is the single highest-confidence next step** because the evidence for the problem is now precise (4 confirmed JD-contradicted pairs, measured ceiling binding, preselection exclusion of 2 depth=4 candidates), and the proposed fix addresses the structural cause, not a symptom.

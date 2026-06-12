# Final RedRob Truth Audit — JD Fit, Behavior & Honeypot Validation

**Team:** OctaOps | **Date:** 2026-06-12

> **Scope:** Analysis only. No ranking changes. No code edits. All findings are interpretive labels, not ground truth.

---

## 1. Official JD Intent Extraction

### What RedRob Actually Wants

The JD is a hiring filter for **Senior AI Engineer (Founding Team)** who will own the **intelligence layer**: ranking, retrieval, and candidate-JD matching systems. This is a technical coding role at a small, fast-moving product company.

**First-90-day deliverables (extracted from JD):**
| Week | Expectation |
|---|---|
| 1–3 | Audit existing BM25 + rule-based ranking; identify top 3-4 leverage points |
| 4–8 | Ship v2 ranking with embeddings, hybrid retrieval; demonstrably improve recruiter-engagement metrics |
| 9–12 | Build evaluation infrastructure: offline benchmarks, A/B tests, feedback loops |
| Ongoing | Drive long-term candidate-JD matching architecture; mentor junior engineers |

**Hard requirements (exact from JD "Things you absolutely need"):**
1. Production experience with embeddings-based retrieval (handled embedding drift, index refresh, retrieval-quality regression in production)
2. Production experience with vector databases or hybrid search (Pinecone, Weaviate, Qdrant, Milvus, OpenSearch, Elasticsearch, FAISS, or equivalent)
3. Strong Python, production code quality
4. Hands-on evaluation framework design (NDCG, MRR, MAP, offline-to-online correlation, A/B testing)

**Explicit disqualifiers:**
- Pure research career (no production deployment)
- Recent-only experience: <12 months, primarily LangChain calling OpenAI — rejected *unless* pre-LLM ML production evidence exists
- Senior title but no production code written in 18+ months
- Title-chasing (1.5-year company hops for "Senior→Staff→Principal" progression)
- Entire career at consulting firms (TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini)
- Primarily CV/speech/robotics without significant NLP/IR exposure
- 5+ years entirely on closed-source proprietary systems with no external validation

**JD's explicit trap warning (verbatim):**
> "The right answer is NOT find candidates whose skills section contains the most AI keywords. A Tier 5 candidate may not use 'RAG' or 'Pinecone' in their profile, but if their career history shows they built a recommendation system at a product company, they're a fit."

**Evidence questions (what we should verify in profiles):**

1. Did this person **build AND operate** a ranking/retrieval/recommendation system to real users — or only experiment offline?
2. Can they **measure their system's quality** with quantitative methods (NDCG, A/B test, etc.)?
3. Did they own the system or **disclaim production responsibility** to another team?
4. Are they **accessible** — open to work, reasonable notice period, responsive to recruiter contact?
5. Is the work **domain-relevant** — IR, search, recommendations, matching — or domain-adjacent at best?

---

## 2. Behavioral Signal Usage Validation

### How signals are used in the production pipeline

Per `backend/competition/rank.py`, Stage 2 (reranker) applies:
- `(availability_score + engagement_score) * 0.005` — a **small positive bonus** (max ~+0.010)
- Behavioral signals act as a **light modifier**, not a dominant signal

Per `redrob_signals_doc.docx`:
> "These behavioral signals are often more predictive of whether a candidate can actually be hired than their static profile... ranking systems can incorporate them as a **multiplier or modifier on top of skill-match scoring**."

**Assessment: Correct usage.** The pipeline uses behavioral signals as a modifier, not as a primary rank driver. A strong technical candidate is not punished for lower behavioral scores. A weak technical candidate cannot win purely on behavioral signals.

### Top-100 Behavioral Health (measured)

| Signal | Value |
|---|---|
| Open to work | 70/100 |
| Inactive >180 days | 3/100 |
| Avg recruiter response rate | 64.8% |
| Avg notice period | 62 days |
| Avg GitHub activity score | 59.2 |
| Notice period >60 days | 36/100 |

**Assessment:** The top-100 behavioral profile is healthy. 70% are actively job-seeking. The 3 candidates inactive >180 days are a minor concern — the JD calls this out explicitly. The 36 candidates with notice >60 days are within acceptable range (JD says "30-day preferred but 30+ still in scope, bar gets higher").

---

## 3. Honeypot Detection Methodology

### Strategy

The official spec states ~80 honeypot profiles exist with "subtly impossible profiles" such as:
- 8 years of experience at a company founded 3 years ago
- "Expert" proficiency in 10 skills with 0 years used

**Detection heuristics applied:**
1. **YoE vs career duration gap >6 years** — claimed total experience inconsistent with sum of role durations
2. **Non-technical title with heavy AI skill claims** — e.g., "Marketing Manager" with 7 AI skills
3. **High YoE + empty career history** — no employers listed despite 8+ claimed years
4. **Skills-only profiles** — 25+ skills, <50 characters of career text
5. **Near-perfect JD skill mirror + zero career evidence** — 8/10 exact JD tool names in skills, nothing in career text

### Results

| Tier | Honeypot Candidates |
|---|---|
| Total detected across 100K | 1,581 flagged |
| In Top 10 | **0** |
| In Top 50 | **0** |
| In Top 100 | **1** |

The 1,581 flagged includes our broad heuristic (non-tech title + AI skills) which may catch legitimate career pivots. The official ~80 count is likely the stricter internal ground truth. The important finding is the **ranking did not promote honeypots**.

**The 1 flagged candidate in top-100:** Our heuristics flagged this candidate based on title/skill pattern. This is a borderline case — the non-tech title pattern cast a wide net. No career-timeline impossibility or skills-only profile was found in the top-100. The production pipeline's `calibrate_candidate_evidence()` and career-text evidence scoring naturally deprioritize profiles without career evidence.

**Sample honeypot profiles (excluded from top-100):**
| Candidate | Title | YoE | Flags |
|---|---|---|---|
| CAND_0000220 | Marketing Manager | 10.9y | Title + 7 AI skills |
| CAND_0000312 | Content Writer | 11.5y | Title + 7 AI skills |
| CAND_0000388 | HR Manager | 6.0y | Title + 6 AI skills |
| CAND_0000498 | Content Writer | 10.7y | Title + 5 AI skills |
| CAND_0000505 | Accountant | 9.2y | Title + 6 AI skills |

**Conclusion:** Honeypot resistance is **strong**. The career-evidence scoring approach naturally avoids these profiles because they have no career text supporting their AI skill claims.

---

## 4. Top-10 Quality Audit

All 10 candidates verified against actual profile data from the JSONL dataset.

### Summary table

| Rank | Candidate | Title / Company | YoE | Career JD hits | Production Evidence | Disclaimer | Open | Notice | Response |
|---|---|---|---|---|---|---|---|---|---|
| 1 | CAND_0002025 | Senior AI Engineer @ Apple | 5.9y | 4/19 | ✅ | — | ✅ | 30d | 80% |
| 2 | CAND_0077337 | Staff MLE @ Paytm | 7.0y | 9/19 | ✅ | — | ✅ | 60d | 95% |
| 3 | CAND_0041669 | Recommendation Sys Eng @ CRED | 8.0y | 7/19 | ✅ | — | ✅ | 60d | 77% |
| 4 | CAND_0081846 | Lead AI Engineer @ Razorpay | 6.7y | 10/19 | ✅ | — | ✅ | 30d | 73% |
| 5 | CAND_0010257 | Senior Data Scientist @ Google | 6.5y | 4/19 | ✅ | — | ✅ | 120d | 72% |
| 6 | CAND_0033861 | Senior NLP Engineer @ Mad Street Den | 8.0y | 9/19 | ✅ | — | ❌ | 30d | 16% |
| 7 | CAND_0008425 | Senior NLP Engineer @ Ola | 7.8y | 10/19 | ✅ | — | ✅ | 90d | 66% |
| 8 | CAND_0051630 | MLE @ Razorpay | 6.0y | 6/19 | ❌* | — | ❌ | 90d | 51% |
| 9 | CAND_0079387 | AI Engineer @ Microsoft | 6.9y | 11/19 | ✅ | — | ✅ | 30d | 81% |
| 10 | CAND_0020877 | Applied ML Engineer @ CRED | 5.1y | 8/19 | ❌* | — | ❌ | 60d | 66% |

*Note: "No production evidence" here reflects our strict heuristic (ownership verb + production context in career text). These candidates do have technical career snippets; the heuristic may be missing evidence expressed differently.

### Individual assessments

**Rank 1 — CAND_0002025 (Apple, Senior AI Engineer, 5.9y)**
Career text: "Built and shipped a production recommendation system at a marketplace product, going from offline experimentation to live A/B test in 5 months. Combined collaborative filtering (matrix factorization)..."
- ✅ Exactly what JD needs: marketplace, recommendation, A/B test, production ship
- ✅ Open, 30d notice, 80% response rate — highly reachable
- ✅ GitHub: 96.9 — active coder
- ⚠️ 4/19 career JD term hits (low count) but the career evidence is high-quality
- **Verdict: Strong #1 pick. Apple, 5.9y, shipped recommendation system to production with measurable A/B evaluation.**

**Rank 2 — CAND_0077337 (Paytm, Staff MLE, 7.0y)**
Career text evidence: 9/19 JD career hits, production evidence confirmed, 95% response rate.
- ✅ Staff-level at Paytm (major Indian fintech) — product company
- ✅ 95% recruiter response rate — highest in top-10; most likely to actually be hired
- ⚠️ 60d notice — manageable
- **Verdict: Excellent #2. High technical signal + strongest availability/engagement in top-10.**

**Rank 3 — CAND_0041669 (CRED, Recommendation Systems Engineer, 8.0y)**
Career text: "Owned the ranking layer for an e-commerce search product, evolving from hand-tuned scoring to a learning-to-rank model over 9 months. Designed the relevance labeling pipeline..."
- ✅ Title literally "Recommendation Systems Engineer" — perfect domain fit
- ✅ Learning-to-rank, relevance labeling = evaluation maturity
- ✅ 8y YoE, open, 77% response
- **Verdict: Excellent #3. Deep LTR experience with evaluation rigor.**

**Rank 4 — CAND_0081846 (Razorpay, Lead AI Engineer, 6.7y)**
Career text: "Built a RAG-based ranking pipeline serving 50M+ queries/month for an internal recruiter-facing search product. Architecture combined BM25 + dense retrieval (BGE embeddings, FAISS HNSW)..."
- ✅ **Highest career JD hits in top-5 (10/19)** — explicit FAISS, BM25, hybrid retrieval
- ✅ 50M+ queries/month = meaningful production scale
- ✅ Razorpay = product company; 30d notice; 73% response
- ✅ Built retrieval infrastructure *for a recruiter-facing product* — directly analogous to JD
- **Verdict: Strong #4. Could arguably be higher. The recruiter-search context is a near-perfect analogue.**

**Rank 5 — CAND_0010257 (Google, Senior Data Scientist, 6.5y)**
Career text: "Built and operated production ML pipelines using MLflow, Kubeflow, and internal feature store. Main project was churn prediction..."
- ⚠️ Career text talks about MLOps and churn prediction — not ranking or retrieval
- ⚠️ Only 4/19 career JD hits; skills show Milvus/OpenSearch/Qdrant but career doesn't
- ⚠️ 120d notice — JD explicitly says "bar gets higher" for 30d+ candidates
- 🔴 **This is a surface-match concern.** Skills section says "vector DB" but career evidence is churn modeling + ML pipelines, not retrieval/ranking
- **Verdict: Possible false positive at #5. Career evidence doesn't match skill claims for this specific JD. The 120d notice further reduces hiring probability.**

**Rank 6 — CAND_0033861 (Mad Street Den, Senior NLP Engineer, 8.0y)**
Career text: "Fine-tuned Llama-2-7b and Mistral-7b using LoRA/QLoRA for domain-specific candidate-JD matching. Built the data curation pipeline with 200k preference pairs..."
- ✅ Candidate-JD matching — directly relevant to RedRob's product
- ✅ LoRA/QLoRA fine-tuning = preferred signal in JD
- ❌ Not open to work; 16% recruiter response rate — this is a critical behavioral flag
- ⚠️ 16% response = the JD's explicit warning about "perfect-on-paper candidate not actually available"
- **Verdict: Strong technical fit, but the 16% response rate is a significant availability risk. The behavioral signal is appropriately weighted here — should the ranking system penalize this more? Current system applies only a small malus. This may be a systematic underweighting of severe engagement failure.**

**Rank 7 — CAND_0008425 (Ola, Senior NLP Engineer, 7.8y)**
Career text: "Owned the design and rollout of a large-scale semantic search system serving an internal corpus of 35M+ items. Migrated from BM25-only to hybrid setup combining sparse and dense vectors..."
- ✅ Semantic search at scale (35M+ items), BM25 → hybrid migration — exactly what the JD needs for week 1-8
- ✅ Open to work, 66% response
- ⚠️ 90d notice — border case
- **Verdict: Solid #7. Strong retrieval ownership signal.**

**Rank 8 — CAND_0051630 (Razorpay, MLE, 6.0y)**
Career text: "Owned the ranking layer for an e-commerce search product, evolving from hand-tuned to LTR over 9 months..."
- ⚠️ Not open to work; 90d notice; no production evidence detected by heuristic
- ✅ Technical career text overlaps well with ranking requirements
- **Verdict: Borderline #8. Strong technical profile but availability concern (not open + 90d notice) is real. The JD says bar gets higher.**

**Rank 9 — CAND_0079387 (Microsoft, AI Engineer, 6.9y)**
Career text: "Built a content recommendation system serving 10M+ users that combined collaborative filtering with content-based ranking. System uses sentence-transformer embeddings..."
- ✅ 10M+ users recommendation system — meaningful scale
- ✅ Sentence-transformers explicitly mentioned
- ✅ Open to work; 30d notice; 81% response — most accessible profile in top-10
- ✅ Highest career JD hits in top-10 (11/19)
- **Verdict: Strong #9. Should possibly be ranked higher based on raw evidence quality + accessibility. The 30d notice and 81% response make this the most hire-ready candidate outside the top-4.**

**Rank 10 — CAND_0020877 (CRED, Applied ML Engineer, 5.1y)**
Career text: "Developed a semantic search feature for an internal knowledge base of ~500k docs. Used sentence-transformers (all-MiniLM initially, later BGE-base) with FAISS for nearest-neighbor..."
- ✅ Sentence-transformers, FAISS, semantic search — technical fit
- ⚠️ "Developed" for internal knowledge base — smaller scale than typical rank-1 candidates
- ⚠️ Not open to work; no production ownership verb detected
- **Verdict: Acceptable #10 but weaker than ranks 1-9. Internal knowledge base project is somewhat limited in scale vs. "50M+ queries" at rank 4.**

---

## 5. Top-50 Quality Assessment

**Pattern observed:** Ranks 11–50 follow the same profile pattern as top-10: product companies, career text with retrieval/recommendation vocabulary, 5-8y YoE range. No honeypots detected.

**Availability distribution (top-50):**
- ~68% open to work
- Avg notice ~55d
- Avg response rate ~60%

**Key risk in 11-50:** Some candidates with strong behavioral scores but weaker career evidence likely appear because the behavioral bonus (max ~+0.010) can offset minor technical score differences. This is working as intended per the signals doc.

---

## 6. Top-100 Quality Assessment

### False positive scan results

| Risk Category | Count |
|---|---|
| "No production evidence" detected | 28/100 |
| Availability concern | 11/100 |
| Engagement concern | 6/100 |
| Has disclaimer phrase | 3/100 |
| Framework-only signal | 2/100 |
| Candidates with 3+ risk flags | 0/100 |

**Important caveat:** "No production evidence" in our heuristic means the career text doesn't contain both an ownership verb AND a production context word. This can be a false alarm if the candidate expresses ownership through other phrasing. No candidate scored 3+ risk flags simultaneously, which is a good sign.

**Tail-100 audit (ranks 80-100):**

| Rank | Candidate | Career Signal Strength | Concern |
|---|---|---|---|
| 80 | CAND_0007411 (Amazon, Sr MLE) | domain=4, eval=3, prod=2 | None — strong tail |
| 82 | CAND_0030827 (Freshworks, Sr DS) | domain=4, eval=0, prod=0 | No evaluation maturity; minimal production signal |
| 85 | CAND_0093912 (Razorpay, Sr DS) | domain=4, eval=0, prod=0 | Same pattern |
| 90 | CAND_0081321 (Freshworks, Sr SWE ML) | domain=3, eval=1, prod=1 | Career snippet: computer vision (image moderation) — **domain mismatch** |
| 94 | CAND_0032807 (CRED, MLE) | domain=0, eval=1, prod=0 | RAG chatbot only; no ranking/retrieval career evidence |
| 96 | CAND_0084819 (Dream11, Search Eng) | domain=3, eval=1, prod=0 | RAG chatbot career text despite "Search Engineer" title |
| 97 | CAND_0068081 (Glance, CV Eng) | domain=3, eval=0, prod=1 | Title: Computer Vision Engineer; career: time-series forecasting |
| 98 | CAND_0068351 (Sarvam AI, Lead AI) | domain=4, eval=2, prod=2 | Strong — no concern |

**Systematic pattern identified in tail-100:**
Several candidates (ranks 82-96) have titles or skills suggesting search/retrieval but career text describing either (a) LTR/ranking layer ownership without evidence of deployment to users, or (b) unrelated ML work (CV, time-series). These represent a soft boundary where the base score picks them up on skill/term overlap but career evidence is weaker.

---

## 7. False Positive Patterns

### Pattern 1 — Skill-career mismatch (surface match)
**Example:** Rank 5, CAND_0010257 (Google DS). Skills list includes vector DBs; career text describes churn prediction and MLOps pipelines. The base score rewards the skill overlap; career evidence scoring catches some of this but not all.
**Scale:** ~8-12 candidates in top-100 appear to fit this pattern.

### Pattern 2 — RAG chatbot without retrieval system ownership
**Example:** Ranks 94-96. "Search Engineer" or "AI Engineer" titles with career text describing RAG-based customer support chatbots. These are infrastructure consumers, not infrastructure builders.
**JD explicitly warns:** "People who use [hot framework] to build [demo]" — we need system thinkers.
**Scale:** ~5-8 candidates in the 85-100 range.

### Pattern 3 — Computer Vision/ML engineers miscategorized
**Example:** Rank 90, Rank 97. Career text clearly describes CV model work (image moderation) or time-series forecasting — not retrieval/ranking. These are caught by the tail of the scoring distribution.
**Scale:** ~3-5 candidates.

### Pattern 4 — Severe behavioral disqualifier not strongly penalized
**Example:** Rank 6, CAND_0033861 (16% recruiter response rate, not open to work). The JD explicitly says: "A perfect-on-paper candidate who hasn't logged in for 6 months and has a 5% recruiter response rate is, for hiring purposes, not actually available." A 16% response rate may warrant stronger down-weighting than the current +/-0.005 scale behavioral adjustment.
**This is not a ranking code change recommendation** — it's a documented risk to hiring outcome at Stage 4 review.

---

## 8. False Negative Search — Hidden Gems

### Search result

Strong candidates NOT in top-100 were identified using a 4-dimensional evidence score (domain vocabulary + evaluation maturity + production context + ownership verbs in career text).

**Finding: 0 candidates scored ≥4 in all four dimensions while being outside top-100.** The broader pass found candidates with 3-dimension matches, but those candidates had critical weaknesses (CV focus, forecasting only, no evaluation maturity).

The hidden gems found (Computer Vision engineers at Meesho, InMobi, etc.) have their "domain" hits from generic mentions of "recommendation" or "matching" inside broader ML careers — their primary work was image classification and fraud detection. These are correctly excluded.

**Interpretation:**
The ranking appears to have **good recall on legitimate non-buzzword candidates**. The career evidence scoring (AI infra terms in career text, capped at 5 hits) is catching candidates who built real systems without using the latest trendy vocabulary. No genuine hidden gem — "built recommendation system at product company, no RAG/Pinecone in profile" — was found outside top-100 that clearly outperforms a top-100 candidate.

**Classification: A) Current ranking selected stronger people** — the gem search found no clearly stronger candidates being missed.

---

## 9. Remaining Ranking Risks

### Risk 1 — Behavioral penalization ceiling (LOW severity)
The behavioral bonus/malus is capped at ~±0.010. A candidate with 16% recruiter response rate (Rank 6) gets nearly the same treatment as one at 65%. For hiring probability purposes, 16% is functionally unavailable. The risk is that a Stage 4 reviewer downgrades OctaOps' submission because rank-6 is visibly a bad hire-probability candidate despite strong technical fit.
**This is not fixable without changing algorithm — documented for interview awareness.**

### Risk 2 — Skill-career mismatch at surface boundary (LOW severity)
Approximately 8-12 candidates in the top-100 have strong skill sections but career evidence pointing to adjacent (not directly relevant) work. The career evidence scoring reduces their scores but doesn't eliminate them. They cluster in ranks 75-100, which is the correct location for candidates with "adjacent" fit.
**Acceptable** — the JD says "relevant" at rank-100 is appropriate for "adjacent only" candidates.

### Risk 3 — 120-day notice period at Rank 5 (LOW severity)
CAND_0010257 (Google, Rank 5) has a 120-day notice period. The JD says "30+ day notice — bar gets higher." This candidate's technical profile may not warrant rank 5 given this availability constraint plus the career-evidence concern (churn prediction, not retrieval).
**Not fixable — ranking frozen. Flag for Stage 4 reasoning awareness.**

### Risk 4 — Honeypot rate in top-100 = 1 (PASS)
Official threshold: <10% honeypot rate in top-100 required to advance to Stage 3. Our count: 1/100 = 1% (and even this is based on a broad title/skill heuristic, not confirmed honeypot). Well within safe range.

---

## 10. Final Decision

### A) Ranking aligns with official JD intent

**Evidence:**

1. **Top-4 are genuinely strong matches.** Ranks 1-4 all show: built-and-shipped retrieval/recommendation systems to real users, at product companies (Apple, Paytm, CRED, Razorpay), with quantitative evaluation methods (A/B tests, LTR metrics, relevance labeling). These are exactly what the JD describes as the "ideal candidate" — 6-8 years total, 4-5 in applied ML at product companies, shipped a ranking/recommendation system to real users.

2. **Zero honeypots in top-10, 1 borderline in top-100 (1%).** The official Stage 3 threshold is ≤10%. The career-evidence scoring inherently deprioritizes profiles whose AI skills appear only in the skills section with no career text support.

3. **Top-100 behavioral health is strong.** 70% open to work, 64.8% avg response rate, 3/100 inactive >180 days. The signals doc called out these exact metrics as important, and the distribution is healthy.

4. **Tail-100 correctly contains adjacent candidates.** Ranks 80-100 have domain vocabulary (recommendation, search, ranking) but weaker evaluation maturity and production scale signals. This matches the JD's implied "Tier 2-3" adjacency — correct placement in the long tail.

5. **No hidden gems found.** The false-negative search across all 100K non-top-100 candidates found no profile that clearly outperforms a top-100 candidate on the JD's actual requirements (domain expertise + production evidence + evaluation maturity + behavioral availability).

**One documented alignment concern (informational, not disqualifying):**
- Rank 5 (CAND_0010257, Google) — skill section matches strongly, but career text describes churn prediction and MLOps rather than ranking/retrieval. The 120-day notice compounds the concern. This is the ranking's clearest surface-match false positive. It sits at #5, not #1, which shows the career-evidence weighting is working but not perfectly.
- Rank 6 (CAND_0033861, Mad Street Den) — 16% recruiter response rate makes this candidate functionally hard-to-reach despite strong technical fit. The behavioral adjustment correctly applies a penalty, but the signal might warrant stronger treatment at this extreme.

**These are edge cases, not systematic failures.** The overall alignment verdict is positive.

---

*Analysis completed 2026-06-12. All findings based on reading `data/candidates.jsonl` and `data/job_description.docx` directly. No ranking changes made. Algorithm remains frozen.*

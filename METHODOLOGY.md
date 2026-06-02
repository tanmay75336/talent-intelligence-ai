# Methodology — RedRob Track 1 (Intelligent Candidate Discovery)

This document is written for RedRob judges evaluating **Stages 4–5**: manual methodology review, reasoning quality, and technical defense. It describes the **frozen** offline pipeline in `backend/competition/` without re-tuning.

## 1. Problem understanding

The challenge is not “find candidates who mention the most AI terms.” The goal is to **understand candidate evidence** in context of a specific job description: what they built, in what environment, with what depth, and whether that evidence is credible.

**Example:** A candidate who built production recommendation, search, or ranking systems with embeddings and evaluation discipline should rank above someone who only lists RAG, LLM, or LangChain on their skills inventory without matching career history.

The released JD emphasizes product engineering over research-only profiles, hands-on ownership, and AI infrastructure depth (retrieval, ranking, embeddings, production ML). The ranker is aligned to that intent.

## 2. Ranking philosophy

**Priority: career evidence > skill keywords.**

| Signal class | Examples |
|--------------|----------|
| **Strong positive** | Retrieval systems, ranking/recommendation systems, embeddings, vector search, semantic search, production ML, backend/platform ownership, A/B evaluation maturity |
| **Weaker / risky** | Framework names (LangChain, OpenAI) or generic “AI/ML/NLP” labels without career backing |
| **Secondary** | RedRob behavioral signals (availability, response rate, GitHub activity) — used as small tie-breakers when technical evidence is already comparable |

Base scoring (`backend/competition/rank.py`) combines JD skill overlap, skill-group overlap, important term overlap, experience-band fit, and competition core signals from `backend/intelligence/candidate_engine.py`. Evidence calibration (`backend/competition/evidence_calibrator.py`) applies a **bounded** adjustment (±0.10 max) on top of that base score.

## 3. Candidate evidence extraction

Each `candidates.jsonl` record is adapted into a unified `CandidateProfile` (`backend/competition/redrob_adapter.py`). Evidence is drawn from:

- **profile** — headline, summary, title, company, years of experience
- **career_history** — role descriptions (primary source for “what they actually did”)
- **skills** — names, proficiency, endorsements, duration months
- **education** — degrees, institutions, tiers
- **certifications** — named credentials
- **redrob_signals** — 23 behavioral/platform fields (see `data/redrob_signals_doc.docx`)

`build_candidate_intelligence()` builds structured signals and an evidence library (experience/summary snippets) used for reasoning text, not for hosted LLM generation.

## 4. Trap handling

The dataset includes intentional traps (keyword stuffers, framework-only profiles, behavioral twins, honeypots with inconsistent timelines). The calibrator applies **explicit penalties** when patterns match; this is **heuristic**, not perfect detection.

| Trap pattern | Detection idea | Effect |
|--------------|----------------|--------|
| **Keyword stuffing** | Many AI-tagged skills with low duration/endorsements and no career AI-infra hits | Penalty flag `keyword_stuffing` |
| **Framework-only AI profile** | LangChain/OpenAI/LLM-heavy skills/summary without career retrieval/ranking/production evidence | `framework_only_ai_profile` |
| **Research-only mismatch** | Research language without production/ownership hits | `research_only_mismatch` |
| **Fake / hands-off seniority** | Very high years + management language, weak ownership verbs | `hands_off_senior` |
| **Impossible / honeypot profiles** | Timeline inconsistencies (e.g., tenure vs company age) | Not special-cased by ID; avoided by reading structured fields and penalizing weak evidence. Organizers note honeypot rate >10% in top-100 is a Stage 3 disqualifier. |

We do **not** claim perfect trap or honeypot detection. The design favors **career-text grounding** so keyword-only profiles naturally score lower.

## 5. RedRob behavioral signals

Behavioral signals are **secondary modifiers**, applied mainly as a small tie-breaker when technical evidence is already present (`_behavioral_tie_breaker` in `evidence_calibrator.py`).

Signals considered in reasoning text (when notable):

- `open_to_work_flag`
- `recruiter_response_rate` (high values surfaced in reasoning)
- `github_activity_score`
- Relocation / work-mode / notice period (available in schema; surfaced when relevant to close calls)

**Important:** Behavioral signals do **not** override much stronger JD technical evidence. A highly available candidate with weak career AI-infra evidence should not outrank a strong builder.

## 6. NDCG optimization strategy

Official composite (see `data/submission_spec.docx`):

- **NDCG@10 (50%)** — top of list matters most
- **NDCG@50 (30%)** — depth of strong ordering
- **MAP (15%)** — precision across relevance tiers
- **P@10 (5%)** — fraction of top-10 that are truly relevant

**Optimization focus:**

| Metric | Strategy |
|--------|----------|
| **NDCG@10** | Heap-retained top 100 after scoring; calibration boosts career-backed retrieval/ranking excellence; traps penalized before final ordering |
| **NDCG@50** | Same score function across the heap cutoff; monotonic scores with deterministic tie-break on `candidate_id` |
| **MAP** | Prefer candidates with verifiable production + ownership language over keyword-only skill overlap |
| **P@10** | Avoid promoting framework-only and keyword-stuffed profiles even if skill overlap is high |

## 7. Reasoning generation (Stage 4 compliance)

Reasoning is generated **deterministically** in `backend/competition/rank.py` (`_competition_reasoning`). For each top-100 candidate:

1. **Actual candidate facts** — years of experience, current title, current company (from structured profile)
2. **JD connection** — career-backed AI-infra terms when calibration found them; otherwise explicit skill overlap wording
3. **Evidence** — best career sentence or evidence snippet (truncated), not invented employers or skills
4. **Strengths / limitations** — RedRob signal clause when notable; weak profiles get weaker JD-connection phrasing rather than generic praise

**No hosted LLM generates reasoning during ranking.** `ENABLE_GROQ_SYNTHESIS=0` and offline transformers flags are set in `configure_offline_environment()`.

Stage 4 checks (specific facts, JD connection, honesty, no hallucination, variation, rank consistency) are design goals of the template; sampled rows should be reviewed against `candidates.jsonl` source records.

## 8. Efficiency

Designed for **100,000 candidates on CPU in under 5 minutes**:

- **Streaming JSONL** — `iter_dataset_records()` reads one candidate at a time
- **CPU-only execution** — no GPU; no network calls in ranking
- **Top-100 min-heap** — retain only the best 100 candidates by score; skip clear non-contenders when heap is full
- **Deferred expensive work** — full `build_candidate_intelligence()` for evidence/reasoning runs only on heap survivors, not every row
- **No external APIs** — ranking does not call OpenAI, Anthropic, or other hosted services

Reference benchmark: **~82 seconds** for 100,000 candidates on the packaged reference environment (see `README.md`).

## 9. Reproducibility checklist (Stage 3)

1. Place `data/candidates.jsonl` (or `.gz`) and `data/job_description.docx`
2. Run the single reproduction command in `README.md`
3. Run `python -m backend.competition.validate_submission submission.csv`
4. Optional: `python -m backend.competition.benchmark` for runtime/memory report

## 10. What this document does not cover

- The optional **recruiter web app** (`frontend/`, `backend/main.py`) uses hybrid retrieval and a separate ranking path for demos; it is **not** the competition submission path.
- **AI tools** (Cursor, ChatGPT, etc.) may be used during development; they are **not** invoked during the official ranking step.

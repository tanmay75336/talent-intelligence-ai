# Talent Intelligence AI — RedRob Track 1

**OctaOps** | Intelligent Candidate Discovery & Ranking Challenge

---

## What this system does

We built an offline candidate ranking system that scores 100,000 RedRob profiles against a specific job description and returns the top 100, ranked best-to-worst, with a plain-language explanation for each.

The main trade-off we focused on was **career evidence over keyword matching.** We wanted candidates with demonstrated production retrieval and ranking experience to score above profiles that only mention popular AI tools without deeper evidence.

## How to reproduce the submission

Place the official data files under `data/`:

```
data/candidates.jsonl       # (or candidates.jsonl.gz)
data/job_description.docx
```
## Dependency installation

```bash
pip install -r backend/requirements.txt
```

The ranking pipeline uses the dependencies listed in `backend/requirements.txt`.

Run the ranker from the repository root:

```bash
python -m backend.competition.rank --candidates data/candidates.jsonl --job data/job_description.docx --output OctaOps.csv
```

**Example terminal output:**

```
[rank] Reading job description: data/job_description.docx
[rank] JD parsed — <detected> core skills, <detected> term signals
[rank] Stage 1 — base scoring + evidence calibration (streaming candidates)
[rank] Dynamic Stage 2 candidate recall pool: 1000 (from 100000 candidates)
[rank]   ...  10,000 candidates scored  |  pool: 1000  |  elapsed time
[rank]   ...  20,000 candidates scored  |  pool: 1000  |  elapsed time
...
[rank]   ... 100,000 candidates scored  |  pool: 1000  |  elapsed time
[rank] Stage 1 complete — 100,000 candidates scored
[rank]   Shortlist pool: 1000 candidates (highest calibrated scores)
[rank] Reloading 1000 pool profiles for reranking...
[rank] Stage 2 — reranking 1000 candidates (evidence depth + behavioral signals)
[rank] Stage 2 complete — 1000 candidates reranked  →  top 100 selected
[rank] Stage 3 — generating reasoning for 100 candidates
[rank] Stage 3 complete — reasoning generated
[rank] Writing submission: /Users/username/talent-intelligence-ai/OctaOps.csv
[rank] Validation PASS
[rank] ──────────────────────────────────────────
[rank]  Candidates processed : 100,000
[rank]  Ranked candidates    : 100
[rank]  Output CSV           : /Users/username/talent-intelligence-ai/OctaOps.csv
[rank]  Total runtime        : machine-dependent
[rank] ──────────────────────────────────────────
```

Progress prints every 10,000 candidates during Stage 1. Actual timing varies by CPU and execution environment. Tested runs complete within the competition's 300-second CPU-only limit.

Validate the output:

```bash
python -m backend.competition.validate_submission OctaOps.csv
# Expected: Submission is valid.
```

The ranked CSV is also committed as `OctaOps.csv` at the root.

---

## Hosted Sandbox Demo

Google Colab sandbox:
https://colab.research.google.com/drive/12h8SmdQUZcTO4LkyQdWoHNU0DGOsgciX?usp=sharing

We use the sandbox as a quick reproducibility check with a small candidate sample.

It demonstrates:

- CPU-only execution
- No hosted LLM or external API calls during ranking
- Same ranking pipeline used for the final submission
- Ranked CSV generation from sample candidates (≤100 candidates)

The full 100,000-candidate reproduction is performed from this repository using the command documented above. The sandbox is meant only as a lightweight verification environment.

---

## Architecture

Our pipeline runs in three sequential stages inside `backend/competition/rank.py`:

```
candidates.jsonl(.gz)
        |
Streaming loader              (dataset_intelligence/loader.py)
        |
Profile normalisation         (competition/redrob_adapter.py)
        |
Signal extraction             (intelligence/candidate_engine.py)
        |
Base scoring                  (competition/rank.py)
  — 6-term weighted formula
  — Career evidence term from history text
  — Production disclaimer detection
  — Evidence calibration ±0.10
  — Dynamic Stage 2 candidate recall pool (scales candidate recall before reranking)
        |
Reranking                     (competition/rank.py)
  — Headroom-scaled evidence depth bonus
  — Behavioral availability/engagement bonus
  — Surface-match penalty
  — Trap flag penalty
  — Top 100 selected
        |
Reasoning generation          (competition/reasoning_generator.py)
  — Deterministic natural prose from candidate facts
  — No hosted LLM
        |
OctaOps.csv
```

Stage 2 candidate recall uses a dynamic pool size. Small datasets pass all available candidates forward, medium datasets preserve the stable minimum recall window, and large datasets expand the candidate pool proportionally before applying the same evidence reranker. This changes only how many candidates reach reranking; scoring, evidence extraction, behavioral signals, and final CSV rules remain unchanged.

## Scoring design

We use a weighted combination of six signals:

| Signal | Weight | Source |
|--------|--------|--------|
| JD skill overlap | 0.26 | Candidate skills vs JD core skills |
| Skill-group overlap | 0.16 | Skill taxonomy groups (broader categories) |
| Important-term overlap | 0.18 | Domain keywords from JD and profile |
| Experience-band fit | 0.12 | Penalty outside the 5–9y target band |
| Execution signals | 0.20 | Depth, domain relevance, startup readiness |
| Career evidence | 0.08 | AI infrastructure terms in career history text |

Evidence calibration adds a bounded ±0.10 adjustment based on production ownership language, retrieval system indicators, and trap patterns found in career text.

**Production disclaimer detection:** The JD explicitly disqualifies candidates who have not personally operated production systems. We detect phrases like "production deployment was handled by the platform team" and apply a 0.5× multiplier to the career evidence signal for those candidates — not a hard exclusion, but a meaningful penalty.

## Reasoning generation

Each of the top-100 candidates receives a 1–2 sentence explanation drawn from:
- Their actual years of experience, title, and employer (no invented facts)
- The specific retrieval/vector/evaluation terms found in their career history
- Relevant RedRob behavioral signals (availability, notice period, GitHub score) when notable

The tone scales with rank confidence: candidates in the top 30 receive confident, specific explanations; candidates near rank 100 receive honest boundary-acknowledgment language.

## Trap handling

The dataset includes profiles where surface-level matches may not represent real role fit. Our calibrator applies pattern-based adjustments for:

| Pattern | Detection |
|---------|-----------|
| Keyword stuffing | AI skill tags with low duration/endorsements and no career AI infrastructure hits |
| Framework-only profiles | LangChain/OpenAI labels without career retrieval/ranking/production evidence |
| Research-only profiles | Research vocabulary without production ownership language |
| Hands-off seniority | Long tenure + management language, no ownership verbs |

We do not hard-code candidate IDs. The checks are based on profile patterns, so the same logic applies across candidates.

## Behavioral signals

We use behavioral signals as **secondary modifiers only**. They do not override strong JD-evidence matches.

Signals used:
- `open_to_work_flag` — availability
- `recruiter_response_rate` — hiring reachability
- `github_activity_score` — engineering signal
- `notice_period_days` — practical consideration
- `willing_to_relocate` — logistics

A strong technical match with weaker engagement signals receives a small adjustment but is not removed from consideration.

## Compute constraints

| Constraint | Limit | Our result |
|------------|-------|------------|
| Runtime | ≤ 300s | Verified under limit on tested CPU environments |
| RAM | ≤ 16 GB | Well within (streaming, no full-pool load) |
| GPU | Not permitted | CPU only |
| Network during ranking | Not permitted | None — `configure_offline_environment()` enforces this |


## Benchmark

```bash
python -m backend.competition.benchmark --candidates data/candidates.jsonl --job data/job_description.docx
```

Outputs: runtime, peak memory, and validation status.

## Tests

```bash
python -m unittest backend.test_redrob_competition
```

Uses `data/sample_candidates.json` when present.

## Repository layout

| Path | Purpose |
|------|---------|
| `backend/competition/rank.py` | **Entry point** — full ranking pipeline |
| `backend/competition/evidence_calibrator.py` | Evidence calibration ±0.10 |
| `backend/competition/redrob_adapter.py` | JSONL → CandidateProfile normalisation |
| `backend/competition/reasoning_generator.py` | Deterministic prose reasoning |
| `backend/competition/evaluate.py` | Career and behavioral signal extraction |
| `backend/competition/validate_submission.py` | Format validator |
| `backend/competition/benchmark.py` | Runtime/memory benchmark |
| `backend/intelligence/` | Core execution signal extraction |
| `backend/models/` | Shared data models (`CandidateProfile`, etc.) |
| `backend/parsers/jd_analyzer.py` | JD skill and term extraction |
| `backend/dataset_intelligence/loader.py` | Streaming JSONL/gz loader |
| `backend/reasoning/evidence_quality.py` | Evidence quality scoring (used by signal extraction) |
| `backend/utils/skill_taxonomy.py` | Skill normalisation and domain keywords |
| `backend/test_redrob_competition.py` | Competition pipeline unit tests |
| `research/experiments/` | Development experiment scripts (not used by competition pipeline) |
| `research/` | Phase reports and audit trail |
| `archive/prototype/` | Archived experiments (not used by competition pipeline) |
| `sandbox/` | Colab sandbox instructions |

## Further reading

- `METHODOLOGY.md` — design rationale, trap handling, scoring decisions
- `sandbox/README.md` — Colab sandbox setup instructions
- `research/experiments/README.md` — what each experiment explored
- `research/` — full phase audit trail

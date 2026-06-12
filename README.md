# Talent Intelligence AI — RedRob Track 1

**OctaOps** | Intelligent Candidate Discovery & Ranking Challenge

---

## What this system does

We built an offline candidate ranking system that scores 100,000 RedRob profiles against a specific job description and returns the top 100, ranked best-to-worst, with a plain-language explanation for each.

The core design decision: **career evidence over keyword matching.** A candidate who built production retrieval and ranking systems should rank above someone who merely lists vector database names on their skills page. Our scoring reflects that.

## How to reproduce the submission

Place the official data files under `data/`:

```
data/candidates.jsonl       # (or candidates.jsonl.gz)
data/job_description.docx
```

Run the ranker from the repository root:

```bash
python -m backend.competition.rank \
  --candidates data/candidates.jsonl \
  --job data/job_description.docx \
  --output submission.csv
```

Validate the output:

```bash
python -m backend.competition.validate_submission submission.csv
# Expected: Submission is valid.
```

The ranked CSV is also committed as `submission.csv` at the root.

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
  — Top-300 min-heap across 100K candidates
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
submission.csv
```

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

The dataset includes honeypot and trap profiles. Our calibrator applies explicit penalties for:

| Pattern | Detection |
|---------|-----------|
| Keyword stuffing | AI skill tags with low duration/endorsements and no career AI infrastructure hits |
| Framework-only profiles | LangChain/OpenAI labels without career retrieval/ranking/production evidence |
| Research-only profiles | Research vocabulary without production ownership language |
| Hands-off seniority | Long tenure + management language, no ownership verbs |

We do not hard-code candidate IDs. Detection is text-pattern based, so it generalises.

## Behavioral signals

We use the 23 RedRob behavioral signals as **secondary modifiers only**. They do not override strong JD-evidence matches.

Signals used:
- `open_to_work_flag` — availability
- `recruiter_response_rate` — hiring reachability
- `github_activity_score` — engineering signal
- `notice_period_days` — practical consideration
- `willing_to_relocate` — logistics

A strong builder who hasn't engaged recently is slightly depressed but not disqualified.

## Compute constraints

| Constraint | Limit | Our result |
|------------|-------|------------|
| Runtime | ≤ 300s | **~174s** |
| RAM | ≤ 16 GB | Well within (streaming, no full-pool load) |
| GPU | Not permitted | CPU only |
| Network during ranking | Not permitted | None — `configure_offline_environment()` enforces this |

## Dependency installation

```bash
pip install -r backend/requirements.txt
```

The competition pipeline requires only three packages: `pandas`, `numpy`, `pydantic`.

## Benchmark

```bash
python -m backend.competition.benchmark \
  --candidates data/candidates.jsonl \
  --job data/job_description.docx
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
| `experiments/` | Development experiment scripts (not in production path) |
| `research/` | Phase reports and audit trail |
| `archive/prototype/` | Early recruiter app prototype (separate system, kept for history) |
| `sandbox/` | Colab sandbox instructions |
| `docs/` | System technical report and release documentation |

## Further reading

- `METHODOLOGY.md` — design rationale, trap handling, scoring decisions
- `sandbox/README.md` — Colab sandbox setup for Stage 1 link
- `experiments/README.md` — what each experiment explored
- `research/` — full phase audit trail

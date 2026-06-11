# Talent Intelligence AI — Ranking System History

Purpose:

This document records stable checkpoints, ranking architecture decisions,
and rollback points.

Source of truth:
- Git commits
- Git tags
- Official challenge documents
- Phase reports in research/

---

# Stable Checkpoints

## phase7-stable-c4524c3

Status:
Stable baseline checkpoint

Purpose:
Rollback point before Phase 8 ranking experiments.

Implemented:
- Competition ranking pipeline
- Evidence-based candidate evaluation foundation
- Benchmark-compatible CPU execution
- Valid submission generation

Notes:
Phase 7 became the baseline for all later ranking experiments.

---

## phase8b3-stable

Status:
Stable ranking improvement checkpoint

Main focus:
Improve ordering quality after Phase 7.

Implemented:
- Top-N reranking experiment
- Evidence-based reranking
- Double-counting correction
- Better evidence interpretation
- JD domain coupling refinement

Important decisions:
- Do not reward generic ownership alone
- Prefer demonstrated JD-relevant system building
- Preserve strong builders without relying only on keywords

Result:
Became stable checkpoint before architecture-level experiments.

---

## phase8c4-stable

Status:
CURRENT CHAMPION

Main focus:
Align ranking architecture with official challenge intent.

Key improvements:

1. Career Evidence Placement

Problem:
Career evidence was influencing ranking too late.

Change:
Made verified career evidence a first-class ranking signal.

Goal:
Prefer candidates who actually built relevant systems,
not only candidates with matching skill vocabulary.

---

2. JD Capability Alignment

Problem:
General AI/system experience could outrank more JD-specific evidence.

Refinement:
Improved distinction between:

- building relevant production systems

vs

- partial system involvement

without penalizing strong engineers.

---

3. Evidence Context Validation

Verified:
- ownership extraction behavior
- production evidence interpretation
- regression risks

Decision:
No unnecessary calibrator rewrite needed.

---

Current Architecture:

Candidate profile

↓

Base JD matching

+

Career evidence signal

↓

Evidence calibration

↓

Reranking

↓

Final Top candidates

---

Current frozen checkpoint:

phase8c4-stable

Use this as rollback before future experiments.

---

# Next Possible Research Direction

## Phase 8D — Semantic Evidence Understanding

Goal:

Detect equivalent meaning when vocabulary differs.

Example:

Candidate says:

"built relevance optimization platform"

JD expects:

"ranking / retrieval system"

Purpose:

Improve understanding.

Not:
- replace current ranking
- add uncontrolled AI behavior
- break CPU/runtime constraints

Rules:

Always compare against:

phase8c4-stable

before accepting changes.
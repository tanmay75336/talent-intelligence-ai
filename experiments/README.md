# Experiments — Ranking Development History

This directory contains the iterative ranking experiments we ran while developing the final system.

Each script is a self-contained experiment that can be run independently. They are **not** imported by the competition ranking pipeline (`backend/competition/rank.py`).

| File | What we explored |
|------|-----------------|
| `rerank_experiment.py` | First pass at a post-scoring reranker using evidence depth and behavioral signals |
| `phase8c3_experiment.py` | Added career evidence as a direct scoring term (not just calibration) |
| `phase8c3_compare.py` | Comparison harness for c3 vs baseline |
| `phase8c4_experiment.py` | Production ownership disclaimer detection — penalises candidates who explicitly report they did not own production systems |
| `phase8d1_full_judge_experiment.py` | Tested whether full evaluation exposure (300 candidate pool) changes final ranking |
| `phase8d2_judge_alignment_audit.py` | Audited alignment between our judge and official JD requirements |
| `phase8d4_skill_alignment_audit.py` | Validated whether skill signals were adding evidence or noise |
| `phase8e0_reasoning_improvement.py` | First pass at improving reasoning from structured labels toward natural prose |

The findings from these experiments are documented in `outputs/` as phase reports.

The final ranking logic (including all improvements validated here) is consolidated in `backend/competition/rank.py`.

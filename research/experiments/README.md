# Experiments — Ranking Development History

This directory contains ranking experiments created while testing different scoring, reranking, and reasoning approaches.

These scripts are kept as development history only. They are **not imported or executed by the final competition pipeline** (`backend/competition/rank.py`).

| File | What we explored |
|------|-----------------|
| `rerank_experiment.py` | Early reranking approach using evidence depth and behavioral signals |
| `phase8c3_experiment.py` | Tested adding career evidence directly into candidate scoring |
| `phase8c3_compare.py` | Comparison script for evaluating scoring changes against the previous approach |
| `phase8c4_experiment.py` | Tested handling of profiles where claimed skills and demonstrated ownership did not align |
| `phase8d1_full_judge_experiment.py` | Explored reranking behavior across a larger candidate pool |
| `phase8d2_judge_alignment_audit.py` | Checked whether ranking signals matched the job description requirements |
| `phase8d4_skill_alignment_audit.py` | Reviewed whether skill signals improved ranking quality or introduced noise |
| `phase8e0_reasoning_improvement.py` | Improved generated reasoning from structured signal output toward readable explanations |

The final competition implementation is maintained separately in:

`backend/competition/rank.py`

The official submission output is generated from the competition pipeline, not from these experiment scripts.

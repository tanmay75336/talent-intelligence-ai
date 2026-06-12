# Reasoning Quality Report

## Scope
- Rows checked: 100
- Checks: factual specificity, JD connection, repeated phrasing, generic language, missing years/title facts, and truncation.

## Detected Problems
- No reasoning problems detected by heuristic checks.

## Repeated Phrases
- `starts_with_years_title_company + jd_match_career_evidence + redrob_signal_sentence` repeated 56 times.
- `starts_with_years_title_company + jd_skill_overlap + redrob_signal_sentence` repeated 30 times.
- `starts_with_years_title_company + jd_match_career_evidence` repeated 7 times.
- `starts_with_years_title_company + jd_skill_overlap` repeated 7 times.

## Audit Judgment
- Reasoning generally cites candidate facts and JD connections.
- The largest manual-review risk is repeated template structure and some truncated evidence snippets.
- No hallucination is asserted by this automated audit; flagged items require manual review before any Phase 5B change.
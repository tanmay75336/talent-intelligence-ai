# RedRob Dataset Strategy Report

## 1. Dataset Overview
- Candidates streamed: 100000
- Schema includes profile, career history, education, skills, certifications, languages, and RedRob behavioral signals.

## 2. Senior AI Engineer Signal Availability
- Strong evidence count: 24471
- Medium evidence count: 61983
- Keyword-only count: 858
- Unrelated count: 12688

## 3. Strong Candidate Patterns
- Career descriptions combine AI infrastructure language with production evidence.
- Skills include retrieval, vector search, ranking, recommendation, Python, NLP, or LLM systems and are backed by work history.
- Behavioral signals may show activity, recruiter responsiveness, GitHub activity, and completed assessments.

## 4. Weak Candidate Patterns
- AI appears mostly in skills/headline but not in career descriptions.
- Profiles emphasize management, operations, marketing, support, or consulting without hands-on technical delivery.
- Computer vision, speech, or robotics profiles may be adjacent but are weaker without NLP/retrieval/ranking evidence.

## 5. Trap Risks
- fake_senior_or_hands_off: 2844
- framework_only_profile: 82144
- keyword_stuffer: 296
- possible_impossible_profile: 27
- research_only_mismatch: 1559

## 6. Behavioral Signal Findings
- Recruiter response rate: {'count': 100000, 'min': 0.02, 'max': 0.95, 'mean': 0.4366, 'median': 0.44, 'p25': 0.25, 'p75': 0.62, 'p90': 0.73, 'p95': 0.76}
- GitHub activity score: {'count': 100000, 'min': -1.0, 'max': 96.9, 'mean': 9.6192, 'median': -1.0, 'p25': -1.0, 'p75': 16.7, 'p90': 40.4, 'p95': 48.4}
- Saved by recruiters 30d: {'count': 100000, 'min': 0.0, 'max': 80.0, 'mean': 7.6587, 'median': 7.0, 'p25': 3.0, 'p75': 11.0, 'p90': 15.0, 'p95': 18.0}
- Interview completion rate: {'count': 100000, 'min': 0.3, 'max': 1.0, 'mean': 0.6195, 'median': 0.62, 'p25': 0.48, 'p75': 0.76, 'p90': 0.85, 'p95': 0.88}

## 7. Recommended Phase 4 Ranking Improvements
- Add evidence-backed boosts for retrieval/ranking/vector-search career descriptions, not just skill tags.
- Add penalties or confidence reductions for keyword-only AI profiles.
- Add behavioral availability as a modifier after technical fit is established.
- Add explicit trap detection diagnostics for review, without silently dropping candidates.
- Strengthen reasoning to cite concrete career-history and RedRob signal facts.
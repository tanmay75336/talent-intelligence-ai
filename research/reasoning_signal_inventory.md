# Reasoning Signal Inventory

## Safe Candidate Facts
- Years of experience: available in `profile.years_of_experience`.
- Current title/company/company size/industry: available in `profile`.
- Career descriptions: available in `career_history.description` and suitable for production/vector/ranking evidence when explicitly present.
- Skills with proficiency, endorsements, and duration: available in `skills`.
- Education and certifications: available as structured arrays.
- RedRob behavioral signals: available in `redrob_signals`, including GitHub activity, assessments, availability, recruiter response, and interview/offer behavior.

## Reasoning Claims That Need Evidence Checks
- Production systems should be mentioned only when career descriptions include deployed, production, users, scale, latency, monitoring, inference, or pipeline evidence.
- Vector search or retrieval should be mentioned only when profile/career/skills explicitly include retrieval, embeddings, vector databases, FAISS, Pinecone, Weaviate, Qdrant, Milvus, Elasticsearch, or OpenSearch.
- Ranking or recommendation systems should be mentioned only when those words or close variants appear in candidate evidence.
- Availability should cite concrete RedRob fields such as open_to_work_flag, last_active_date, recruiter_response_rate, notice_period_days, or willing_to_relocate.

## Dataset Evidence Availability
- Strong AI infrastructure evidence candidates: 24471
- Medium evidence candidates: 61983
- Keyword-only candidates: 858
- Unrelated candidates: 12688
- Skill assessment score summary: {'count': 35895, 'min': 20.0, 'max': 97.3, 'mean': 52.9191, 'median': 53.1, 'p25': 40.3, 'p75': 65.9, 'p90': 74.0, 'p95': 77.3}
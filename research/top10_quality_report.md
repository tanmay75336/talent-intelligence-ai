# Top 10 Quality Report

## 1. Current Top 10 Summary
- Rank 1 `CAND_0005260`: 5.2 years, Senior NLP Engineer; AI hits=['embedding', 'embeddings', 'faiss', 'learning-to-rank', 'rag'], production hits=['deployed', 'inference', 'latency', 'pipeline'], weaknesses=[].
- Rank 2 `CAND_0030031`: 5.7 years, AI Engineer; AI hits=['embedding', 'embeddings', 'ranking', 'recommendation'], production hits=['a/b test', 'monitoring', 'pipeline', 'pipelines', 'production'], weaknesses=[].
- Rank 3 `CAND_0088025`: 8.6 years, Staff Machine Learning Engineer; AI hits=['embedding', 'learning-to-rank', 'pinecone', 'rag', 'ranking'], production hits=['a/b test', 'pipeline'], weaknesses=[].
- Rank 4 `CAND_0096142`: 5.0 years, Applied ML Engineer; AI hits=['embedding', 'embeddings', 'ranking', 'recommendation'], production hits=['a/b test', 'pipeline', 'shipped', 'users'], weaknesses=[].
- Rank 5 `CAND_0051630`: 6.0 years, Machine Learning Engineer; AI hits=['elasticsearch', 'faiss', 'learning-to-rank', 'ranking', 'retrieval'], production hits=['pipeline'], weaknesses=[].
- Rank 6 `CAND_0068351`: 6.4 years, Lead AI Engineer; AI hits=['ranking'], production hits=['pipeline', 'production', 'users'], weaknesses=['wrong_ai_domain'].
- Rank 7 `CAND_0002025`: 5.9 years, Senior AI Engineer; AI hits=['embedding', 'embeddings', 'ranking', 'recommendation'], production hits=['a/b test', 'deployed', 'inference', 'latency', 'pipeline'], weaknesses=[].
- Rank 8 `CAND_0022894`: 7.4 years, Data Engineer; AI hits=[], production hits=['pipeline', 'pipelines', 'shipped'], weaknesses=['keyword_heavy'].
- Rank 9 `CAND_0091254`: 5.2 years, AI Research Engineer; AI hits=[], production hits=['inference', 'observability', 'pipeline', 'production'], weaknesses=['keyword_heavy', 'wrong_ai_domain'].
- Rank 10 `CAND_0008425`: 7.8 years, Senior NLP Engineer; AI hits=['embedding', 'learning-to-rank', 'pinecone', 'ranking', 'recommendation'], production hits=['a/b test', 'deployed', 'inference', 'latency', 'monitoring'], weaknesses=[].

## 2. Why Top Candidates Win
- The top 10 mostly show career-backed retrieval, ranking, recommendation, embeddings, vector search, or inference evidence rather than skills-only claims.
- Several top candidates include production ownership terms such as shipped, production, users, monitoring, latency, or pipelines.
- RedRob behavioral signals are present in reasoning only as secondary facts and do not appear to dominate technical evidence.

## 3. Rank Separation Analysis
- Rank 1-10 average AI infrastructure hits: 4; average production hits: 4.3.
- Rank 11-25 average AI infrastructure hits: 5; average production hits: 4.
- Rank 26-50 average AI infrastructure hits: 1.6; average production hits: 3.2.

## 4. Possible Missed Candidates
- Rank 11 `CAND_0077337` trails rank 10 by 0.000373; AI hits=['embedding', 'embeddings', 'rag', 'ranking', 'recommendation', 'retrieval'], production hits=['a/b test', 'latency', 'monitoring', 'production', 'scale', 'shipped'], weaknesses=[].
- Rank 13 `CAND_0030953` trails rank 10 by 0.004090; AI hits=['elasticsearch', 'embedding', 'embeddings', 'faiss', 'pinecone', 'rag'], production hits=['a/b test', 'pipeline', 'shipped', 'users'], weaknesses=[].
- Rank 14 `CAND_0064326` trails rank 10 by 0.004336; AI hits=['embedding', 'embeddings', 'learning-to-rank', 'pinecone', 'rag', 'ranking'], production hits=['a/b test', 'pipeline', 'shipped'], weaknesses=[].
- Rank 15 `CAND_0042029` trails rank 10 by 0.005360; AI hits=['embedding', 'embeddings', 'pinecone', 'rag', 'ranking'], production hits=['a/b test', 'pipeline', 'shipped'], weaknesses=[].
- Rank 16 `CAND_0081846` trails rank 10 by 0.006976; AI hits=['embedding', 'embeddings', 'faiss', 'learning-to-rank', 'rag', 'ranking'], production hits=['latency', 'monitoring', 'pipeline', 'scale'], weaknesses=[].
- Rank 17 `CAND_0037944` trails rank 10 by 0.008999; AI hits=['embedding', 'embeddings', 'pinecone', 'rag', 'ranking'], production hits=['a/b test', 'pipeline', 'shipped'], weaknesses=[].
- Rank 18 `CAND_0010257` trails rank 10 by 0.009373; AI hits=['embedding', 'embeddings', 'ranking', 'recommendation'], production hits=['a/b test', 'monitoring', 'pipeline', 'pipelines', 'production', 'shipped'], weaknesses=[].
- Rank 19 `CAND_0017960` trails rank 10 by 0.011874; AI hits=['embedding', 'embeddings', 'pinecone', 'rag', 'ranking'], production hits=['a/b test', 'pipeline', 'shipped'], weaknesses=[].
- Rank 20 `CAND_0043228` trails rank 10 by 0.014760; AI hits=['elasticsearch', 'faiss', 'learning-to-rank', 'ranking', 'retrieval', 'semantic search'], production hits=['monitoring', 'pipeline', 'pipelines', 'production'], weaknesses=[].
- Rank 21 `CAND_0081686` trails rank 10 by 0.017622; AI hits=['elasticsearch', 'embedding', 'embeddings', 'faiss', 'learning-to-rank', 'ranking'], production hits=['a/b test', 'pipeline', 'users'], weaknesses=[].

## 5. Ranking Weaknesses
- Some top-10 entries are weaker on explicit retrieval/ranking/vector career evidence than nearby ranks 11-20.
- Evaluation framework evidence such as NDCG, MRR, MAP, offline-online correlation, or A/B testing is sparse and not visibly separating the top 10.
- Reasoning is factual but templated in structure, often starting with years/title/company followed by the same JD-match phrase.

## 6. Reasoning Quality
- Rows checked: 100
- Rows with detected issues: 0
- Main issue: repeated sentence pattern and truncated evidence excerpts, not hallucinated skills.

## 7. Recommended Phase 5B Changes
- Consider a small top-10 close-call adjustment that prefers career-backed retrieval/ranking/vector evidence over adjacent data-engineering or generic inference evidence when score gaps are tiny.
- Consider adding an explicit evaluation-framework signal for NDCG/MRR/MAP/A/B testing, but only where career history states it.
- Consider improving reasoning variation and adding concise weakness notes for borderline top-10 candidates.

## 8. Final Decision Gate
B: Small calibration issue found. Recommend Phase 5B minor adjustment.
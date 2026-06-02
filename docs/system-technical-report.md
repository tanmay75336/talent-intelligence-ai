# Talent Intelligence AI: Technical System Report

## Executive Summary

Talent Intelligence AI is a hiring decision-support platform that ranks candidates against a job description using deterministic parsing, hybrid retrieval, evidence-backed scoring, recruiter-readable reasoning, and saved workflow history. The system is designed to solve a common recruiting failure mode: keyword filters and basic semantic matchers can miss candidates whose resumes show transferable capability, implementation ownership, or project depth without exact wording overlap.

The current product is best described as an advanced hackathon-stage modular monolith rather than a production ATS. It goes beyond a simple resume filter by extracting structured job and candidate intelligence, retrieving supporting evidence, applying calibrated deterministic ranking, generating strengths/risks/interview focus areas, and preserving historical ranking runs. It also includes a dataset intelligence layer for unknown hackathon datasets so the team can profile schemas and evaluate rankings quickly when new data arrives.

The platform is mature enough to demonstrate an end-to-end recruiter workflow: upload a job description and resumes, rank candidates, inspect evidence, compare candidates, reopen saved runs, and profile unknown datasets. It is not yet a fully productionized recruiting system: it has no authentication, tenant isolation, enterprise audit model, human feedback loop, advanced security posture, or large-scale evaluation harness.

## System Architecture

The system is a deterministic-first modular monolith with a FastAPI backend and a Next.js frontend. Backend responsibilities are separated into parsing, intelligence extraction, retrieval, scoring, reasoning, persistence, and dataset intelligence modules.

High-level backend subsystems:

- `backend/parsers/`: extracts text and basic sections from resumes and job descriptions.
- `backend/intelligence/`: converts parsed text into structured `JobIntelligence` and `CandidateIntelligence`.
- `backend/retrieval/`: chunks resumes/JDs, embeds text, indexes Chroma, performs sparse TF-IDF retrieval, fuses dense/sparse rankings, deduplicates evidence, and returns retrieval contexts.
- `backend/ranking/`: computes deterministic scores and candidate ordering.
- `backend/reasoning/`: converts scores and evidence into recruiter-facing summaries, strengths, risks, comparison explanations, trust checks, optional Groq synthesis, and differentiation.
- `backend/storage/`: persists jobs, candidates, ranking runs, ranking results, and evidence metadata in SQLite.
- `backend/dataset_intelligence/`: profiles unknown datasets, inventories available signals, and evaluates ranking strategies when labels or expected orderings exist.
- `backend/main.py`: exposes FastAPI routes and orchestrates upload, ranking, saved-run, dataset, and comparison APIs.

Frontend responsibilities are concentrated in `frontend/app/page.tsx`, reusable components under `frontend/components/`, API helpers under `frontend/lib/api.ts`, and shared types under `frontend/types/recruitment.ts`. The frontend now presents a recruiter workspace with dashboard, new analysis, candidate list, detail view, comparison, saved runs, and local pipeline state.

End-to-end flow:

```text
JD + resumes
-> PDF/text parsing
-> job/candidate intelligence extraction
-> JD/resume chunking
-> dense Chroma retrieval + sparse TF-IDF retrieval
-> reciprocal rank fusion + evidence dedupe/diversification
-> deterministic scoring
-> trust calibration + differentiation
-> optional bounded Groq synthesis
-> ranked recruiter output
-> SQLite persistence
-> frontend review/comparison/saved-run workflow
```

## Technology Stack

Frontend:

- Next.js 14 with React 18 and TypeScript for the recruiter workspace.
- Tailwind CSS for styling.
- Client-side API helpers in `frontend/lib/api.ts`.

Backend:

- FastAPI for HTTP APIs.
- Pydantic models for typed request/response and intelligence schemas.
- Python standard library `sqlite3` for persistence.
- `pdfplumber` and PyMuPDF (`pymupdf`) dependencies for PDF text extraction support.
- `pandas` for dataset profiling and tabular analysis.

Retrieval and embeddings:

- `sentence-transformers` with `BAAI/bge-small-en-v1.5` as the default local embedding model.
- ChromaDB as the local vector database for embeddings and chunk retrieval indexes.
- Scikit-learn TF-IDF sparse retrieval in `backend/retrieval/bm25_retriever.py`.
- Reciprocal Rank Fusion in `backend/retrieval/rank_fusion.py`.

AI provider:

- Optional Groq chat completion endpoint in `backend/reasoning/groq_synthesis.py`.
- Groq synthesis is disabled unless `GROQ_API_KEY` is present and `ENABLE_GROQ_SYNTHESIS` is configured appropriately.
- The AI layer polishes deterministic reasoning only; it does not own score or rank decisions.

Storage:

- SQLite stores recruiter workflow state, structured intelligence JSON, ranking results, and evidence metadata.
- Chroma stores embeddings and retrieval indexes only.

Testing:

- Python `unittest` tests cover retrieval, storage, dataset intelligence, reasoning quality, and ranking trust.
- Frontend type validation uses `npm exec tsc -- --noEmit`.

Deployment assumptions:

- The current system is local-first and hackathon-friendly.
- No cloud infrastructure, background workers, queues, auth provider, or managed vector DB is required.

## End-to-End Candidate Ranking Flow

The primary demo endpoint is `POST /upload-and-rank/`. A recruiter submits a job description and one or more resume PDFs. The backend saves uploaded files to `backend/uploads/`, extracts text, builds job intelligence once, ranks each resume, sorts candidates, applies trust/differentiation/synthesis, persists the run, and returns a frontend-ready payload.

Major ranking stages:

1. Job description validation and analysis through `build_jd_analysis()` and `build_jd_intelligence()`.
2. Resume text extraction through `extract_text_from_pdf()`.
3. Candidate profile construction through `build_candidate_profile()`.
4. Candidate intelligence generation through `build_candidate_intelligence()`.
5. JD and candidate chunking through `chunk_job_intelligence()` and `chunk_candidate_profile()`.
6. Retrieval indexing through `EvidenceRetriever.index_documents()`.
7. Evidence retrieval through `EvidenceRetriever.retrieve_for_candidate()`.
8. Deterministic scoring through `score_candidate_profile()`.
9. Recruiter-facing result construction through `build_ranking_result()`.
10. Slate-level ordering trust checks through `apply_ranking_trust_analysis()`.
11. Candidate differentiation through `apply_candidate_differentiation()`.
12. Optional Groq synthesis through `apply_optional_groq_synthesis()`.
13. Rank-order annotation through `annotate_ranked_order()`.
14. SQLite persistence through `persist_ranked_workflow()`.

Saved ranking runs are immutable historical artifacts. Reopening a run uses stored JSON via `GET /ranking-runs/{run_id}/results`; it does not recompute retrieval, scoring, or reasoning.

## Candidate Intelligence Layer

Candidate intelligence begins with resume parsing in `backend/parsers/resume_parser.py`. The parser builds a `CandidateProfile` containing name, source file, raw text, summary, sections, skills, projects, experience, deployment signals, AI signals, and other extracted material.

`backend/intelligence/candidate_engine.py` converts that profile into `CandidateIntelligence`. It normalizes skills, creates project and experience signals, detects education and certifications, estimates seniority and years of experience, records domains, and generates evidence references. It also infers limited hidden capabilities from concrete project and experience text. For example, project descriptions involving live bidding, synchronization, or multiplayer systems can trigger realtime-system and backend-orchestration capability signals.

Candidate intelligence exposes information used by later stages:

- Hard signals: skills, technologies, projects, experience items, education, certifications, domains.
- Deep signals: ownership, execution capability, learning velocity, engineering sophistication, deployment understanding, product ownership, and collaboration indicators.
- Supporting signals: deployment maturity, authenticity, consistency, adaptability, leadership, AI capability, and related modifiers.
- Contradiction flags: broad unsupported skill inventories or AI claims without strong implementation evidence.

The system intentionally keeps these in structured models so scoring and explanation can operate over evidence rather than raw resume text alone.

## Retrieval Architecture

Retrieval exists to connect ranking and explanations to concrete evidence. It helps answer: “What in this resume supports this score or recruiter conclusion?”

The retrieval pipeline is implemented in `backend/retrieval/`:

- `chunking.py` creates structured chunks from JD overview, responsibilities, must-haves, preferred skills, resume summaries, projects, experience items, skills, education, and certifications.
- `embeddings.py` lazily loads `BAAI/bge-small-en-v1.5`, caches the model globally, validates embedding dimensions, and supports batch embeddings.
- `chroma_store.py` stores embeddings and chunk metadata in Chroma.
- `bm25_retriever.py` provides lightweight sparse lexical retrieval using scikit-learn TF-IDF.
- `rank_fusion.py` fuses dense and sparse rankings with Reciprocal Rank Fusion.
- `deduplication.py` suppresses repeated snippets, caps source overlap, and applies lightweight diversity filtering.
- `evidence_retriever.py` orchestrates pillar-aware retrieval and returns `RetrievalContext`.

The system uses dense retrieval for semantic meaning and sparse retrieval for explicit must-have reinforcement. Dense retrieval can connect adjacent concepts such as “live bidding synchronization” to “realtime backend systems.” Sparse retrieval helps prevent broad engineering language from overmatching when explicit JD requirements are absent.

Retrieval is pillar-aware. Semantic fit, ownership, execution maturity, technical depth, and transferability use different query expansions and chunk priorities. Transferability expands concepts around realtime systems, deployments, backend architecture, AI retrieval, APIs, and adjacent stack signals.

Must-have coverage is calculated separately from generic evidence retrieval. This lets the scoring engine apply soft penalties when a candidate has transferable capability but weak support for explicit requirements.

## Ranking Engine

The ranking engine remains deterministic. The main scoring implementation is `backend/ranking/scoring_engine.py`. It uses a weighted blend of concrete match and evidence signals rather than allowing the AI layer to assign scores.

Current score components include:

- Skill overlap and exact JD skill support.
- Project relevance.
- Semantic alignment.
- Deployment experience.
- AI/API experience.
- Adjacent transferability.

The scorer also includes calibration logic for exact support, weak must-have ratios, project/experience authority, generic engineering language suppression, and score normalization. This is designed to prevent adjacent-fit candidates or generic engineering resumes from inflating into near-perfect scores without explicit evidence.

Ranking authority is determined by deterministic output first:

1. Candidate profile and JD analysis are scored deterministically.
2. Retrieval context informs evidence-backed scoring where available.
3. Candidates are sorted by `final_score`.
4. Trust analysis may apply deterministic suppression or ordering refinement.
5. Explanations and summaries are generated after scoring.
6. Optional Groq synthesis may rewrite text, but cannot change ranking order or assign scores.

Recommendation labels such as `Highly Recommended`, `Recommended`, `Consider for Interview`, `Low Match`, and `Hidden Gem` are derived from deterministic score bands and flags.

## Evidence Quality and Trust Layer

The evidence and trust layer exists because strong-looking semantic matches can still be unreliable. `backend/reasoning/evidence_quality.py` classifies evidence strength based on implementation verbs, shipped work, deployment ownership, architecture terms, operational terms, measurements, and weak/vague language.

High-quality evidence generally includes:

- Shipped or deployed systems.
- Direct implementation responsibility.
- Production integrations.
- Architecture or backend design.
- Measurable outcomes.
- Operational or deployment ownership.

Weak evidence includes:

- Generic summaries.
- Unsupported skill lists.
- Buzzword-heavy claims.
- Skill inventories without project or experience support.

`backend/reasoning/ranking_trust.py` applies false-positive suppression and slate-level trust checks. It identifies patterns such as keyword overlap without implementation evidence, AI claims without strong AI evidence, adjacent-fit inflation, skill-inventory dominance, and elite scores that are under-supported by evidence.

`backend/reasoning/differentiation.py` improves candidate differentiation across a ranked slate by surfacing more candidate-specific evidence categories and suppressing repetitive generic observations. The goal is to make candidates easier to compare as humans rather than simply presenting scorecards.

## AI Reasoning Layer

The reasoning layer has deterministic and optional AI-assisted parts.

Deterministic reasoning is implemented primarily in `backend/reasoning/explanation_builder.py`. It builds `RankingResult` objects with:

- Final score, recommendation, and recruiter confidence.
- Pillar scores.
- Strengths.
- Risks.
- Missing must-haves.
- Missing evidence.
- Why-not-selected reasoning.
- Reasons ranked below stronger candidates.
- Interview focus areas.
- Supporting evidence snippets.
- Hidden-gem flag.
- Recruiter decision summary.
- Optional ATS-vs-intelligence reasoning.

Pairwise comparison is also deterministic. `build_pairwise_comparison()` compares two ranked candidates and explains winner/loser differences through score deltas, must-have coverage, strengths, risks, evidence quality, and recruiter summaries.

Groq synthesis in `backend/reasoning/groq_synthesis.py` is optional and bounded. Its job is to polish deterministic text into sharper recruiter language. It receives deterministic summaries, strengths, risks, interview validations, ordering constraints, and a small set of evidence snippets. It is explicitly instructed not to add new claims, scores, rankings, recommendations, technologies, outcomes, or evidence.

AI is allowed to:

- Rewrite deterministic explanations for clarity.
- Make summaries less repetitive.
- Make candidate reasoning more recruiter-readable.

AI is not allowed to:

- Assign raw scores.
- Change ranking order.
- Invent evidence.
- Add unsupported strengths or risks.
- Override deterministic recommendations.

This boundary preserves deterministic ranking authority while improving explanation quality when configured.

## Persistence Layer

The persistence layer is implemented with Python `sqlite3` in `backend/storage/`. Database initialization happens at FastAPI startup through `initialize_database()`.

SQLite tables:

- `jobs`: stores role title, raw JD text, and structured `JobIntelligence` JSON.
- `candidates`: stores candidate name, resume text, and structured `CandidateIntelligence` JSON.
- `ranking_runs`: stores one recruiter ranking session with configuration flags for rerank, embeddings, and retrieval.
- `ranking_results`: stores immutable ranked output JSON, final score, recommendation, confidence, hidden-gem flag, and rank position.
- `evidence_metadata`: stores lightweight evidence metadata such as chunk ID, source type, source label, strength, and retrieval score.

Repositories in `backend/storage/repositories.py` are intentionally thin. Business logic remains outside persistence. `backend/storage/workflows.py` persists completed ranking runs and reconstructs saved-run responses.

Storage responsibilities are separated:

- SQLite stores workflow history and recruiter-facing outputs.
- Chroma stores embeddings and retrieval indexes.
- Saved runs are restored from SQLite JSON and are not recalculated.

This gives the product continuity: recruiters can reopen prior sessions, inspect historical evidence, and compare previous evaluations without changing old rankings when scoring logic evolves.

## Frontend Architecture

The frontend is a Next.js recruiter workspace. The main application is `frontend/app/page.tsx`. It uses API helpers from `frontend/lib/api.ts`, presentation helpers from `frontend/lib/recruiterPresentation.ts`, and shared types from `frontend/types/recruitment.ts`.

Current workspace views include:

- Dashboard.
- New analysis.
- Candidate list.
- Candidate detail.
- Comparison.
- Saved runs.
- Local pipeline state.

The UI is designed to prioritize recruiter decision-making over score spectacle. Candidate cards emphasize recommendation band, must-have status, concise summary, strongest evidence, top strengths/risks, and workflow actions. Detailed evidence is available in deeper candidate inspection rather than being dumped into every card.

Saved runs are loaded through `GET /ranking-runs/` and restored through `GET /ranking-runs/{run_id}/results`. Local recruiter workflow state such as review, shortlist, interview, and reject is presentation-only and does not mutate backend ranking order or persisted scores.

The frontend currently uses the existing API contract and does not perform frontend reranking. Candidate ordering is derived from backend ranking output and saved-run rank positions.

## Dataset Intelligence Layer

The dataset intelligence layer was added to prepare for unknown hackathon datasets. It does not change ranking automatically. Its purpose is to help the team understand new data quickly and identify useful signals before adapting the ranking engine.

Implemented modules:

- `loader.py`: loads CSV, JSON, and JSONL/NDJSON datasets.
- `profiler.py`: profiles schema, field types, missing rates, coverage, duplicate rates, sparsity, text-heavy fields, numeric fields, categorical fields, useful/noisy signals, and profile completeness indicators.
- `signals.py`: builds a candidate signal inventory across skills, titles, experience, education, certifications, endorsements, activity, projects, achievements, engagement, behavior, and career progression.
- `evaluation.py`: computes ranking evaluation metrics and compares strategies.
- `reporting.py`: generates markdown reports.
- `workspace.py`: provides a CLI for local dataset profiling.

The API exposes:

- `POST /dataset/profile/`: uploads a dataset and returns a structured profile report.
- `POST /dataset/evaluate-rankings/`: evaluates ranking strategy outputs against expected order, positives/negatives, hidden gems, and optional baseline strategy.

This layer makes the system data-adaptive at the analysis level: it can discover fields and propose candidate signals without assuming a fixed schema.

## Evaluation and Benchmarking

The repo includes several evaluation and regression tools:

- `backend/ranking_benchmark.py` and benchmark case files for ranking behavior.
- `backend/evaluation_test_cases.py` for evaluation scenarios.
- `backend/test_retrieval.py` for retrieval quality, hybrid retrieval, deduplication, and must-have suppression.
- `backend/test_ranking_trust.py` for trust calibration and false-positive suppression.
- `backend/test_reasoning_quality.py` for explanation differentiation and bounded synthesis behavior.
- `backend/test_storage.py` for SQLite persistence and historical integrity.
- `backend/test_dataset_intelligence.py` for dataset profiling and ranking evaluation utilities.

Dataset evaluation supports pairwise accuracy, ranking accuracy, top-k quality, false positive rate, false negative rate, hidden gem detection rate, ranking stability, and strategy comparison. These tools are intended to help compare multiple ranking outputs once labels or expected examples are available.

The evaluation layer is still lightweight. It is not a full ML experiment tracking system, does not train models, and does not yet integrate human recruiter feedback loops.

## Current Strengths

- The system is deterministic-first, so ranking authority is inspectable and not delegated to an LLM.
- Hybrid retrieval materially improves evidence grounding compared with keyword-only or embedding-only matching.
- Evidence snippets include source type, source label, strength, and retrieval score, enabling recruiter trust.
- Trust calibration suppresses some common false positives such as unsupported skill lists and adjacent-fit inflation.
- Optional Groq synthesis is bounded and fails back to deterministic reasoning.
- SQLite persistence makes the product feel like a real recruiter workflow rather than a one-off demo.
- Dataset intelligence prepares the team to inspect unknown hackathon data quickly.
- The frontend has evolved into a calmer recruiter workspace rather than a debug-heavy scoring dashboard.
- The architecture remains lightweight and hackathon-practical: FastAPI, Next.js, SQLite, Chroma, and local embeddings.

## Current Limitations

Ranking limitations:

- Scoring is still heuristic and calibrated by rules, not learned from large-scale recruiter judgments.
- Exact skill extraction and JD parsing can miss nuanced requirements or over-detect ambiguous terms.
- Transferability reasoning is rule- and retrieval-driven; it can identify adjacent capability but cannot fully understand career context.
- Seniority and years-of-experience estimation are approximate.

Dataset limitations:

- Dataset profiling identifies signals but does not automatically adapt ranking weights or schemas.
- Ground-truth evaluation depends on external labels, expected ordering, positives/negatives, or hidden-gem annotations.
- Unknown data with highly nested or unconventional fields may require manual interpretation after profiling.

AI limitations:

- Groq synthesis depends on external API configuration and network availability.
- AI synthesis does not create new evidence or improve ranking quality; it only improves wording.
- If disabled or unavailable, the system falls back to deterministic summaries, which can still be less nuanced than human recruiter writing.

Production limitations:

- No authentication, authorization, tenant isolation, or audit controls.
- CORS is permissive for local demo use.
- Local SQLite and Chroma are not designed for multi-user production concurrency.
- No background job queue for large batch processing.
- No production observability, tracing, rate limiting, or robust file security model.
- Uploaded files are stored locally under `backend/uploads/`.

Recruiter workflow limitations:

- Local pipeline actions are presentation state and are not a full ATS workflow.
- Notes, feedback, and recruiter decisions are not yet persisted as first-class records.
- Comparison is available but not a complete collaborative review workflow.

## Future Directions

Highest-value future improvements should focus on ranking quality, dataset adaptation, evaluation quality, and reasoning quality rather than generic SaaS expansion.

Priority improvements:

- Build a labeled evaluation set from real recruiter preferences and use it to tune scoring weights and suppression thresholds.
- Use dataset intelligence reports to map unknown fields into candidate intelligence inputs with explicit human approval.
- Add a human feedback loop for accepted/rejected rankings and interview outcomes.
- Improve JD understanding for business context, required vs optional requirements, and seniority expectations.
- Strengthen resume parsing for non-standard PDF formats and portfolio/profile exports.
- Add recruiter-editable must-haves and evidence validation controls.
- Improve pairwise comparison with more direct evidence citations and clearer “why not higher” reasoning.
- Persist recruiter workflow actions and notes once auth/workspace ownership exists.
- Add production hardening: auth, stricter CORS, file validation, observability, and scalable processing for large resume batches.

## Appendix

### Directory Overview

```text
backend/
  dataset_intelligence/   Schema profiling, signal inventory, ranking evaluation, markdown reporting
  intelligence/           Job and candidate intelligence builders
  models/                 Pydantic schemas for evidence, intelligence, ranking results, profiles
  parsers/                Resume and JD parsing/analyzer utilities
  ranking/                Deterministic scoring and ranking pipeline
  reasoning/              Explanations, trust checks, differentiation, Groq synthesis
  retrieval/              Chunking, embeddings, Chroma, sparse retrieval, RRF, dedupe, evidence retrieval
  storage/                SQLite initialization, migrations, repositories, workflow persistence
  main.py                 FastAPI application and route definitions

frontend/
  app/                    Next.js app shell and recruiter workspace page
  components/             Candidate cards, analytics panel, header, upload zone
  lib/                    API helpers, presentation helpers, utilities
  types/                  Shared TypeScript recruitment types
```

### Important Backend Files

- `backend/main.py`: FastAPI app, upload/rank endpoints, saved-run endpoints, dataset endpoints.
- `backend/ranking/pipeline.py`: ranking orchestration.
- `backend/ranking/scoring_engine.py`: deterministic scoring.
- `backend/retrieval/evidence_retriever.py`: hybrid retrieval orchestration.
- `backend/retrieval/embeddings.py`: local BGE embedding provider.
- `backend/reasoning/explanation_builder.py`: recruiter-facing ranking result and pairwise comparison generation.
- `backend/reasoning/ranking_trust.py`: trust calibration and false-positive suppression.
- `backend/reasoning/groq_synthesis.py`: optional bounded AI synthesis.
- `backend/storage/migrations.py`: SQLite schema.
- `backend/storage/workflows.py`: ranking persistence and saved-run reconstruction.
- `backend/dataset_intelligence/profiler.py`: schema-agnostic dataset profiling.
- `backend/dataset_intelligence/evaluation.py`: ranking evaluation metrics.

### Important Frontend Files

- `frontend/app/page.tsx`: recruiter workspace and view state.
- `frontend/components/CandidateCard.tsx`: compact candidate review cards.
- `frontend/components/UploadZone.tsx`: JD/resume upload flow.
- `frontend/components/AnalyticsPanel.tsx`: workspace summary metrics.
- `frontend/lib/api.ts`: backend API client functions.
- `frontend/lib/recruiterPresentation.ts`: UI presentation helpers.
- `frontend/types/recruitment.ts`: frontend data contracts.

### Important API Endpoints

- `GET /`: backend health message.
- `POST /upload-resume/`: parse one resume and return extracted intelligence.
- `POST /upload-jd/`: analyze a job description.
- `POST /analyze-jd/`: return structured job intelligence.
- `POST /rank-candidate/`: rank one resume text against a JD.
- `POST /rank-multiple-candidates/`: rank multiple text resumes.
- `POST /semantic-rank/`: legacy semantic ranking route.
- `POST /compare-candidates/`: deterministic pairwise comparison.
- `POST /upload-and-rank/`: primary demo route for JD + uploaded resumes.
- `POST /rank-dataset/`: rank local dataset resumes against a JD.
- `GET /jobs/`: list saved jobs.
- `GET /jobs/{job_id}`: retrieve saved job.
- `GET /ranking-runs/`: list saved ranking runs.
- `GET /ranking-runs/{run_id}`: retrieve saved run metadata.
- `GET /ranking-runs/{run_id}/results`: restore immutable saved ranking results.
- `GET /ranking-runs/{run_id}/comparison`: restore saved-run comparison output.
- `POST /dataset/profile/`: profile an unknown dataset.
- `POST /dataset/evaluate-rankings/`: evaluate ranking strategy outputs.


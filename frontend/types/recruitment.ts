export interface AdjacentMatch {
  missing_skill: string;
  related_skill: string;
}

export interface EvidenceSnippet {
  evidence_id: string;
  source_type: "project" | "experience" | "summary" | "skills" | "education" | "jd";
  source_label: string;
  snippet: string;
  evidence_strength: "high" | "medium" | "low";
  retrieval_score?: number | null;
}

export interface PillarScore {
  score: number;
  confidence: "High" | "Medium" | "Low" | string;
  summary: string;
  evidence_ids: string[];
}

export interface CandidateIntelligence {
  candidate_name: string;
  normalized_skills: string[];
  domains: string[];
  seniority_band: string;
  years_experience_estimate: number;
  core_signals: Record<string, number>;
  supporting_signals: Record<string, number>;
  contradiction_flags: string[];
}

export interface JobIntelligence {
  role_title: string;
  explicit_skills: string[];
  preferred_skills: string[];
  responsibilities: string[];
  domains: string[];
  seniority: string;
  startup_vs_enterprise: string;
  ownership_expectation: number;
  communication_expectation: number;
  confidence: Record<string, string>;
}

export interface CandidateRanking {
  final_score: number;
  keyword_score: number;
  semantic_score: number;
  adjacency_bonus: number;
  project_relevance_score?: number;
  deployment_score?: number;
  ai_experience_score?: number;
  confidence_score?: number;
  recruiter_confidence?: string;
  matched_skills: string[];
  missing_skills: string[];
  adjacent_matches: AdjacentMatch[];
  pillar_scores: Record<string, PillarScore>;
  strengths: string[];
  risks: string[];
  missing_must_haves: string[];
  missing_evidence: string[];
  why_not_selected: string[];
  reasons_ranked_below_stronger_candidates: string[];
  interview_focus_areas: string[];
  supporting_evidence_snippets: Record<string, EvidenceSnippet[]>;
  hidden_gem_flag?: boolean;
  recruiter_decision_summary: string;
  ats_vs_intelligence_reasoning?: string | null;
  weaknesses: string[];
  recommendation: string;
  recruiter_summary?: string;
  scoring_diagnostics?: {
    scoring_version?: string;
    raw_scores?: Record<string, number>;
    component_scores?: Record<string, number>;
    coverage_metrics?: Record<string, number>;
    semantic_details?: Record<string, unknown>;
    adjustments?: Record<string, unknown>;
  };
}

export interface RankedCandidate {
  candidate_name: string;
  resume_file?: string;
  candidate_skills: string[];
  candidate_intelligence?: CandidateIntelligence;
  ranking: CandidateRanking;
}

export interface UploadAndRankResponse {
  total_candidates: number;
  ranked_candidates: RankedCandidate[];
  job_intelligence?: JobIntelligence;
  processing_errors?: string[];
  ranking_run_id?: string | null;
}

export interface RankDatasetResponse {
  dataset_size: number;
  ranked_candidates: RankedCandidate[];
  job_intelligence?: JobIntelligence;
  processing_errors?: string[];
  ranking_run_id?: string | null;
}

export type SortOption = "ranked" | "score" | "semantic" | "keyword" | "name";

export interface RankingRunSummary {
  id: string;
  job_id: string;
  role_title: string;
  result_count: number;
  top_score?: number | null;
  top_candidate_name?: string | null;
  average_confidence?: string | null;
  rerank_enabled: boolean;
  embeddings_enabled: boolean;
  retrieval_enabled: boolean;
  created_at: string;
}

export interface SavedRankingRunResults {
  ranking_run_id: string;
  total_candidates: number;
  ranked_candidates: RankedCandidate[];
  job_intelligence?: JobIntelligence;
  run: {
    id: string;
    role_title: string;
    created_at: string;
  };
}

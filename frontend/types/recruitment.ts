export interface AdjacentMatch {
  missing_skill: string;
  related_skill: string;
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
  strengths: string[];
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
  ranking: CandidateRanking;
}

export interface UploadAndRankResponse {
  total_candidates: number;
  ranked_candidates: RankedCandidate[];
  processing_errors?: string[];
}

export interface RankDatasetResponse {
  dataset_size: number;
  ranked_candidates: RankedCandidate[];
  processing_errors?: string[];
}

export type SortOption = "score" | "semantic" | "keyword" | "name";

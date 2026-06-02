import type { RankedCandidate, SortOption } from "@/types/recruitment";

export function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function formatScore(score?: number) {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return "0";
  }

  return Number.isInteger(score) ? `${score}` : score.toFixed(1);
}

export function getScoreTone(score?: number) {
  if ((score ?? 0) >= 80) {
    return "text-emerald-200 bg-emerald-500/15 border-emerald-400/25";
  }

  if ((score ?? 0) >= 60) {
    return "text-sky-200 bg-sky-500/15 border-sky-400/25";
  }

  if ((score ?? 0) >= 40) {
    return "text-amber-200 bg-amber-500/15 border-amber-400/25";
  }

  return "text-rose-200 bg-rose-500/15 border-rose-400/25";
}

export function getRecommendationTone(recommendation?: string) {
  switch (recommendation) {
    case "Highly Recommended":
      return "text-emerald-200 bg-emerald-500/15 border-emerald-400/25";
    case "Recommended":
      return "text-sky-200 bg-sky-500/15 border-sky-400/25";
    case "Consider for Interview":
      return "text-amber-200 bg-amber-500/15 border-amber-400/25";
    default:
      return "text-slate-200 bg-slate-500/15 border-slate-400/25";
  }
}

export function getConfidence(candidate: RankedCandidate) {
  const recruiterConfidence = candidate.ranking?.recruiter_confidence;
  if (recruiterConfidence === "High") {
    return {
      label: "High confidence",
      tone: "text-emerald-200 bg-emerald-500/12 border-emerald-400/25",
    };
  }

  if (recruiterConfidence === "Medium") {
    return {
      label: "Moderate confidence",
      tone: "text-sky-200 bg-sky-500/12 border-sky-400/25",
    };
  }

  if (recruiterConfidence === "Low") {
    return {
      label: "Needs validation",
      tone: "text-amber-200 bg-amber-500/12 border-amber-400/25",
    };
  }

  const finalScore = candidate.ranking?.final_score ?? 0;
  const semanticScore = candidate.ranking?.semantic_score ?? 0;
  const keywordScore = candidate.ranking?.keyword_score ?? 0;

  if (finalScore >= 80 || (semanticScore >= 75 && keywordScore >= 60)) {
    return {
      label: "High confidence",
      tone: "text-emerald-200 bg-emerald-500/12 border-emerald-400/25",
    };
  }

  if (finalScore >= 55 || semanticScore >= 60) {
    return {
      label: "Moderate confidence",
      tone: "text-sky-200 bg-sky-500/12 border-sky-400/25",
    };
  }

  return {
    label: "Needs review",
    tone: "text-amber-200 bg-amber-500/12 border-amber-400/25",
  };
}

export function isHiddenGem(candidate: RankedCandidate) {
  if (candidate.ranking?.hidden_gem_flag) {
    return true;
  }

  const semanticScore = candidate.ranking?.semantic_score ?? 0;
  const keywordScore = candidate.ranking?.keyword_score ?? 0;
  const adjacencyBonus = candidate.ranking?.adjacency_bonus ?? 0;

  return semanticScore >= 60 && keywordScore < 55 && adjacencyBonus >= 5;
}

export function getCandidateKey(candidate: RankedCandidate, index: number) {
  const stableLabel =
    candidate.resume_file ??
    candidate.candidate_name ??
    candidate.candidate_intelligence?.candidate_name;

  if (stableLabel) {
    return stableLabel
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
  }

  return `candidate-${index}`;
}

export function sortCandidates(
  candidates: RankedCandidate[],
  sortOption: SortOption,
) {
  const sorted = [...candidates];

  sorted.sort((left, right) => {
    switch (sortOption) {
      case "ranked":
        return 0;
      case "name":
        return (left.candidate_name ?? "").localeCompare(right.candidate_name ?? "");
      case "semantic":
        return (right.ranking?.semantic_score ?? 0) - (left.ranking?.semantic_score ?? 0);
      case "keyword":
        return (right.ranking?.keyword_score ?? 0) - (left.ranking?.keyword_score ?? 0);
      case "score":
      default:
        return (right.ranking?.final_score ?? 0) - (left.ranking?.final_score ?? 0);
    }
  });

  return sorted;
}

export function calculateAnalytics(candidates: RankedCandidate[]) {
  const total = candidates.length;
  const topScore = candidates[0]?.ranking?.final_score ?? 0;
  const averageScore =
    total === 0
      ? 0
      : candidates.reduce((sum, candidate) => sum + (candidate.ranking?.final_score ?? 0), 0) /
        total;
  const recommendedCount = candidates.filter((candidate) =>
    ["Highly Recommended", "Recommended"].includes(
      candidate.ranking?.recommendation ?? "",
    ),
  ).length;

  return {
    total,
    topScore,
    averageScore,
    recommendedCount,
  };
}

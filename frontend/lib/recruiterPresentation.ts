import type { EvidenceSnippet, RankedCandidate } from "@/types/recruitment";

const GENERIC_PATTERNS = [
  "validate backend understanding",
  "assess communication",
  "review deployment experience",
  "confirm ability",
  "validate scalability understanding",
  "probe production deployment ownership",
  "assess testing and reliability discipline",
  "technical depth claims need",
  "ownership scope is mentioned lightly",
  "production deployment ownership is not strongly evidenced",
  "direct role alignment is weaker",
  "project-level relevance is not consistently strong",
];

const SOURCE_PRIORITY: Record<string, number> = {
  project: 0,
  experience: 1,
  summary: 2,
  education: 3,
  skills: 4,
  jd: 5,
};

function isGenericInsight(value: string) {
  const lowered = value.toLowerCase();
  return GENERIC_PATTERNS.some((pattern) => lowered.includes(pattern));
}

function isGroundedInsight(value: string) {
  const lowered = value.toLowerCase();
  const hasSpecificMarker =
    /\b(built|shipped|deployed|owned|integrated|implemented|architected|launched|optimized)\b/.test(lowered) ||
    /\b(api|fastapi|react|next\.js|postgresql|docker|aws|llm|retrieval|pipeline|realtime|real-time|synchronization)\b/.test(lowered);

  return hasSpecificMarker && !isGenericInsight(value);
}

export function decisionBand(candidate: RankedCandidate) {
  const recommendation = candidate.ranking?.recommendation;
  if (recommendation === "Highly Recommended") {
    return "Strong fit";
  }
  if (recommendation === "Recommended") {
    return "Recommended";
  }
  if (recommendation === "Consider for Interview") {
    return "Review";
  }
  return "Low match";
}

export function decisionTone(candidate: RankedCandidate) {
  const band = decisionBand(candidate);
  if (band === "Strong fit") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (band === "Recommended") {
    return "border-sky-200 bg-sky-50 text-sky-800";
  }
  if (band === "Review") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

export function mustHaveStatus(candidate: RankedCandidate) {
  const missing = candidate.ranking?.missing_must_haves ?? [];
  const matched = candidate.ranking?.matched_skills?.length ?? 0;
  const total = matched + missing.length;

  if (total === 0 || missing.length === 0) {
    return {
      label: "Must-haves covered",
      tone: "text-emerald-700",
      detail: "",
    };
  }

  return {
    label: `${missing.length} gap${missing.length === 1 ? "" : "s"} to verify`,
    tone: missing.length <= 2 ? "text-amber-700" : "text-rose-700",
    detail: missing.slice(0, 2).join(", "),
  };
}

export function conciseSummary(candidate: RankedCandidate) {
  const summary =
    candidate.ranking?.recruiter_decision_summary ||
    candidate.ranking?.recruiter_summary ||
    "Review the attached evidence before making a decision.";

  return summary.replace(/\s+/g, " ").trim();
}

export function visibleStrengths(candidate: RankedCandidate) {
  return (candidate.ranking?.strengths ?? [])
    .filter(isGroundedInsight)
    .slice(0, 2);
}

export function visibleRisks(candidate: RankedCandidate) {
  return (candidate.ranking?.risks ?? candidate.ranking?.weaknesses ?? [])
    .filter(isGroundedInsight)
    .slice(0, 2);
}

export function visibleInterviewValidations(candidate: RankedCandidate) {
  return (candidate.ranking?.interview_focus_areas ?? [])
    .filter(isGroundedInsight)
    .slice(0, 2);
}

export function strongestEvidence(candidate: RankedCandidate, limit = 1) {
  const snippets = Object.values(candidate.ranking?.supporting_evidence_snippets ?? {})
    .flat()
    .filter(Boolean)
    .filter((snippet) => snippet.source_type !== "skills");

  const seen = new Set<string>();
  return snippets
    .filter((snippet) => {
      const key = `${snippet.source_label}:${snippet.snippet.slice(0, 120)}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    })
    .sort((left, right) => {
      const strengthDelta = strengthValue(right.evidence_strength) - strengthValue(left.evidence_strength);
      if (strengthDelta !== 0) {
        return strengthDelta;
      }
      const sourceDelta = (SOURCE_PRIORITY[left.source_type] ?? 9) - (SOURCE_PRIORITY[right.source_type] ?? 9);
      if (sourceDelta !== 0) {
        return sourceDelta;
      }
      return (right.retrieval_score ?? 0) - (left.retrieval_score ?? 0);
    })
    .slice(0, limit);
}

export function evidencePreview(snippet: EvidenceSnippet, maxLength = 220) {
  const normalized = snippet.snippet.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  const boundary = normalized.lastIndexOf(" ", maxLength);
  return `${normalized.slice(0, boundary > 140 ? boundary : maxLength).trim()}...`;
}

function strengthValue(value: EvidenceSnippet["evidence_strength"]) {
  if (value === "high") {
    return 3;
  }
  if (value === "medium") {
    return 2;
  }
  return 1;
}

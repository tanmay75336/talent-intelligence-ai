"use client";

import { useState } from "react";
import {
  cx,
  formatScore,
  getConfidence,
  getRecommendationTone,
} from "@/lib/utils";
import type { RankedCandidate } from "@/types/recruitment";
import { ScoreBadge } from "@/components/ScoreBadge";

interface CandidateCardProps {
  candidate: RankedCandidate;
  rank: number;
  isTopCandidate?: boolean;
  hiddenGem?: boolean;
  animationDelayMs?: number;
}

function MetricBar({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: string;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 text-sm">
        <span className="text-slate-400">{label}</span>
        <span className="font-medium text-slate-100">{formatScore(value)} / 100</span>
      </div>
      <div className="h-2 rounded-full bg-slate-900/80">
        <div
          className={cx("h-2 rounded-full", tone)}
          style={{ width: `${Math.max(0, Math.min(value, 100))}%` }}
        />
      </div>
    </div>
  );
}

export function CandidateCard({
  candidate,
  rank,
  isTopCandidate = false,
  hiddenGem = false,
  animationDelayMs = 0,
}: CandidateCardProps) {
  const [isExpanded, setIsExpanded] = useState(rank <= 2);
  const confidence = getConfidence(candidate);

  return (
    <article
      className={cx(
        "card-surface animate-fade-up overflow-hidden border px-5 py-5 sm:px-6",
        isTopCandidate
          ? "border-sky-400/30 bg-[linear-gradient(180deg,rgba(12,28,48,0.96),rgba(8,18,32,0.96))]"
          : "border-slate-700/60",
      )}
      style={{ animationDelay: `${animationDelayMs}ms` }}
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full border border-slate-700/70 bg-slate-950/60 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-slate-300">
              Rank #{rank}
            </span>
            {isTopCandidate ? (
              <span className="rounded-full border border-sky-400/30 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-200">
                Top candidate
              </span>
            ) : null}
            {hiddenGem ? (
              <span className="rounded-full border border-amber-400/25 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-200">
                Hidden gem
              </span>
            ) : null}
            <span
              className={cx(
                "rounded-full border px-3 py-1 text-xs font-medium",
                getRecommendationTone(candidate.ranking?.recommendation),
              )}
            >
              {candidate.ranking?.recommendation ?? "Awaiting recommendation"}
            </span>
            <span
              className={cx(
                "rounded-full border px-3 py-1 text-xs font-medium",
                confidence.tone,
              )}
            >
              {confidence.label}
            </span>
          </div>

          <div className="mt-4">
            <h3 className="truncate text-2xl font-semibold text-slate-50">
              {candidate.candidate_name || "Unnamed candidate"}
            </h3>
            <p className="mt-2 text-sm text-slate-400">
              Source file: {candidate.resume_file ?? "Uploaded document"}
            </p>
          </div>
        </div>

        <ScoreBadge score={candidate.ranking?.final_score} />
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-[1.3fr_0.9fr]">
        <div className="space-y-5">
          <div>
            <p className="text-sm font-medium text-slate-300">Detected skills</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {candidate.candidate_skills?.length ? (
                candidate.candidate_skills.map((skill) => (
                  <span
                    key={skill}
                    className="rounded-full border border-slate-700/70 bg-slate-950/45 px-3 py-1.5 text-sm text-slate-200"
                  >
                    {skill}
                  </span>
                ))
              ) : (
                <span className="text-sm text-slate-500">No candidate skills extracted.</span>
              )}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-slate-700/60 bg-slate-950/35 p-4">
              <p className="text-sm font-medium text-slate-200">Strengths</p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-400">
                {candidate.ranking?.strengths?.length ? (
                  candidate.ranking.strengths.map((strength) => (
                    <li key={strength} className="flex gap-2">
                      <span className="mt-2 h-1.5 w-1.5 rounded-full bg-emerald-300" />
                      <span>{strength}</span>
                    </li>
                  ))
                ) : (
                  <li className="text-slate-500">No strengths generated.</li>
                )}
              </ul>
            </div>

            <div className="rounded-2xl border border-slate-700/60 bg-slate-950/35 p-4">
              <p className="text-sm font-medium text-slate-200">Weaknesses</p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-400">
                {candidate.ranking?.weaknesses?.length ? (
                  candidate.ranking.weaknesses.map((weakness) => (
                    <li key={weakness} className="flex gap-2">
                      <span className="mt-2 h-1.5 w-1.5 rounded-full bg-rose-300" />
                      <span>{weakness}</span>
                    </li>
                  ))
                ) : (
                  <li className="text-slate-500">No weaknesses generated.</li>
                )}
              </ul>
            </div>
          </div>

          {isExpanded ? (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-slate-700/60 bg-slate-950/35 p-4">
                <p className="text-sm font-medium text-slate-200">Matched skills</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {candidate.ranking?.matched_skills?.length ? (
                    candidate.ranking.matched_skills.map((skill) => (
                      <span
                        key={skill}
                        className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-1 text-sm text-emerald-100"
                      >
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span className="text-sm text-slate-500">No direct skill overlap detected.</span>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-700/60 bg-slate-950/35 p-4">
                <p className="text-sm font-medium text-slate-200">Missing skills</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {candidate.ranking?.missing_skills?.length ? (
                    candidate.ranking.missing_skills.map((skill) => (
                      <span
                        key={skill}
                        className="rounded-full border border-rose-400/20 bg-rose-500/10 px-3 py-1 text-sm text-rose-100"
                      >
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span className="text-sm text-slate-500">No missing skills detected.</span>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-700/60 bg-slate-950/35 p-4 md:col-span-2">
                <p className="text-sm font-medium text-slate-200">Transferable skill insights</p>
                <div className="mt-3 space-y-2 text-sm text-slate-400">
                  {candidate.ranking?.adjacent_matches?.length ? (
                    candidate.ranking.adjacent_matches.map((match) => (
                      <div
                        key={`${match.missing_skill}-${match.related_skill}`}
                        className="rounded-2xl border border-slate-700/60 bg-slate-900/50 px-4 py-3"
                      >
                        <span className="text-slate-200">{match.related_skill}</span> may
                        transfer into <span className="text-slate-200">{match.missing_skill}</span>.
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-500">
                      No adjacent or transferable skill signals were detected for this profile.
                    </p>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/35 p-4">
            <p className="text-sm font-medium text-slate-200">Scoring breakdown</p>
            <div className="mt-4 space-y-4">
              <MetricBar
                label="Semantic score"
                tone="bg-sky-400"
                value={candidate.ranking?.semantic_score ?? 0}
              />
              <MetricBar
                label="Keyword score"
                tone="bg-emerald-400"
                value={candidate.ranking?.keyword_score ?? 0}
              />
            </div>
            <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/50 px-4 py-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">Adjacency bonus</span>
                <span className="font-medium text-slate-100">
                  +{formatScore(candidate.ranking?.adjacency_bonus ?? 0)}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/35 p-4">
            <p className="text-sm font-medium text-slate-200">Recruiter brief</p>
            <p className="mt-3 text-sm leading-7 text-slate-400">
              {candidate.ranking?.recruiter_summary ??
                (candidate.ranking?.recommendation === "Highly Recommended"
                ? "Strong overall alignment with the role. Prioritize for review and shortlist quickly."
                : candidate.ranking?.recommendation === "Recommended"
                  ? "Solid candidate with meaningful overlap and promising role fit."
                  : candidate.ranking?.recommendation === "Consider for Interview"
                    ? "Worth exploring for fit, especially if the team values adjacent skill transfer."
                    : "Lower direct fit. Review only if the role has flexibility or volume needs.")}
            </p>
          </div>

          <button
            className="w-full rounded-2xl border border-slate-700/70 bg-slate-950/50 px-4 py-3 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:text-white"
            type="button"
            onClick={() => setIsExpanded((current) => !current)}
          >
            {isExpanded ? "Collapse details" : "Expand details"}
          </button>
        </div>
      </div>
    </article>
  );
}

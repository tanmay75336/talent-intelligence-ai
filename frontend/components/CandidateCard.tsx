"use client";

import { memo } from "react";
import {
  conciseSummary,
  decisionBand,
  decisionTone,
  evidencePreview,
  mustHaveStatus,
  strongestEvidence,
  visibleRisks,
  visibleStrengths,
} from "@/lib/recruiterPresentation";
import { cx } from "@/lib/utils";
import type { RankedCandidate } from "@/types/recruitment";

interface CandidateCardProps {
  candidate: RankedCandidate;
  rank: number;
  selected?: boolean;
  onOpen: () => void;
  onCompare?: () => void;
  onMoveToPipeline?: () => void;
}

function CandidateCardComponent({
  candidate,
  rank,
  selected = false,
  onOpen,
  onCompare,
  onMoveToPipeline,
}: CandidateCardProps) {
  const mustHave = mustHaveStatus(candidate);
  const evidence = strongestEvidence(candidate, 1)[0];
  const risks = visibleRisks(candidate);
  const strengths = visibleStrengths(candidate);

  return (
    <article
      className={cx(
        "rounded-lg border bg-white p-4 shadow-sm transition hover:border-slate-300 hover:shadow-md",
        selected ? "border-slate-900" : "border-slate-200",
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-slate-500">#{rank}</span>
            <span className={cx("rounded-full border px-2.5 py-1 text-xs font-medium", decisionTone(candidate))}>
              {decisionBand(candidate)}
            </span>
            <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700">
              Score {Math.round(candidate.ranking?.final_score ?? 0)}
            </span>
            <span className={cx("text-xs font-medium", mustHave.tone)}>
              {mustHave.label}
            </span>
          </div>
          <h3 className="mt-2 truncate text-lg font-semibold text-slate-950">
            {candidate.candidate_name || "Unnamed candidate"}
          </h3>
          <p className="mt-1 truncate text-sm text-slate-500">
            {candidate.resume_file ?? "Uploaded resume"}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {onMoveToPipeline ? (
            <button
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              type="button"
              onClick={onMoveToPipeline}
            >
              Shortlist
            </button>
          ) : null}
          {onCompare ? (
            <button
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              type="button"
              onClick={onCompare}
            >
              Compare
            </button>
          ) : null}
          <button
            className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700"
            type="button"
            onClick={onOpen}
          >
            Review
          </button>
        </div>
      </div>

      <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-700">
        {conciseSummary(candidate)}
      </p>

      <div className="mt-4 grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Strongest evidence
          </p>
          {evidence ? (
            <>
              <p className="mt-2 text-sm leading-6 text-slate-700">
                {evidencePreview(evidence)}
              </p>
              <p className="mt-2 text-xs text-slate-500">
                {evidence.source_type} · {evidence.source_label}
              </p>
            </>
          ) : (
            <p className="mt-2 text-sm text-slate-500">No strong evidence surfaced.</p>
          )}
        </div>

        <div className="space-y-3">
          {strengths.length ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Strengths</p>
              <ul className="mt-1 space-y-1 text-sm leading-6 text-slate-700">
                {strengths.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {risks.length ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Risks</p>
              <ul className="mt-1 space-y-1 text-sm leading-6 text-slate-700">
                {risks.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {!strengths.length && !risks.length ? (
            <p className="text-sm text-slate-500">
              No differentiated insight strong enough to show.
            </p>
          ) : null}
        </div>
      </div>
    </article>
  );
}

export const CandidateCard = memo(CandidateCardComponent);

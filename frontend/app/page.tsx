"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { AnalyticsPanel } from "@/components/AnalyticsPanel";
import { CandidateCard } from "@/components/CandidateCard";
import { Header } from "@/components/Header";
import { UploadZone } from "@/components/UploadZone";
import {
  getRankingRunResults,
  listRankingRuns,
  rankDatasetCandidates,
  uploadAndRankCandidates,
} from "@/lib/api";
import {
  conciseSummary,
  decisionBand,
  decisionTone,
  evidencePreview,
  mustHaveStatus,
  strongestEvidence,
  visibleInterviewValidations,
  visibleRisks,
  visibleStrengths,
} from "@/lib/recruiterPresentation";
import { cx, getCandidateKey, sortCandidates } from "@/lib/utils";
import type { EvidenceSnippet, RankedCandidate, RankingRunSummary, SortOption } from "@/types/recruitment";

type View = "dashboard" | "new-analysis" | "candidates" | "detail" | "comparison" | "saved-runs" | "pipeline";
type PipelineStatus = "Review" | "Shortlisted" | "Interview" | "Rejected";

const NAV_ITEMS: Array<{ id: View; label: string }> = [
  { id: "dashboard", label: "Dashboard" },
  { id: "new-analysis", label: "New Analysis" },
  { id: "candidates", label: "Candidate List" },
  { id: "comparison", label: "Comparison" },
  { id: "saved-runs", label: "Saved Runs" },
  { id: "pipeline", label: "Pipeline" },
];

const SORT_OPTIONS: Array<{ label: string; value: SortOption }> = [
  { label: "Recommended order", value: "ranked" },
  { label: "Fit band", value: "score" },
  { label: "Candidate name", value: "name" },
];

function formatRunDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Saved run";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function SectionHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description?: string;
}) {
  return (
    <div>
      <p className="section-label">{eyebrow}</p>
      <h2 className="mt-2 text-2xl font-semibold text-slate-950">{title}</h2>
      {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{description}</p> : null}
    </div>
  );
}

function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
      <h3 className="text-lg font-semibold text-slate-950">{title}</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

function EvidenceBlock({ snippet }: { snippet: EvidenceSnippet }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          {snippet.source_type} · {snippet.source_label}
        </p>
        <span className="text-xs text-slate-500">{snippet.evidence_strength} evidence</span>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-700">{evidencePreview(snippet, 320)}</p>
    </div>
  );
}

function CandidateDetail({
  candidate,
  rank,
  status,
  onStatusChange,
}: {
  candidate: RankedCandidate;
  rank: number;
  status: PipelineStatus;
  onStatusChange: (status: PipelineStatus) => void;
}) {
  const mustHave = mustHaveStatus(candidate);
  const evidence = strongestEvidence(candidate, 4);
  const strengths = visibleStrengths(candidate);
  const risks = visibleRisks(candidate);
  const validations = visibleInterviewValidations(candidate);

  return (
    <section className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-slate-500">Rank {rank}</span>
              <span className={cx("rounded-full border px-2.5 py-1 text-xs font-medium", decisionTone(candidate))}>
                {decisionBand(candidate)}
              </span>
              <span className={cx("text-sm font-medium", mustHave.tone)}>{mustHave.label}</span>
            </div>
            <h2 className="mt-3 text-3xl font-semibold text-slate-950">
              {candidate.candidate_name || "Unnamed candidate"}
            </h2>
            <p className="mt-1 text-sm text-slate-500">{candidate.resume_file ?? "Uploaded resume"}</p>
          </div>

          <div className="flex flex-wrap gap-2">
            {(["Review", "Shortlisted", "Interview", "Rejected"] as PipelineStatus[]).map((nextStatus) => (
              <button
                key={nextStatus}
                className={cx(
                  "rounded-md border px-3 py-2 text-sm font-medium",
                  status === nextStatus
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
                )}
                type="button"
                onClick={() => onStatusChange(nextStatus)}
              >
                {nextStatus}
              </button>
            ))}
          </div>
        </div>

        <p className="mt-5 max-w-4xl text-base leading-7 text-slate-700">{conciseSummary(candidate)}</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <SectionHeader
            eyebrow="Evidence"
            title="Best supporting evidence"
            description="Highest-value snippets are prioritized over skill inventories and repeated text."
          />
          <div className="mt-5 space-y-3">
            {evidence.length ? (
              evidence.map((snippet, index) => <EvidenceBlock key={`${snippet.evidence_id}-${index}`} snippet={snippet} />)
            ) : (
              <p className="text-sm text-slate-500">No strong evidence available for this candidate.</p>
            )}
          </div>
        </div>

        <div className="space-y-5">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <SectionHeader eyebrow="Decision Notes" title="What matters" />
            <div className="mt-4 space-y-4">
              {strengths.length ? (
                <InsightGroup title="Strengths" items={strengths} />
              ) : null}
              {risks.length ? (
                <InsightGroup title="Risks" items={risks} />
              ) : null}
              {validations.length ? (
                <InsightGroup title="Interview validation" items={validations} />
              ) : null}
              {!strengths.length && !risks.length && !validations.length ? (
                <p className="text-sm leading-6 text-slate-500">
                  No resume-grounded insight strong enough to surface. Review evidence directly.
                </p>
              ) : null}
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <SectionHeader eyebrow="Must-Haves" title={mustHave.label} />
            {mustHave.detail ? <p className="mt-3 text-sm leading-6 text-slate-700">{mustHave.detail}</p> : null}
            <div className="mt-4 flex flex-wrap gap-2">
              {(candidate.ranking?.matched_skills ?? []).slice(0, 8).map((skill) => (
                <span key={skill} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-700">
                  {skill}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function InsightGroup({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
        {items.slice(0, 2).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default function HomePage() {
  const [view, setView] = useState<View>("dashboard");
  const [jdText, setJdText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [candidates, setCandidates] = useState<RankedCandidate[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [compareAId, setCompareAId] = useState<string | null>(null);
  const [compareBId, setCompareBId] = useState<string | null>(null);
  const [sortOption, setSortOption] = useState<SortOption>("ranked");
  const [rankingRuns, setRankingRuns] = useState<RankingRunSummary[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [resultContext, setResultContext] = useState("");
  const [pipelineStatus, setPipelineStatus] = useState<Record<string, PipelineStatus>>({});
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [progressMessage, setProgressMessage] = useState("");

  useEffect(() => {
    void refreshRankingRuns();
  }, []);

  const candidateIds = useMemo(
    () =>
      new Map(
        candidates.map((candidate, index) => [
          candidate,
          getCandidateKey(candidate, index),
        ]),
      ),
    [candidates],
  );

  const candidatesById = useMemo(() => {
    const entries = candidates.map((candidate) => [candidateIds.get(candidate), candidate] as const);
    return new Map(entries.filter((entry): entry is [string, RankedCandidate] => Boolean(entry[0])));
  }, [candidateIds, candidates]);

  const sortedCandidates = useMemo(() => sortCandidates(candidates, sortOption), [candidates, sortOption]);
  const selectedCandidate = selectedCandidateId ? candidatesById.get(selectedCandidateId) : undefined;
  const selectedRank = selectedCandidate ? candidates.indexOf(selectedCandidate) + 1 : 0;
  const compareA = compareAId ? candidatesById.get(compareAId) : undefined;
  const compareB = compareBId ? candidatesById.get(compareBId) : undefined;

  const shortlistedCount = Object.values(pipelineStatus).filter((status) => status === "Shortlisted").length;
  const interviewCount = Object.values(pipelineStatus).filter((status) => status === "Interview").length;

  const openCandidate = (candidate: RankedCandidate, index: number) => {
    const id = candidateIds.get(candidate) ?? getCandidateKey(candidate, index);
    setSelectedCandidateId(id);
    setView("detail");
  };

  const appendFiles = (incomingFiles: File[]) => {
    if (!incomingFiles.length) {
      return;
    }

    setFiles((current) => {
      const nextFiles = [...current];
      incomingFiles.forEach((incomingFile) => {
        const exists = nextFiles.some(
          (file) =>
            file.name === incomingFile.name &&
            file.size === incomingFile.size &&
            file.lastModified === incomingFile.lastModified,
        );
        if (!exists) {
          nextFiles.push(incomingFile);
        }
      });
      return nextFiles;
    });
  };

  const removeFile = (fileName: string) => {
    setFiles((current) => current.filter((file) => file.name !== fileName));
  };

  const refreshRankingRuns = async () => {
    try {
      const runs = await listRankingRuns();
      setRankingRuns(runs);
    } catch {
      setRankingRuns([]);
    }
  };

  const handleOpenHistoricalRun = async (runId: string) => {
    setHistoryLoading(true);
    setErrorMessage("");
    setProgressMessage("Loading saved review...");

    try {
      const response = await getRankingRunResults(runId);
      const reopenedCandidates = response.ranked_candidates ?? [];
      setCandidates(reopenedCandidates);
      setActiveRunId(runId);
      setResultContext(`${response.total_candidates} candidates reopened from ${response.run?.role_title ?? "saved run"}.`);
      setSelectedCandidateId(reopenedCandidates[0] ? getCandidateKey(reopenedCandidates[0], 0) : null);
      setCompareAId(reopenedCandidates[0] ? getCandidateKey(reopenedCandidates[0], 0) : null);
      setCompareBId(reopenedCandidates[1] ? getCandidateKey(reopenedCandidates[1], 1) : null);
      setView("candidates");
      setProgressMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load saved ranking history.");
      setProgressMessage("");
    } finally {
      setHistoryLoading(false);
    }
  };

  const applyRankingResponse = (
    rankedCandidates: RankedCandidate[],
    context: string,
    rankingRunId?: string | null,
  ) => {
    setCandidates(rankedCandidates);
    setActiveRunId(rankingRunId ?? null);
    setResultContext(context);
    setSelectedCandidateId(rankedCandidates[0] ? getCandidateKey(rankedCandidates[0], 0) : null);
    setCompareAId(rankedCandidates[0] ? getCandidateKey(rankedCandidates[0], 0) : null);
    setCompareBId(rankedCandidates[1] ? getCandidateKey(rankedCandidates[1], 1) : null);
    setPipelineStatus({});
    setSortOption("ranked");
    setView("candidates");
    void refreshRankingRuns();
  };

  const handleAnalyzeCandidates = async () => {
    if (!jdText.trim()) {
      setErrorMessage("Paste a job description before running candidate analysis.");
      return;
    }
    if (!files.length) {
      setErrorMessage("Upload at least one PDF resume before running candidate analysis.");
      return;
    }

    setLoading(true);
    setErrorMessage("");
    setProgressMessage("Preparing candidate review...");

    try {
      const response = await uploadAndRankCandidates(files, jdText.trim());
      const rankedCandidates = response.ranked_candidates ?? [];
      if (!rankedCandidates.length) {
        setErrorMessage(response.processing_errors?.[0] ?? "No readable candidates were ranked.");
        setProgressMessage("");
      } else {
        applyRankingResponse(
          rankedCandidates,
          `${response.total_candidates} uploaded resumes reviewed.`,
          response.ranking_run_id,
        );
        setProgressMessage("");
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to connect to the ranking service.");
      setProgressMessage("");
    } finally {
      setLoading(false);
    }
  };

  const handleRankDataset = async () => {
    if (!jdText.trim()) {
      setErrorMessage("Paste a job description before ranking the dataset.");
      return;
    }

    setLoading(true);
    setErrorMessage("");
    setProgressMessage("Preparing sample candidate review...");

    try {
      const response = await rankDatasetCandidates(jdText.trim());
      const rankedCandidates = response.ranked_candidates ?? [];
      if (!rankedCandidates.length && response.processing_errors?.length) {
        setErrorMessage(response.processing_errors[0]);
        setProgressMessage("");
      } else {
        applyRankingResponse(
          rankedCandidates,
          `${response.dataset_size} sample resumes reviewed.`,
          response.ranking_run_id,
        );
        setProgressMessage("");
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to rank the backend dataset.");
      setProgressMessage("");
    } finally {
      setLoading(false);
    }
  };

  const setCandidateStatus = (candidateId: string, status: PipelineStatus) => {
    setPipelineStatus((current) => ({ ...current, [candidateId]: status }));
  };

  return (
    <main className="shell">
      <Header />

      <nav className="mt-6 rounded-lg border border-slate-200 bg-white p-2 shadow-sm">
        <div className="flex gap-1 overflow-x-auto">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={cx(
                "shrink-0 rounded-md px-3 py-2 text-sm font-medium",
                view === item.id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
              )}
              type="button"
              onClick={() => setView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </nav>

      {errorMessage ? (
        <div className="mt-5 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {errorMessage}
        </div>
      ) : null}

      {progressMessage ? (
        <div className="mt-5 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          {progressMessage}
        </div>
      ) : null}

      <div className="mt-8">
        {view === "dashboard" ? (
          <section className="space-y-6">
            <SectionHeader
              eyebrow="Dashboard"
              title="Recruiter review workspace"
              description="Start a new analysis, reopen saved work, or continue reviewing candidates without exposing ranking internals."
            />
            <AnalyticsPanel candidates={candidates} />
            <div className="grid gap-5 lg:grid-cols-3">
              <DashboardCard label="Current slate" value={candidates.length} detail={resultContext || "No active review loaded"} />
              <DashboardCard label="Shortlisted" value={shortlistedCount} detail="Local workflow state for this session" />
              <DashboardCard label="Interviews" value={interviewCount} detail="Candidates moved to interview review" />
            </div>
            <div className="grid gap-5 lg:grid-cols-2">
              <ActionPanel
                title="Run a new review"
                description="Upload resumes and review a role-specific candidate list."
                actionLabel="New Analysis"
                onClick={() => setView("new-analysis")}
              />
              <ActionPanel
                title="Continue saved work"
                description={`${rankingRuns.length} saved run${rankingRuns.length === 1 ? "" : "s"} available locally.`}
                actionLabel="Open Saved Runs"
                onClick={() => setView("saved-runs")}
              />
            </div>
          </section>
        ) : null}

        {view === "new-analysis" ? (
          <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <SectionHeader
                eyebrow="New Analysis"
                title="Define the target role"
                description="Paste the role brief, must-haves, and context. The backend ranking remains deterministic; this screen keeps setup separate from review."
              />
              <textarea
                className="mt-5 h-[340px] w-full resize-none rounded-md border border-slate-300 bg-white px-4 py-3 text-sm leading-7 text-slate-900 outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                placeholder="Paste the job description here."
                value={jdText}
                onChange={(event) => setJdText(event.target.value)}
              />
              <p className="mt-3 text-sm text-slate-500">{jdText.trim().length} characters entered</p>
            </div>

            <div className="space-y-5">
              <UploadZone disabled={loading} files={files} onAddFiles={appendFiles} onRemoveFile={removeFile} />
              <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                <SectionHeader eyebrow="Run" title="Prepare review" />
                <div className="mt-5 space-y-3">
                  <button
                    className={cx(
                      "w-full rounded-md px-4 py-3 text-sm font-medium",
                      loading || !jdText.trim() || !files.length
                        ? "cursor-not-allowed bg-slate-200 text-slate-500"
                        : "bg-slate-900 text-white hover:bg-slate-700",
                    )}
                    disabled={loading || !jdText.trim() || !files.length}
                    type="button"
                    onClick={handleAnalyzeCandidates}
                  >
                    {loading ? "Preparing review" : "Analyze uploaded resumes"}
                  </button>
                  <button
                    className={cx(
                      "w-full rounded-md border px-4 py-3 text-sm font-medium",
                      loading || !jdText.trim()
                        ? "cursor-not-allowed border-slate-200 text-slate-400"
                        : "border-slate-300 text-slate-700 hover:bg-slate-50",
                    )}
                    disabled={loading || !jdText.trim()}
                    type="button"
                    onClick={handleRankDataset}
                  >
                    Review sample dataset
                  </button>
                </div>
              </div>
            </div>
          </section>
        ) : null}

        {view === "candidates" ? (
          <section className="space-y-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <SectionHeader
                eyebrow="Candidate List"
                title="Review candidates"
                description={resultContext || "Load or run an analysis to see candidates."}
              />
              <label className="flex flex-col gap-2 text-sm text-slate-600">
                Sort
                <select
                  className="rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900"
                  value={sortOption}
                  onChange={(event) => setSortOption(event.target.value as SortOption)}
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {sortedCandidates.length ? (
              <div className="space-y-4">
                {sortedCandidates.map((candidate, index) => {
                  const candidateId = candidateIds.get(candidate) ?? getCandidateKey(candidate, index);
                  return (
                    <CandidateCard
                      key={candidateId}
                      candidate={candidate}
                      rank={candidates.indexOf(candidate) + 1}
                      selected={candidateId === selectedCandidateId}
                      onOpen={() => openCandidate(candidate, index)}
                      onCompare={() => {
                        if (!compareAId || compareAId === candidateId) {
                          setCompareAId(candidateId);
                        } else {
                          setCompareBId(candidateId);
                        }
                        setView("comparison");
                      }}
                      onMoveToPipeline={() => setCandidateStatus(candidateId, "Shortlisted")}
                    />
                  );
                })}
              </div>
            ) : (
              <EmptyState
                title="No candidate review loaded"
                description="Start a new analysis or reopen a saved run."
                action={
                  <button className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white" type="button" onClick={() => setView("new-analysis")}>
                    New Analysis
                  </button>
                }
              />
            )}
          </section>
        ) : null}

        {view === "detail" ? (
          selectedCandidate && selectedCandidateId ? (
            <CandidateDetail
              candidate={selectedCandidate}
              rank={selectedRank}
              status={pipelineStatus[selectedCandidateId] ?? "Review"}
              onStatusChange={(status) => setCandidateStatus(selectedCandidateId, status)}
            />
          ) : (
            <EmptyState
              title="No candidate selected"
              description="Open a candidate from the list to review focused evidence and decision notes."
              action={
                <button className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white" type="button" onClick={() => setView("candidates")}>
                  Candidate List
                </button>
              }
            />
          )
        ) : null}

        {view === "comparison" ? (
          <section className="space-y-5">
            <SectionHeader
              eyebrow="Comparison"
              title="Compare two finalists"
              description="Use comparison only for close calls. This view summarizes evidence; it does not rerank candidates."
            />
            {candidates.length >= 2 ? (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <CandidateSelect label="Candidate A" value={compareAId ?? ""} candidates={candidates} candidateIds={candidateIds} onChange={setCompareAId} />
                  <CandidateSelect label="Candidate B" value={compareBId ?? ""} candidates={candidates} candidateIds={candidateIds} onChange={setCompareBId} />
                </div>
                <div className="grid gap-5 lg:grid-cols-2">
                  <ComparisonSide candidate={compareA} label="Candidate A" />
                  <ComparisonSide candidate={compareB} label="Candidate B" />
                </div>
              </>
            ) : (
              <EmptyState title="Comparison needs two candidates" description="Run or reopen a review with at least two candidates." />
            )}
          </section>
        ) : null}

        {view === "saved-runs" ? (
          <section className="space-y-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <SectionHeader eyebrow="Saved Runs" title="Reopen previous reviews" />
              <button
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                disabled={historyLoading}
                type="button"
                onClick={() => void refreshRankingRuns()}
              >
                Refresh
              </button>
            </div>
            {rankingRuns.length ? (
              <div className="grid gap-4 lg:grid-cols-2">
                {rankingRuns.map((run) => (
                  <button
                    key={run.id}
                    className={cx(
                      "rounded-lg border bg-white p-4 text-left shadow-sm hover:border-slate-300",
                      activeRunId === run.id ? "border-slate-900" : "border-slate-200",
                    )}
                    disabled={historyLoading}
                    type="button"
                    onClick={() => void handleOpenHistoricalRun(run.id)}
                  >
                    <p className="font-semibold text-slate-950">{run.role_title || "Saved role"}</p>
                    <p className="mt-1 text-sm text-slate-500">
                      {formatRunDate(run.created_at)} · {run.result_count} candidates
                    </p>
                    <p className="mt-3 text-sm text-slate-600">Open preserved candidate order and evidence.</p>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState title="No saved runs yet" description="Completed analyses are saved locally by the backend." />
            )}
          </section>
        ) : null}

        {view === "pipeline" ? (
          <section className="space-y-5">
            <SectionHeader
              eyebrow="Pipeline"
              title="Recruiter workflow"
              description="Operational status is local to this browser session in the current MVP."
            />
            {candidates.length ? (
              <div className="grid gap-4 lg:grid-cols-4">
                {(["Review", "Shortlisted", "Interview", "Rejected"] as PipelineStatus[]).map((status) => (
                  <PipelineColumn
                    key={status}
                    status={status}
                    candidates={candidates}
                    candidateIds={candidateIds}
                    statuses={pipelineStatus}
                    onOpen={(candidate, index) => openCandidate(candidate, index)}
                  />
                ))}
              </div>
            ) : (
              <EmptyState title="No active pipeline" description="Run or reopen a review before moving candidates through workflow." />
            )}
          </section>
        ) : null}
      </div>
    </main>
  );
}

function DashboardCard({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-950">{value}</p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{detail}</p>
    </div>
  );
}

function ActionPanel({
  title,
  description,
  actionLabel,
  onClick,
}: {
  title: string;
  description: string;
  actionLabel: string;
  onClick: () => void;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-950">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
      <button className="mt-5 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700" type="button" onClick={onClick}>
        {actionLabel}
      </button>
    </div>
  );
}

function CandidateSelect({
  label,
  value,
  candidates,
  candidateIds,
  onChange,
}: {
  label: string;
  value: string;
  candidates: RankedCandidate[];
  candidateIds: Map<RankedCandidate, string>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
      <span className="font-medium text-slate-700">{label}</span>
      <select
        className="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Select candidate</option>
        {candidates.map((candidate, index) => {
          const id = candidateIds.get(candidate) ?? getCandidateKey(candidate, index);
          return (
            <option key={id} value={id}>
              {candidate.candidate_name || "Unnamed candidate"}
            </option>
          );
        })}
      </select>
    </label>
  );
}

function ComparisonSide({ candidate, label }: { candidate?: RankedCandidate; label: string }) {
  const evidence = candidate ? strongestEvidence(candidate, 2) : [];
  const risks = candidate ? visibleRisks(candidate) : [];

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      {candidate ? (
        <>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <h3 className="text-xl font-semibold text-slate-950">{candidate.candidate_name}</h3>
            <span className={cx("rounded-full border px-2.5 py-1 text-xs font-medium", decisionTone(candidate))}>
              {decisionBand(candidate)}
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-700">{conciseSummary(candidate)}</p>
          <div className="mt-5 space-y-3">
            {evidence.map((snippet, index) => (
              <EvidenceBlock key={`${snippet.evidence_id}-${index}`} snippet={snippet} />
            ))}
          </div>
          {risks.length ? <InsightGroup title="Risks to validate" items={risks} /> : null}
        </>
      ) : (
        <p className="mt-3 text-sm text-slate-500">Select a candidate to compare.</p>
      )}
    </div>
  );
}

function PipelineColumn({
  status,
  candidates,
  candidateIds,
  statuses,
  onOpen,
}: {
  status: PipelineStatus;
  candidates: RankedCandidate[];
  candidateIds: Map<RankedCandidate, string>;
  statuses: Record<string, PipelineStatus>;
  onOpen: (candidate: RankedCandidate, index: number) => void;
}) {
  const visible = candidates.filter((candidate, index) => {
    const id = candidateIds.get(candidate) ?? getCandidateKey(candidate, index);
    return (statuses[id] ?? "Review") === status;
  });

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">{status}</h3>
        <span className="text-xs text-slate-500">{visible.length}</span>
      </div>
      <div className="mt-3 space-y-2">
        {visible.map((candidate, index) => (
          <button
            key={`${status}-${candidateIds.get(candidate) ?? getCandidateKey(candidate, index)}`}
            className="w-full rounded-md border border-slate-200 bg-white p-3 text-left text-sm shadow-sm hover:border-slate-300"
            type="button"
            onClick={() => onOpen(candidate, candidates.indexOf(candidate))}
          >
            <span className="block font-medium text-slate-950">{candidate.candidate_name || "Unnamed candidate"}</span>
            <span className="mt-1 block text-xs text-slate-500">{decisionBand(candidate)}</span>
          </button>
        ))}
        {!visible.length ? <p className="rounded-md border border-dashed border-slate-300 p-3 text-sm text-slate-500">Empty</p> : null}
      </div>
    </div>
  );
}

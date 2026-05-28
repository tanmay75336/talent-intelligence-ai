"use client";

import { useEffect, useRef, useState } from "react";
import { AnalyticsPanel } from "@/components/AnalyticsPanel";
import { CandidateCard } from "@/components/CandidateCard";
import { Header } from "@/components/Header";
import { UploadZone } from "@/components/UploadZone";
import { rankDatasetCandidates, uploadAndRankCandidates } from "@/lib/api";
import {
  cx,
  getCandidateKey,
  isHiddenGem,
  sortCandidates,
} from "@/lib/utils";
import type { RankedCandidate, SortOption } from "@/types/recruitment";

const SORT_OPTIONS: Array<{ label: string; value: SortOption }> = [
  { label: "Final score", value: "score" },
  { label: "Semantic score", value: "semantic" },
  { label: "Keyword score", value: "keyword" },
  { label: "Candidate name", value: "name" },
];

export default function HomePage() {
  const [jdText, setJdText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [candidates, setCandidates] = useState<RankedCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [progressMessage, setProgressMessage] = useState("");
  const [sortOption, setSortOption] = useState<SortOption>("score");
  const [recommendationFilter, setRecommendationFilter] = useState("All");
  const [resultContext, setResultContext] = useState("");

  const leaderboardRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (candidates.length > 0) {
      leaderboardRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }, [candidates]);

  const recommendationOptions = [
    "All",
    ...Array.from(
      new Set(
        candidates
          .map((candidate) => candidate.ranking?.recommendation)
          .filter(Boolean),
      ),
    ),
  ];

  const sortedCandidates = sortCandidates(candidates, sortOption);
  const filteredCandidates =
    recommendationFilter === "All"
      ? sortedCandidates
      : sortedCandidates.filter(
          (candidate) =>
            (candidate.ranking?.recommendation ?? "") === recommendationFilter,
        );
  const topCandidateName = sortCandidates(candidates, "score")[0]?.candidate_name;

  const appendFiles = (incomingFiles: File[]) => {
    if (!incomingFiles.length) {
      return;
    }

    setFiles((current) => {
      const deduped = [...current];

      incomingFiles.forEach((incomingFile) => {
        const exists = deduped.some(
          (file) =>
            file.name === incomingFile.name &&
            file.size === incomingFile.size &&
            file.lastModified === incomingFile.lastModified,
        );

        if (!exists) {
          deduped.push(incomingFile);
        }
      });

      return deduped;
    });
  };

  const removeFile = (fileName: string) => {
    setFiles((current) => current.filter((file) => file.name !== fileName));
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
    setProgressMessage("Uploading resumes and running AI ranking...");

    try {
      const response = await uploadAndRankCandidates(files, jdText.trim());
      const rankedCandidates = response.ranked_candidates ?? [];
      setCandidates(rankedCandidates);
      setResultContext(`${response.total_candidates} resumes ranked from uploaded PDFs.`);
      setRecommendationFilter("All");
      setSortOption("score");
      if (rankedCandidates.length === 0) {
        const backendError = response.processing_errors?.[0];
        setErrorMessage(
          backendError ??
            "The API responded, but no candidates were ranked. Make sure the uploaded PDFs contain readable text.",
        );
        setProgressMessage("");
      } else {
        setProgressMessage("Ranking complete. Leaderboard ready for recruiter review.");
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to connect to the ranking service.",
      );
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
    setProgressMessage("Ranking the backend dataset against the current job description...");

    try {
      const response = await rankDatasetCandidates(jdText.trim());
      setCandidates(response.ranked_candidates ?? []);
      setResultContext(`${response.dataset_size} dataset resumes ranked from the backend sample set.`);
      setRecommendationFilter("All");
      setSortOption("score");
      if ((response.ranked_candidates ?? []).length === 0 && response.processing_errors?.length) {
        setErrorMessage(response.processing_errors[0]);
        setProgressMessage("");
      } else {
        setProgressMessage("Dataset ranking complete. Review the leaderboard below.");
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to rank the backend dataset.",
      );
      setProgressMessage("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="shell">
      <Header />

      <section className="mt-8 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="card-surface animate-fade-up px-6 py-6 sm:px-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="section-label">Job Description</p>
              <h2 className="mt-3 text-2xl font-semibold text-slate-50">
                Define the target role
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                Paste the hiring brief, responsibilities, and must-have skills. The
                ranking engine will use this as the anchor for semantic and keyword fit.
              </p>
            </div>
            <div className="hidden rounded-2xl border border-slate-700/70 bg-slate-950/40 px-4 py-3 text-right sm:block">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Input quality</p>
              <p className="mt-2 text-lg font-semibold text-slate-100">
                {jdText.trim().length > 120 ? "Ready" : "Add more detail"}
              </p>
            </div>
          </div>

          <textarea
            className="mt-6 h-[360px] w-full resize-none rounded-3xl border border-slate-700/60 bg-slate-950/40 px-5 py-4 text-sm leading-7 text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-sky-400/40 focus:ring-2 focus:ring-sky-400/20"
            placeholder="Paste the full job description here, including responsibilities, required skills, preferred experience, and role context."
            value={jdText}
            onChange={(event) => setJdText(event.target.value)}
          />

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
            <p className="text-slate-500">
              {jdText.trim().length} characters entered
            </p>
            <p className="text-slate-500">
              Clear requirements improve ranking precision and hidden-fit detection.
            </p>
          </div>
        </div>

        <div className="space-y-6">
          <UploadZone
            disabled={loading}
            files={files}
            onAddFiles={appendFiles}
            onRemoveFile={removeFile}
          />

          <section className="card-surface animate-fade-up px-5 py-5">
            <p className="section-label">Run Analysis</p>
            <h2 className="mt-3 text-xl font-semibold text-slate-50">
              Generate the candidate leaderboard
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Use uploaded PDFs for live recruiter review, or rank the backend dataset
              against the same job description.
            </p>

            <div className="mt-6 space-y-3">
              <button
                className={cx(
                  "flex w-full items-center justify-center gap-3 rounded-2xl px-5 py-4 text-sm font-medium transition",
                  loading || !jdText.trim() || !files.length
                    ? "cursor-not-allowed bg-slate-800 text-slate-500"
                    : "bg-sky-500 text-slate-950 hover:bg-sky-400",
                )}
                disabled={loading || !jdText.trim() || !files.length}
                type="button"
                onClick={handleAnalyzeCandidates}
              >
                {loading ? (
                  <span className="animate-pulse-soft inline-flex items-center gap-3">
                    <span className="h-2.5 w-2.5 rounded-full bg-slate-950/80" />
                    Analyzing candidates
                  </span>
                ) : (
                  "Analyze Candidates"
                )}
              </button>

              <button
                className={cx(
                  "w-full rounded-2xl border px-5 py-4 text-sm font-medium transition",
                  loading || !jdText.trim()
                    ? "cursor-not-allowed border-slate-800 bg-slate-900/50 text-slate-500"
                    : "border-slate-700/70 bg-slate-950/50 text-slate-200 hover:border-slate-500 hover:text-slate-50",
                )}
                disabled={loading || !jdText.trim()}
                type="button"
                onClick={handleRankDataset}
              >
                Rank Dataset Candidates
              </button>
            </div>

            <div className="mt-5 rounded-2xl border border-slate-700/60 bg-slate-950/40 px-4 py-4">
              <p className="text-sm text-slate-300">
                {progressMessage || "Results will appear here once ranking completes."}
              </p>
              <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">
                API base URL: http://127.0.0.1:8000
              </p>
            </div>

            {errorMessage ? (
              <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                {errorMessage}
              </div>
            ) : null}
          </section>
        </div>
      </section>

      {candidates.length > 0 ? (
        <div className="mt-10 space-y-8">
          <AnalyticsPanel candidates={sortCandidates(candidates, "score")} />

          <section ref={leaderboardRef} className="animate-fade-up">
            <div className="mb-6 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <p className="section-label">Leaderboard</p>
                <h2 className="mt-3 text-3xl font-semibold text-slate-50">
                  Ranked candidates
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  {resultContext || "Candidate results returned by the backend ranking service."}
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="card-muted flex flex-col gap-2 p-4 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.18em] text-slate-500">
                    Sort by
                  </span>
                  <select
                    className="rounded-2xl border border-slate-700/60 bg-slate-950/55 px-4 py-3 text-slate-100 outline-none focus:border-sky-400/40"
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

                <label className="card-muted flex flex-col gap-2 p-4 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.18em] text-slate-500">
                    Filter
                  </span>
                  <select
                    className="rounded-2xl border border-slate-700/60 bg-slate-950/55 px-4 py-3 text-slate-100 outline-none focus:border-sky-400/40"
                    value={recommendationFilter}
                    onChange={(event) => setRecommendationFilter(event.target.value)}
                  >
                    {recommendationOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>

            <div className="space-y-5">
              {filteredCandidates.length ? (
                filteredCandidates.map((candidate, index) => (
                  <CandidateCard
                    key={getCandidateKey(candidate, index)}
                    animationDelayMs={index * 70}
                    candidate={candidate}
                    hiddenGem={isHiddenGem(candidate)}
                    isTopCandidate={candidate.candidate_name === topCandidateName}
                    rank={index + 1}
                  />
                ))
              ) : (
                <div className="card-muted p-8 text-center">
                  <p className="text-lg font-medium text-slate-100">
                    No candidates match the current filter.
                  </p>
                  <p className="mt-2 text-sm text-slate-400">
                    Try switching the recommendation filter back to All to review the
                    full ranked list.
                  </p>
                </div>
              )}
            </div>
          </section>
        </div>
      ) : (
        <section className="mt-10 card-surface animate-fade-up px-6 py-8">
          <p className="section-label">Ready State</p>
          <h2 className="mt-3 text-2xl font-semibold text-slate-50">
            Prepare a recruiter-grade candidate review
          </h2>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="card-muted p-5">
              <p className="text-sm font-medium text-slate-100">1. Add the role brief</p>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Paste the hiring context, must-have skills, and role expectations.
              </p>
            </div>
            <div className="card-muted p-5">
              <p className="text-sm font-medium text-slate-100">2. Upload PDF resumes</p>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Drop multiple resumes into the upload area for batch evaluation.
              </p>
            </div>
            <div className="card-muted p-5">
              <p className="text-sm font-medium text-slate-100">3. Review AI ranking</p>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Compare top candidates by match score, strengths, weaknesses, and hidden-fit signals.
              </p>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}

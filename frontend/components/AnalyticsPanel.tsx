import { calculateAnalytics, formatScore } from "@/lib/utils";
import type { RankedCandidate } from "@/types/recruitment";

interface AnalyticsPanelProps {
  candidates: RankedCandidate[];
}

export function AnalyticsPanel({ candidates }: AnalyticsPanelProps) {
  const analytics = calculateAnalytics(candidates);

  const items = [
    {
      label: "Total resumes processed",
      value: analytics.total,
      caption: "Candidates returned by the ranking API",
    },
    {
      label: "Top match score",
      value: `${formatScore(analytics.topScore)} / 100`,
      caption: "Highest-ranked candidate in the leaderboard",
    },
    {
      label: "Average score",
      value: `${formatScore(analytics.averageScore)} / 100`,
      caption: "Average final score across processed resumes",
    },
    {
      label: "Recommended candidates",
      value: analytics.recommendedCount,
      caption: "Highly Recommended or Recommended profiles",
    },
  ];

  return (
    <section className="animate-fade-up">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="section-label">Analytics Snapshot</p>
          <h2 className="mt-3 text-2xl font-semibold text-slate-50">
            Recruiter-ready pipeline metrics
          </h2>
        </div>
        <p className="hidden text-sm text-slate-400 sm:block">
          Quick read on volume, quality, and recommendation density.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {items.map((item) => (
          <div key={item.label} className="card-muted p-5">
            <p className="text-sm text-slate-400">{item.label}</p>
            <p className="mt-4 text-3xl font-semibold text-slate-50">{item.value}</p>
            <p className="mt-3 text-sm leading-6 text-slate-500">{item.caption}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

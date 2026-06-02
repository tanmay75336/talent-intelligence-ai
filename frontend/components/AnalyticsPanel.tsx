import { calculateAnalytics } from "@/lib/utils";
import type { RankedCandidate } from "@/types/recruitment";

interface AnalyticsPanelProps {
  candidates: RankedCandidate[];
}

export function AnalyticsPanel({ candidates }: AnalyticsPanelProps) {
  const analytics = calculateAnalytics(candidates);

  const items = [
    {
      label: "Candidates",
      value: analytics.total,
    },
    {
      label: "Recommended",
      value: analytics.recommendedCount,
    },
    {
      label: "Top band",
      value: analytics.topScore >= 85 ? "Strong" : analytics.topScore >= 70 ? "Good" : analytics.total ? "Review" : "-",
    },
  ];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="section-label">Slate Summary</p>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">Current review</h2>
          <p className="mt-1 text-sm text-slate-600">
            A quiet summary of the active candidate slate.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {items.map((item) => (
            <div key={item.label} className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-xs text-slate-500">{item.label}</p>
              <p className="mt-1 text-xl font-semibold text-slate-950">{item.value}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

import { cx, formatScore, getScoreTone } from "@/lib/utils";

interface ScoreBadgeProps {
  score?: number;
  label?: string;
  compact?: boolean;
}

export function ScoreBadge({
  score,
  label = "Match score",
  compact = false,
}: ScoreBadgeProps) {
  return (
    <div
      className={cx(
        "rounded-2xl border px-4 py-3 text-right",
        compact ? "min-w-[96px]" : "min-w-[132px]",
        getScoreTone(score),
      )}
    >
      <p className="text-[0.7rem] uppercase tracking-[0.2em] text-current/70">
        {label}
      </p>
      <p className={cx("font-semibold", compact ? "text-2xl" : "text-3xl")}>
        {formatScore(score)}
        <span className="ml-1 text-sm text-current/70">/ 100</span>
      </p>
    </div>
  );
}

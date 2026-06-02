from __future__ import annotations

from backend.dataset_intelligence.models import DatasetProfileReport, StrategyComparisonReport


def build_dataset_markdown_report(report: DatasetProfileReport) -> str:
    lines = [
        f"# Dataset Readiness Report: {report.dataset_name}",
        "",
        "## Summary",
        f"- Rows: {report.row_count}",
        f"- Fields: {report.column_count}",
        f"- Duplicate row rate: {report.duplicate_row_rate:.1%}",
        f"- Overall sparsity: {report.sparsity:.1%}",
        "",
        "## Readiness Notes",
    ]
    lines.extend(f"- {item}" for item in report.readiness_summary)
    lines.extend(
        [
            "",
            "## Field Groups",
            f"- Text-heavy fields: {_join_or_none(report.text_heavy_fields)}",
            f"- Numeric fields: {_join_or_none(report.numeric_fields)}",
            f"- Categorical fields: {_join_or_none(report.categorical_fields)}",
            "",
            "## Candidate Signal Inventory",
        ]
    )
    if report.signal_inventory:
        for item in report.signal_inventory:
            lines.append(
                f"- **{item.category}** ({item.strength}, {item.coverage_pct:.1f}% coverage): "
                f"{_join_or_none(item.fields)}. {item.rationale}"
            )
    else:
        lines.append("- No obvious candidate signal groups detected.")

    lines.extend(["", "## Useful Signals"])
    lines.extend(f"- {item}" for item in report.potentially_useful_signals[:10]) or lines.append("- None detected.")

    lines.extend(["", "## Noisy Or Low-Readiness Signals"])
    lines.extend(f"- {item}" for item in report.potentially_noisy_signals[:10]) or lines.append("- None detected.")

    lines.extend(["", "## Proposed Signals To Consider Later"])
    if report.proposed_candidate_signals:
        for item in report.proposed_candidate_signals:
            lines.append(
                f"- **{item.name}** ({item.readiness}): {item.description} "
                f"Fields: {_join_or_none(item.source_fields)}. Caveat: {item.caveat}"
            )
    else:
        lines.append("- No new candidate signals proposed from this dataset yet.")

    lines.extend(["", "## Field Quality Table", "| Field | Type | Coverage | Unique | Usefulness | Notes |", "|---|---:|---:|---:|---|---|"])
    for field in report.fields:
        lines.append(
            f"| {field.name} | {field.inferred_type} | {field.coverage_pct:.1f}% | "
            f"{field.unique_count} | {field.usefulness} | {_join_or_none(field.quality_notes)} |"
        )
    return "\n".join(lines)


def build_strategy_markdown_report(report: StrategyComparisonReport) -> str:
    lines = ["# Ranking Evaluation Report", ""]
    if report.best_strategy:
        lines.append(f"Best strategy by available metrics: **{report.best_strategy}**")
        lines.append("")
    lines.extend(["| Strategy | Pairwise | Ranking | FP Rate | FN Rate | Hidden Gems | Stability |", "|---|---:|---:|---:|---:|---:|---:|"])
    for result in report.results:
        lines.append(
            f"| {result.strategy_name} | {_fmt(result.pairwise_accuracy)} | {_fmt(result.ranking_accuracy)} | "
            f"{_fmt(result.false_positive_rate)} | {_fmt(result.false_negative_rate)} | "
            f"{_fmt(result.hidden_gem_detection_rate)} | {_fmt(result.ranking_stability)} |"
        )
    lines.append("")
    lines.append("## Notes")
    notes = [note for result in report.results for note in result.notes]
    if notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("- No evaluation warnings generated.")
    return "\n".join(lines)


def _join_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


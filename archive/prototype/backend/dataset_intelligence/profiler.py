from __future__ import annotations

from pathlib import Path
from typing import Any
import re
import warnings

import pandas as pd

from backend.dataset_intelligence.loader import load_dataset
from backend.dataset_intelligence.models import DatasetProfileReport, FieldProfile
from backend.dataset_intelligence.reporting import build_dataset_markdown_report
from backend.dataset_intelligence.signals import (
    build_signal_inventory,
    categorize_field,
    propose_candidate_signals,
)


TEXT_HEAVY_MIN_AVG_LENGTH = 80
LOW_COVERAGE_THRESHOLD = 35.0
HIGH_COVERAGE_THRESHOLD = 70.0


def profile_dataset_path(path: str | Path) -> DatasetProfileReport:
    frame = load_dataset(path)
    return profile_dataframe(frame, dataset_name=Path(path).name)


def profile_dataframe(frame: pd.DataFrame, dataset_name: str = "dataset") -> DatasetProfileReport:
    row_count = int(len(frame))
    column_count = int(len(frame.columns))
    normalized_for_duplicates = frame.map(_normalize_value) if row_count and column_count else frame
    duplicate_row_rate = round(float(normalized_for_duplicates.duplicated().mean() if row_count else 0.0), 4)
    fields = [_profile_field(frame[column], str(column), row_count) for column in frame.columns]
    sparsity = round(_average([field.missing_rate for field in fields]), 4)
    inventory = build_signal_inventory(fields)
    proposals = propose_candidate_signals(fields, inventory)
    report = DatasetProfileReport(
        dataset_name=dataset_name,
        row_count=row_count,
        column_count=column_count,
        duplicate_row_rate=duplicate_row_rate,
        sparsity=sparsity,
        fields=fields,
        text_heavy_fields=[field.name for field in fields if field.inferred_type == "text"],
        numeric_fields=[field.name for field in fields if field.inferred_type == "numeric"],
        categorical_fields=[field.name for field in fields if field.inferred_type == "categorical"],
        potentially_useful_signals=_potentially_useful_signals(fields),
        potentially_noisy_signals=_potentially_noisy_signals(fields),
        profile_completeness_indicators=_profile_completeness_indicators(fields),
        signal_inventory=inventory,
        proposed_candidate_signals=proposals,
        readiness_summary=_readiness_summary(row_count, column_count, duplicate_row_rate, fields, inventory),
    )
    report.markdown_report = build_dataset_markdown_report(report)
    return report


def _profile_field(series: pd.Series, name: str, row_count: int) -> FieldProfile:
    normalized = series.map(_normalize_value)
    missing_mask = normalized.map(lambda value: value == "")
    missing_count = int(missing_mask.sum())
    present = normalized[~missing_mask]
    unique_count = int(present.nunique(dropna=True))
    missing_rate = round(float(missing_count / row_count), 4) if row_count else 0.0
    coverage_pct = round((1.0 - missing_rate) * 100, 2)
    unique_rate = round(float(unique_count / max(1, len(present))), 4) if len(present) else 0.0
    duplicate_value_rate = round(max(0.0, 1.0 - unique_rate), 4) if len(present) else 0.0
    avg_text_length = round(float(present.map(len).mean()), 2) if len(present) else 0.0
    inferred_type = _infer_type(series, present, unique_rate, avg_text_length)
    samples = [str(value)[:120] for value in present.head(5).tolist()]
    categories = categorize_field(name, samples)
    usefulness, notes = _field_usefulness(
        name=name,
        inferred_type=inferred_type,
        coverage_pct=coverage_pct,
        unique_rate=unique_rate,
        duplicate_value_rate=duplicate_value_rate,
        avg_text_length=avg_text_length,
        categories=categories,
    )
    return FieldProfile(
        name=name,
        inferred_type=inferred_type,
        missing_count=missing_count,
        missing_rate=missing_rate,
        coverage_pct=coverage_pct,
        unique_count=unique_count,
        unique_rate=unique_rate,
        duplicate_value_rate=duplicate_value_rate,
        sparsity=missing_rate,
        avg_text_length=avg_text_length,
        sample_values=samples,
        signal_categories=categories,
        usefulness=usefulness,
        quality_notes=notes,
    )


def _infer_type(series: pd.Series, present: pd.Series, unique_rate: float, avg_text_length: float) -> str:
    if not len(present):
        return "empty"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if _date_like_signal(present):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed_dates = pd.to_datetime(present.head(50), errors="coerce")
        if len(parsed_dates) and parsed_dates.notna().mean() >= 0.8:
            return "datetime"
    if present.map(_looks_like_list_or_json).mean() >= 0.5:
        return "structured"
    if avg_text_length >= TEXT_HEAVY_MIN_AVG_LENGTH or unique_rate >= 0.65:
        return "text"
    return "categorical"


def _field_usefulness(
    name: str,
    inferred_type: str,
    coverage_pct: float,
    unique_rate: float,
    duplicate_value_rate: float,
    avg_text_length: float,
    categories: list[str],
) -> tuple[str, list[str]]:
    notes = []
    if coverage_pct < LOW_COVERAGE_THRESHOLD:
        notes.append("low coverage")
    if duplicate_value_rate > 0.85 and inferred_type != "categorical":
        notes.append("high duplicate rate")
    if inferred_type == "text" and avg_text_length < 35:
        notes.append("short text field")
    if not categories:
        notes.append("no obvious hiring signal category")

    if coverage_pct >= HIGH_COVERAGE_THRESHOLD and categories and inferred_type in {"text", "numeric", "categorical", "datetime", "structured"}:
        return "strong", notes
    if coverage_pct >= LOW_COVERAGE_THRESHOLD and categories:
        return "moderate", notes
    if inferred_type in {"empty"} or coverage_pct < LOW_COVERAGE_THRESHOLD:
        return "weak", notes
    return "unknown", notes


def _potentially_useful_signals(fields: list[FieldProfile]) -> list[str]:
    useful = []
    for field in fields:
        if field.usefulness in {"strong", "moderate"} and field.signal_categories:
            useful.append(f"{field.name}: {', '.join(field.signal_categories)}")
    return useful[:12]


def _potentially_noisy_signals(fields: list[FieldProfile]) -> list[str]:
    noisy = []
    for field in fields:
        if field.coverage_pct < LOW_COVERAGE_THRESHOLD:
            noisy.append(f"{field.name}: low coverage ({field.coverage_pct:.1f}%)")
        elif field.usefulness == "weak":
            noisy.append(f"{field.name}: weak signal quality")
        elif "no obvious hiring signal category" in field.quality_notes:
            noisy.append(f"{field.name}: unclear hiring relevance")
    return noisy[:12]


def _profile_completeness_indicators(fields: list[FieldProfile]) -> list[str]:
    indicators = []
    for field in fields:
        lowered = field.name.lower()
        if any(token in lowered for token in ("completeness", "profile_quality", "verified", "updated", "last_active")):
            indicators.append(field.name)
    if not indicators:
        core_categories = {"skills", "titles", "experience", "education", "projects"}
        covered = sorted({category for field in fields for category in field.signal_categories if category in core_categories})
        if covered:
            indicators.append(f"Core profile coverage categories present: {', '.join(covered)}")
    return indicators[:8]


def _readiness_summary(
    row_count: int,
    column_count: int,
    duplicate_row_rate: float,
    fields: list[FieldProfile],
    inventory,
) -> list[str]:
    summary = [f"Dataset has {row_count} rows and {column_count} fields."]
    strong_inventory = [item for item in inventory if item.strength == "strong"]
    weak_fields = [field for field in fields if field.usefulness == "weak"]
    if strong_inventory:
        summary.append(f"Strong candidate signals detected: {', '.join(item.category for item in strong_inventory[:5])}.")
    else:
        summary.append("No strong ranking signals detected yet; inspect text fields before ranking.")
    if weak_fields:
        summary.append(f"{len(weak_fields)} fields appear sparse or weak and should not drive ranking directly.")
    if duplicate_row_rate > 0.05:
        summary.append(f"Duplicate row rate is {duplicate_row_rate:.1%}; deduplication should happen before evaluation.")
    return summary


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key}: {val}" for key, val in value.items())
    return str(value).strip()


def _looks_like_list_or_json(value: str) -> bool:
    cleaned = str(value).strip()
    return (cleaned.startswith("[") and cleaned.endswith("]")) or (cleaned.startswith("{") and cleaned.endswith("}"))


def _date_like_signal(values: pd.Series) -> bool:
    sample = [str(value).strip() for value in values.head(20).tolist() if str(value).strip()]
    if not sample:
        return False
    date_pattern = re.compile(
        r"^\d{4}-\d{1,2}-\d{1,2}|^\d{1,2}/\d{1,2}/\d{2,4}|^\d{4}/\d{1,2}/\d{1,2}",
        re.IGNORECASE,
    )
    return sum(1 for value in sample if date_pattern.search(value)) / len(sample) >= 0.6


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0

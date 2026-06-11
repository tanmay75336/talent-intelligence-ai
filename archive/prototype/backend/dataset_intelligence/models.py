from __future__ import annotations

from pydantic import BaseModel, Field


class FieldProfile(BaseModel):
    name: str
    inferred_type: str
    missing_count: int
    missing_rate: float
    coverage_pct: float
    unique_count: int
    unique_rate: float
    duplicate_value_rate: float
    sparsity: float
    avg_text_length: float
    sample_values: list[str] = Field(default_factory=list)
    signal_categories: list[str] = Field(default_factory=list)
    usefulness: str = "unknown"
    quality_notes: list[str] = Field(default_factory=list)


class SignalInventoryItem(BaseModel):
    category: str
    fields: list[str] = Field(default_factory=list)
    coverage_pct: float
    strength: str
    rationale: str


class ProposedSignal(BaseModel):
    name: str
    source_fields: list[str] = Field(default_factory=list)
    description: str
    readiness: str
    caveat: str


class DatasetProfileReport(BaseModel):
    dataset_name: str
    row_count: int
    column_count: int
    duplicate_row_rate: float
    sparsity: float
    fields: list[FieldProfile] = Field(default_factory=list)
    text_heavy_fields: list[str] = Field(default_factory=list)
    numeric_fields: list[str] = Field(default_factory=list)
    categorical_fields: list[str] = Field(default_factory=list)
    potentially_useful_signals: list[str] = Field(default_factory=list)
    potentially_noisy_signals: list[str] = Field(default_factory=list)
    profile_completeness_indicators: list[str] = Field(default_factory=list)
    signal_inventory: list[SignalInventoryItem] = Field(default_factory=list)
    proposed_candidate_signals: list[ProposedSignal] = Field(default_factory=list)
    readiness_summary: list[str] = Field(default_factory=list)
    markdown_report: str = ""


class RankingEvaluationResult(BaseModel):
    strategy_name: str
    candidate_count: int
    pairwise_accuracy: float | None = None
    ranking_accuracy: float | None = None
    top_k_quality: dict[str, float] = Field(default_factory=dict)
    false_positive_rate: float | None = None
    false_negative_rate: float | None = None
    hidden_gem_detection_rate: float | None = None
    ranking_stability: float | None = None
    notes: list[str] = Field(default_factory=list)


class StrategyComparisonReport(BaseModel):
    results: list[RankingEvaluationResult]
    best_strategy: str | None = None
    markdown_report: str = ""

